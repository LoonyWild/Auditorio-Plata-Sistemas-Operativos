-- AUDITORIO PLATA | ACTUALIZACION NO DESTRUCTIVA DE CARTELERA
-- Ejecutar conectado como AUDITORIO en XEPDB1. Puede ejecutarse mas de una vez.
-- NO borra, modifica aforos existentes, ni reinicia los folios.
SET SERVEROUTPUT ON;
WHENEVER SQLERROR EXIT SQL.SQLCODE ROLLBACK;

MERGE INTO eventos e USING (SELECT 2 id_evento, 'Jesse & Joy - El Despecho Tour' nombre FROM dual) x
 ON (e.id_evento=x.id_evento)
 WHEN NOT MATCHED THEN INSERT (id_evento,nombre,aforo,emitidos) VALUES (x.id_evento,x.nombre,20000,0);
MERGE INTO eventos e USING (SELECT 3 id_evento, 'Edith Márquez - En Vivo' nombre FROM dual) x
 ON (e.id_evento=x.id_evento)
 WHEN NOT MATCHED THEN INSERT (id_evento,nombre,aforo,emitidos) VALUES (x.id_evento,x.nombre,20000,0);
MERGE INTO eventos e USING (SELECT 4 id_evento, 'Andrés Obregón Acústico' nombre FROM dual) x
 ON (e.id_evento=x.id_evento)
 WHEN NOT MATCHED THEN INSERT (id_evento,nombre,aforo,emitidos) VALUES (x.id_evento,x.nombre,20000,0);
MERGE INTO eventos e USING (SELECT 5 id_evento, 'Gloria Trevi - Celebration' nombre FROM dual) x
 ON (e.id_evento=x.id_evento)
 WHEN NOT MATCHED THEN INSERT (id_evento,nombre,aforo,emitidos) VALUES (x.id_evento,x.nombre,20000,0);
MERGE INTO eventos e USING (SELECT 6 id_evento, 'Pimpinela - Leyendas' nombre FROM dual) x
 ON (e.id_evento=x.id_evento)
 WHEN NOT MATCHED THEN INSERT (id_evento,nombre,aforo,emitidos) VALUES (x.id_evento,x.nombre,20000,0);

DECLARE
  n NUMBER;
BEGIN
  SELECT COUNT(*) INTO n FROM user_tab_columns WHERE table_name='BOLETOS' AND column_name='ZONA';
  IF n=0 THEN
    EXECUTE IMMEDIATE q'[ALTER TABLE boletos ADD (zona VARCHAR2(64) DEFAULT 'Entrada general' NOT NULL)]';
    DBMS_OUTPUT.PUT_LINE('Columna ZONA creada.');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Columna ZONA existente.');
  END IF;
  SELECT COUNT(*) INTO n FROM user_tab_columns WHERE table_name='BOLETOS' AND column_name='PRECIO_REFERENCIA';
  IF n=0 THEN
    EXECUTE IMMEDIATE 'ALTER TABLE boletos ADD (precio_referencia NUMBER(8) DEFAULT 0 NOT NULL)';
    DBMS_OUTPUT.PUT_LINE('Columna PRECIO_REFERENCIA creada.');
  ELSE
    DBMS_OUTPUT.PUT_LINE('Columna PRECIO_REFERENCIA existente.');
  END IF;
END;
/
COMMIT;
PROMPT CARTELERA DE AUDITORIO PLATA:
SELECT id_evento,nombre,aforo,emitidos FROM eventos ORDER BY id_evento;
