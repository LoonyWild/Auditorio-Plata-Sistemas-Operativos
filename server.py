"""Auditorio Plata: cartelera multievento + Oracle XE + tickets reales.

Requiere 02_crear_esquema.sql y DESPUES 05_agregar_cartelera.sql.
Los precios de la interfaz son exclusivamente ilustrativos; no se procesa dinero.
"""
from __future__ import annotations
import base64
from datetime import datetime
from io import BytesIO
import hmac
import os
import threading
import time
import uuid
from zipfile import ZipFile, ZIP_DEFLATED
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file
import oracledb
from boletos_pdf import generar_pdf, generar_png_qr, texto_qr, validar_firma

load_dotenv()
app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
_LOCAL = ZoneInfo('America/Mexico_City')
_pool = None
_pool_mutex = threading.Lock()

# Los nombres, folios y aforos reales siempre se consultan en Oracle.
# Fechas y descripciones ilustrativas de la cartelera original aportada.
CARTELERA = {
  1: {'titulo': 'Juan Gabriel - Concierto Navideño', 'fecha': '28 DIC 2026', 'hora': '20:00', 'mes': '12', 'descripcion': 'Homenaje monumental en vivo (simulación académica).'},
  2: {'titulo': 'Jesse & Joy - El Despecho Tour', 'fecha': '21 OCT 2026', 'hora': '20:30', 'mes': '10', 'descripcion': 'El Despecho Tour.'},
  3: {'titulo': 'Edith Márquez - En Vivo', 'fecha': '22 OCT 2026', 'hora': '20:30', 'mes': '10', 'descripcion': 'Gira 2026.'},
  4: {'titulo': 'Andrés Obregón Acústico', 'fecha': '23 OCT 2026', 'hora': '20:30', 'mes': '10', 'descripcion': 'Concierto acústico.'},
  5: {'titulo': 'Gloria Trevi - Celebration', 'fecha': '24 OCT 2026', 'hora': '20:00', 'mes': '10', 'descripcion': 'Celebration Tour.'},
  6: {'titulo': 'Pimpinela - Leyendas', 'fecha': '25 OCT 2026', 'hora': '19:00', 'mes': '10', 'descripcion': 'Gira Leyendas.'},
}
PRECIOS_REFERENCIA = {
    'Preferente Planta Baja': 1800,
    'Primer Piso C': 550,
    'Primer Piso D': 450,
    'Segundo Piso A': 450,
    'Segundo Piso B': 400,
    'Segundo Piso C y D': 300,
}

from sincronizacion import MesaFilosofos, MonitorEmision
monitor_emision=MonitorEmision(limite=12)


def ahora():
    return datetime.now(_LOCAL).replace(tzinfo=None)


def config_obligatoria(clave):
    valor = os.getenv(clave, '').strip()
    if not valor or valor.startswith('CAMBIAR_'):
        raise RuntimeError(f'Falta configurar {clave} en el archivo .env')
    return valor


def bd():
    global _pool
    if _pool is None:
        with _pool_mutex:
            if _pool is None:
                _pool = oracledb.create_pool(user=config_obligatoria('DB_USER'),
                    password=config_obligatoria('DB_PASSWORD'),
                    dsn=config_obligatoria('DB_DSN'), min=1, max=16, increment=1)
    return _pool


def campo_corto(valor, maximo):
    return str(valor or '').strip()[:maximo]


def guardar_bitacora(cur, req_id, equipo, hilo, inicio, folio, estado, tiempo0):
    fin = ahora()
    ms = max(0, int((time.perf_counter()-tiempo0)*1000))
    cur.execute('''INSERT INTO bitacora_solicitudes
       (id,request_id,equipo,id_hilo,hora_envio,hora_respuesta,folio,estado,duracion_ms)
       VALUES(seq_bitacora.NEXTVAL,:1,:2,:3,:4,:5,:6,:7,:8)''',
       [req_id, equipo, hilo, inicio, fin, folio, estado, ms])


