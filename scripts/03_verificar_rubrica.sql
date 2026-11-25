-- Ejecutar como AUDITORIO, con F5. Debe mostrar:
-- (1) 20000 de aforo, (2) sobrecupo = 0, (3) duplicados = 0.
SELECT id_evento, nombre, aforo, emitidos, aforo-emitidos AS disponibles FROM eventos;
SELECT COUNT(*) AS boletos_totales FROM boletos;
SELECT COUNT(*) AS duplicados_numero_entrada
FROM (SELECT id_evento, numero_entrada FROM boletos
      GROUP BY id_evento, numero_entrada HAVING COUNT(*) > 1);
SELECT COUNT(*) AS sobrecupo FROM eventos WHERE emitidos > aforo;
SELECT e.emitidos AS contador, COUNT(b.folio) AS boletos_guardados
FROM eventos e LEFT JOIN boletos b ON e.id_evento=b.id_evento
WHERE e.id_evento=1 GROUP BY e.emitidos;
SELECT estado, COUNT(*) AS solicitudes FROM bitacora_solicitudes
GROUP BY estado ORDER BY estado;
SELECT corrida, modo, COUNT(*) AS intentos,
       SUM(CASE WHEN estado='EXITO' THEN 1 ELSE 0 END) AS exitos,
       SUM(CASE WHEN estado='RECHAZADO' THEN 1 ELSE 0 END) AS rechazados,
       COUNT(DISTINCT CASE WHEN estado='EXITO' THEN numero_entrada END) AS numeros_distintos
FROM laboratorio_intentos GROUP BY corrida, modo ORDER BY corrida;
