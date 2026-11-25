import csv
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from contextlib import redirect_stdout

from boletos_pdf import texto_qr, validar_firma, generar_pdf
from spawner import planificar_tiempos, main


class TestBoleto(unittest.TestCase):
    def test_qr_con_firma_y_cambios(self):
        fecha=datetime(2026,12,15,18,25,33)
        qr=texto_qr(123,fecha,'clave-de-prueba',evento='Concierto Navideño')
        self.assertIn('Folio:123|Fecha:2026-12-15|Hora:18:25:33',qr)
        self.assertTrue(validar_firma(qr,'clave-de-prueba'))
        self.assertFalse(validar_firma(qr.replace('123','124'),'clave-de-prueba'))
        self.assertFalse(validar_firma(qr,'otra clave'))

    def test_pdf_valido_y_muestra(self):
        fecha=datetime(2026,12,15,18,25,33)
        qr=texto_qr(42,fecha,'clave-de-prueba')
        pdf=generar_pdf(42,fecha,qr,muestra=True).getvalue()
        self.assertTrue(pdf.startswith(b'%PDF-'))
        self.assertGreater(len(pdf),5000)

    def test_planificador(self):
        a=planificar_tiempos(100,60,10,'uniforme')
        self.assertEqual(len(a),100)
        self.assertEqual(a[0],0)
        self.assertAlmostEqual(a[-1],50)
        self.assertTrue(all(x<=y for x,y in zip(a,a[1:])))
        self.assertEqual(planificar_tiempos(3,10,2,'rafaga'),[0]*3)


class TestSpawnerSinOracle(unittest.TestCase):
    """Prueba de cliente y log contra servidor HTTP de simulacion.
    NO valida la parte Oracle, que requiere la instalacion real de PC 1.
    """
    def test_spawner_csv_y_barrera(self):
        class Servidor(BaseHTTPRequestHandler):
            guardia=threading.Lock()
            contador=0
            def log_message(self,*args):
                return
            def do_GET(self):
                if self.path=='/api/salud':
                    cuerpo=b'{"oracle":"CONECTADA"}'
                else:
                    cuerpo=b'{}'
                self.send_response(200)
                self.send_header('Content-Length',str(len(cuerpo)))
                self.end_headers()
                self.wfile.write(cuerpo)
            def do_POST(self):
                with self.guardia:
                    type(self).contador+=1
                    folio=type(self).contador
                self.send_response(200)
                self.send_header('X-Folio',str(folio))
                self.send_header('Content-Length','0')
                self.end_headers()
        srv=ThreadingHTTPServer(('127.0.0.1',0),Servidor)
        hilo=threading.Thread(target=srv.serve_forever,daemon=True)
        hilo.start()
        try:
            with tempfile.TemporaryDirectory() as temp:
                with redirect_stdout(io.StringIO()):
                    r=main(['--url',f'http://127.0.0.1:{srv.server_port}',
                            '--equipo','TEST', '--total','9','--hilos','12',
                            '--duracion','1','--margen','0.2',
                            '--semaforo','4','--salida',temp])
                self.assertEqual(r['exitos'],9)
                self.assertEqual(r['duplicados_cliente'],0)
                self.assertEqual(r['errores'],0)
                with open(r['bitacora_csv'],encoding='utf-8-sig') as x:
                    self.assertEqual(len(list(csv.DictReader(x))),9)
                self.assertEqual(len(list(Path(temp).glob('*.json'))),1)
        finally:
            srv.shutdown()
            srv.server_close()


if __name__=='__main__':
    unittest.main()
