# Proposal

## Why

C-01…C-21 dejaron el proyecto, la evidencia y el despliegue en estado entregable, pero falta el
artefacto que la cátedra corrige: un único `.zip` con la forma exacta que pide la consigna, dos
READMEs que identifiquen al grupo y permitan levantarlo desde cero, y una autoevaluación honesta
contra la rúbrica. Sin ese cierre, un proyecto que funciona puede quedar afuera por un `.env`
incluido, una carpeta de menos o un README con placeholders. Es la puerta de entrega y tiene
governance **CRÍTICO**.

## What Changes

- **READMEs de las dos carpetas**: reemplazar los placeholders por el grupo **AURA** y los cinco
  integrantes con nombre y apellido (Enzo Giaquinta, Agustin Contardi, Fernando Torrez, Ramiro
  Salcedo e Ignacio Sanchez). En `parcial/README.md`, cerrar la puesta en marcha desde cero con
  `python seed.py` entre las migraciones y el arranque, y advertir que el seed vacía la base.
- **Revisión de `env.example`** en ambas carpetas: sólo placeholders y la forma de las variables,
  sin valores reales; confirmar que ningún `.env` está versionado.
- **Evidencia de entrega**: crear `parcial/evidencia/autoevaluacion.md` con los 10 criterios de la
  rúbrica, su peso, la evidencia concreta y las condiciones que anulan la corrección. El
  transcript completo de la corrida limpia queda en `docs/auditoria-final/`, fuera del zip.
- **Corrida en carpeta limpia** de `docs/CHECKLIST_ENTREGA.md` (secciones §0–§13, con foco en §12
  y §13): base vacía, esquema sólo por Alembic, seed, arranque, `.http`, pytest y verificación de
  evidencia. Se registran las sustituciones de versión y los ítems que no se pudieron correr.
- **Cierre git**: revisar el historial por credenciales, dejar el árbol limpio y generar el zip
  **desde el commit final** con `git archive`, sin `.git`, sin `.venv`, sin `__pycache__` y sin
  `.env`.
- **Entrega**: `Parcial_Cap1a6_AURA.zip` con exactamente `parcial/` y `despliegue/`, verificado por
  extracción en carpeta temporal, con SHA-256 registrado y guardado fuera del repositorio.
- **Cierre documental**: marcar `[C-22]` en `CHANGES.md`, archivar el change y dejar el árbol limpio.
  El commit y el push requieren pedido explícito del usuario.

## Capabilities

### New Capabilities

- `entrega-final`: forma y contenido del `.zip` de entrega, identificación del grupo en los dos
  READMEs, puesta en marcha desde cero, corrida limpia del checklist, autoevaluación contra la
  rúbrica y trazabilidad zip ↔ commit limpio sin credenciales.

### Modified Capabilities

- Ninguna. `casos-de-prueba-c`, `suite-pytest-evidencia`, `imagen-contenedor` y `despliegue-vps`
  ya cubren lo que se reutiliza; C-22 no cambia sus requisitos, sólo los verifica y empaqueta.

## Impact

- **Archivos modificados**: `parcial/README.md`, `despliegue/README.md`, `CHANGES.md` (estado de
  C-22 al cerrar). `parcial/env.example` y `despliegue/env.example` sólo si la revisión detecta un
  valor que no sea placeholder.
- **Archivos nuevos**: `parcial/evidencia/autoevaluacion.md` (entra al zip) y el transcript de la
  corrida limpia en `docs/auditoria-final/` (no entra al zip).
- **Artefacto externo**: `Parcial_Cap1a6_AURA.zip`, guardado fuera del repositorio; nunca se
  versiona.
- **Sin impacto en código**: no se toca `parcial/app/`, `parcial/main.py`, `parcial/migrations/`,
  `parcial/tests/`, `despliegue/app/`, `despliegue/main.py`, la imagen ni el despliegue en línea.
- **Riesgos de corrección**: `.env` presentes en el working tree pero ignorados; historial con
  credenciales; diferencia Python 3.13.2/PostgreSQL 17.11 local contra 3.12/16 pedidos; README con
  pasos no ejecutados. Cada riesgo tiene su verificación y su registro explícito en el diseño.
