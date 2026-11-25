/* Auditorio Plata - interfaz original integrada a la API Flask/Oracle.
   NO se inventan folios, disponibilidad, ni firmas. Todos provienen del servidor.
*/
'use strict';
let eventosBD = {};
let eventoElegido = 1;
let solicitudReserva = null; // conservar X-Request-ID si la red falla tras emitir
let filtroMesActivo = '';
let aforoGlobal = {total: 0, vendidos: 0, disponibles: 0};
const TABLA_PRECIOS = {
  'Preferente Planta Baja':1800, 'Primer Piso C':550, 'Primer Piso D':450,
  'Segundo Piso A':450, 'Segundo Piso B':400, 'Segundo Piso C y D':300
};
const NOMBRES_INICIALES = {
  1:'Juan Gabriel - Concierto Navideño', 2:'Jesse & Joy - El Despecho Tour',
  3:'Edith Márquez - En Vivo', 4:'Andrés Obregón Acústico',
  5:'Gloria Trevi - Celebration', 6:'Pimpinela - Leyendas'
};
const ES = new Intl.NumberFormat('es-MX');
function elemento(id) { return document.getElementById(id); }
function texto(id,t) { const e=elemento(id); if(e) e.textContent=String(t); }
function nombreEvento(id) { return eventosBD[id]?.titulo || NOMBRES_INICIALES[id] || 'Concierto'; }
function estadoEvento(id) { return eventosBD[id] || null; }
function uuid() { return (crypto?.randomUUID?.() || `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}`); }

async function cargarEventos() {
  try {
    const res=await fetch('/api/eventos',{cache:'no-store'});
    if(!res.ok) throw new Error(`HTTP ${res.status}`);
    const data=await res.json();
    eventosBD=Object.fromEntries((data.eventos || []).map(x=>[x.id_evento,x]));
    const nav=eventosBD[1];
    if(nav) {
      aforoGlobal={total:nav.aforo,vendidos:nav.emitidos,disponibles:nav.disponibles};
      texto('stat-aforo-total',ES.format(nav.aforo));
      texto('stat-vendidos',ES.format(nav.emitidos));
      texto('stat-disponibles',ES.format(nav.disponibles));
      texto('card-disponibles',nav.disponibles?`${ES.format(nav.disponibles)} boletos libres`:'AGOTADO');
    }
    texto('badge-estado-bd','ORACLE XE CONECTADA');
    const estado=elemento('badge-estado-bd');
    if(estado) estado.className='text-xs font-bold text-green-400 flex items-center space-x-1 mt-1';
    for(let id=2;id<=6;id++) {
      const etiqueta=document.querySelector(`[data-estado-evento="${id}"]`);
      if(!etiqueta) continue;
      const ev=eventosBD[id];
      etiqueta.textContent=ev?`${ES.format(ev.disponibles)} disponibles de ${ES.format(ev.aforo)} · boleto gratis`:'Evento aún no registrado en Oracle (ejecutar script 05)';
      etiqueta.className=`px-5 pb-3 text-xs font-semibold ${ev && ev.disponibles>0?'text-green-700':'text-red-700'}`;
    }
  } catch(err) {
    texto('badge-estado-bd','SIN CONEXIÓN A ORACLE');
    const estado=elemento('badge-estado-bd');
    if(estado) estado.className='text-xs font-bold text-red-400 mt-1';
    console.error('No se pudo cargar cartelera desde Oracle:',err);
  }
}
async function cargarAforoRealBD() { return cargarEventos(); }