def autorizacion_lab():
    token = config_obligatoria('ADMIN_TOKEN')
    recibido = request.headers.get('X-Admin-Token', '')
    return bool(recibido) and hmac.compare_digest(recibido, token)


def respuesta_pdf(folio, fecha, qr, evento='Concierto Navideño', zona='Entrada general', numero=None, precio=0):
    archivo = generar_pdf(int(folio), fecha, qr, evento=evento, zona=zona,
                          numero_entrada=numero, precio_referencia=precio)
    res = send_file(archivo, mimetype='application/pdf', as_attachment=True,
                    download_name=f'Auditorio_Plata_folio_{folio}.pdf')
    res.headers['X-Folio'] = str(folio)
    res.headers['X-Fecha'] = fecha.isoformat(timespec='seconds')
    res.headers['X-QR-B64'] = base64.b64encode(qr.encode('utf-8')).decode('ascii')
    res.headers['X-Numero-Entrada'] = str(numero or '')
    res.headers['Cache-Control'] = 'no-store'
    return res


@app.get('/')
def pagina_inicio():
    return render_template('index.html')


@app.get('/validador')
def pagina_validador():
    return render_template('validador.html')


@app.get('/api/salud')
def salud():
    try:
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM dual')
                cur.fetchone()
        return jsonify(estado='OK', oracle='CONECTADA', servicio='Auditorio Plata')
    except Exception:
        app.logger.exception('Error en /api/salud')
        return jsonify(estado='ERROR', oracle='NO DISPONIBLE'), 503


@app.get('/api/eventos')
def listar_eventos():
    try:
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id_evento,nombre,aforo,emitidos FROM eventos ORDER BY id_evento')
                filas = cur.fetchall()
        eventos=[]
        for id_evento,nombre,aforo,emitidos in filas:
            d = CARTELERA.get(int(id_evento), {})
            eventos.append({'id_evento': int(id_evento),'nombre': nombre,
              'titulo': d.get('titulo', nombre), 'fecha': d.get('fecha','Por confirmar'),
              'hora': d.get('hora','Por confirmar'), 'mes': d.get('mes',''),
              'descripcion': d.get('descripcion',''),
              'aforo': int(aforo), 'emitidos': int(emitidos),
              'disponibles': int(aforo)-int(emitidos), 'gratuito': True})
        return jsonify(eventos=eventos)
    except Exception:
        app.logger.exception('Fallo al listar eventos')
        return jsonify(error='No se pudo consultar la cartelera en Oracle'), 503


@app.get('/api/estado')
def estado_evento():
    try:
        evento_id = int(request.args.get('id_evento','1'))
    except ValueError:
        return jsonify(error='id_evento invalido'),400
    try:
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id_evento,nombre,aforo,emitidos FROM eventos WHERE id_evento=:1', [evento_id])
                row=cur.fetchone()
        if not row:
            return jsonify(error='Evento no registrado'),404
        return jsonify(id_evento=int(row[0]),nombre=row[1],aforo=int(row[2]),
                       emitidos=int(row[3]),disponibles=int(row[2])-int(row[3]),gratuito=True)
    except Exception:
        app.logger.exception('Fallo al consultar evento')
        return jsonify(error='No se pudo consultar Oracle'), 503


