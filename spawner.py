"""Spawner distribuido: un worker por solicitante (hasta --hilos).
Usa Barrier, Semaphore, Lock, productor-consumidor, CSV y JSON.
Funciona en otra PC: solo necesita la URL HTTP, NO Oracle.
"""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import queue
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from uuid import uuid4
import requests


def argumentos(argv=None):
    p=argparse.ArgumentParser(description='Auditorio Plata: spawner de boletos')
    p.add_argument('--url',required=True,help='Ej. http://192.168.1.20:5000 o https://tunnel.trycloudflare.com')
    p.add_argument('--equipo',default='EQUIPO-CLIENTE')
    p.add_argument('--total',type=int,default=100)
    p.add_argument('--id-evento',type=int,default=1,help='ID Oracle: 1=Navideño; 2..6=cartelera')
    p.add_argument('--hilos',type=int,default=100)
    p.add_argument('--duracion',type=float,default=60)
    p.add_argument('--margen',type=float,default=10,help='Reserva estos segundos para ultimas respuestas')
    p.add_argument('--distribucion',choices=('uniforme','rafaga','aleatorio'),default='uniforme')
    p.add_argument('--semaforo',type=int,default=20,help='Solicitudes HTTP maximas simultaneas; 0=sin limite')
    p.add_argument('--timeout',type=float,default=10)
    p.add_argument('--modo',choices=('principal','lab-con','lab-sin'),default='principal')
    p.add_argument('--reiniciar-lab',action='store_true',help='Reinicia laboratorio ANTES de la prueba')
    p.add_argument('--admin-token',default=os.getenv('ADMIN_TOKEN',''),help='Preferir variable de entorno ADMIN_TOKEN')
    p.add_argument('--salida',default='resultados',help='Carpeta de bitacoras y resultados')
    p.add_argument('--reintentos',type=int,default=0,help='Reintentos con el MISMO request-id, 0 por defecto')
    args=p.parse_args(argv)
    if not 1<=args.total<=50000 or not 1<=args.hilos<=1000 or not 1<=args.id_evento<=6:
        p.error('total entre 1 y 50000; hilos entre 1 y 1000')
    if args.duracion<=0 or not 0<=args.margen<args.duracion or args.timeout<=0:
        p.error('duracion/timeout positivos; margen menor que duracion')
    if args.modo!='principal' and not args.admin_token:
        p.error('Para laboratorio debes configurar ADMIN_TOKEN')
    if args.reiniciar_lab and args.modo=='principal':
        p.error('--reiniciar-lab solo se usa en laboratorio')
    if args.reintentos not in (0,1,2):
        p.error('reintentos admitidos: 0, 1 o 2')
    args.url=args.url.rstrip('/')
    return args


def planificar_tiempos(total,duracion,margen,distribucion,semilla=123):
    ventana=max(0.0,duracion-margen)
    if distribucion=='rafaga':
        return [0.0]*total
    if distribucion=='uniforme':
        return [(i*ventana/max(1,total-1)) for i in range(total)]
    aleatorio=random.Random(semilla)
    return sorted(aleatorio.uniform(0,ventana) for _ in range(total))


