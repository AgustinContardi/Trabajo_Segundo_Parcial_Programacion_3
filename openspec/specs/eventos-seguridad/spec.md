# eventos-seguridad Specification

## Purpose

Consulta paginada del historial de eventos de seguridad para auditoría, con el envoltorio de paginación canónico y acceso restringido a administradores.

## Requirements

### Requirement: Historial de eventos de seguridad paginado

El sistema SHALL exponer `GET /eventos` y responder `200` con el envoltorio canónico `{items, total, page, size, pages}`. Cada ítem SHALL contener `id`, `cuando`, `actor` y `accion`. `page` SHALL tener valor por defecto 1 y `size` valor por defecto 20; `size` SHALL aceptar solo valores entre 1 y 100. El orden SHALL ser del evento más reciente al más antiguo por `cuando` e `id`. La respuesta MUST NOT contener datos de usuario distintos de los que ya están en `actor`.

#### Scenario: Listado con valores por defecto

- **WHEN** un administrador llama `GET /eventos` sin parámetros
- **THEN** la respuesta es `200` con `page = 1`, `size = 20` e `items` ordenados del más reciente al más antiguo

#### Scenario: Paginación explícita

- **WHEN** se llama `GET /eventos?page=2&size=5` con más de cinco eventos registrados
- **THEN** la respuesta es `200` con `page = 2`, `size = 5`, `total` igual a la cantidad de eventos y como máximo cinco ítems

#### Scenario: Sin eventos registrados

- **WHEN** no hay filas en `evento_seguridad`
- **THEN** la respuesta es `200` con `items` vacío, `total = 0`, `page = 1` y `pages = 1`

#### Scenario: Tamaño de página fuera de rango

- **WHEN** se llama `GET /eventos?size=0`, `GET /eventos?size=101` o `GET /eventos?size=500`
- **THEN** la respuesta es `422`

#### Scenario: Página fuera de rango

- **WHEN** se llama `GET /eventos?page=0` o una página mayor que la última disponible
- **THEN** la respuesta es `422`

#### Scenario: Actor del sistema

- **WHEN** el historial incluye una línea escrita sin usuario humano
- **THEN** el ítem correspondiente muestra `actor = "SISTEMA"` sin error

### Requirement: Control de acceso del historial de seguridad

`GET /eventos` SHALL exigir sesión válida y rol `ADMIN` vigente, y SHALL estar dentro del grupo de rutas protegido.

#### Scenario: Sin sesión

- **WHEN** se llama `GET /eventos` sin cookie válida
- **THEN** la respuesta es `401`

#### Scenario: Autenticado sin rol ADMIN

- **WHEN** un usuario con rol vigente `VENDEDOR` o `CLIENTE` llama `GET /eventos`
- **THEN** la respuesta es `403`

#### Scenario: Administrador con cambio de contraseña pendiente

- **WHEN** un usuario con rol `ADMIN` y `debe_cambiar_password = true` llama `GET /eventos`
- **THEN** la respuesta es `403`