def pedir_boletos(cantidad_maxima):
    """Emite 1 boleto para el spawner o 1..4 para la interfaz, en UNA sola transacción.

    Bloqueo FOR UPDATE por evento; folio global por secuencia; peticiones
    idempotentes por request_id (en lote usa sufijos :1..:4).
    """
    inicio=ahora()
    t0=time.perf_counter()
    datos=request.get_json(silent=True) or {}
    try:
        id_evento=int(datos.get('id_evento',1))
        cantidad=int(datos.get('cantidad',1))
    except (ValueError,TypeError):
        return jsonify(error='Evento o cantidad inválida'), 400
    if cantidad not in range(1,cantidad_maxima+1):
        return jsonify(error=f'Cantidad permitida: 1..{cantidad_maxima}'), 400
    zona=campo_corto(datos.get('zona') or 'Entrada general',64)
    if zona not in PRECIOS_REFERENCIA and zona!='Entrada general':
        return jsonify(error='Zona inválida'),400
    precio=PRECIOS_REFERENCIA.get(zona,0) # valor ilustrativo, NO hay pagos
    req_id=campo_corto(request.headers.get('X-Request-ID') or uuid.uuid4().hex,48)
    equipo=campo_corto(request.headers.get('X-Equipo') or 'WEB',50)
    hilo=campo_corto(request.headers.get('X-Thread-ID') or 'WEB',80)
    if len(req_id)<8:
        return jsonify(error='X-Request-ID demasiado corto'),400
    claves=[f'{req_id}:{i+1}' if cantidad_maxima>1 else req_id for i in range(cantidad)]
    try:
        with monitor_emision.turno():
            with bd().acquire() as conn:
                with conn.cursor() as cur:
                    cur.execute('''SELECT nombre,aforo,emitidos FROM eventos
                                   WHERE id_evento=:1 FOR UPDATE WAIT 15''',[id_evento])
                    ev=cur.fetchone()
                    if ev is None:
                        conn.rollback()
                        return jsonify(error='Evento no registrado; ejecuta scripts/05_agregar_cartelera.sql'),404
                    nombre,aforo,emitidos=ev
                    titulo=CARTELERA.get(id_evento,{}).get('titulo',nombre)
                    encontrados=[]
                    for clave in claves:
                        cur.execute('''SELECT folio,fecha_emision,qr_texto,zona,numero_entrada,precio_referencia,id_evento
                                       FROM boletos WHERE request_id=:1''',[clave])
                        item=cur.fetchone()
                        if item:
                            if int(item[6]) != id_evento:
                                conn.rollback()
                                return jsonify(error='X-Request-ID ya utilizado para otro evento'),409
                            encontrados.append(item)
                    if encontrados:
                        if len(encontrados)!=cantidad:
                            conn.rollback()
                            return jsonify(error='Petición existente con diferente cantidad'),409
                        tickets=[(int(f),fecha,qr,z,n,int(p)) for f,fecha,qr,z,n,p,_ in encontrados]
                        guardar_bitacora(cur,req_id,equipo,hilo,inicio,tickets[0][0],'REINTENTO',t0)
                        conn.commit()
                        return emitir_respuesta(tickets,titulo,id_evento,cantidad)
                    if int(emitidos)+cantidad > int(aforo):
                        guardar_bitacora(cur,req_id,equipo,hilo,inicio,None,'RECHAZADO',t0)
                        conn.commit()
                        return jsonify(estado='RECHAZADO',motivo='AFORO_AGOTADO',
                          disponibles=int(aforo)-int(emitidos)),409
                    tickets=[]
                    for i,clave in enumerate(claves):
                        numero=int(emitidos)+i+1
                        cur.execute('SELECT seq_folio.NEXTVAL FROM dual')
                        folio=int(cur.fetchone()[0])
                        fecha=ahora()
                        qr=texto_qr(folio,fecha,config_obligatoria('APP_SECRET'),evento=titulo)
                        cur.execute('''INSERT INTO boletos
                          (folio,id_evento,numero_entrada,fecha_emision,qr_texto,request_id,zona,precio_referencia)
                          VALUES (:1,:2,:3,:4,:5,:6,:7,:8)''',
                          [folio,id_evento,numero,fecha,qr,clave,zona,precio])
                        tickets.append((folio,fecha,qr,zona,numero,precio))
                    cur.execute('UPDATE eventos SET emitidos=:1 WHERE id_evento=:2',
                                [int(emitidos)+cantidad,id_evento])
                    guardar_bitacora(cur,req_id,equipo,hilo,inicio,tickets[0][0],'EXITO',t0)
                    conn.commit()
        # PDFs DESPUES del commit y del monitor: no mantienen bloqueada la fila Oracle.
        return emitir_respuesta(tickets,titulo,id_evento,cantidad)
    except oracledb.Error:
        app.logger.exception('Error Oracle en emision')
        return jsonify(estado='ERROR',error='Error Oracle; reintenta con el mismo X-Request-ID'),503
    except Exception:
        app.logger.exception('Error en emision')
        return jsonify(estado='ERROR',error='Error interno; conserva el X-Request-ID'),500


