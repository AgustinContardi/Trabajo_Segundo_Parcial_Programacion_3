"""Cota de concurrencia del hash de registro (C-12, escenario «Concurrencia acotada»).

El registro usa el mismo `bcrypt_sem` del `lifespan`. Este test comprueba que
`hash_password` (la primitiva que llama `service.registrar`) nunca supera el
semáforo compartido y que corre fuera del event loop.
"""

import asyncio
import threading
import time

import pytest

from app.core import security

pytestmark = pytest.mark.asyncio


async def test_hash_de_registros_concurrentes_respeta_el_semaforo(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    activos = 0
    maximo = 0
    hilos: set[int] = set()
    hilo_del_loop = threading.get_ident()
    lock = threading.Lock()

    def fake_hashpw(password: bytes, salt: bytes) -> bytes:
        nonlocal activos, maximo
        with lock:
            activos += 1
            maximo = max(maximo, activos)
            hilos.add(threading.get_ident())
        time.sleep(0.02)
        with lock:
            activos -= 1
        return b"$2b$04$hash-generado"

    monkeypatch.setattr(security.bcrypt, "hashpw", fake_hashpw)
    monkeypatch.setattr(security.bcrypt, "gensalt", lambda rounds: b"salt")
    semaforo = asyncio.Semaphore(2)

    resultados = await asyncio.gather(
        *(
            security.hash_password("clave-segura", rounds=4, semaphore=semaforo)
            for _ in range(6)
        )
    )

    assert resultados == ["$2b$04$hash-generado"] * 6
    assert maximo == 2
    assert hilos and hilo_del_loop not in hilos
