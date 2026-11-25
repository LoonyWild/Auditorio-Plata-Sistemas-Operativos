# Diagramas del Concierto Navideño

## 1. Conexiones entre las 3 computadoras

```mermaid
flowchart LR
 A[PC 2 - Spawner A<br/>100 hilos en prueba oficial] -->|HTTP:5000| S[PC 1 - Flask / Waitress]
 B[PC 3 - Spawner B<br/>prueba opcional] -->|HTTP:5000| S
 W[Teléfono / navegador] -->|HTTPS túnel temporal| S
 S -->|Oracle Thin localhost:1521| D[(Oracle XE o Free<br/>AUDITORIO / 20000 lugares)]
 D --> S
 S -->|Boleto PDF + QR| A
 S -->|Boleto PDF + QR| B
```

**Conexión simple:** los 3 equipos deben poder acceder a `http://IP_DE_PC1:5000`. Oracle no se instala en PC 2/PC 3 ni expone 1521. Solo PC 1 conoce la contraseña Oracle.

## 2. Sección crítica de emisión real

```mermaid
flowchart TD
 A[POST /api/boletos con Request-ID] --> B[Adquirir conexión Oracle]
 B --> C[SELECT eventos FOR UPDATE]
 C --> D{¿Request-ID ya existe?}
 D -- Sí --> E[Leer boleto existente / registrar REINTENTO]
 D -- No --> F{¿emitidos menor que 20,000?}
 F -- No --> G[Bitácora RECHAZADO + COMMIT / HTTP 409]
 F -- Sí --> H[seq_folio.NEXTVAL + INSERT boleto + UPDATE contador]
 H --> I[Bitácora EXITO + COMMIT]
 E --> J[Generar PDF/QR FUERA del bloqueo]
 I --> J
 J --> K[HTTP 200 + PDF + folio]
```

## 3. Carrera del laboratorio (recurso separado de boletos)

```mermaid
flowchart LR
 A[Hilo A: lee contador=0] --> C[Espera artificial 45 ms]
 B[Hilo B: lee contador=0] --> D[Espera artificial 45 ms]
 C --> E[Escribe contador=1 y entrada 1]
 D --> F[Escribe contador=1 y entrada 1]
 E --> G[Dos exitos con el MISMO numero]
 F --> G
```

SIN: la lectura y actualización no están protegidas como una operación indivisible. CON: `FOR UPDATE` impide que dos transacciones consulten y asignen el mismo valor simultáneamente.
