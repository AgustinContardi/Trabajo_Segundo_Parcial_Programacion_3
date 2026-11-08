"""Pruebas sin base de datos del contrato de datos de `seed.py` (C-17).

El módulo `seed` se importa sin `.env`: no debe llamar `get_settings()` ni
abrir conexiones al importar. Estos casos fijan los datos del PDF/TP que la
carga real debe producir: usuarios y roles, catálogo, clientes, venta 1,
movimientos de stock y la línea de auditoría.
"""

import re
from decimal import Decimal
from types import SimpleNamespace

import pytest

import seed
from seed import (
    ACCION_SEED,
    AUTORES,
    AUTORIAS,
    CLIENTES,
    CONTEOS_ESPERADOS,
    EDITORIALES,
    GENEROS,
    LIBROS,
    PASSWORDS,
    RENGLONES_VENTA,
    TABLAS_DOMINIO,
    USUARIOS,
    sentencia_truncate,
    stock_final,
    total_venta,
)
from app.modules.autores.repository import AutorRepository
from app.modules.clientes.repository import ClienteRepository
from app.modules.editoriales.repository import EditorialRepository
from app.modules.generos.repository import GeneroRepository
from app.modules.libros.repository import LibroRepository
from app.modules.usuarios.repository import (
    AsignacionRolRepository,
    EventoSeguridadRepository,
    UsuarioRepository,
)
from app.modules.ventas.repository import RenglonVentaRepository, VentaRepository

ROLES_VALIDOS = {"ADMIN", "VENDEDOR", "CLIENTE"}
EMAILS = [
    "admin@example.com",
    "admin2@example.com",
    "vendedor@example.com",
    "ana@example.com",
    "nuevo@example.com",
]


def _usuario(email: str) -> dict:
    return next(u for u in USUARIOS if u["email"] == email)


def _precio_de(titulo: str) -> Decimal:
    return next(libro["precio"] for libro in LIBROS if libro["titulo"] == titulo)


def _unidades_vendidas(titulo: str) -> int:
    return sum(
        renglon["cantidad"]
        for renglon in RENGLONES_VENTA
        if renglon["libro"] == titulo
    )


# --- Usuarios y roles -------------------------------------------------------


def test_cinco_usuarios_en_el_orden_del_contrato() -> None:
    assert [u["email"] for u in USUARIOS] == EMAILS
    assert all(u["nombre"].strip() for u in USUARIOS)


def test_roles_de_los_cinco_usuarios() -> None:
    roles = {u["email"]: u["rol"] for u in USUARIOS}
    assert roles == {
        "admin@example.com": "ADMIN",
        "admin2@example.com": "ADMIN",
        "vendedor@example.com": "VENDEDOR",
        "ana@example.com": "CLIENTE",
        "nuevo@example.com": "VENDEDOR",
    }
    assert set(roles.values()) <= ROLES_VALIDOS


def test_solo_nuevo_debe_cambiar_password() -> None:
    assert {u["email"]: u["debe_cambiar_password"] for u in USUARIOS} == {
        "admin@example.com": False,
        "admin2@example.com": False,
        "vendedor@example.com": False,
        "ana@example.com": False,
        "nuevo@example.com": True,
    }


def test_contrasenas_ficticias_cubren_los_cinco_usuarios_y_caben_en_bcrypt() -> None:
    assert PASSWORDS == {
        "admin@example.com": "admin-ficticia-2024",
        "admin2@example.com": "admin2-ficticia-2024",
        "vendedor@example.com": "vendedor-ficticia-2024",
        "ana@example.com": "ana-ficticia-2024",
        "nuevo@example.com": "nuevo-ficticia-2024",
    }
    assert set(PASSWORDS) == {u["email"] for u in USUARIOS}
    for password in PASSWORDS.values():
        assert isinstance(password, str) and password
        assert len(password.encode("utf-8")) <= 72


# --- Catálogo ---------------------------------------------------------------


