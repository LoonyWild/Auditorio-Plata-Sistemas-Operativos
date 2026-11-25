# Reporte: Concierto Navideño — Auditorio Plata

> **PLANTILLA POR COMPLETAR TRAS LA PRUEBA REAL.** No afirmar resultados no medidos. Adjuntar capturas, CSV y SQL.

## 1. Objetivo general
Implementar una aplicación web que emite boletos gratuitos en PDF con QR para un evento de aforo 20,000 y demostrar el control de la sección crítica frente a solicitudes concurrentes con Oracle.

## 2. Arquitectura
Ver `DIAGRAMAS.pdf` y `DIAGRAMAS.md`.
- PC 1: Flask/Waitress y Oracle XE/Free en la misma máquina (puerto Flask 5000; Oracle solo local).
- PC 2: spawner para 100 solicitantes HTTP; PC 3: observación o ensayo opcional simultáneo.
- Acceso HTTP local con IP de PC 1; publicación temporal HTTPS con túnel.

## 3. Algoritmos de sincronización
**Mutex Python:** protege los diccionarios, folios vistos y métricas del cliente; **no** sustituye el bloqueo del servidor.

**Semáforo (`BoundedSemaphore`)**: permite un máximo configurado de solicitudes HTTP en vuelo (por defecto 20).

**Barrera (`Barrier`)**: libera a la primera ola de workers juntos. Al cambiar `--total` y `--hilos`, la barrera utiliza `min(total,hilos)`.

**Productor-consumidor (`Queue`)**: los workers producen registros y un hilo consumidor único escribe CSV.

**Sección crítica Oracle:** `SELECT aforo, emitidos FROM eventos ... FOR UPDATE WAIT 15` bloquea la única fila de aforo, verifica disponibilidad, obtiene folio de `seq_folio.NEXTVAL`, inserta boleto, incrementa contador y confirma con un único `COMMIT`. Los índices PK/UNIQUE/CHECK rechazan inconsistencias. En el laboratorio, el modo sin sincronización separa la lectura del contador de la escritura y crea una ventana TOCTOU deliberada. La sección crítica no es el PDF; este se produce después de `COMMIT`.

**Peterson:** exclusión mutua de **dos** procesos mediante turnos e intención compartidos; requiere supuestos de memoria ordenada y no escala de forma simple a múltiples hosts. **Panadería de Lamport:** selecciona turnos numéricos para N procesos y muestra fairness teórica bajo sus supuestos. Ambos se estudian conceptualmente; la implementación usa primitivas estándar y bloqueo transaccional Oracle, aptos para tres PCs.

## 4. Experimentos

### 4.1 Prueba obligatoria: 100 boletos en 60 s desde PC 2
Comando ejecutado: `spawner.py --url http://IP_PC1:5000 --equipo PC2 --total 100 --hilos 100 --duracion 60 --margen 10 --distribucion uniforme --semaforo 20`

| Métrica | Resultado observado |
|---|---|
| Fecha, hora y equipos | **[COMPLETAR]** |
| Tiempo total (segundos) | **[COMPLETAR]** |
| Solicitudes exitosas | **[COMPLETAR]** |
| Rechazos | **[COMPLETAR]** |
| Errores/timeouts | **[COMPLETAR]** |
| Tiempo promedio de respuesta (ms) | **[COMPLETAR]** |
| Boletos por segundo | **[COMPLETAR]** |
| Folios duplicados (consulta Oracle) | **[COMPLETAR]** |
| Boletos emitidos por encima de aforo | **[COMPLETAR]** |
| ¿100 éxitos en <=60 s? | **[COMPLETAR: SÍ / NO]** |

Evidencias: **[adjuntar captura consola y JSON, archivo CSV, `03_verificar_rubrica.sql`, captura QR en celular]**.

### 4.2 Prueba SIN sincronización (laboratorio 20 lugares)
Comando: `spawner.py --modo lab-sin --reiniciar-lab --total 60 --hilos 60 --distribucion rafaga --duracion 10 --margen 2 --semaforo 30 --admin-token ...`

| Métrica | SIN |
|---|---|
| Total de solicitudes | **[COMPLETAR]** |
| Éxitos | **[COMPLETAR]** |
| Rechazos | **[COMPLETAR]** |
| Folios/números duplicados | **[COMPLETAR]** |
| Exceso de emisiones sobre aforo 20 | **[COMPLETAR]** |

### 4.3 Prueba CON sincronización (laboratorio 20 lugares)
Comando igual a anterior cambiando `--modo lab-con`; se reinicia laboratorio entre ambas pruebas.

| Métrica | CON |
|---|---|
| Total de solicitudes | **[COMPLETAR]** |
| Éxitos | **[COMPLETAR]** |
| Rechazos | **[COMPLETAR]** |
| Folios/números duplicados | **[COMPLETAR]** |
| Exceso de emisiones sobre aforo 20 | **[COMPLETAR]** |

**Interpretación:** explicar por qué los dos hilos que leyeron el mismo contador sin bloqueo obtuvieron el mismo número; destacar que el modo CON solo permite 20 éxitos y rechaza el resto. Los boletos reales usan siempre la versión CON.

### 4.4 Prueba opcional desde PC 2 + PC 3
Describir inicio simultáneo, URL común, cantidad de solicitudes de cada PC, CSV combinado, folios únicos y las métricas SQL. Esta prueba **no sustituye** la prueba individual obligatoria.

## 5. Fallos de red y resiliencia
Documentar un ensayo real de desconexión, timeout o HTTP 409, mostrando que los demás workers continúan y producen registros. El `X-Request-ID` se reutiliza durante los reintentos para no duplicar la emisión.

## 6. Conclusiones
1. **[COMPLETAR: efecto del bloqueo de fila de Oracle y restricciones sobre integridad]**
2. **[COMPLETAR: diferencia entre sincronización del cliente y del servidor]**
3. **[COMPLETAR: margen de rendimiento, hardware/red, y posibles mejoras]**

## 7. Enlaces y evidencias finales
- URL HTTPS del evento: **[PEGAR URL REAL]**
- Repositorio GitHub: **[PEGAR URL REAL]**
- PDF de boleto **REAL** emitido durante la prueba y captura del QR escaneado: **[ADJUNTAR]**
- Bitácoras PC 2 y PC 3: **[ADJUNTAR CSV Y JSON]**
- SQL de esquema, verificación, diagramas, pruebas automáticas: ya incluidos en esta carpeta.
