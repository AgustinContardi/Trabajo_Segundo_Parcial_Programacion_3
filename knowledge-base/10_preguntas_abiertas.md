# Preguntas Abiertas

## Inconsistencias Detectadas y Dudas

### P-01: Implementación exacta del trigger `solo-agregado`
- **Pregunta**: El trigger `solo-agregado` que bloquea UPDATE y DELETE en `users`, `vehicles`, `repuestos` - ¿cómo se determina qué registros son "solo-agregados"? ¿Se basa en una columna de marca de tiempo, un flag `eliminado`, o un patrón de nombres?
- **Impacto**: Define la implementación exacta de los triggers y las pruebas de validación.
- **Prioridad**: Alta - afecta la integridad de los datos.

### P-02: Alcance del rate limiting en endpoints adicionales
- **Pregunta**: El rate limit (`LOGIN_MAX_INTENTOS`, `LOGIN_VENTANA_SEG`) ¿solo aplica al endpoint `/login` o también a otros endpoints de autenticación como `/auth/cambiar-password` o registro de usuarios?
- **Impacto**: Comportamiento de seguridad consistente o necesario implementar capas adicionales.
- **Prioridad**: Media.

### P-03: Manejo de `JWT_SECRET` en entornos de desarrollo vs producción
- **Pregunta**: ¿Cómo se maneja `JWT_SECRET` en entornos donde no hay variables de entorno configuradas (ej. desarrollo local)? ¿Se usa un secreto por defecto o la aplicación falla rotundamente?
- **Impacto**: Experience del desarrollador en setup inicial.
- **Prioridad**: Media - pero la regla RN-10 dice "sin default, la app no arranca si falta".

### P-04: Comportamiento ante `null` explícito en PATCH
- **Pregunta**: En las actualizaciones PATCH, cuándo un campo se envía con valor `null` explícito vs. no enviarse: ambos comportamientos setean el campo a NULL o uno sobreescribe y el otro no?
- **Impacto**: Comportimiento de actualizaciones parciales y validación de schemas Pydantic.
- **Prioridad**: Alta - define cómo funcionan las actualizaciones parciales.

### P-05: Definición exacta de "repuestos repetidos" en una orden
- **Pregunta**: ¿Qué cuenta como "repuesto repetido" en una orden? ¿El mismo `repuesto_id` aparezca dos veces en los ítems, o mismo nombre de repuesto, o configuración diferente (mismo nombre pero referencias diferentes)?
- **Impacto**: Validación RN-08 al crear órdenes.
- **Prioridad**: Alta - regla de negocio crítica.

### P-06: Estructura exacta del historial de precios
- **Pregunta**: El `historial_precios` - ¿cada entrada registra el `precio_anterior` exacto antes del cambio, o es un registro simple de `precio_nuevo` con timestamp? ¿Quién (`user_id`) registra los cambios: solo admin o también mecánico?
- **Impacto**: Implementación del modelo y triggers.
- **Prioridad**: Media.

### P-07: Comportamiento de `downgrade base` en migraciones
- **Pregunta**: `alembic downgrade base` / `upgrade head` - ¿qué pasa si hay datos en la base que contradicen el downgrade? ¿Se pierde data o se bloquea la operación?
- **Impacto**: Operaciones de rollback en deployments.
- **Prioridad**: Baja - escenario poco usual en el TP.

### P-08: Validación de `patente` formát o
- **Pregunta**: El formato de `patente` de vehículos - ¿hay una expresión regular o patrón definido, o se valida solo que no esté vacía y sea única? El CHECK de dominio ¿es sobre el formato o sobre el rango de años?
- **Impacto**: Validación de entrada y migraciones.
- **Prioridad**: Media.

### P-09: Manejo de órdenes con cero ítems
- **Pregunta**: ¿Se permite crear una orden con cero ítems (válido temporalmente antes de agregar ítems) o la validación RN-08 obliga como mínimo un ítem al crear?
- **Impacto**: Flujo de creación de órdenes y validación frontend/backend.
- **Prioridad**: Alta.

### P-10: Exención de rutas `/mis-*` en rate limiting
- **Pregunta**: Las rutas `/mis-*` exentas de rate limiting (para que el usuario pueda ver su propio historial sin bloqueos) o están sujetas al mismo límite que cualquier otra ruta?
- **Impacto**: Experiencia de usuario al consultar propios datos.
- **Prioridad**: Baja.

### P-11: Campo `total` en paginación con filtros de búsqueda
- **Pregunta**: Cuando hay parámetros de búsqueda (`q`), el `total` computado ¿usa COUNT con los mismos WHERE que la query de items o es una query separada? ¿Y si los filtros cambian levemente entre count y data?
- **Impacto**: Consistencia de datos mostrados en paginación.
- **Prioridad**: Alta - RN-19 exige que total use los mismos filtros.

### P-12: Mécanismo de `asignacion_rol` inicial
- **Pregunta**: ¿Cómo se inicializa la tabla `asignacion_rol` al crear un nuevo usuario? ¿Es automático al crear el usuario, o debe hacerse explícitamente mediante un endpoint o migration?
- **Impacto**: Onboarding de nuevos usuarios y seed data.
- **Prioridad**: Media.

### P-13: Comportamiento ante vehículo dado de baja con órdenes históricas
- **Pregunta**: Si un vehículo fue dado de baja anteriormente, ¿puede consultarse su historial de órdenes o se oculta completamente? ¿Las órdenes antiguas mantienen la referencia o se setea `vehicle_id` a NULL?
- **Impacto**: Lógica de borrado lógico y consultas históricas.
- **Prioridad**: Baja.

### P-14: Formato de respuesta `debe_cambiar_password`
- **Pregunta**: El campo `debe_cambiar_password` en la respuesta de login - ¿está en el nivel superior del objeto JSON o anidado? ¿Es un boolean o un string con mensaje?
- **Impacto**: Implementación en el frontend y consumo de la API.
- **Prioridad**: Alta - RN-06/checklist menciona esto en autenticación.

### P-15: Migración manual vs autogenerada - línea de separación
- **Pregunta**: Qué exactamente se considera "cambio a mano" en las migraciones vs. qué genera Alembic automáticamente. ¿Hay una guía o convención para delimitar esto?
- **Impacto**: Cumplimiento de RN-06 y mantenimiento de migraciones.
- **Prioridad**: Media.

## Priorización

### Prioridad Alta (definir pronto)
1. P-01: Trigger `solo-agregado` - determinación de "solo-agregado"
2. P-04: Comportamiento `null` en PATCH
3. P-05: "Repuestos repetidos" en órdenes
4. P-09: Órdenes con cero ítems
5. P-11: `total` con filtros de búsqueda
6. P-14: Formato `debe_cambiar_password`

### Prioridad Media (definir cuando haya tiempo)
7. P-02: Rate limiting en endpoints adicionales
8. P-03: JWT_SECRET en desarrollo
9. P-06: Estructura exacta historial_precios
10. P-07: `downgrade` comportamiento
11. P-08: Formato de patente
12. P-10: `/mis-*` y rate limiting
13. P-12: `asignacion_rol` inicial
14. P-15: Migración manual vs autogenerada

### Prioridad Baja (definir si es necesario)
13. P-03 (ya listada en alta) - redundancia
15. Otros escenarios edge case