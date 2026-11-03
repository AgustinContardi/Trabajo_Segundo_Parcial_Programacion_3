# Reglas de Negocio

## Formato
Todas las reglas están codificadas con el prefijo `RN-XX` donde XX es un número sequencial. Cada regla incluye el contexto de cuándo se aplica y la consecuencia de violarla.

### RN-01: Nombres exactos de tablas y columnas
- **Contexto**: Cada migración y consulta debe usar nombres exactos de la consigna.
- **Consecuencia**: Fallo en migraciones o queries que no coincidan con el esquema definido.

### RN-02: UNIQUE e índices parciales para borrado lógico
- **Contexto**: Cualquier operación sobre `vehicles` o `users` debe considerar los índices parciales para borrado lógico.
- **Consecuencia**: Violación de constraint UNIQUE si se intenta insertar un registro con mismo email/patente de un registro dado de baja.

### RN-03: CHECKs de dominio
- **Contexto**: Año de vehículo, precios, stock, cantidades, total.
- **Consecuencia**: Rechazo 422 si se intenta insertar/actualizar fuera de los rangos definidos.

### RN-04: Navegación uno-a-uno `Usuario.cliente` y su inversa
- **Contexto**: Cada usuario tiene exactamente un cliente y cada cliente pertenece a exactamente un usuario.
- **Consecuencia**: Inconsistencia de datos si se crea un usuario sin cliente o un cliente huérfano.

### RN-05: Índice en cada FK
- **Contexto**: Cada foreign key en el esquema debe tener un índice asociado.
- **Consecuencia**: Performance degradation y posible fallo en validaciones de integridad referencial.

### RN-06: Migración autogenerada con comentario
- **Contexto**: Toda migración generada automáticamente debe tener un comentario indicando qué se revisó y qué se cambió a mano.
- **Consecuencia**: Diff difícil de revisar en revisiones de código.

### RN-07: Trigger `solo-agregado` bloquea UPDATE/DELETE
- **Contexto**: Triggers a nivel de BD bloquean UPDATE y DELETE en `users`, `vehicles`, `repuestos` para registros "solo-agregados".
- **Consecuencia**: La operación falla en BD con error específico si se intenta violar.

### RN-08: Crear orden - restricciones críticas
- **Contexto**: Al crear una nueva orden:
  - Estado inicial debe ser `PENDIENTE`
  - Debe tener al menos un ítem
  - No pueden tener repuestos repetidos en la misma orden
  - El precio debe copiarse del ítem al total calculado
  - Debe inicializarse el historial de precios
- **Consecuencia**: Orden inválida, rechazo 422 o validación de servicio.

### RN-09: Terminar orden - descuento de stock
- **Contexto**: Al marcar una orden como terminada:
  - Descuenta stock de cada repuesto ítem
  - Deja un movimiento por ítem en `historial_stock`
  - Deja una línea de historial en la orden
  - Si falta stock, **nada** queda escrito (transacción completa revertida)
- **Consecuencia**: Stock inconsistente si la validación falla y la transacción no se revierte.

### RN-10: Cancelar orden - permisos y estado
- **Contexto**: Cancelación permitida solo por:
  - El propio cliente
  - Un administrador
  - Un mecánico asignado
- **Requisito previo**: Solo desde estado `PENDIENTE`
- **Consecuencia**: Retorno 403 si no se tiene permiso, o 409 si el estado no es PENDIENTE.

### RN-11: Iniciar orden - solo mecánico
- **Contexto**: Solo un mecánico puede iniciar una orden en PENDIENTE.
- **Consecuencia**: La orden queda asignada al mecánico y el estado pasa de `PENDIENTE` a `EN_REPARACION`.

### RN-12: Stock - único punto de escritura
- **Contexto**: Alta, reposición y terminación son los únicos puntos de escritura de stock.
- **Consecuencia**: Cualquier modificación directa de `repuestos.stock` fuera de estos puntos es rejection.

### RN-13: Precio - historial en misma transacción
- **Contexto**: Cada cambio de precio deja historial en la misma transacción; sin cambio, sin línea.
- **Consecuencia**: Si el precio no cambia, no se crea registro en `historial_precios`.

### RN-14: Vehículo/repuesto dado de baja
- **Contexto**: No se usa en órdenes nuevas; no se da de baja con órdenes abiertas.
- **Consecuencia**: Violación de integridad si se intenta dar de baja un vehículo que tiene órdenes PENDIENTE o EN_REPARACION.

### RN-15: Búsqueda con parámetros ligados
- **Contexto**: Nunca concatenación SQL para búsquedas.
- **Consecuencia**: Vulnerabilidad SQL injection si se usa concatenación en lugar de parámetros ligados.

### RN-16: códigos de respuesta HTTP
- **Contexto**: Orden de códigos: 404 → 403 → 409 → 422, en ese orden.
- **Consecuencia**: Manejo incorrecto de errores si el orden no se sigue.

### RN-17: PATCH parcial - solo modifica lo enviado
- **Contexto**: En actualizaciones PATCH, solo se modifican los campos enviados; `null` explícito según contrato.
- **Consecuencia**: Campos no enviados mantienen su valor anterior; `null` explícito sets the field to null según el schema.

### RN-18: Paginación - estructura y límites
- **Contexto**: `{items,total,page,size,pages}`, `page` desde 1, `size` 1..100 default **20**.
- **Consecuencia**: Página fuera de rango retorna 422; cero resultados retorna una página vacía con `items: []`.

### RN-19: `total` cuenta con los mismos filtros
- **Contexto**: El `total` paginado debe usar los mismos filtros (búsqueda, etc.) que la página de items.
- **Consecuencia**: Total inconsistente si los filtros difieren entre count y data query.

### RN-20: Login - rate limit antes que verificación
- **Contexto**: Primero rate limit (429 con Retry-After), después verificación de credenciales.
- **Misma mensagem y mismo tiempo**: Tanto correo existente como inexistente deben producir el mismo mensaje y mismo tiempo de respuesta (hash ficticio).
- **Consecuencia**: Enumeración de cuentas si se trata distinto.

### RN-21: bcrypt rounds desde Settings
- **Contexto**: `rounds` configurable, `to_thread` + semáforo para operaciones costosas.
- **Consecuencia**: Performance inestable si los rounds son muy altos sin semáforo.

### RN-22: Cookie `access_token` propiedades
- **Contexto**: `HttpOnly`, `SameSite=Lax`, `Max-Age`, `Secure según entorno`.
- **Consecuencia**: Vulnerabilidad XSS o CSRF si las propiedades no se configuran correctamente.

### RN-23: `mis-*` rutas dueño estricto
- **Contexto**: Solo con sesión; dueño estricto; 403 si no es propio.
- **Consecuencia**: Acceso no autorizado a recursos del usuario.

### RN-24: Autoprotección de ADMIN
- **Contexto**: NUNCA sin administradores en el sistema.
- **Consecuencia**: Restricción de que no se puede remover el último admin.

### RN-25: Trigger bloquea UPDATE/DELETE en 3 tablas
- **Contexto**: Mismo trigger RN-07, se extiende a confirmar que las tres tablas afectadas tienen el trigger activo.
- **Consecuencia**: Migración incompleta si no se aplican los triggers en todas las tablas.