import functools
import os
import tempfile
import types
import uuid
from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "t.db"


@pytest.fixture(scope="session")
def _pg_uri():
    """DSN de Postgres para pruebas: TEST_DATABASE_URL o un Postgres local con pgserver."""
    import ajustes
    if ajustes.TEST_DATABASE_URL:
        return ajustes.TEST_DATABASE_URL
    try:
        import pgserver._commands as cmd
    except ImportError:
        pytest.skip("Sin TEST_DATABASE_URL ni pgserver")
    # initdb escribe la ruta (con tildes) en otra codificación: leer su salida sin fallar.
    cmd.tempfile = types.SimpleNamespace(
        TemporaryFile=functools.partial(tempfile.TemporaryFile, encoding="utf-8", errors="replace"))
    import pgserver
    datos = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "GuionDeMedios" / "pgtest"
    return pgserver.get_server(datos).get_uri()


def pg_esquema_temporal(uri):
    """Crea un esquema aislado y devuelve (dsn, borrar)."""
    import psycopg
    esquema = f"t_{uuid.uuid4().hex[:12]}"
    with psycopg.connect(uri, autocommit=True) as c:
        c.execute(f"CREATE SCHEMA {esquema}")
    sep = "&" if "?" in uri else "?"
    dsn = f"{uri}{sep}options=-csearch_path%3D{esquema}"

    def borrar():
        with psycopg.connect(uri, autocommit=True) as c:
            c.execute(f"DROP SCHEMA {esquema} CASCADE")
    return dsn, borrar


@pytest.fixture
def pg_dsn(request):
    uri = request.getfixturevalue("_pg_uri")
    dsn, borrar = pg_esquema_temporal(uri)
    yield dsn
    borrar()


@pytest.fixture(params=["sqlite", "postgres"])
def motor(request, tmp_path):
    """(módulo de store, destino) para correr el mismo contrato con los dos motores."""
    if request.param == "sqlite":
        from store import sqlite
        return sqlite, tmp_path / "c.db"
    from store import postgres
    return postgres, request.getfixturevalue("pg_dsn")


@pytest.fixture(autouse=True)
def _sin_google(monkeypatch):
    """Las pruebas nunca piden a Google el enlace real; las que lo necesitan reemplazan esta función."""
    from collectors import google_enlaces
    monkeypatch.setattr(google_enlaces, "enlace_real", lambda url, sesion=None: None)