def test_conteos_del_catalogo() -> None:
    assert len(EDITORIALES) == 3
    assert len(GENEROS) == 3
    assert len(AUTORES) == 6
    assert len(LIBROS) == 5


def test_autores_del_tp_todos_argentinos() -> None:
    assert [autor["nombre"] for autor in AUTORES] == [
        "Julio Cortázar",
        "Jorge Luis Borges",
        "Adolfo Bioy Casares",
        "Silvina Ocampo",
        "Ricardo Piglia",
        "César Aira",
    ]
    assert {autor["nacionalidad"] for autor in AUTORES} == {"Argentina"}


def test_libros_en_orden_de_ids_con_su_stock_final() -> None:
    assert [libro["titulo"] for libro in LIBROS] == [
        "Rayuela",
        "Antología de la literatura fantástica",
        "Ficciones",
        "Respiración artificial",
        "Bestiario",
    ]
    assert [stock_final(libro) for libro in LIBROS] == [10, 5, 8, 3, 1]


def test_precios_del_pdf() -> None:
    assert [_precio_de("Rayuela"), _precio_de("Antología de la literatura fantástica"), _precio_de("Ficciones")] == [
        Decimal("25000.00"),
        Decimal("30000.00"),
        Decimal("22000.00"),
    ]


def test_stock_inicial_por_libro_en_orden() -> None:
    assert [libro["stock_inicial"] for libro in LIBROS] == [11, 5, 10, 3, 1]


def test_stock_inicial_positivo_y_suficiente_para_la_venta() -> None:
    for libro in LIBROS:
        assert libro["stock_inicial"] > 0
        assert libro["stock_inicial"] >= _unidades_vendidas(libro["titulo"])
        assert stock_final(libro) == libro["stock_inicial"] - _unidades_vendidas(
            libro["titulo"]
        )


def test_isbn_unicos() -> None:
    isbnes = [libro["isbn"] for libro in LIBROS]
    assert len(isbnes) == len(set(isbnes))
    assert all(isbn.strip() for isbn in isbnes)


def test_cada_libro_tiene_autorias_validas() -> None:
    for libro in LIBROS:
        autorias = [
            autoria for autoria in AUTORIAS if autoria["libro"] == libro["titulo"]
        ]
        assert autorias
        assert all(a["rol"] in {"autor", "coautor", "traductor", "ilustrador"} for a in autorias)
        assert all(a["orden"] >= 1 for a in autorias)


# --- Clientes ---------------------------------------------------------------


def test_clientes_del_contrato() -> None:
    assert [c["nombre"] for c in CLIENTES] == [
        "Lucía Fernández",
        "Tomás Ríos",
        "Ana Paz",
    ]
    assert [c["email"] for c in CLIENTES] == [
        "lucia@example.com",
        "tomas@example.com",
        "ana@example.com",
    ]


def test_lucia_con_perfil_sin_usuario() -> None:
    lucia = CLIENTES[0]
    assert lucia["usuario_email"] is None
    assert lucia["perfil"] == {"telefono": "111", "direccion": "Calle 1"}


def test_tomas_sin_usuario_y_sin_perfil() -> None:
    tomas = CLIENTES[1]
    assert tomas["usuario_email"] is None
    assert tomas["perfil"] is None


def test_ana_ligada_al_usuario_ana() -> None:
    ana = CLIENTES[2]
    assert ana["usuario_email"] == "ana@example.com"


# --- Venta 1 ----------------------------------------------------------------


def test_total_de_la_venta_calculado_con_los_precios_del_catalogo() -> None:
    esperado = sum(
        (renglon["cantidad"] * _precio_de(renglon["libro"]) for renglon in RENGLONES_VENTA),
        Decimal("0.00"),
    )
    assert total_venta() == Decimal("69000.00")
    assert total_venta() == esperado


