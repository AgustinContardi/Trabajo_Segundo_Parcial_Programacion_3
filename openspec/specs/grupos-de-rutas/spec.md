# grupos-de-rutas Specification

## Purpose

Define los dos grupos de rutas de `main.py` (abierto y protegido), el control de cambio obligatorio montado una sola vez en el router protegido, el comportamiento de `403` cuando `debe_cambiar_password = true`, que las rutas abiertas sigan funcionando, y el repositorio `EventoSeguridadRepository` con `add()` y listado paginado que `C-15` reutiliza.

## Requirements

### Requirement: Dos grupos de rutas en main.py

El sistema SHALL montar en `main.py` un grupo abierto (`/health`, `/auth`, catálogo público) y un grupo protegido (todo lo demás), de modo que el control del cambio obligatorio se aplique solo al protegido.

#### Scenario: main.py tiene dos bloques de include_router

- **WHEN** se inspecciona `main.py`
- **THEN** existen dos agrupamientos de routers: uno abierto sin control de cambio obligatorio y otro protegido con el control montado

### Requirement: Control de cambio obligatorio montado una vez

El sistema SHALL montar la dependencia de cambio obligatorio **una sola vez** a nivel del router protegido, no ruta por ruta, porque FastAPI suma y no resta dependencias y `/auth/cambiar-password` debe quedar exento.

#### Scenario: Una sola dependencia de cambio obligatorio

- **WHEN** se inspecciona la definición del router protegido en `main.py`
- **THEN** el control de `debe_cambiar_password` aparece una única vez, a nivel de router, y no se repite en cada endpoint protegido

### Requirement: Grupo protegido devuelve 403 cuando debe_cambiar_password = true

El sistema SHALL responder `403` a toda petición autenticada con `debe_cambiar_password = true` que apunte a una ruta del grupo protegido, y permitir solo `/auth` y las rutas públicas.

#### Scenario: Ruta protegida con cambio pendiente

- **WHEN** un usuario autenticado con `debe_cambiar_password = true` pide una ruta del grupo protegido
- **THEN** la respuesta es `403` sin ejecutar el handler de negocio

#### Scenario: Rutas de auth y públicas siguen funcionando con cambio pendiente

- **WHEN** un usuario autenticado con `debe_cambiar_password = true` pide `POST /auth/cambiar-password`, `GET /auth/yo` o una ruta pública del catálogo
- **THEN** la respuesta es la del contrato del endpoint (no `403` por el cambio pendiente)

### Requirement: Rutas abiertas exigen sesión cuando corresponde

El sistema SHALL exigir sesión válida (`401` sin cookie o token inválido/vencido) en `GET /auth/yo` y `POST /auth/cambiar-password`, aunque vivan en el grupo abierto.

#### Scenario: GET /auth/yo sin cookie

- **WHEN** se pide `GET /auth/yo` sin cookie válida
- **THEN** la respuesta es `401`

#### Scenario: POST /auth/cambiar-password sin cookie

- **WHEN** se pide `POST /auth/cambiar-password` sin cookie válida
- **THEN** la respuesta es `401`

### Requirement: EventoSeguridadRepository con add y listado paginado

El sistema SHALL proporcionar en el módulo `usuarios` un `EventoSeguridadRepository` con `add()` para escribir una línea en `evento_seguridad` y un listado paginado que devuelva el envoltorio `{items, total, page, size, pages}`, reutilizado por `C-15`.

#### Scenario: Listado paginado de eventos de seguridad

- **WHEN** se consulta el listado de `evento_seguridad` con `page` y `size`
- **THEN** la respuesta tiene `items`, `total`, `page`, `size` y `pages`, con `size` default 20 y rango 1..100

#### Scenario: Cero eventos devuelve página vacía

- **WHEN** no hay filas en `evento_seguridad`
- **THEN** la respuesta tiene `items` vacío, `total = 0` y `pages = 1`
