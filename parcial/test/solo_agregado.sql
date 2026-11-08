-- C-14 · `movimiento_stock` es de sólo agregado (RN-12)
--
-- Ejecutar desde `parcial/`, sobre la base del seed:
--   python seed.py
--   psql -h 127.0.0.1 -p 5432 -U libreria -d libreria -f test/solo_agregado.sql
--
-- NO se abre una transacción propia (nada de BEGIN/COMMIT) y se corre sin
-- `ON_ERROR_STOP`: el primer error no debe abortar el archivo, porque lo que
-- se evidencia son LOS DOS errores del disparador.
--
-- Esperado (dos errores del motor, uno por sentencia):
--   ERROR:  movimiento_stock es de solo agregado: operacion UPDATE no permitida
--   ERROR:  movimiento_stock es de solo agregado: operacion DELETE no permitida
-- Y al final la tabla conserva sus 7 filas del seed (`count(*) = 7`).
--
-- El disparador `trg_movimiento_stock_no_modificable` (migración 0004) es
-- BEFORE UPDATE OR DELETE: ninguna fila cambia.
--
-- Rastrea: checklist §10 y §12 (C-14), RN-12.

-- 1. UPDATE rechazado (apunta a la fila más antigua del seed).
UPDATE movimiento_stock
SET cantidad = cantidad
WHERE id = (SELECT min(id) FROM movimiento_stock);

-- 2. DELETE rechazado (apunta a la fila más nueva del seed).
DELETE FROM movimiento_stock
WHERE id = (SELECT max(id) FROM movimiento_stock);

-- 3. Control: la tabla conserva exactamente las 7 filas del seed.
SELECT count(*) AS filas_movimiento_stock FROM movimiento_stock;