def test_renglones_uno_rayuela_y_dos_ficciones() -> None:
    assert [(r["libro"], r["cantidad"]) for r in RENGLONES_VENTA] == [
        ("Rayuela", 1),
        ("Ficciones", 2),
    ]


# --- Evento y limpieza ------------------------------------------------------


def test_accion_del_evento_de_seguridad() -> None:
    assert ACCION_SEED == "Carga de los datos iniciales"


def test_tablas_de_dominio_sin_alembic_version() -> None:
    assert len(TABLAS_DOMINIO) == 14
    assert set(TABLAS_DOMINIO) == {
        "usuario",
        "asignacion_rol",
        "intento_acceso",
        "evento_seguridad",
        "editorial",
        "genero",
        "autor",
        "libro",
        "libro_autor",
        "cliente",
        "perfil_cliente",
        "venta",
        "renglon_venta",
        "movimiento_stock",
    }
    assert "alembic_version" not in TABLAS_DOMINIO


def test_conteos_esperados_cubren_doce_tablas_y_siete_movimientos() -> None:
    assert len(CONTEOS_ESPERADOS) == 12
    assert set(CONTEOS_ESPERADOS) <= set(TABLAS_DOMINIO)
    assert "intento_acceso" not in CONTEOS_ESPERADOS
    assert CONTEOS_ESPERADOS["movimiento_stock"] == len(LIBROS) + len(RENGLONES_VENTA)


def test_sentencia_truncate_enumera_las_catorce_tablas() -> None:
    sentencia = sentencia_truncate()
    assert sentencia.startswith("TRUNCATE TABLE")
    assert sentencia.endswith("RESTART IDENTITY CASCADE")
    for tabla in TABLAS_DOMINIO:
        assert tabla in sentencia
    assert "DELETE" not in sentencia.upper()
    assert "alembic_version" not in sentencia


# --- Limpieza y frontera de transacción -------------------------------------


class _SesionQueRegistra:
    """Doble de sesión que sólo anota el SQL ejecutado."""

    def __init__(self) -> None:
        self.sentencias: list[str] = []

    async def execute(self, sentencia: object) -> None:
        self.sentencias.append(str(sentencia))


@pytest.mark.asyncio
async def test_vaciar_ejecuta_un_unico_truncate_sin_delete() -> None:
    session = _SesionQueRegistra()

    await seed.vaciar(session)

    assert session.sentencias == [sentencia_truncate()]
    assert "DELETE" not in session.sentencias[0].upper()
    assert "alembic_version" not in session.sentencias[0]


def test_seed_unit_of_work_compone_los_diez_repositorios_sobre_la_misma_sesion() -> None:
    session = object()
    uow = seed.SeedUnitOfWork(session)

    repositorios = {
        "usuarios": UsuarioRepository,
        "roles": AsignacionRolRepository,
        "eventos": EventoSeguridadRepository,
        "editoriales": EditorialRepository,
        "generos": GeneroRepository,
        "autores": AutorRepository,
        "libros": LibroRepository,
        "clientes": ClienteRepository,
        "ventas": VentaRepository,
        "renglones": RenglonVentaRepository,
    }
    for nombre, clase in repositorios.items():
        repo = getattr(uow, nombre)
        assert isinstance(repo, clase), nombre
        assert repo._session is session, nombre
    assert uow.session is session


# --- Doble del UoW: registra el orden y asigna ids autoincrementales --------


class _DobleRepositorio:
    """`add` genérico: asigna id y anota la creación."""

    def __init__(self, doble: "_DobleSeedUoW", clase: str) -> None:
        self._doble = doble
        self._clase = clase

    async def add(self, entidad: object) -> object:
        entidad.id = self._doble.siguiente_id(self._clase)  # type: ignore[attr-defined]
        self._doble.anotar(self._clase, entidad)
        return entidad