function filtrarCartelera() {
  const textoBusqueda=(elemento('buscador-conciertos')?.value || '').toLocaleLowerCase('es-MX').trim();
  let encontrados=0;
  document.querySelectorAll('[data-card-evento]').forEach(card=>{
    const id=Number(card.dataset.cardEvento);
    const porMes=!filtroMesActivo || card.dataset.mes===filtroMesActivo;
    const porTexto=nombreEvento(id).toLocaleLowerCase('es-MX').includes(textoBusqueda);
    card.classList.toggle('hidden',!(porMes && porTexto));
    if(porMes && porTexto) encontrados++;
  });
  elemento('cartelera-vacia')?.classList.toggle('hidden',encontrados>0);
}
function filtroMes(mes) {
  filtroMesActivo = filtroMesActivo===mes ? '' : mes;
  document.querySelectorAll('[data-filtro-mes]').forEach(b=>{
    const elegido=Boolean(filtroMesActivo) && b.dataset.filtroMes===filtroMesActivo;
    b.classList.toggle('bg-auditorioBlack',elegido);
    b.classList.toggle('text-white',elegido);
    b.classList.toggle('bg-white',!elegido);
  });
  filtrarCartelera();
}
function verMasEvento(id) {
  const ev=estadoEvento(id);
  texto('detalle-titulo',nombreEvento(id));
  const d=elemento('detalle-cuerpo');
  if(d) {
    d.replaceChildren();
    const lineas=ev ? [
      ev.descripcion || 'Evento de demostración',
      `Fecha y hora ilustrativa: ${ev.fecha} · ${ev.hora}`,
      `Boletos emitidos en Oracle: ${ES.format(ev.emitidos)} de ${ES.format(ev.aforo)}`,
      `Disponibles: ${ES.format(ev.disponibles)}`,
      'El boleto es gratuito. No existe procesamiento de pagos ni venta real.'
    ] : ['Aún no existe este evento en Oracle. Ejecuta scripts/05_agregar_cartelera.sql como AUDITORIO.'];
    for(const linea of lineas) { const p=document.createElement('p'); p.textContent=linea; d.append(p); }
  }
  elemento('detalle-reservar').onclick=()=>{ cerrarDetalles(); abrirModalCompra(id); };
  elemento('detalle-reservar').disabled=!ev;
  const modal=elemento('modal-detalles');
  modal.classList.remove('hidden'); modal.classList.add('flex');
}
function cerrarDetalles() {
  const modal=elemento('modal-detalles');
  modal.classList.add('hidden'); modal.classList.remove('flex');
}
function abrirModalCompra(id=1) {
  id=Number(id);
  const ev=estadoEvento(id);
  if(!ev) {
    alert('Este concierto aún no está registrado en Oracle. Ejecuta el script 05_agregar_cartelera.sql y actualiza la página.');
    return;
  }
  if(ev.disponibles<=0) { mostrarModalSoldOut(id); return; }
  eventoElegido=id;
  solicitudReserva=null;
  texto('modal-titulo-evento',nombreEvento(id));
  elemento('paso-formulario').classList.remove('hidden');
  elemento('paso-boleto').classList.add('hidden');
  elemento('select-zona').selectedIndex=0;
  elemento('select-cantidad').selectedIndex=0;
  recalcularTotalModal();
  elemento('modal-compra').classList.remove('hidden');
}
function cerrarModalCompra() { elemento('modal-compra').classList.add('hidden'); cargarEventos(); }
async function mostrarModalSoldOut(id=1) {
  texto('soldout-nombre-evento',nombreEvento(id));
  const ev=estadoEvento(id);
  texto('agotado-cifras',ev?`${ES.format(ev.emitidos)} / ${ES.format(ev.aforo)}`:'Consultando...');
  elemento('modal-soldout').classList.remove('hidden');
  await cargarEventos();
  const nuevo=estadoEvento(id);
  if(nuevo) texto('agotado-cifras',`${ES.format(nuevo.emitidos)} / ${ES.format(nuevo.aforo)}`);
}
function cerrarModalSoldOut() { elemento('modal-soldout').classList.add('hidden'); }
function recalcularTotalModal() {
  const zona=elemento('select-zona').value;
  const cant=parseInt(elemento('select-cantidad').value,10)||1;
  texto('text-total-pagar',`$${ES.format((TABLA_PRECIOS[zona]||0)*cant)} MXN (simulado)`);
}
function decodificarQrBase64(s) {
  if(!s) return '';
  return new TextDecoder().decode(Uint8Array.from(atob(s),c=>c.charCodeAt(0)));
}
function descargarBlob(blob,nombre) {
  const url=URL.createObjectURL(blob);
  const link=document.createElement('a'); link.href=url; link.download=nombre;
  document.body.append(link); link.click(); link.remove();
  setTimeout(()=>URL.revokeObjectURL(url),30000);
}
async function confirmarCompraModal() {
  const boton=elemento('btn-confirmar-modal');
  const cantidad=Number(elemento('select-cantidad').value)||1;
  const zona=elemento('select-zona').value;
  // Si ya se registró la reserva pero falla la descarga, reintentar con el MISMO ID.
  const firmaPeticion=JSON.stringify([eventoElegido,cantidad,zona]);
  if(!solicitudReserva || solicitudReserva.firma!==firmaPeticion) {
    solicitudReserva={firma:firmaPeticion,id:uuid()};
  }
  boton.disabled=true;
  boton.textContent='Procesando transacción en Oracle...';
  try {
    const res=await fetch('/api/reservas',{
      method:'POST',
      headers:{'Content-Type':'application/json','X-Request-ID':solicitudReserva.id,
               'X-Equipo':'NAVEGADOR','X-Thread-ID':'Usuario-Web'},
      body:JSON.stringify({id_evento:eventoElegido,cantidad,zona})
    });
    if(res.status===409) {
      const fallo=await res.json();
      if(fallo.motivo==='AFORO_AGOTADO') {
        cerrarModalCompra(); await mostrarModalSoldOut(eventoElegido);
      } else alert(fallo.error || 'La reserva no pudo completarse.');
      return;
    }
    if(!res.ok) {
      const error=await res.json().catch(()=>({}));
      throw new Error(error.error || `HTTP ${res.status}`);
    }
    const blob=await res.blob();
    const folios=(res.headers.get('X-Folios') || res.headers.get('X-Folio') || '').split(',');
    const folio=folios[0];
    const fecha=res.headers.get('X-Fecha') || '';
    const qrReal=decodificarQrBase64(res.headers.get('X-QR-B64'));
    const numero=res.headers.get('X-Numero-Entrada') || '-';
    descargarBlob(blob,cantidad>1?`Auditorio_Plata_${folios.length}_boletos.zip`:`Boleto_Auditorio_Plata_${folio}.pdf`);
    await cargarEventos();
    texto('resultado-boleto',cantidad>1?
      `Se emitieron ${folios.length} boletos reales (folios: ${folios.join(', ')}). Se descargó un ZIP con un PDF por boleto. A continuación se muestra el primero.`:
      `Boleto real emitido, folio ${folio}. Se descargó el PDF oficial con QR verificable.`);
    texto('pdf-folio',`#${folio}`);
    texto('pdf-fecha',fecha.replace('T',' '));
    texto('pdf-asiento',`${zona} · Número de entrada: ${numero}`);
    texto('pdf-hash',qrReal.split('|Firma:')[1] || 'Firma no disponible');
    // Un QR firmado puede exceder la capacidad de qrcodejs (p. ej. 2300 > 1440).
    // En vez de dibujarlo en JS, mostrar el PNG generado desde el texto real en Oracle.
    const qrBox=elemento('qrcode-container');
    if(qrBox) {
      qrBox.replaceChildren();
      if(/^\d+$/.test(folio)) {
        const img=document.createElement('img');
        img.alt=`QR verificable del folio ${folio}`;
        img.width=100; img.height=100;
        img.onerror=()=>{ qrBox.textContent='El QR oficial está dentro del PDF descargado.'; };
        img.src=`/api/boletos/${encodeURIComponent(folio)}/qr.png`;
        qrBox.append(img);
      } else {
        qrBox.textContent='El QR oficial está dentro del PDF descargado.';
      }
    }
    solicitudReserva=null; // reserva y descarga terminadas
    elemento('paso-formulario').classList.add('hidden');
    elemento('paso-boleto').classList.remove('hidden');
  } catch(e) {
    alert(`No se completó la descarga: ${e.message}. Si la conexión falló después de confirmar, revisa el aforo antes de reintentar.`);
  } finally {
    boton.disabled=false;
    boton.textContent='CONFIRMAR BOLETOS GRATIS';
  }
}
function descargarPDFCaptura() {
  // El PDF de Oracle ya se descarga automáticamente. Esta es SOLO una copia visual.
  const element=elemento('area-boleto-pdf');
  if(!element || typeof html2pdf==='undefined') { alert('La copia visual requiere conexión a la biblioteca html2pdf. El PDF oficial ya se descargó.'); return; }
  const clon=element.cloneNode(true);
  const lienzo=element.querySelector('#qrcode-container canvas');
  if(lienzo) {
    const img=document.createElement('img'); img.src=lienzo.toDataURL('image/png'); img.width=100; img.height=100;
    clon.querySelector('#qrcode-container')?.replaceChildren(img);
  }
  const wrap=document.createElement('div');
  wrap.style.cssText='position:fixed;left:-9999px;top:0;width:680px;padding:20px;background:#fff';
  wrap.append(clon); document.body.append(wrap);
  html2pdf().set({margin:.2,filename:'Copia_visual_Auditorio_Plata.pdf',
      image:{type:'jpeg',quality:.98},html2canvas:{scale:2,useCORS:true},
      jsPDF:{unit:'in',format:'letter',orientation:'portrait'}})
     .from(wrap).save().finally(()=>wrap.remove());
}
function avisoSeccion(ev, nombre) {
  if(ev) ev.preventDefault();
  alert(`${nombre}: sección decorativa de la maqueta escolar. La emisión de boletos, búsqueda, detalles y pruebas sí están conectados a Oracle.`);
}
function toggleSpawnerModal() { elemento('modal-spawner').classList.toggle('hidden'); }
async function ejecutarSimulacionSpawner() {
  const boton=elemento('btn-ejecutar-spawner');
  const n=Math.min(100,Math.max(1,parseInt(elemento('spawner-threads').value,10)||1));
  if(!confirm(`Esta prueba enviará ${n} solicitudes concurrentes y EMITIRÁ ${n} boletos reales si hay aforo. ¿Continuar?`)) return;
  const logs=elemento('terminal-logs'); logs.replaceChildren();
  function linea(mensaje,clase='text-gray-300') {
    const p=document.createElement('div'); p.className=clase; p.textContent=mensaje; logs.append(p);
    logs.parentElement.scrollTop=logs.parentElement.scrollHeight;
  }
  boton.disabled=true;
  const inicio=performance.now();
  let siguiente=0,exitos=0,rechazos=0,errores=0;
  linea(`INICIO: ${n} solicitudes HTTP para Concierto Navideño. Concurrencia máximo 20.`, 'text-yellow-400');
  async function trabajador() {
    while(true) {
      const i=++siguiente;
      if(i>n) return;
      try {
        const res=await fetch('/api/boletos',{
          method:'POST',headers:{'Content-Type':'application/json','X-Request-ID':uuid(),
              'X-Thread-ID':`Navegador-${i}`,'X-Equipo':'NAVEGADOR-PRUEBA'},
          body:JSON.stringify({id_evento:1})
        });
        if(res.status===200) { exitos++; linea(`[200] Solicitud ${i} · folio ${res.headers.get('X-Folio')}`,'text-green-400'); }
        else if(res.status===409) { rechazos++; linea(`[409] Solicitud ${i} · aforo agotado`,'text-orange-300'); }
        else { errores++; linea(`[${res.status}] Solicitud ${i} · error HTTP`,'text-red-400'); }
      } catch(e) { errores++; linea(`[ERROR] Solicitud ${i} · ${e.message}`,'text-red-400'); }
    }
  }
  try {
    await Promise.all(Array.from({length:Math.min(20,n)},trabajador));
    const segundos=(performance.now()-inicio)/1000;
    linea(`FINAL: ${exitos} éxitos, ${rechazos} rechazos, ${errores} errores · ${segundos.toFixed(2)} s · ${(exitos/segundos).toFixed(2)} boletos/s`,'text-yellow-300');
    await cargarEventos();
  } finally { boton.disabled=false; }
}

document.addEventListener('DOMContentLoaded',()=>{
  if(window.lucide) { try{lucide.createIcons();}catch(e){console.warn(e);} }
  cargarEventos(); setInterval(cargarEventos,4000);
  elemento('buscador-conciertos')?.addEventListener('input',filtrarCartelera);
  elemento('select-zona')?.addEventListener('change',recalcularTotalModal);
  elemento('select-cantidad')?.addEventListener('change',recalcularTotalModal);
  const botonLupa=document.querySelector('header button:has([data-lucide="search"])');
  if(botonLupa) botonLupa.onclick=()=>{elemento('buscador-conciertos')?.focus();elemento('cartelera')?.scrollIntoView({behavior:'smooth'});};
});
