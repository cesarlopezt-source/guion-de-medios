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