def main(argv=None):
    a=argumentos(argv)
    ruta=Path(a.salida)
    ruta.mkdir(parents=True,exist_ok=True)
    prefijo=f'{a.equipo}_{a.modo}_{datetime.now():%Y%m%d_%H%M%S}'
    prefijo=''.join(c if c.isalnum() or c in '._-' else '_' for c in prefijo)
    path_csv=ruta/(prefijo+'.csv')
    path_json=ruta/(prefijo+'.json')
    token_headers={'X-Admin-Token':a.admin_token} if a.modo!='principal' else {}

    # Comprobacion ANTES del cronometro de la prueba.
    try:
        r=requests.get(a.url+'/api/salud',timeout=a.timeout)
        r.raise_for_status()
        if r.json().get('oracle')!='CONECTADA':
            raise RuntimeError('La API no confirma conexion a Oracle')
        if a.reiniciar_lab:
            rr=requests.post(a.url+'/api/laboratorio/reiniciar',headers=token_headers,timeout=a.timeout)
            rr.raise_for_status()
            print('Laboratorio reiniciado. Corrida:',rr.json()['corrida'])
    except Exception as e:
        raise SystemExit(f'No se puede acceder a {a.url}: {e}') from e

    print(f'Conectado a {a.url} | Equipo: {a.equipo}')
    print(f'Modo: {a.modo} | {a.total} solicitudes | {min(a.total,a.hilos)} hilos | '
          f'{a.distribucion} | ventana: {a.duracion}s | semaforo: {a.semaforo}')

    cols=['request_id','equipo','id_hilo','hora_envio','hora_respuesta','folio_obtenido',
          'estado','http','duracion_ms','intento']
    cola=queue.Queue()
    stop=object()
    errores_consumidor=[]
    def consumir():
        try:
            with path_csv.open('w',newline='',encoding='utf-8-sig') as f:
                w=csv.DictWriter(f,fieldnames=cols)
                w.writeheader()
                while True:
                    elemento=cola.get()
                    try:
                        if elemento is stop:
                            return
                        w.writerow(elemento)
                        f.flush()
                    finally:
                        cola.task_done()
        except Exception as e:
            errores_consumidor.append(str(e))
            # Si falla el disco, drenar la cola para no bloquear join().
            while True:
                elemento=cola.get()
                cola.task_done()
                if elemento is stop:
                    return

    consumidor=threading.Thread(target=consumir,name='ConsumidorCSV',daemon=True)
    consumidor.start()

    lock=threading.Lock()
    numeros=set()
    resumen={'exitos':0,'rechazados':0,'errores':0,'duplicados_cliente':0,
             'duraciones_ms':[],'en_vuelo':0,'max_en_vuelo':0}
    workers=min(a.total,a.hilos)
    barrera=threading.Barrier(workers,timeout=30) if workers>1 else None
    semaforo=threading.BoundedSemaphore(a.semaforo) if a.semaforo>0 else None
    offsets=planificar_tiempos(a.total,a.duracion,a.margen,a.distribucion)
    inicio_monotono=time.monotonic()

    def solicitar(indice):
        if indice<workers and barrera:
            try:
                barrera.wait()
            except threading.BrokenBarrierError:
                # Si el arranque simultaneo falla, no paralizar el cliente.
                pass
        plazo=inicio_monotono+offsets[indice]
        espera=plazo-time.monotonic()
        if espera>0:
            time.sleep(espera)
        if semaforo:
            semaforo.acquire()
        with lock:
            resumen['en_vuelo']+=1
            resumen['max_en_vuelo']=max(resumen['max_en_vuelo'],resumen['en_vuelo'])
        req_id=uuid4().hex  # UUID diferente por solicitud; ESTABLE en reintentos.
        hilo=threading.current_thread().name
        encabezados={'X-Request-ID':req_id,'X-Thread-ID':hilo,'X-Equipo':a.equipo,
                     **token_headers}
        endpoint='/api/boletos' if a.modo=='principal' else '/api/laboratorio/solicitar?modo='+a.modo[4:]
        folio=''
        estado='ERROR_RED'
        codigo=''
        intento=0
        envio=datetime.now(timezone.utc).astimezone().isoformat(timespec='milliseconds')
        t0=time.perf_counter()
        try:
            for intento in range(1,a.reintentos+2):
                try:
                    r=requests.post(a.url+endpoint,json={'id_evento':a.id_evento},
                                    headers=encabezados,timeout=a.timeout)
                    codigo=r.status_code
                    if codigo==200:
                        if a.modo=='principal':
                            folio=r.headers.get('X-Folio','')
                            if not folio:
                                raise ValueError('Falta X-Folio')
                        else:
                            folio=str(r.json().get('numero_entrada',''))
                        estado='EXITO'
                    elif codigo in (403,409):
                        estado='RECHAZADO'
                    else:
                        estado='ERROR_HTTP'
                    if estado in ('EXITO','RECHAZADO'):
                        break
                except (requests.RequestException,ValueError):
                    estado='ERROR_RED'
                if intento<=a.reintentos:
                    time.sleep(.20)
        finally:
            dur=(time.perf_counter()-t0)*1000
            respuesta=datetime.now(timezone.utc).astimezone().isoformat(timespec='milliseconds')
            with lock:
                resumen['en_vuelo']-=1
                resumen['duraciones_ms'].append(dur)
                if estado=='EXITO':
                    resumen['exitos']+=1
                    if folio in numeros:
                        resumen['duplicados_cliente']+=1
                    numeros.add(folio)
                elif estado=='RECHAZADO':
                    resumen['rechazados']+=1
                else:
                    resumen['errores']+=1
            cola.put({'request_id':req_id,'equipo':a.equipo,'id_hilo':hilo,
                      'hora_envio':envio,'hora_respuesta':respuesta,
                      'folio_obtenido':folio,'estado':estado,'http':codigo,
                      'duracion_ms':round(dur,2),'intento':intento})
            if semaforo:
                semaforo.release()

    try:
        with ThreadPoolExecutor(max_workers=workers,thread_name_prefix='Spawner') as ex:
            futuros=[ex.submit(solicitar,i) for i in range(a.total)]
            for f in as_completed(futuros):
                f.result()
    finally:
        cola.put(stop)
        cola.join()
        consumidor.join(timeout=5)
    transcurrido=time.monotonic()-inicio_monotono
    duraciones=resumen.pop('duraciones_ms')
    resultado={**resumen,'equipo':a.equipo,'modo':a.modo,'solicitudes':a.total,
               'hilos':workers,'id_evento':a.id_evento,'duracion_seg':round(transcurrido,3),
               'promedio_ms':round(sum(duraciones)/len(duraciones),2) if duraciones else 0,
               'boletos_por_segundo':round(resumen['exitos']/transcurrido,3) if transcurrido else 0,
               'meta_100_en_60':(a.modo=='principal' and a.total==100 and
                                resumen['exitos']==100 and transcurrido<=60),
               'bitacora_csv':str(path_csv),'error_consumidor':errores_consumidor}
    if a.modo!='principal':
        try:
            rr=requests.get(a.url+'/api/laboratorio/resultado',headers=token_headers,timeout=a.timeout)
            rr.raise_for_status()
            resultado['laboratorio_oracle']=rr.json()
        except Exception as e:
            resultado['laboratorio_error']=str(e)
    path_json.write_text(json.dumps(resultado,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n========== RESULTADO =========')
    print(json.dumps(resultado,ensure_ascii=False,indent=2))
    print('Archivo CSV:',path_csv)
    return resultado


if __name__=='__main__':
    main()
