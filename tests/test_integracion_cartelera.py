"""Pruebas locales sin Oracle: validaciones HTML, PDF y sincronización."""
import concurrent.futures
from datetime import datetime
from pathlib import Path
import threading
import time
import unittest
from io import BytesIO
from zipfile import ZipFile
from boletos_pdf import generar_pdf, texto_qr, validar_firma
from sincronizacion import MesaFilosofos, MonitorEmision

BASE=Path(__file__).resolve().parent.parent

class TestCartelera(unittest.TestCase):
    def test_html_registra_los_seis_eventos(self):
        html=(BASE/'templates'/'index.html').read_text(encoding='utf-8')
        for i in range(1,7):
            self.assertIn(f'data-card-evento="{i}"',html)
            self.assertIn(f'abrirModalCompra({i})',html)
        for i in range(2,7):
            self.assertIn(f'verMasEvento({i})',html)
        self.assertIn("static', filename='cartelera.js'",html)
        self.assertNotIn("fetch('/solicitar_boleto'",html)

    def test_pdf_para_todos_los_conciertos(self):
        for evento in ('Juan Gabriel - Concierto Navideño', 'Jesse & Joy - El Despecho Tour',
                       'Edith Márquez - En Vivo','Andrés Obregón Acústico',
                       'Gloria Trevi - Celebration','Pimpinela - Leyendas'):
            fecha=datetime(2026,11,25,3,45,0)
            qr=texto_qr(101,fecha,'clave-prueba',evento)
            self.assertTrue(validar_firma(qr,'clave-prueba'))
            pdf=generar_pdf(101,fecha,qr,evento=evento,zona='Primer Piso C',numero_entrada=12)
            self.assertTrue(pdf.getvalue().startswith(b'%PDF-'))
            self.assertGreater(len(pdf.getvalue()),4000)

class TestSincronizacion(unittest.TestCase):
    def test_monitor_limita_concurrencia(self):
        monitor=MonitorEmision(limite=2)
        cuenta=[0,0]
        candado=threading.Lock()
        def worker():
            with monitor.turno():
                with candado:
                    cuenta[0]+=1
                    cuenta[1]=max(cuenta[1],cuenta[0])
                time.sleep(.015)
                with candado: cuenta[0]-=1
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _:worker(),range(18)))
        self.assertLessEqual(cuenta[1],2)
        self.assertEqual(cuenta[0],0)

    def test_filosofos_sin_interbloqueo(self):
        mesa=MesaFilosofos(5)
        en_mesa=set()
        errores=[]
        candado=threading.Lock()
        def worker(i):
            for _ in range(3):
                mesa.tomar(i)
                try:
                    with candado:
                        if (i-1)%5 in en_mesa or (i+1)%5 in en_mesa:
                            errores.append(f'Vecinos concurrentes {i}')
                        en_mesa.add(i)
                    time.sleep(.001)
                    with candado: en_mesa.remove(i)
                finally:
                    mesa.soltar(i)
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
            list(pool.map(worker,range(5)))
        self.assertEqual(errores,[])
        self.assertEqual(mesa.tenedores,[False]*5)

if __name__=='__main__': unittest.main()
