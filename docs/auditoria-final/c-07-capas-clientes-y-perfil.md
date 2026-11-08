# Auditoría — C-07 capas-clientes-y-perfil

- **Fecha**: 2026-11-08
- **Auditor**: agente auditor (solo lectura; sin pytest, sin uvicorn, sin escrituras en la base)
- **Método**: lectura de código, `SELECT` vía `psql` (information_schema/pg_constraint) y
  verificación runtime con `from main import app` + `httpx.ASGITransport` + cookies JWT firmadas
  con el `JWT_SECRET` local (sin pasar por login, para no escribir `intento_acceso`).
- **Base verificada**: PostgreSQL local, seed con admin/vendedor/ana activos y roles vigentes;
  clientes: 1 Lucía (con perfil, sin usuario), 2 Tomás (sin perfil), 3 Ana Paz (`usuario_id=4`).
- **Contexto de cierre**: C-07 quedó archivado; el cableado de autorización (401/403 de
  `GET /clientes/{id}/ventas`) lo completó C-13, tal como documenta CHANGES.md `### [C-07]`.

## Veredicto

**PASS** (sin FAIL; 1 WARN menor).

## Tabla por ítem

| Ítem (CHECKLIST_ENTREGA.md) | Resultado | Evidencia |
|---|---|---|
| §6 — `GET /clientes/1/ventas` sin cookie → **401** | PASS | ASGITransport: `401 {"detail":"No autenticado"}`. Token inválido → 401 también. |
| §6 — cookie CLIENTE (ana@example.com) → **403** | PASS | ASGITransport: `403 {"detail":"No autorizado"}`; `requiere_rol("VENDEDOR","ADMIN")` montado en la ruta (`_solo_personal`). |
| §6 — VENDEDOR y ADMIN → **200** con envoltorio | PASS | Ambos `200` con `{items,total,page,size,pages}`; total=1, items=[venta 1] con `ClienteRef` correcto. |
| §6 — `requiere_rol` consulta `asignacion_rol` por petición (RN-04) | PASS | `dependencies.py`: `get_sesion_actual` relee `roles_vigentes` vía `UsuarioRepository`; compara solo `roles_db`, nunca el claim. |
| §6 — el servicio recibe la identidad actual | PASS | `service.ventas_de(..., actual=sesion)` recibe `IdentidadActual`; guard `_es_cliente_solo` como defensa en profundidad (documentado). |
| §4 — `cliente.usuario_id` nulo permitido y `UNIQUE` | PASS | psql: `is_nullable=YES`; `uq_cliente_usuario_id UNIQUE (usuario_id)`; seed con 3 clientes sin usuario coexistiendo. |
| §4 — `Cliente.usuario` objeto con navegación en los dos extremos | PASS | `clientes/models.py`: `usuario = Relationship(back_populates="cliente")`; `usuarios/models.py:51`: `cliente = Relationship(back_populates="usuario")`. |
| §4 — `perfil_cliente.cliente_id` FK `UNIQUE` 1—1 | PASS | psql: `uq_perfil_cliente_cliente_id UNIQUE (cliente_id)` + FK a `cliente(id)`. |
| §1 — módulo `clientes` con las seis capas | PASS | `models, schemas, repository, unit_of_work, service, router` presentes; `PerfilCliente` declarado en `clientes/models.py`. |
| §7 — `BaseRepository`/UoW base: commit en `__aexit__`, rollback con excepción, no cierra sesión | PASS | `core/unit_of_work.py`: `commit()` si no hay excepción, `rollback()` si hay, `return False`, no `close()`. |
| §7 — repositorios sin `commit()` (solo `flush()`) | PASS | `grep "commit("` sobre `app/core/repository.py` y `app/modules/*/repository.py`: vacío. |
| §7 — UoW del módulo compone su repositorio con la misma sesión | PASS | `ClientesUnitOfWork(session)` pasa la misma `session` a `ClienteRepository`. |
| §7 — servicio sin `AsyncSession` ni `UnitOfWork(` | PASS | `grep` en `app/modules/clientes/service.py`: vacío. (En `usuarios/service.py` aparece `AsyncSession` solo en `registrar_intento_acceso`, sesión/transacción propias, ítem propio del checklist §7 con su comentario documentado — fuera del scope de C-07.) |
| §7 — router construye el UoW y lo pasa; sin `commit()`/`rollback()` | PASS | `router.py`: `Depends(get_clientes_uow)`; servicio abre con `async with`. |
| §7 — dependencias de identidad/rol y UoW comparten la misma sesión | PASS | `get_sesion_actual` y `get_clientes_uow` dependen ambas de `get_session`; cache de `Depends` por petición → una conexión. |
| §7 — precarga solo en `repository.py` (CV-03) | PASS | `selectinload(Cliente.perfil/usuario)` declarada dentro de `ClienteRepository.get_by_id`; `grep selectinload/joinedload` en `service.py`/`router.py` del módulo: vacío. |
| §9 — envoltorio `{items,total,page,size,pages}` | PASS | Runtime: todas las respuestas 200 lo devuelven. |
| §9 — `page` desde 1; `size` 1..100, default **20** | PASS | Runtime: sin `size` → `size: 20`; `size=1` → `200`; `size=500` → `422`. |
| §9 — página más allá de la última → **422** con mensaje propio | PASS | Runtime: `page=99` → `422 {"detail":"La página 99 no existe: hay 1"}`. |
| §9 — `total` con los mismos filtros; 0 resultados → `pages: 1` | PASS (estructural) | `paginar()` cuenta sobre `select(count()).select_from(stmt.subquery())` con el mismo `WHERE`; `pages = max(1, ceil(total/size))`. |
| §9 — errores sin texto interno de la base | PASS | 404/403/422 con mensajes propios (`"Cliente no encontrado"`, `"No autorizado"`, mensaje de página). |
| Spec — `GET /clientes/{id}` 200 con/sin perfil; 404 inexistente | PASS | Runtime: cliente 1 con `perfil: {...}`, cliente 2 con `perfil: null`; `999999999` → `404`. |
| Tasks 1.x — sin cambios de esquema ni migraciones nuevas | PASS | `models.py` intacto (contratos ya presentes por C-03); auditoría no detectó versiones nuevas (no re-ejecutado `alembic check`, fuera de las herramientas permitidas). |

## WARN

1. **`ClienteRepository.ventas_de` no aplica `ORDER BY`.** `select(Venta).where(cliente_id==...)`
   se pagina sin orden determinista. El design D-6 preveía «ordena por id (o fecha)» y el
   código no lo implementó. Sin ítem del checklist que lo exija explícitamente y sin fallo
   observable con 1 venta, queda como WARN menor: recomendado `order_by(Venta.id)` para
   paginación estable.

## Notas de alcance

- No se auditaron aquí rutas de escritura (`POST/PATCH /clientes`, `POST .../perfil`) porque
  la regla de solo lectura del auditor prohíbe INSERT/UPDATE/DELETE; su implementación se
  verificó por lectura de código (UoW, `flush()`, traducción de `IntegrityError`, `exclude_unset`,
  `extra="forbid"` en schemas) y coincide con las specs del change.
- El cierre de autorización (401/403 de la ruta de ventas) es de C-13; C-07 lo dejó documentado
  y C-13 lo cableó sin cambiar la firma del servicio, coherente con proposal/tasks/CHANGES.md.
