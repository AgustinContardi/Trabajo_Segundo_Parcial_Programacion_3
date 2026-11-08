# Auditoría — C-11 seguridad-login-cookie

- **Fecha**: 2026-11-08
- **Auditor**: subagente (auditoría solo-lectura; únicos registros: logins de auditoría vía `POST /auth/login`)
- **Método**: ASGITransport (httpx, sin servidor) + `psql` SELECT + lectura de código
- **Fuentes**: `docs/CHECKLIST_ENTREGA.md` §5/§7/§10, `CHANGES.md` §C-11, `openspec/changes/archive/2026-11-06-c-11-seguridad-login-cookie/`
- **Veredicto**: **PASS**

## Tabla por ítem

| # | Ítem (checklist §5 / §7) | Resultado | Evidencia |
|---|---|---|---|
| 1 | Login 200; token **solo** en cookie, no en body | PASS | `POST /auth/login` admin@example.com → 200, body `{mensaje, debe_cambiar_password, expira_en_segundos}` sin token |
| 2 | `Set-Cookie: access_token` con `HttpOnly`, `SameSite=Lax`, `Max-Age` | PASS | `httponly=true, samesite="lax", max_age="1800", path="/"`; `Secure` configurable (`COOKIE_SECURE=false` en dev, `true` en prod) |
| 3 | `/auth/yo` sin cookie → 401 | PASS | 401 `{"detail":"No autenticado"}` |
| 4 | `/auth/yo` con `Authorization` inventado → 401 (nunca Bearer) | PASS | 401 idéntico; `dependencies.py` lee solo `request.cookies` |
| 5 | Token inválido o vencido → 401 | PASS | cookie `access_token=token-invalido` → 401; token firmado con `exp` en el pasado → 401 |
| 6 | JWT con `sub`, `exp` y roles; `exp` validado por PyJWT | PASS | claims decodificados: `sub="1"`, `exp=iat+1800`, `roles=["ADMIN"]`; `require=["sub","exp"]` |
| 7 | 401 uniforme: contraseña mala vs email inexistente | PASS | mismo body `{"detail":"Credenciales inválidas"}` en ambos; email inexistente verifica contra `HASH_FICTICIO` (mismo costo, anti-enumeración RN-08) |
| 8 | Límite **antes** de verificar; 6.º fallo → 429 + `Retry-After` numérico en ms | PASS | 6 fallos con `audit-c11@example.com` → `[401×5, 429]`; `Retry-After: 59968` (entero decimal, ms); código: `resumen_fallos` precede a `verify_password` |
| 9 | El intento limitado (429) también se registra | PASS | 6 filas en `intento_acceso` para `audit-c11@example.com`, todas `exito=false` (incluye el 6.º) |
| 10 | Login correcto reinicia la cuenta (fallos previos dejan de contar) | PASS (código) | `resumen_fallos` cuenta solo fallos `cuando > último éxito`; no probado en runtime para no ensuciar el rate-limit de usuarios del seed |
| 11 | `intento_acceso` en sesión/transacción propia (DD-05) | PASS (código) | `registrar_intento_acceso` con `sessionmaker` propio + `commit()` propio; sobrevive al 401 de la petición (verificado: las 6 filas existen) |
| 12 | `logout` → 200 y `Set-Cookie` con `Max-Age=0` | PASS | 200 `{mensaje:"Sesión cerrada"}`, cookie `max_age="0"`, `httponly=true`, `samesite="lax"` |
| 13 | bcrypt desde `Settings` + `to_thread` + semáforo; nunca en el event loop | PASS (código) | `BCRYPT_ROUNDS` de Settings; `asyncio.to_thread` + `asyncio.Semaphore(BCRYPT_MAX_CONCURRENCY)` en `security.py` |
| 14 | Campos bcrypt ≤ 72 bytes → 422 (no 500) | PASS | login con contraseña de 73 bytes → 422 `value_error` en `password`, sin fila nueva ni hash |
| 15 | Router solo HTTP; servicio abre el UoW (CV-01) | PASS (código) | `router.py` construye UoW por `Depends`, `service.autenticar` abre `async with uow` |

## Observaciones

- Ningún FAIL ni WARN. Todo lo exigido por la Aceptación de C-11 está implementado y verificado.
- Filas agregadas por esta auditoría (append-only, sin efecto en el resto): 2 éxitos y 1 fallo de `admin@example.com`, 1 fallo de `no-existe-audit@example.com`, 6 fallos de `audit-c11@example.com`.
- Verificaciones por lectura de código (no ejecutadas para no ensuciar el rate-limit del seed): reinicio de conteo tras login OK (ítem 10) y sesión propia de `intento_acceso` — ambas confirmadas en `service.py`/`repository.py`.
- El tiempo de respuesta de los dos 401 (existente vs inexistente) no se midió con cronómetro; el código hace `verify_password` contra el mismo hash ficticio en ambos caminos, lo que garantiza paridad por construcción (RN-08).
