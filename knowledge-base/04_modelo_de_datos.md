# Modelo de Datos

## Entidades Principales

### Tabla `users` (autenticación)
- `id`: PK, entero autoincremental
- `email`: VARCHAR(72), UNIQUE, índice único
- `password_hash`: VARCHAR(60), bcrypt hash
- `role`: ENUM ('ADMIN', 'MECANICO', 'CLIENTE')
- `activo`: BOOLEAN, default TRUE
- `ultimo_acceso`: TIMESTAMP
- `password_cambiada_en`: TIMESTAMP, para validación JWT `iat`/`exp`

### Tabla `clientes`
- `id`: PK, entero autoincremental
- `user_id`: FK → users.id (one-to-one, único)
- `nombre`: VARCHAR
- `email`: VARCHAR
- `telefono`: VARCHAR
- `direccion`: TEXT (optional)

### Tabla `vehicles`
- `id`: PK, entero autoincremental
- `cliente_id`: FK → clientes.id
- `marca`: VARCHAR
- `modelo`: VARCHAR
- `agno`: INTEGER, CHECK (agno >= 1900 AND agno <= 2026)
- `patente`: VARCHAR, UNIQUE
- `estado`: ENUM ('activo', 'dado_baja')
- `CHECK`: Validación de que el vehículo no esté dado de baja con órdenes abiertas

### Tabla `repuestos`
- `id`: PK, entero autoincremental
- `nombre`: VARCHAR
- `descripcion`: TEXT (optional)
- `precio_costo`: NUMERIC
- `precio_venta`: NUMERIC, CHECK (> 0)
- `stock`: INTEGER, CHECK (>= 0)
- `stock_minimo`: INTEGER, default 10
- `CHECK`: Precios positivos, stock no negativo

### Tabla `items` (líneas de orden)
- `id`: PK, entero autoincremental
- `orden_id`: FK → orders.id
- `vehicle_id`: FK → vehicles.id (opcional, para asociación)
- `repuesto_id`: FK → repuestos.id (opcional)
- `nombre`: VARCHAR (denormalizado para búsquedas)
- `cantidad`: INTEGER, CHECK (> 0)
- `precio_unitario`: NUMERIC, CHECK (> 0)
- `precio_total`: NUMERIC GENERATED ALWAYS AS (cantidad * precio_unitario) STORED

### Tabla `historial_precios`
- `id`: PK, entero autoincremental
- `repuesto_id`: FK → repuestos.id
- `precio_anterior`: NUMERIC
- `precio_nuevo`: NUMERIC, CHECK (> 0)
- `cambio_tipo`: ENUM ('SISTEMA', 'MANUAL')
- `motivo`: TEXT (optional)
- `usuario_id`: FK → users.id (quien realizó el cambio)
- `fecha`: TIMESTAMP DEFAULT NOW()

### Tabla `asignacion_rol` (relación muchos-a muchos)
- `id`: PK
- `user_id`: FK → users.id
- `role`: ENUM ('ADMIN', 'MECANICO', 'CLIENTE')
- `asignado_en`: TIMESTAMP DEFAULT NOW()

## Relaciones Clave

### Uno-a-Uno: `Usuario` <-> `Cliente`
- `users.id` <-> `clientes.user_id` (UNIQUE)
- Cada usuario tiene exactamente un cliente o ninguno
- La relación es bidireccional con acceso inverso

### Uno-a-Muchos: `Cliente` <-> `Vehículo`
- Un cliente puede tener varios vehículos
- `clientes.id` → `vehicles.cliente_id`
- `ON DELETE`: Restringido si hay órdenes asociadas

### Muchos-a-Uno: `Vehículo` <-> `Items` (orden)
- Un vehículo puede tener varias líneas en órdenes
- `vehicles.id` → `items.vehicle_id`

### Muchos-a-Uno: `Repuesto` <-> `Historial_precios`
- Un repuesto tiene historial de precios a lo largo del tiempo
- `repuestos.id` → `historial_precios.repuesto_id`

### Uno-a-Muchos: `Orden` <-> `Items`
- Una orden tiene varias líneas de items
- `orders.id` → `items.orden_id`
- `ON DELETE CASCADE`: Al borrar orden, sus items también

## Índices y Constrains

### Índices obligatorios (por consigna)
- Índice único en `users.email`
- Índice único en `vehicles.patente`
- **Índice en CADA FK** (verificar con query del Anexo A)
- `UNIQUE` parcial para borrado lógico en `vehicles` (estado + cliente combinado)
- `CHECK` de dominio en `repuestos.precio_venta` (> 0)
- `CHECK` de dominio en `repuestos.stock` (>= 0)
- `CHECK` de dominio en `vehicles.agno` (rango 1900-2026)
- `CHECK` en `items.cantidad` (> 0)
- `CHECK` en `items.precio_unitario` (> 0)

### Trigger `solo-agregado`
- Bloquea UPDATE y DELETE en las tres tablas: `users`, `vehicles`, `repuestos`
- Implementado a nivel de base de datos, no en aplicación
- Impide modificar registros "solo-agregados" (solo se pueden insertar nuevos)

## Seed Data (carga inicial)

### Usuarios (según consigna)
- `admin1`, `admin2`, `mecanico1`, `mecanico2`, `nuevo`
- Credenciales y passwords hasheadas con bcrypt rounds desde Settings

### Catálogo de estados (cargar primero en seed)
- Estados base para clasificación de órdenes y vehículos

### Carga específica
- **Laura**: usuario + dos vehículos
- **Jorge**: sin usuario, un vehículo
- **Filtro** (10), **pastillas** (4), **bujía** (2), **aceite** (20)
- **Orden 1**: PENDIENTE
- **Orden 2**: EN_REPARACION, asignada, con 4 bujías
- Historial de precio: 8000 → 8500, evento SISTEMA

## ERD Conceptual

```
(users)1 ── 1<(cliente) (clientes)
(clientes)1 ── *<(vehicles) (vehicles)
(vehicles)1 ── *<(items) (items_orden)
(repuestos)1 ── *<(historial_precios) (precio_hist)
(repuestos)1 ── *<(items) (items_con_repuesto)
(orders)1 ── *<(items) (items_orden)
```

Todas las flechas tienen restricciones NOT NULL o CHECK según corresponda. Cada FK tiene índice asociado.