class _DobleRoles:
    def __init__(self, doble: "_DobleSeedUoW") -> None:
        self._doble = doble

    async def abrir(
        self,
        usuario_id: int,
        rol: str,
        *,
        vence_en: object = None,
        otorgada_por: int | None = None,
    ) -> SimpleNamespace:
        asignacion = SimpleNamespace(
            id=self._doble.siguiente_id("asignacion_rol"),
            usuario_id=usuario_id,
            rol=rol,
            vence_en=vence_en,
            revocada_en=None,
            otorgada_por=otorgada_por,
        )
        self._doble.anotar("asignacion_rol", asignacion)
        return asignacion


class _DobleLibros:
    def __init__(self, doble: "_DobleSeedUoW") -> None:
        self._doble = doble

    async def add(self, entidad: object) -> object:
        entidad.id = self._doble.siguiente_id("libro")  # type: ignore[attr-defined]
        self._doble.anotar("libro", entidad, entidad.stock)  # type: ignore[attr-defined]
        return entidad

    async def add_autoria(
        self, libro_id: int, autor_id: int, rol: str, orden: int
    ) -> SimpleNamespace:
        self._doble.anotar("autoria", libro_id, autor_id, rol, orden)
        return SimpleNamespace(
            libro_id=libro_id, autor_id=autor_id, rol=rol, orden=orden
        )

    async def aplicar_movimiento(
        self,
        libro: object,
        cantidad: int,
        motivo: str,
        usuario_id: int,
        venta_id: int | None = None,
    ) -> SimpleNamespace:
        libro.stock += cantidad  # type: ignore[attr-defined]
        self._doble.anotar(
            "movimiento", libro, cantidad, motivo, usuario_id, venta_id
        )
        return SimpleNamespace(
            libro_id=libro.id,  # type: ignore[attr-defined]
            cantidad=cantidad,
            motivo=motivo,
            usuario_id=usuario_id,
            venta_id=venta_id,
        )


class _DobleClientes:
    def __init__(self, doble: "_DobleSeedUoW") -> None:
        self._doble = doble

    async def add(self, entidad: object) -> object:
        entidad.id = self._doble.siguiente_id("cliente")  # type: ignore[attr-defined]
        self._doble.anotar("cliente", entidad)
        return entidad

    async def add_perfil(self, perfil: object) -> object:
        perfil.id = self._doble.siguiente_id("perfil_cliente")  # type: ignore[attr-defined]
        self._doble.anotar("perfil_cliente", perfil)
        return perfil


class _DobleSeedUoW:
    """Doble mínimo del `SeedUnitOfWork` para probar `cargar` sin PostgreSQL."""

    def __init__(self) -> None:
        self.llamadas: list[tuple] = []
        self._ids: dict[str, int] = {}
        self.usuarios = _DobleRepositorio(self, "usuario")
        self.roles = _DobleRoles(self)
        self.eventos = _DobleRepositorio(self, "evento_seguridad")
        self.editoriales = _DobleRepositorio(self, "editorial")
        self.generos = _DobleRepositorio(self, "genero")
        self.autores = _DobleRepositorio(self, "autor")
        self.libros = _DobleLibros(self)
        self.clientes = _DobleClientes(self)
        self.ventas = _DobleRepositorio(self, "venta")
        self.renglones = _DobleRepositorio(self, "renglon_venta")

    def siguiente_id(self, clase: str) -> int:
        self._ids[clase] = self._ids.get(clase, 0) + 1
        return self._ids[clase]

    def anotar(self, *llamada: object) -> None:
        self.llamadas.append(llamada)

    def de(self, nombre: str) -> list[tuple]:
        return [llamada for llamada in self.llamadas if llamada[0] == nombre]


def _hashes_de_prueba() -> dict[str, str]:
    return {email: f"hash-bcrypt-de-{email}" for email in EMAILS}


# --- Carga de datos ---------------------------------------------------------


