# Visión y Objetivos

## Propósito
Sistema de gestión integral para taller mecánico con operaciones de órdenes de servicio, inventario de repuestos, gestión de usuarios y clientes, y autorización por roles. El sistema debe soportar flujos completos desde la creación de una orden hasta el cierre con actualización de stock y historial de precios.

## Objetivos por Actor

- **Administrador**: Supervisión completa del sistema, gestión de usuarios y roles, vista consolidada de todas las órdenes y estadísticas.
- **Mecánico**: Creación y gestión de órdenes de trabajo, actualización de estado de reparaciones, consulta de historial de vehículos y repuestos.
- **Cliente**: Consulta del estado de sus órdenes, historial de servicios previos, capacidad de programar mantenimiento.

## Alcance del Sistema

### Dentro del alcance
- Gestión de clientes y vehículos asociados
- Catálogo y inventario de repuestos con stock en tiempo real
- Sistema de órdenes de servicio con estados PENDIENTE, EN_REPARACIÓN, COMPLETADA
- Autenticación y autorización basada en roles (RBAC)
- Generación de historial de precios y movimientos de stock
- Seed de datos iniciales para despliegues nuevos

### Fuera del alcance
- Integración con pasarelas de pago reales
- Aplicación móvil nativa
- Sistema de puntos de fidelidad
- Integración con ERP externo

## Limitaciones Conocidas
- SQLite no está permitido; debe usarse PostgreSQL versión de la cátedra
- Sin credencialeshardcoded en ningún archivo de configuración
- Migraciones autogestionadas con Alembic, sin edición manual de `alembic.ini` con credenciales