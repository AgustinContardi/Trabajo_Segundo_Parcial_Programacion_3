# Tasks

## 1. Verificar suite de tests existente

- [x] 1.1 Confirmar que `tests/` existe y contiene solo archivos de prueba pytest → Verificar listado del directorio `tests/` y que todos los archivos terminan en `.py`
- [x] 1.2 Confirmar que `tests/` no tiene archivos `.http` ni `.sql` sueltos → Ejecutar búsqueda de `*.http` y `*.sql` dentro de `tests/`; resultado esperado: cero archivos

## 2. Crear carpeta de evidencia `parcial/evidencia/`

- [x] 2.1 Crear directorio `parcial/evidencia/` → Verificar que el directorio `parcial/evidencia/` existe
- [x] 2.2 Colocar captura de consola de C-15 (detalle de venta con 2 y 4 renglones, `SQL_ECHO=true`) → Verificar que existe un archivo de captura de C-15 dentro de `parcial/evidencia/`
- [x] 2.3 Colocar captura de `psql` de C-14 → Verificar que existe un archivo de captura de `psql` de C-14 dentro de `parcial/evidencia/`

## 3. Ejecutar y verificar `pytest -q`

- [x] 3.1 Ejecutar `pytest -q` contra PostgreSQL real (127.0.0.1:5432, base `libreria`) → Verificar código de salida 0 y que todos los tests pasan
- [x] 3.2 Confirmar que los tests comparan status + body, no `model_dump()` → Revisar que ningún test de `tests/` use `model_dump()` para comparación de respuestas

## 4. Verificación final de aceptación de C-19

- [x] 4.1 Verificar que `pytest -q` pasa completo contra PostgreSQL real (nunca SQLite) → Ejecutar `pytest -q` y observar salida verde
- [x] 4.2 Verificar que `tests/` tiene solo pytest, sin `.http` ni `.sql` sueltos → Listar `tests/` y confirmar cero archivos con esas extensiones
- [x] 4.3 Verificar que `parcial/evidencia/` tiene la captura de C-15 y la de `psql` de C-14 → Confirmar presencia de ambos archivos en `parcial/evidencia/`

## Workflow follow-up

- Ejecutar `/opsx:archive c-19-suite-pytest-y-evidencia` una vez implementado y verificado.
- Marcar el change como `[x]` en `CHANGES.md`.