@pytest.mark.asyncio
async def test_cargar_recibe_los_hashes_y_crea_los_cinco_usuarios() -> None:
    doble = _DobleSeedUoW()
    hashes = _hashes_de_prueba()

    await seed.cargar(doble, hashes)

    usuarios = [llamada[1] for llamada in doble.de("usuario")]
    assert [usuario.email for usuario in usuarios] == EMAILS
    assert [usuario.password_hash for usuario in usuarios] == [
        hashes[email] for email in EMAILS
    ]
    assert all(usuario.activo for usuario in usuarios)
    assert [usuario.debe_cambiar_password for usuario in usuarios] == [
        False,
        False,
        False,
        False,
        True,
    ]
    assert all(usuario.nombre.strip() for usuario in usuarios)


@pytest.mark.asyncio
async def test_cargar_abre_los_cinco_roles_y_el_admin_otorga_los_demas() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    roles = [llamada[1] for llamada in doble.de("asignacion_rol")]
    assert [(r.usuario_id, r.rol) for r in roles] == [
        (1, "ADMIN"),
        (2, "ADMIN"),
        (3, "VENDEDOR"),
        (4, "CLIENTE"),
        (5, "VENDEDOR"),
    ]
    assert all(r.vence_en is None and r.revocada_en is None for r in roles)
    assert [r.otorgada_por for r in roles] == [None, 1, 1, 1, 1]


@pytest.mark.asyncio
async def test_cargar_crea_los_usuarios_antes_de_cualquier_movimiento() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    posiciones = [indice for indice, llamada in enumerate(doble.llamadas) if llamada[0] == "usuario"]
    primera_movimiento = next(
        indice
        for indice, llamada in enumerate(doble.llamadas)
        if llamada[0] == "movimiento"
    )
    assert len(posiciones) == 5
    assert max(posiciones) < primera_movimiento


@pytest.mark.asyncio
async def test_cargar_crea_libros_con_stock_cero_y_catalogo_completo() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    assert [llamada[1].nombre for llamada in doble.de("editorial")] == [
        editorial["nombre"] for editorial in EDITORIALES
    ]
    assert [llamada[1].nombre for llamada in doble.de("genero")] == [
        genero["nombre"] for genero in GENEROS
    ]
    assert [llamada[1].nombre for llamada in doble.de("autor")] == [
        autor["nombre"] for autor in AUTORES
    ]
    libros = [llamada[1] for llamada in doble.de("libro")]
    assert [libro.titulo for libro in libros] == [libro["titulo"] for libro in LIBROS]
    # El doble imita `aplicar_movimiento` (libro.stock += cantidad), así que el
    # stock final debe coincidir con la aritmética del contrato.
    assert [libro.stock for libro in libros] == [
        stock_final(libro) for libro in LIBROS
    ]
    assert [llamada[2] for llamada in doble.de("libro")] == [0, 0, 0, 0, 0]
    assert [
        (libro.isbn, libro.precio, libro.editorial_id, libro.genero_id)
        for libro in libros
    ] == [
        (
            libro["isbn"],
            libro["precio"],
            next(
                indice
                for indice, editorial in enumerate(EDITORIALES, start=1)
                if editorial["nombre"] == libro["editorial"]
            ),
            next(
                indice
                for indice, genero in enumerate(GENEROS, start=1)
                if genero["nombre"] == libro["genero"]
            ),
        )
        for libro in LIBROS
    ]


@pytest.mark.asyncio
async def test_cargar_registra_las_autorias_del_seed_heredado() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    assert [llamada[1:] for llamada in doble.de("autoria")] == [
        (1, 1, "autor", 1),
        (2, 2, "autor", 1),
        (2, 3, "coautor", 2),
        (2, 4, "coautor", 3),
        (3, 2, "autor", 1),
        (4, 5, "autor", 1),
        (5, 1, "autor", 1),
    ]


