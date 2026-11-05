"""Seed de datos iniciales para el TP cap. 1-4."""

import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.modules.editoriales.models import Editorial
from app.modules.generos.models import Genero
from app.modules.autores.models import Autor
from app.modules.libros.models import Libro, LibroAutor
from app.modules.clientes.models import Cliente, PerfilCliente
from app.modules.ventas.models import Venta, RenglonVenta


async def main():
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        # limpiar
        for model in (RenglonVenta, Venta, LibroAutor, Libro, PerfilCliente, Cliente, Autor, Genero, Editorial):
            await session.execute(model.__table__.delete())
        await session.commit()

        # editoriales
        e1 = Editorial(nombre="Sudamericana", pais="Argentina")
        e2 = Editorial(nombre="Emecé", pais="Argentina")
        e3 = Editorial(nombre="Losada", pais="Argentina")
        session.add_all([e1, e2, e3])
        await session.flush()

        # generos
        g1 = Genero(nombre="Novela")
        g2 = Genero(nombre="Cuentos")
        g3 = Genero(nombre="Poesía")
        session.add_all([g1, g2, g3])
        await session.flush()

        # autores
        a1 = Autor(nombre="Julio Cortázar", nacionalidad="Argentina")
        a2 = Autor(nombre="Jorge Luis Borges", nacionalidad="Argentina")
        a3 = Autor(nombre="Adolfo Bioy Casares", nacionalidad="Argentina")
        a4 = Autor(nombre="Silvina Ocampo", nacionalidad="Argentina")
        a5 = Autor(nombre="Ricardo Piglia", nacionalidad="Argentina")
        a6 = Autor(nombre="César Aira", nacionalidad="Argentina")
        session.add_all([a1, a2, a3, a4, a5, a6])
        await session.flush()

        # libros
        l1 = Libro(isbn="978-950-00-0001-1", titulo="Rayuela", precio=25000.00, stock=10, editorial_id=e1.id, genero_id=g1.id)
        l2 = Libro(isbn="978-950-00-0002-2", titulo="Antología de la literatura fantástica", precio=30000.00, stock=5, editorial_id=e2.id, genero_id=g2.id)
        l3 = Libro(isbn="978-950-00-0003-3", titulo="Ficciones", precio=22000.00, stock=8, editorial_id=e2.id, genero_id=g1.id)
        l4 = Libro(isbn="978-950-00-0004-4", titulo="Respiración artificial", precio=27000.00, stock=3, editorial_id=e3.id, genero_id=g1.id)
        l5 = Libro(isbn="978-950-00-0005-5", titulo="Bestiario", precio=18000.00, stock=1, editorial_id=e1.id, genero_id=g2.id)
        session.add_all([l1, l2, l3, l4, l5])
        await session.flush()

        # autorias
        session.add_all([
            LibroAutor(libro_id=l1.id, autor_id=a1.id, rol="autor", orden=1),
            LibroAutor(libro_id=l2.id, autor_id=a2.id, rol="autor", orden=1),
            LibroAutor(libro_id=l2.id, autor_id=a3.id, rol="coautor", orden=2),
            LibroAutor(libro_id=l2.id, autor_id=a4.id, rol="coautor", orden=3),
            LibroAutor(libro_id=l3.id, autor_id=a2.id, rol="autor", orden=1),
            LibroAutor(libro_id=l4.id, autor_id=a5.id, rol="autor", orden=1),
            LibroAutor(libro_id=l5.id, autor_id=a1.id, rol="autor", orden=1),
        ])
        await session.flush()

        # clientes
        c1 = Cliente(nombre="Lucía Fernández", email="lucia@example.com")
        c2 = Cliente(nombre="Tomás Ríos", email="tomas@example.com")
        session.add_all([c1, c2])
        await session.flush()
        session.add(PerfilCliente(cliente_id=c1.id, telefono="111", direccion="Calle 1"))

        # venta 1
        v1 = Venta(cliente_id=c1.id, total=25000.00 + 2 * 22000.00)
        session.add(v1)
        await session.flush()
        session.add_all([
            RenglonVenta(venta_id=v1.id, libro_id=l1.id, cantidad=1, precio_unitario=25000.00),
            RenglonVenta(venta_id=v1.id, libro_id=l3.id, cantidad=2, precio_unitario=22000.00),
        ])

        await session.commit()
    await engine.dispose()
    print("Seed OK")


if __name__ == "__main__":
    asyncio.run(main())