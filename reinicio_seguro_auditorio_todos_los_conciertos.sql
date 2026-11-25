-- AUDITORIO PLATA - REINICIO TOTAL PARA DEMOSTRACION
-- PELIGRO: BORRA TODOS LOS BOLETOS Y BITACORAS DE LOS SEIS CONCIERTOS.
-- RESPALDA LAS EVIDENCIAS ANTES. NO EJECUTAR CON SPAWNERS EN MARCHA.
-- Deten app y tunel; conecta como AUDITORIO a XEPDB1.
SET SERVEROUTPUT ON
SET DEFINE ON
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK
PROMPT ESTADO ANTES DE REINICIAR:
SELECT id_evento, aforo, emitidos FROM eventos ORDER BY id_evento;
SELECT COUNT(*) AS boletos_antes FROM boletos;
ACCEPT CONFIRMACION CHAR PROMPT 'Escribe REINICIAR_TODO para borrar los datos reales: '
DECLARE
  v_opcion VARCHAR2(30) := UPPER(TRIM('&CONFIRMACION'));
BEGIN
  IF v_opcion <> 'REINICIAR_TODO' THEN
    RAISE_APPLICATION_ERROR(-20001,'Cancelado: no se borraron boletos');
  END IF;
END;
/
DELETE FROM bitacora_solicitudes;
DELETE FROM boletos;
UPDATE eventos SET emitidos=0;
COMMIT;
PROMPT ESTADO DESPUES DEL REINICIO:
SELECT id_evento, aforo, emitidos, aforo-emitidos AS disponibles FROM eventos ORDER BY id_evento;
SELECT COUNT(*) AS boletos_restantes FROM boletos;
SELECT COUNT(*) AS bitacoras_restantes FROM bitacora_solicitudes;
PROMPT NOTA: Las secuencias SEQ_FOLIO y SEQ_BITACORA NO se reinician.
