import importlib

import ajustes


def test_data_dir_respeta_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    importlib.reload(ajustes)
    assert ajustes.DB_PATH == tmp_path / "guion.db"
    assert ajustes.LOCK_PATH == tmp_path / "watcher.lock"
    assert ajustes.LOG_DIR.is_dir()


def test_port_por_defecto(monkeypatch):
    monkeypatch.delenv("PORT", raising=False)
    importlib.reload(ajustes)
    assert ajustes.PORT == 5050


def test_limpiar_dsn_quita_comillas_y_pasa_supabase_a_session_pooler():
    from ajustes import limpiar_dsn
    sucio = ' "postgresql://u.x:clave@aws-0-us-east-2.pooler.supabase.com:6543/postgres?pgbouncer=true" '
    assert limpiar_dsn(sucio) == "postgresql://u.x:clave@aws-0-us-east-2.pooler.supabase.com:5432/postgres"
    assert limpiar_dsn("postgresql://h/db?sslmode=require&pgbouncer=true") == "postgresql://h/db?sslmode=require"
    assert limpiar_dsn("postgresql://otro.host:6543/db") == "postgresql://otro.host:6543/db"
    assert limpiar_dsn("") is None and limpiar_dsn(None) is None
