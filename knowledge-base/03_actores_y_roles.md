# Actores y Roles

## Actores del Sistema

### Roles Definidos

- **ADMIN**: Administrador del sistema. Permisos completos sobre todos los recursos. Puede gestionar usuarios, roles, ver todo el historial y estadísticas. No tiene restricciones de recurso propio (puede acceder a cualquier entidad).

- **MECANICO**: Mecánico autorizado. Puede crear, actualizar y dar de órdenes de servicio. Tiene acceso restringido a sus propias asignaciones. No puede acceder a recursos de solo lectura de administrador.

- **CLIENTE**: Usuario final del servicio. Puede crear órdenes (propios), consultar el estado de sus órdenes, y ver historial de servicios previos. Está aislado de los recursos de otros clientes.

- **USUARIO**: Sesión activa autenticada. Base para autenticación y autorización. Las exenciones de ruta incluyen `/auth/*` y `/health/*`.

### Jerarquía de Permisos

```
ADMIN > MECANICO > CLIENTE
```

- Las reglas de recurso son estrictas: un cliente solo puede acceder a sus propios vehículos y órdenes.
- Un mecánico solo puede operar en vehículos asignados a su perfil.
- ADMIN puede saltarse restricciones de recurso pero debe respetar la "autoprotección de ADMIN y nunca sin administradores".

### Rutas Públicas (exentas de gating)

- `/auth/*` - Rutas de autenticación (login, cambiar password)
- `/health/*` - Health checks y rutas de módulo health (solo router.py)

### Gating de Rutas Específicas

- `/mis-*` - Solo con sesión activa; dueño estricto; retorna 403 si no es propio.
- `/auth/cambiar-password` - Entrega cookie nueva; la anterior da 401.
- Rate limiting (429 con Retry-After) aplica antes de verificación de credenciales en login.

### Tabla RBAC Resumen

| Recurso | ADMIN | MECANICO | CLIENTE |
|---------|-------|----------|---------|
| Usuarios (CRUD) | ✓ | ✗ | ✗ |
| Órdenes (CRUD) | ✓ | ✓ (propias/asignadas) | ✓ (propias) |
| Vehículos | ✓ | ✓ (asignados) | ✓ (propios) |
| Repuestos/Stock | ✓ | ✗ | ✗ |
| Reportes/estadísticas | ✓ | ✗ | ✗ |