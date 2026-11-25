-- CUIDADO: BORRA boletos y bitacoras reales para repetir la practica.
-- SOLO para el laboratorio, SIN spawners ni servidores emitiendo boletos.
-- Mantiene la secuencia (pueden existir saltos; los folios siguen siendo unicos).
DELETE FROM bitacora_solicitudes;
DELETE FROM boletos;
UPDATE eventos SET emitidos=0 WHERE id_evento=1;
COMMIT;
SELECT id_evento, aforo, emitidos FROM eventos;