def emitir_respuesta(tickets,titulo,id_evento,cantidad):
    primer=tickets[0]
    if cantidad==1:
        respuesta=respuesta_pdf(primer[0],primer[1],primer[2],titulo,primer[3],primer[4],primer[5])
    else:
        salida=BytesIO()
        with ZipFile(salida,'w',compression=ZIP_DEFLATED) as zipf:
            for folio,fecha,qr,zona,numero,precio in tickets:
                pdf=generar_pdf(folio,fecha,qr,evento=titulo,zona=zona,
                                 numero_entrada=numero,precio_referencia=precio)
                zipf.writestr(f'Boleto_Auditorio_Plata_{folio}.pdf',pdf.getvalue())
        salida.seek(0)
        respuesta=send_file(salida,mimetype='application/zip',as_attachment=True,
                            download_name=f'Auditorio_Plata_{cantidad}_boletos.zip')
    respuesta.headers['X-Folio']=str(primer[0])
    respuesta.headers['X-Folios']=','.join(str(t[0]) for t in tickets)
    respuesta.headers['X-QR-B64']=base64.b64encode(primer[2].encode('utf-8')).decode('ascii')
    respuesta.headers['X-Fecha']=primer[1].isoformat(timespec='seconds')
    respuesta.headers['X-Numero-Entrada']=str(primer[4])
    respuesta.headers['X-Evento-ID']=str(id_evento)
    respuesta.headers['Cache-Control']='no-store'
    return respuesta


@app.post('/api/boletos')
def emitir_boleto():
    return pedir_boletos(1)


@app.post('/api/reservas')
def emitir_reserva():
    return pedir_boletos(4)


@app.get('/api/boletos/<int:folio>/pdf')
def descargar_folio(folio):
    try:
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                cur.execute('''SELECT b.fecha_emision,b.qr_texto,e.nombre,b.zona,
                       b.numero_entrada,b.precio_referencia,b.id_evento
                       FROM boletos b JOIN eventos e ON e.id_evento=b.id_evento
                       WHERE b.folio=:1''',[folio])
                row=cur.fetchone()
        if not row:
            return jsonify(error='Folio inexistente'),404
        fecha,qr,nombre,zona,numero,precio,id_evento=row
        titulo=CARTELERA.get(int(id_evento),{}).get('titulo',nombre)
        return respuesta_pdf(folio,fecha,qr,titulo,zona,numero,precio)
    except Exception:
        app.logger.exception('Error descargando folio')
        return jsonify(error='No se pudo descargar el boleto'),503


@app.get('/api/boletos/<int:folio>/qr.png')
def qr_folio_png(folio):
    """Vista previa del QR firmado; evita el limite de qrcodejs en el navegador."""
    try:
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT qr_texto FROM boletos WHERE folio=:1', [folio])
                row = cur.fetchone()
        if not row:
            return jsonify(error='Folio inexistente'), 404
        respuesta = send_file(generar_png_qr(row[0]), mimetype='image/png')
        respuesta.headers['Cache-Control'] = 'private, no-store'
        return respuesta
    except Exception:
        app.logger.exception('Error mostrando QR del boleto')
        return jsonify(error='No se pudo cargar el QR; revisa el PDF oficial'), 503


