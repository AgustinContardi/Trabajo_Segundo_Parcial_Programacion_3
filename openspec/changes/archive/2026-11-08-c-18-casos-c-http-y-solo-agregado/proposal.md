# Proposal — C-18 casos-c-http-y-solo-agregado

## Why

La consigna exige que `parcial/test/` demuestre los dieciséis casos `C-01…C-16` con un `.http` por módulo,
la respuesta esperada escrita en un comentario y `test/solo_agregado.sql` (p. 21-22, checklist §10). Hoy el
repo tiene cinco `.http` heredados de changes anteriores que cubren sólo una parte: `auth.http` (C-03/04/05),
`registro.http` (C-02), `roles.http` (C-06/07 con usuarios y SQL de preparación propios), `ventas.http`
(C-10/11/12 y contrato de C-16) y un `tp.http` del baseline con payloads viejos (`stock` en vez de
`stock_inicial`). Faltan C-01 con sesión, C-08, C-09, C-13, C-14, C-15, la paginación y el PATCH de C-16, el
caso de `BackgroundTasks` y el truco de dos sesiones con `# @name` / `# @no-cookie-jar` que la consigna pide
para C-07. Además, los archivos viejos dependen de datos que ya no existen: desde C-17 el estado canónico es
`python seed.py` (usuarios, roles, cinco libros con stock 10/5/8/3/1, clientes y venta 1). Sin este change no
hay evidencia corregible caso por caso.

## What Changes

- Reorganizar `parcial/test/` en un `.http` por módulo que cubra **C-01…C-16**, cada bloque con
  `# Esperado:` (status, cuerpo y cabeceras relevantes) y la/las `RN-xx` que lo justifican, y todos pensados
  para correrse con REST Client **después** de `python seed.py`.
- Reescribir `auth.http`, `registro.http`, `roles.http` y `ventas.http` sobre los datos del seed; retirar
  `tp.http` (payloads obsoletos) y mover sus dos verificaciones útiles a `libros.http`.
- Agregar `libros.http` (C-01, C-13, C-16 de catálogo), los casos C-08/C-09 en `roles.http` y la paginación,
  la inyección `' OR '1'='1`, el PATCH parcial y el `stock` en PATCH → 422 en `libros.http`.
- Implementar C-07 con **dos sesiones simultáneas en el mismo archivo**: cada login con `# @name login_admin`
  / `# @name login_vendedor`, las peticiones de esa sesión con `# @no-cookie-jar` y
  `Cookie: {{login_vendedor.response.headers.Set-Cookie}}`.
- Agregar `parcial/test/solo_agregado.sql` con un `UPDATE` y un `DELETE` sobre `movimiento_stock` que el
  disparador rechaza (C-14), para correr con `psql -f`.
- Documentar y ejecutar el caso del aviso con `uvicorn main:app` sin configuración extra de logging: registrar
  una venta y comprobar que la línea del comprobante aparece **después** de la línea de la respuesta (C-10).
- Producir las capturas sin procesar de C-14 (`psql -f`) y C-15 (conteo de `SELECT` con `SQL_ECHO=true` para
  una venta de 2 y otra de 4 renglones); C-19 las consolida en `parcial/evidencia/`.
- Dejar registrado por escrito qué se ejecutó y con qué salida (`parcial/test/EVIDENCIA.md` o un `.md` por
  archivo), separando «archivo escrito con resultado esperado» de «corrida real».

## Capabilities

### New Capabilities

- `casos-de-prueba-c`: el conjunto de evidencia ejecutable que demuestra los casos `C-01…C-16` y el aviso de
  `BackgroundTasks` sobre la API real: archivos `.http` por módulo con resultado esperado, el SQL de sólo
  agregado y las capturas que la entrega exige.

### Modified Capabilities

Ninguna. No cambia ningún contrato de la API, el esquema ni una regla de negocio: el change sólo escribe y
ejecuta la evidencia de lo que ya está implementado.

## Impact

- **Sólo artefactos de prueba**: `parcial/test/*.http`, `parcial/test/solo_agregado.sql`, un registro de
  evidencia y las capturas crudas de C-14/C-15. No se toca `parcial/app/`, `parcial/main.py`,
  `parcial/migrations/`, `parcial/seed.py` ni `despliegue/`.
- **Reutiliza el estado de C-17**: ids estables (libros 1…5, venta 1, usuarios por correo), lo que elimina el
  bootstrap SQL manual de `roles.http`.
- **Dependencias cumplidas**: C-12 (registro atómico), C-14 (cambio de contraseña) y C-17 (seed canónico).
- **Habilita C-19**: sus capturas de C-14/C-15 y el mapa caso → archivo son el insumo de la carpeta
  `parcial/evidencia/` y de la suite `tests/`.
- **Riesgo asumido**: REST Client es una GUI y el agente no puede correrla headless; el change entrega los
  archivos y su ejecución equivalente documentada, y no declara corridas que no hizo.
