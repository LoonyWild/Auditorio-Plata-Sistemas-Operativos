"""Boletos PDF con QR HMAC autentico (sin archivos temporales ni fuentes externas)."""
from __future__ import annotations
from datetime import datetime
from hmac import new as hmac_new, compare_digest
from hashlib import sha256
from io import BytesIO
import qrcode
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.pagesizes import letter

AUDITORIO = "Auditorio Plata"
EVENTO = "Concierto Navideño"


def texto_qr(folio: int, fecha: datetime, clave: str, evento: str = EVENTO) -> str:
    base = (f"AUDITORIO PLATA|Evento:{evento}|Folio:{folio}|"
            f"Fecha:{fecha:%Y-%m-%d}|Hora:{fecha:%H:%M:%S}")
    firma = hmac_new(clave.encode('utf-8'), base.encode('utf-8'), sha256).hexdigest()
    return f"{base}|Firma:{firma}"


def validar_firma(qr: str, clave: str) -> bool:
    try:
        base, firma = qr.rsplit('|Firma:', 1)
    except ValueError:
        return False
    esperado = hmac_new(clave.encode('utf-8'), base.encode('utf-8'), sha256).hexdigest()
    return compare_digest(esperado, firma)


def generar_pdf(folio: int, fecha: datetime, qr: str, evento: str = EVENTO,
                muestra: bool = False, zona: str = 'Entrada general',
                numero_entrada: int | None = None, precio_referencia: int = 0) -> BytesIO:
    """PDF legitimo o de muestra, con folio y QR reales. El costo es siempre cero."""
    salida = BytesIO()
    c = canvas.Canvas(salida, pagesize=letter)
    ancho, alto = letter
    c.setTitle(f'Auditorio Plata - {evento} - folio {folio}')
    c.setFillColorRGB(.075, .087, .13)
    c.rect(0, 0, ancho, alto, fill=1, stroke=0)
    c.setFillColorRGB(.12, .14, .19)
    c.roundRect(32, 104, ancho-64, alto-180, 17, fill=1, stroke=0)
    c.setStrokeColorRGB(.87, .12, .16)
    c.setLineWidth(2)
    c.roundRect(34, 106, ancho-68, alto-184, 16, fill=0, stroke=1)
    c.setFillColorRGB(.98, .76, .37)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(ancho/2, 720, 'AUDITORIO PLATA')
    titulo = evento.upper()
    c.setFont('Helvetica-Bold', 22 if len(titulo)<=31 else 15)
    c.drawCentredString(ancho/2, 670, titulo[:65])
    c.setFillColorRGB(.96, .96, .96)
    c.setFont('Helvetica-Bold', 12)
    c.drawCentredString(ancho/2, 641, 'BOLETO GRATUITO - PRACTICA ACADEMICA')
    c.setStrokeColorRGB(.5, .5, .56)
    c.line(65, 622, ancho-65, 622)
    c.setFont('Helvetica-Bold', 16)
    c.drawString(70, 587, f'Folio unico: {folio}')
    c.setFont('Helvetica', 12)
    c.drawString(70, 558, f'Fecha de emision: {fecha:%d/%m/%Y}')
    c.drawString(70, 537, f'Hora de emision: {fecha:%H:%M:%S}')
    c.drawString(70, 516, f'Numero de entrada: {numero_entrada if numero_entrada is not None else "MUESTRA"}')
    c.drawString(70, 495, f'Zona seleccionada: {zona[:62]}')
    c.drawString(70, 474, 'Total cobrado: $0.00 MXN (sin pago real)')
    qr_img = qrcode.QRCode(box_size=8, border=2,
                          error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr_img.add_data(qr)
    qr_img.make(fit=True)
    img = qr_img.make_image(fill_color='black', back_color='white').convert('RGB')
    c.drawImage(ImageReader(img), 190, 230, 232, 232, preserveAspectRatio=True, mask='auto')
    c.setFont('Helvetica', 10)
    c.setFillColorRGB(.96, .96, .96)
    c.drawCentredString(ancho/2, 206, 'QR verificable: evento, folio, fecha, hora y firma HMAC')
    c.drawCentredString(ancho/2, 185, 'Valida el QR en /validador')
    c.setFillColorRGB(.8, .8, .84)
    c.setFont('Helvetica', 9)
    c.drawCentredString(ancho/2, 70, 'Emision atomica con Oracle XE - Proyecto Sistemas Operativos')
    if muestra:
        c.setFillColorRGB(.98, .35, .29)
        c.setFont('Helvetica-Bold', 15)
        c.drawCentredString(ancho/2, 146, 'MUESTRA - NO EMITIDO EN ORACLE')
    c.showPage()
    c.save()
    salida.seek(0)
    return salida


def generar_png_qr(qr: str) -> BytesIO:
    """Mismo texto QR almacenado en Oracle, renderizado sin limite fijo de version."""
    codigo = qrcode.QRCode(box_size=8, border=2,
                           error_correction=qrcode.constants.ERROR_CORRECT_M)
    codigo.add_data(qr)
    codigo.make(fit=True)
    imagen = codigo.make_image(fill_color='black', back_color='white').convert('RGB')
    resultado = BytesIO()
    imagen.save(resultado, format='PNG')
    resultado.seek(0)
    return resultado