@app.get('/api/validar')
def validar():
    qr=request.args.get('qr','')
    if not qr or len(qr)>800:
        return jsonify(valido=False,razon='Texto QR ausente o demasiado largo'),400
    if not validar_firma(qr,config_obligatoria('APP_SECRET')):
        return jsonify(valido=False,razon='Firma HMAC incorrecta')
    try:
        folios=[s[6:] for s in qr.split('|') if s.startswith('Folio:')]
        if len(folios)!=1:
            return jsonify(valido=False,razon='QR sin folio'),400
        folio=int(folios[0])
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT qr_texto,id_evento FROM boletos WHERE folio=:1',[folio])
                row=cur.fetchone()
        valido = bool(
    row
    and row[0] is not None
    and hmac.compare_digest(
        str(row[0]).encode("utf-8"),
        qr.encode("utf-8")
    )
)
        return jsonify(valido=valido,folio=folio,
          id_evento=int(row[1]) if valido else None,
          razon='Folio emitido y firma verificada' if valido else 'Folio no emitido o QR distinto')
    except (ValueError,IndexError):
        return jsonify(valido=False,razon='Folio incorrecto'),400
    except Exception:
        app.logger.exception('Error validando QR')
        return jsonify(valido=False,razon='Oracle no disponible'),503


@app.post('/api/laboratorio/filosofos')
def filosofos_lab():
    if not autorizacion_lab():
        return jsonify(error='No autorizado'),401
    mesa=MesaFilosofos(5)
    registro=[]
    mutex=threading.Lock()
    def trabajador(i):
        mesa.tomar(i)
        with mutex:
            registro.append({'filosofo':i+1,'accion':'tomó dos tenedores'})
        time.sleep(.025)
        mesa.soltar(i)
        with mutex:
            registro.append({'filosofo':i+1,'accion':'liberó dos tenedores'})
    hilos=[threading.Thread(target=trabajador,args=(i,)) for i in range(5)]
    for h in hilos: h.start()
    for h in hilos: h.join()
    return jsonify(algoritmo='Filósofos comensales con monitor Condition',
                   participantes=5,interbloqueos=0,registro=registro)

@app.get('/api/bitacora')
def bitacora():
    if not autorizacion_lab():
        return jsonify(error='No autorizado'), 401
    with bd().acquire() as conn:
        with conn.cursor() as cur:
            cur.execute('''SELECT id, equipo,id_hilo,TO_CHAR(hora_envio,'YYYY-MM-DD HH24:MI:SS.FF3'),
                       TO_CHAR(hora_respuesta,'YYYY-MM-DD HH24:MI:SS.FF3'),folio,estado,duracion_ms
                       FROM bitacora_solicitudes ORDER BY id DESC FETCH FIRST 100 ROWS ONLY''')
            filas=[{'id':r[0], 'equipo':r[1], 'hilo':r[2], 'envio':r[3],
                    'respuesta':r[4], 'folio':r[5], 'estado':r[6], 'ms':r[7]}
                   for r in cur.fetchall()]
    return jsonify(registros=filas)


@app.post('/api/laboratorio/reiniciar')
def reiniciar_lab():
    if not autorizacion_lab():
        return jsonify(error='No autorizado'), 401
    corrida=str(uuid.uuid4())
    with bd().acquire() as conn:
        with conn.cursor() as cur:
            cur.execute('''UPDATE laboratorio_estado SET emitidos=0,corrida=:1 WHERE id=1''', [corrida])
            conn.commit()
    return jsonify(corrida=corrida, aforo=20,
                   instruccion='Ejecuta el spawner en modo laboratorio; al terminar consulta el resultado')


