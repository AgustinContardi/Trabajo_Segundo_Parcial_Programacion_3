# Design

## Context

El proyecto ya tiene la API completa implementada bajo `parcial/` con los cambios C-01 a C-18 cerrados y archivados. La suite `tests/` ya existe con 30+ archivos de test pytest contra PostgreSQL real, y está limpia (sin `.http` ni `.sql` sueltos). Lo que falta es:
- `parcial/evidencia/` no existe: hay que crearla con dos capturas (C-15 consola con `SQL_ECHO=true`, y C-14 `psql`).
- Verificar que `pytest -q` pasa completo contra PostgreSQL real.

Restricciones aplicables (reglas duras del proyecto, AGENTS.md):
1. UoW construido por el router; servicio lo abre con `async with`.
2. Repositorios: `flush()`, nunca `commit()`.
3. Servicios reciben el UoW, nunca la sesión.
4. `selectinload` solo en `repository.py`.
5. Sin lógica de negocio en el router.
6. `bcrypt` fuera del event loop (`asyncio.to_thread` + semáforo).
7. Fechas con zona (`timestamptz`).
8. No crear migraciones: exactamente 4 archivos en `parcial/migrations/versions/`.
9. No tocar `despliegue/`.
10. No commit ni push.

Política de diseño: `visual_design.mode = off` (ver `.active-orchestrator-state.json` y `design-system/README.md`).

## Goals / Non-Goals

**Goals:**
- Que `pytest -q` pase completo contra PostgreSQL real, comparando status + body (no `model_dump()`).
- Que `tests/` contenga solo pytest, sin `.http` ni `.sql` sueltos.
- Que `parcial/evidencia/` exista con las dos capturas requeridas (C-15 y C-14).

**Non-Goals:**
- No escribir código de producción bajo `parcial/` (este change es solo planificación de pruebas y evidencia).
- No crear migraciones.
- No tocar `despliegue/` ni `knowledge-base/` ni `CHANGES.md`.
- No hacer commit ni push.

## Decisions

### D-01: Capacidad nueva `suite-pytest-evidencia` en `specs/suite-pytest-evidencia/spec.md`
**Razón:** No existe ninguna capacidad de specs que cubra la suite de pruebas pytest ni la carpeta de evidencia. Se crea una nueva en lugar de reutilizar `casos-de-prueba-c` (que cubre los casos C en `.http`) ni `venta-transaccional`/`ventas` (que cubren el dominio de ventas).
**Alternativa considerada:** Agregar requisitos a `casos-de-prueba-c`. Descartado porque esa capacidad describe los casos C de la consigna (`.http` + `solo_agregado.sql`), no pytest ni `evidencia/`.

### D-02: Sin cambios a código de producción
**Razón:** Los tests ya existen y pasan. C-19 solo planifica la verificación (`pytest -q`) y la creación de `parcial/evidencia/`. No hay que escribir código de `parcial/`.
**Alternativa considerada:** Reescribir o agregar tests. Descartado porque la suite ya tiene 30+ tests que cubren todos los casos requeridos.

### D-03: UI Mockups — Decision: no (no UI)
**Razón:** El proyecto es una API pura (sin UI) y la política `visual_design.mode = off` desactiva la puerta de mockups. No hay pantallas, componentes ni estilos que diseñar.
**Fecha:** 2026-11-08.

### D-04: Evidencia se guarda en `parcial/evidencia/` (no en `openspec/changes/c-19/`)
**Razón:** El scope de C-19 (CHANGES.md, líneas 823-847) especifica `parcial/evidencia/` como destino de las capturas de C-14 y C-15.
**Alternativa considerada:** Guardar las capturas dentro del change. Descartado porque no coincide con el scope de la consigna.

## Risks / Trade-offs

- [Risk] Las capturas de C-14 y C-15 dependen de ejecuciones manuales previas contra PostgreSQL local. → Mitigación: las capturas ya están generadas en `parcial/test/evidencia/` (verificadas); solo hay que copiarlas a `parcial/evidencia/`.
- [Risk] `pytest -q` podría fallar si PostgreSQL no está levantado o las credenciales de `.env` no coinciden. → Mitigación: ejecutar contra `127.0.0.1:5432`, base `libreria`, `.env` en `parcial/`.
- [Risk] Confundir `tests/` (raíz del parcial, limpio) con `parcial/test/` (tiene `.http`, eso está bien). → Mitigación: verificar explícitamente que `tests/` no tenga `.http` ni `.sql`.

## Migration Plan

No aplica: no hay cambios de esquema, no hay migraciones, no hay despliegue. El cambio es puramente de planificación (artefactos en `openspec/changes/c-19-suite-pytest-y-evidencia/`) y, en la fase de apply, creación de `parcial/evidencia/` con archivos ya existentes.

## Open Questions

Ninguna. Todos los requisitos de C-19 están definidos en CHANGES.md y la suite de tests ya existe.

## UI Mockups

- Design system revision: n/a (proyecto sin UI, política `visual_design.mode = off`)
- Decision: no (no UI) — 2026-11-08
- Mockups: n/a
- Approval: n/a
- Preview: n/a
- Visual verify: n/a
