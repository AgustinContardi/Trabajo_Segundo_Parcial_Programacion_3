# Spec Delta — grupos-de-rutas

## MODIFIED Requirements

### Requirement: Dos grupos de rutas en main.py

El sistema SHALL montar en `main.py` un grupo abierto (`/health`, `/auth` y las **lecturas** públicas del catálogo) y un grupo protegido (todo lo demás: clientes, ventas, **las mutaciones de catálogo** y la superficie de administración de usuarios, roles y eventos), de modo que el control del cambio obligatorio se aplique solo al protegido.

#### Scenario: main.py tiene dos bloques de include_router

- **WHEN** se inspecciona `main.py`
- **THEN** existen dos agrupamientos de routers: uno abierto sin control de cambio obligatorio y otro protegido con el control montado

#### Scenario: Las lecturas públicas del catálogo quedan abiertas

- **WHEN** se piden las lecturas públicas de editoriales, géneros, autores y libros sin cookie
- **THEN** la respuesta es la del contrato del endpoint, sin `401`

#### Scenario: Las mutaciones de catálogo quedan protegidas

- **WHEN** se inspecciona `main.py`
- **THEN** el alta, la modificación, la baja, la reposición y el listado de movimientos de libros, y el alta y la modificación de editoriales, géneros y autores, figuran en el grupo protegido; no así sus lecturas

#### Scenario: Mutación de catálogo con cambio de contraseña pendiente

- **WHEN** un usuario autenticado con rol `ADMIN` y `debe_cambiar_password = true` pide una mutación de catálogo (por ejemplo `POST /libros`)
- **THEN** la respuesta es `403` sin ejecutar el handler de negocio, y las lecturas públicas del catálogo siguen respondiendo `200`

#### Scenario: Rutas de administración en el grupo protegido

- **WHEN** un usuario autenticado con `debe_cambiar_password = true` pide `/usuarios/*` o `/eventos`
- **THEN** la respuesta es `403` sin ejecutar el handler de negocio

## ADDED Requirements

### Requirement: La separación no cambia los contratos del catálogo

Mover los routers de administración del catálogo al grupo protegido SHALL NOT cambiar el path, el método, el cuerpo ni la respuesta de ninguna ruta existente; solo SHALL agregar la puerta del cambio obligatorio.

#### Scenario: El contrato de las rutas de catálogo no cambia

- **WHEN** se comparan los paths y métodos del catálogo antes y después de la separación
- **THEN** la lista es idéntica y las únicas diferencias observables son `403` por cambio de contraseña pendiente o por falta de sesión en las mutaciones
