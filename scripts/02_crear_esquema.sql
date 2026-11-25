-- EJECUTAR COMO USUARIO AUDITORIO en la PDB, con F5 (Run Script).
-- ATENCION: la ejecucion se hace en un esquema vacio. No es un reset.
CREATE TABLE eventos (
  id_evento NUMBER(3) CONSTRAINT pk_eventos PRIMARY KEY,
  nombre VARCHAR2(120) NOT NULL,
  aforo NUMBER(6) NOT NULL,
  emitidos NUMBER(6) DEFAULT 0 NOT NULL,
  CONSTRAINT ck_evento_aforo CHECK (aforo > 0 AND emitidos >= 0 AND emitidos <= aforo)
);
INSERT INTO eventos (id_evento, nombre, aforo, emitidos)
VALUES (1, 'Concierto Navideño', 20000, 0);

CREATE SEQUENCE seq_folio START WITH 1 INCREMENT BY 1 NOCYCLE CACHE 50;
CREATE TABLE boletos (
  folio NUMBER(12) CONSTRAINT pk_boletos PRIMARY KEY,
  id_evento NUMBER(3) NOT NULL REFERENCES eventos(id_evento),
  numero_entrada NUMBER(6) NOT NULL,
  fecha_emision TIMESTAMP(0) NOT NULL,
  qr_texto VARCHAR2(700) NOT NULL,
  request_id VARCHAR2(64) NOT NULL,
  CONSTRAINT uq_boletos_numero UNIQUE (id_evento, numero_entrada),
  CONSTRAINT uq_boletos_peticion UNIQUE (request_id)
);
CREATE INDEX ix_boletos_evento ON boletos (id_evento);

CREATE SEQUENCE seq_bitacora START WITH 1 INCREMENT BY 1 NOCYCLE CACHE 50;
CREATE TABLE bitacora_solicitudes (
  id NUMBER(12) CONSTRAINT pk_bitacora PRIMARY KEY,
  request_id VARCHAR2(64) NOT NULL,
  equipo VARCHAR2(50) NOT NULL,
  id_hilo VARCHAR2(80) NOT NULL,
  hora_envio TIMESTAMP(3) NOT NULL,
  hora_respuesta TIMESTAMP(3) NOT NULL,
  folio NUMBER(12),
  estado VARCHAR2(30) NOT NULL,
  duracion_ms NUMBER(12) NOT NULL,
  CONSTRAINT ck_bitacora_estado CHECK (estado IN ('EXITO','RECHAZADO','REINTENTO','ERROR'))
);
CREATE INDEX ix_bitacora_estado ON bitacora_solicitudes (estado);

-- LABORATORIO aislado: permite provocar duplicados de numeros de entrada
-- SIN afectar las tablas de los 20,000 boletos reales.
CREATE TABLE laboratorio_estado (
  id NUMBER(1) CONSTRAINT pk_lab_estado PRIMARY KEY,
  aforo NUMBER(5) NOT NULL,
  emitidos NUMBER(8) NOT NULL,
  corrida VARCHAR2(36) NOT NULL
);
INSERT INTO laboratorio_estado VALUES (1, 20, 0, 'INICIAL');
CREATE SEQUENCE seq_lab START WITH 1 INCREMENT BY 1 NOCYCLE CACHE 50;
CREATE TABLE laboratorio_intentos (
  id NUMBER(12) CONSTRAINT pk_lab_intentos PRIMARY KEY,
  corrida VARCHAR2(36) NOT NULL,
  modo VARCHAR2(3) NOT NULL,
  numero_entrada NUMBER(8),
  estado VARCHAR2(15) NOT NULL,
  id_hilo VARCHAR2(80),
  creado_en TIMESTAMP(3) DEFAULT LOCALTIMESTAMP NOT NULL
);
CREATE INDEX ix_lab_corrida ON laboratorio_intentos(corrida);
COMMIT;

SELECT id_evento, nombre, aforo, emitidos FROM eventos;
