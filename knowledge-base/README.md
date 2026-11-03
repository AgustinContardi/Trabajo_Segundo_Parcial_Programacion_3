# Librería — Parcial Capítulos 1 a 6 — Base de Conocimiento

Base de conocimiento del parcial de **Programación III** (UNIDAD 1 A 6 · «Del objeto a la
transacción»): la librería del TP de los capítulos 1 a 4, ampliada con acceso por roles (cap. 5),
repositorios + Unit of Work (cap. 6) y el despliegue del TP original en el VPS dentro de un
contenedor.

> Fuente autoritativa: `docs/Parcial_Cap1a6_Consigna.pdf` (24 páginas).
> Fuente secundaria **no autoritativa**: `docs/CHECKLIST_ANTES_DE_ENTREGAR.md`, del que sólo se toman
> convenciones de ingeniería. Cada conflicto entre las dos está resuelto y registrado en
> `10_preguntas_abiertas.md` § 1.

## Índice de archivos

| Archivo | Contenido |
|---|---|
| [01_vision_y_objetivos.md](01_vision_y_objetivos.md) | Propósito, objetivos por actor, los 7 objetivos técnicos, alcance, fuera de alcance (concurrencia y Redis), métricas de éxito |
| [02_descripcion_general.md](02_descripcion_general.md) | Stack con versiones mínimas, arquitectura de capas, API REST completa por grupo, envoltorio de listados |
| [03_actores_y_roles.md](03_actores_y_roles.md) | Visitante / CLIENTE / VENDEDOR / ADMIN / SISTEMA, RBAC tabla completa, 401 vs 403, rutas públicas, los dos grupos de rutas |
| [04_modelo_de_datos.md](04_modelo_de_datos.md) | **ERD completo**, las 13 tablas con columna, tipo, nullabilidad, default, CHECK, UNIQUE, índices parciales y FKs; invariante del stock; seed |
| [05_reglas_de_negocio.md](05_reglas_de_negocio.md) | **RN-01 … RN-16** textuales con su garante, más `CV-NN` (convenciones) y `RD-NN` (propias, «no está en la consigna») |
| [06_funcionalidades.md](06_funcionalidades.md) | 7 épicas, 30+ historias de usuario con criterios de aceptación y trazabilidad a RN y casos |
| [07_flujos_principales.md](07_flujos_principales.md) | 10 flujos end-to-end con **fronteras de transacción** explícitas |
| [08_arquitectura_propuesta.md](08_arquitectura_propuesta.md) | Patrones, árbol de directorios, qué puede cada capa, UoW, Settings, seguridad, health, BackgroundTasks, migraciones, pruebas |
| [09_decisiones_y_supuestos.md](09_decisiones_y_supuestos.md) | 18 decisiones documentadas (`DD`) y 15 supuestos (`SU`) con riesgo y forma de validar |
| [10_preguntas_abiertas.md](10_preguntas_abiertas.md) | 12 conflictos checklist ≠ PDF resueltos, columnas heredadas a confirmar, 11 preguntas abiertas priorizadas |
| [11_despliegue_y_devops.md](11_despliegue_y_devops.md) | Dockerfile, `.dockerignore`, `--env-file`, `HEALTHCHECK`, `DEPLOY.md`, casos D-01…D-08, zip de dos carpetas (18 % de la nota) |

## Quick Start para desarrolladores

1. **Entender el dominio** → [01](01_vision_y_objetivos.md), [03](03_actores_y_roles.md)
2. **Entender los datos** → [04](04_modelo_de_datos.md) (nombres de tablas y columnas **obligatorios**)
3. **Entender las reglas** → [05](05_reglas_de_negocio.md) (RN-01…RN-16 son las que cita la corrección)
4. **Entender la arquitectura** → [02](02_descripcion_general.md), [08](08_arquitectura_propuesta.md)
5. **Implementar** → [07](07_flujos_principales.md), [06](06_funcionalidades.md)
6. **Desplegar** → [11](11_despliegue_y_devops.md)
7. **Antes de codificar o de entregar** → [10](10_preguntas_abiertas.md)

## Resumen ejecutivo

El sistema es la **librería** del TP cap 1-4 con acceso por roles: tres roles (`ADMIN`, `VENDEDOR`,
`CLIENTE`) que viven en `asignacion_rol` con vigencia y revocación (nunca se borran), leídos de la base
**en cada petición**. El stock deja de editarse y pasa a ser un libro mayor: `movimiento_stock`, de
sólo agregado por disparador, con la invariante `libro.stock = SUM(movimiento_stock.cantidad)`. Cada
operación de negocio —auto-registro, venta, alta de personal, cambio de rol— es **una sola
transacción** mediante repositorios + Unit of Work. El despliegue es un proyecto aparte: el TP cap 1-4
en una imagen `python:3.12-alpine` sin root y sin secretos, corriendo en el VPS con `docker run`.

## Convenciones de lectura

| Marca | Significado |
|---|---|
| **RN-NN** | Regla de la consigna. No se renumera ni se redefine. |
| **CV-NN** | Convención de ingeniería (del checklist heredado). No es regla de negocio. |
| **RD-NN** | Regla propia del equipo. **No está en la consigna.** |
| **DD-NN** | Decisión documentada en la consigna. |
| **SU-NN** | Suposición inferida, con riesgo y forma de validar. |
| **IN-NN** | Conflicto entre documentos, ya resuelto (gana el PDF). |
| **AB-NN** | Pregunta realmente abierta. |
| `(heredado TP cap 1-4 — confirmar contra el repo)` | Columna que el PDF no restate: hay que leerla del repositorio del TP anterior. |
