"""Consolida CSV de varias PCs y detecta duplicados entre ellas."""
import argparse, csv, json
from collections import Counter
from pathlib import Path
p=argparse.ArgumentParser()
p.add_argument('archivos',nargs='+',help='CSV de cada equipo (se admiten patrones de PowerShell ya expandidos)')
a=p.parse_args()
filas=[]
for nombre in a.archivos:
    f=Path(nombre)
    with f.open(encoding='utf-8-sig',newline='') as x:
        filas.extend(list(csv.DictReader(x)))
folios=[str(r['folio_obtenido']) for r in filas if r['estado']=='EXITO' and r['folio_obtenido']]
repeticiones={k:v for k,v in Counter(folios).items() if v>1}
resultado={'archivos':len(a.archivos),'solicitudes':len(filas),
           'exitos':sum(r['estado']=='EXITO' for r in filas),
           'rechazos':sum(r['estado']=='RECHAZADO' for r in filas),
           'errores':sum(r['estado'] not in ('EXITO','RECHAZADO') for r in filas),
           'folios_unicos':len(set(folios)),
           'folios_duplicados':sum(v-1 for v in repeticiones.values()),
           'repetidos_detalle':repeticiones}
print(json.dumps(resultado,ensure_ascii=False,indent=2))