@pytest.mark.asyncio
async def test_cargar_aplica_el_stock_inicial_por_el_punto_unico() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    movimientos = [
        llamada
        for llamada in doble.de("movimiento")
        if llamada[3] == "Stock inicial"
    ]
    assert [movimiento[2] for movimiento in movimientos] == [11, 5, 10, 3, 1]
    assert [movimiento[1].titulo for movimiento in movimientos] == [
        libro["titulo"] for libro in LIBROS
    ]
    assert all(movimiento[4] == 1 for movimiento in movimientos)  # admin
    assert all(movimiento[5] is None for movimiento in movimientos)


@pytest.mark.asyncio
async def test_cargar_crea_los_clientes_con_su_perfil_y_su_usuario() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    clientes = [llamada[1] for llamada in doble.de("cliente")]
    assert [(c.nombre, c.email, c.usuario_id) for c in clientes] == [
        ("Lucía Fernández", "lucia@example.com", None),
        ("Tomás Ríos", "tomas@example.com", None),
        ("Ana Paz", "ana@example.com", 4),
    ]
    perfiles = [llamada[1] for llamada in doble.de("perfil_cliente")]
    assert len(perfiles) == 1
    assert (perfiles[0].cliente_id, perfiles[0].telefono, perfiles[0].direccion) == (
        1,
        "111",
        "Calle 1",
    )


@pytest.mark.asyncio
async def test_cargar_crea_la_venta_uno_con_total_calculado_y_precios_del_libro() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    ventas = [llamada[1] for llamada in doble.de("venta")]
    assert len(ventas) == 1
    assert ventas[0].id == 1
    assert ventas[0].cliente_id == 1
    assert ventas[0].total == total_venta() == Decimal("69000.00")
    renglones = [llamada[1] for llamada in doble.de("renglon_venta")]
    assert [
        (renglon.venta_id, renglon.libro_id, renglon.cantidad, renglon.precio_unitario)
        for renglon in renglones
    ] == [
        (1, 1, 1, Decimal("25000.00")),
        (1, 3, 2, Decimal("22000.00")),
    ]


@pytest.mark.asyncio
async def test_cargar_aplica_las_salidas_de_la_venta_con_el_vendedor() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    salidas = [
        llamada for llamada in doble.de("movimiento") if llamada[3] == "Venta"
    ]
    assert [(m[2], m[4], m[5]) for m in salidas] == [
        (-1, 3, 1),  # vendedor = id 3, venta = id 1
        (-2, 3, 1),
    ]
    assert [m[1].titulo for m in salidas] == ["Rayuela", "Ficciones"]
    venta_pos = next(
        indice for indice, llamada in enumerate(doble.llamadas) if llamada[0] == "venta"
    )
    primera_salida = next(
        indice
        for indice, llamada in enumerate(doble.llamadas)
        if llamada[0] == "movimiento" and llamada[3] == "Venta"
    )
    assert venta_pos < primera_salida


@pytest.mark.asyncio
async def test_cargar_nunca_aplica_un_movimiento_de_cantidad_cero() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    assert [llamada[2] for llamada in doble.de("movimiento")] == [
        11,
        5,
        10,
        3,
        1,
        -1,
        -2,
    ]
    assert all(llamada[2] != 0 for llamada in doble.de("movimiento"))


@pytest.mark.asyncio
async def test_cargar_escribe_una_sola_linea_de_evento_sistema() -> None:
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    eventos = [llamada[1] for llamada in doble.de("evento_seguridad")]
    assert len(eventos) == 1
    assert eventos[0].actor == "SISTEMA"
    assert eventos[0].accion == ACCION_SEED


@pytest.mark.asyncio
async def test_cargar_no_hashea_ni_lee_configuracion(monkeypatch: pytest.MonkeyPatch) -> None:
    """`cargar` recibe los hashes: no debe tocar bcrypt ni `Settings`."""

    def explota(*args: object, **kwargs: object) -> None:
        raise AssertionError("cargar no debe hashear ni leer configuración")

    monkeypatch.setattr(seed, "hash_password", explota)
    monkeypatch.setattr(seed, "get_settings", explota)
    doble = _DobleSeedUoW()

    await seed.cargar(doble, _hashes_de_prueba())

    assert len(doble.de("usuario")) == 5
    assert len(doble.de("movimiento")) == 7