@app.post('/api/laboratorio/solicitar')
def solicitar_lab():
    if not autorizacion_lab():
        return jsonify(error='No autorizado'), 401
    modo=request.args.get('modo','con').lower()
    if modo not in ('con','sin'):
        return jsonify(error='Modo invalido'), 400
    id_hilo=campo_corto(request.headers.get('X-Thread-ID'),80)
    try:
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                # SIN sincronizacion: TOCTOU intencional exclusivamente en lab.
                # CON sincronizacion: bloqueo de fila al consultar el contador.
                sql='SELECT aforo,emitidos,corrida FROM laboratorio_estado WHERE id=1'
                if modo == 'con':
                    sql+=' FOR UPDATE WAIT 15'
                cur.execute(sql)
                aforo, contador, corrida = cur.fetchone()
                if modo == 'sin':
                    time.sleep(.045)  # ventana de carrera reproducible
                nuevo = int(contador)+1
                exito = int(contador)<int(aforo)
                if exito:
                    # SIN usa un contador leido antes del bloqueo; puede
                    # repetir numero y perder actualizaciones (TOCTOU).
                    cur.execute('UPDATE laboratorio_estado SET emitidos=:1 WHERE id=1', [nuevo])
                cur.execute('''INSERT INTO laboratorio_intentos
                    (id,corrida,modo,numero_entrada,estado,id_hilo)
                    VALUES(seq_lab.NEXTVAL,:1,:2,:3,:4,:5)''',
                    [corrida,modo,nuevo if exito else None,'EXITO' if exito else 'RECHAZADO',id_hilo])
                conn.commit()
                if exito:
                    return jsonify(estado='EXITO', numero_entrada=nuevo, corrida=corrida)
                return jsonify(estado='RECHAZADO', motivo='AFORO_AGOTADO', corrida=corrida),409
    except Exception:
        app.logger.exception('Fallo en laboratorio')
        return jsonify(estado='ERROR', error='Error transaccional laboratorio'), 503


@app.get('/api/laboratorio/resultado')
def resultado_lab():
    if not autorizacion_lab():
        return jsonify(error='No autorizado'), 401
    corrida=request.args.get('corrida','')
    with bd().acquire() as conn:
        with conn.cursor() as cur:
            if not corrida:
                cur.execute('SELECT corrida, aforo, emitidos FROM laboratorio_estado WHERE id=1')
                estado=cur.fetchone()
                corrida,aforo,contador=estado
            else:
                cur.execute('SELECT aforo,emitidos FROM laboratorio_estado WHERE id=1 AND corrida=:1', [corrida])
                estado=cur.fetchone()
                aforo,contador=(estado if estado else (20,None))
            cur.execute('''SELECT COUNT(*),
                NVL(SUM(CASE WHEN estado='EXITO' THEN 1 ELSE 0 END),0),
                NVL(SUM(CASE WHEN estado='RECHAZADO' THEN 1 ELSE 0 END),0),
                COUNT(DISTINCT CASE WHEN estado='EXITO' THEN numero_entrada END)
                FROM laboratorio_intentos WHERE corrida=:1''', [corrida])
            intentos,exitos,rechazos,distintos=cur.fetchone()
    return jsonify(corrida=corrida,aforo=int(aforo),contador_actual=contador,
                   intentos=int(intentos),exitos=int(exitos),rechazos=int(rechazos),
                   numeros_distintos=int(distintos),duplicados=int(exitos-distintos),
                   exceso_de_emisiones=max(0,int(exitos)-int(aforo)))


if __name__=='__main__':
    from waitress import serve
    try:
        config_obligatoria('APP_SECRET')
        config_obligatoria('ADMIN_TOKEN')
        with bd().acquire() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT 1 FROM dual')
        puerto=int(os.getenv('PORT','5000'))
        print(f'AUDITORIO PLATA listo: http://0.0.0.0:{puerto}')
        print('Oracle conectada. Control de aforo ACTIVADO. Laboratorio protegido por token.')
        serve(app,host='0.0.0.0',port=puerto,threads=24)
    except Exception as exc:
        raise SystemExit(f'ERROR DE INICIO: {exc}') from exc
