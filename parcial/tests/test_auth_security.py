import asyncio
import threading
import time

import pytest

from app.core import security


@pytest.mark.asyncio
async def test_verify_password_runs_bcrypt_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    loop_thread = threading.get_ident()
    worker_threads: list[int] = []

    def fake_checkpw(password: bytes, hashed: bytes) -> bool:
        worker_threads.append(threading.get_ident())
        return password == b"correct" and hashed == b"stored-hash"

    monkeypatch.setattr(security.bcrypt, "checkpw", fake_checkpw)

    result = await security.verify_password(
        "correct", "stored-hash", asyncio.Semaphore(1)
    )

    assert result is True
    assert worker_threads and all(thread_id != loop_thread for thread_id in worker_threads)


@pytest.mark.asyncio
async def test_bcrypt_concurrency_never_exceeds_shared_semaphore(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = 0
    maximum_active = 0
    lock = threading.Lock()

    def fake_checkpw(password: bytes, hashed: bytes) -> bool:
        nonlocal active, maximum_active
        with lock:
            active += 1
            maximum_active = max(maximum_active, active)
        time.sleep(0.03)
        with lock:
            active -= 1
        return True

    monkeypatch.setattr(security.bcrypt, "checkpw", fake_checkpw)
    semaphore = asyncio.Semaphore(2)

    results = await asyncio.gather(
        *(
            security.verify_password("password", "stored-hash", semaphore)
            for _ in range(6)
        )
    )

    assert results == [True] * 6
    assert maximum_active == 2


@pytest.mark.asyncio
async def test_hash_password_runs_bcrypt_off_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    loop_thread = threading.get_ident()
    worker_threads: list[int] = []

    def fake_hashpw(password: bytes, salt: bytes) -> bytes:
        worker_threads.append(threading.get_ident())
        assert password == b"password"
        return b"generated-hash"

    monkeypatch.setattr(security.bcrypt, "hashpw", fake_hashpw)
    monkeypatch.setattr(security.bcrypt, "gensalt", lambda rounds: b"salt")

    result = await security.hash_password(
        "password", rounds=4, semaphore=asyncio.Semaphore(1)
    )

    assert result == "generated-hash"
    assert worker_threads and all(thread_id != loop_thread for thread_id in worker_threads)


@pytest.mark.asyncio
async def test_password_over_72_bytes_is_rejected_before_bcrypt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called = False

    def fake_checkpw(password: bytes, hashed: bytes) -> bool:
        nonlocal called
        called = True
        return True

    monkeypatch.setattr(security.bcrypt, "checkpw", fake_checkpw)

    with pytest.raises(ValueError, match="72 bytes"):
        await security.verify_password("ñ" * 37, "stored-hash", asyncio.Semaphore(1))

    assert called is False


@pytest.mark.asyncio
async def test_password_at_72_bytes_hashes_and_verifies() -> None:
    semaphore = asyncio.Semaphore(1)
    password = "a" * 72

    password_hash = await security.hash_password(
        password, rounds=4, semaphore=semaphore
    )

    assert await security.verify_password(password, password_hash, semaphore) is True
    assert await security.verify_password("different", password_hash, semaphore) is False