# --- Verificación final: doble de sesión que despacha según el SQL ----------


class _Resultado:
    def __init__(self, filas: list[tuple]) -> None:
        self._filas = filas

    def all(self) -> list[tuple]:
        return list(self._filas)

    def first(self) -> tuple | None:
        return self._filas[0] if self._filas else None

    def scalar_one(self) -> object:
        return self._filas[0]


class _SesionDeVerificacion:
    """Doble que responde la query del invariante, los conteos y la venta."""

    def __init__(
        self,
        *,
        invariante: list[tuple] | None = None,
        conteos: dict[str, int] | None = None,
        venta: tuple | None = (1, Decimal("69000.00")),
    ) -> None:
        self.invariante = [] if invariante is None else list(invariante)
        self.conteos = (
            dict(CONTEOS_ESPERADOS) if conteos is None else dict(conteos)
        )
        self.venta = venta
        self.consultas: list[str] = []

    async def execute(self, sentencia: object) -> _Resultado:
        sql = str(sentencia)
        self.consultas.append(sql)
        normalizado = sql.lower()
        if "left join movimiento_stock" in normalizado:
            return _Resultado(self.invariante)
        coincidencia = re.search(r"count\(\*\)\s+from\s+(\w+)", normalizado)
        if coincidencia:
            tabla = coincidencia.group(1)
            return _Resultado([self.conteos[tabla]])
        if "from venta" in normalizado:
            return _Resultado([self.venta] if self.venta is not None else [])
        raise AssertionError(f"SQL inesperado para el doble: {sql}")


@pytest.mark.asyncio
async def test_verificar_devuelve_vacio_cuando_todo_cuadra() -> None:
    session = _SesionDeVerificacion()

    problemas = await seed.verificar(session)

    assert problemas == []
    assert len(session.consultas) == 1 + len(CONTEOS_ESPERADOS) + 1
    for tabla in CONTEOS_ESPERADOS:
        assert any(
            f"count(*) from {tabla}" in consulta.lower()
            for consulta in session.consultas
        ), tabla


@pytest.mark.asyncio
async def test_verificar_reporta_el_libro_que_rompe_el_invariante() -> None:
    session = _SesionDeVerificacion(invariante=[(3, 8, 10)])

    problemas = await seed.verificar(session)

    assert len(problemas) == 1
    assert "3" in problemas[0]
    assert "8" in problemas[0]
    assert "10" in problemas[0]


@pytest.mark.asyncio
async def test_verificar_reporta_un_conteo_incorrecto() -> None:
    conteos = dict(CONTEOS_ESPERADOS)
    conteos["libro"] = 4

    problemas = await seed.verificar(_SesionDeVerificacion(conteos=conteos))

    assert len(problemas) == 1
    assert "libro" in problemas[0]
    assert "4" in problemas[0]
    assert "5" in problemas[0]


@pytest.mark.asyncio
async def test_verificar_reporta_venta_con_id_distinto_de_uno() -> None:
    session = _SesionDeVerificacion(venta=(2, Decimal("69000.00")))

    problemas = await seed.verificar(session)

    assert any("id 2" in problema and "id 1" in problema for problema in problemas)


@pytest.mark.asyncio
async def test_verificar_reporta_total_distinto_de_69000() -> None:
    session = _SesionDeVerificacion(venta=(1, Decimal("68999.00")))

    problemas = await seed.verificar(session)

    assert any("69000.00" in problema for problema in problemas)


@pytest.mark.asyncio
async def test_verificar_reporta_venta_inexistente() -> None:
    session = _SesionDeVerificacion(venta=None)

    problemas = await seed.verificar(session)

    assert any("venta" in problema.lower() for problema in problemas)
