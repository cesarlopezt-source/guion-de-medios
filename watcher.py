"""Recolecta, clasifica, agrupa y guarda las noticias. Lo corre la tarea programada cada hora."""
import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

import ajustes
import link_checker
import store
from classifier import clasificar
from collectors import recolectar
from config.fuentes import FUENTES, consultas_google_news
from noticias import construir_noticias

log = logging.getLogger("watcher")

MAX_PARALELO = 8
ENLACES_POR_CORRIDA = 300  # verificación de noticias archivadas, por tandas
PRIORIDAD_VIA = {"rss": 0, "web": 1, "google_news": 2}


def _edad_min(lock_path: Path) -> float:
    return (time.time() - lock_path.stat().st_mtime) / 60


def esta_bloqueado(lock_path: Path = None, max_edad_min: int = 50) -> bool:
    lock_path = lock_path or ajustes.LOCK_PATH
    try:
        return _edad_min(lock_path) < max_edad_min
    except FileNotFoundError:
        return False


def adquirir_bloqueo(lock_path: Path, max_edad_min: int = 50) -> bool:
    """Crea el archivo de bloqueo; uno de más de `max_edad_min` se considera abandonado y se reemplaza."""
    if lock_path.exists() and not esta_bloqueado(lock_path, max_edad_min):
        lock_path.unlink(missing_ok=True)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w") as f:
        f.write(f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}")
    return True


def liberar_bloqueo(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def meses_a_reconstruir(ahora: datetime) -> list:
    """Mes actual en hora de El Salvador; los 2 primeros días también el anterior (notas que llegan tarde)."""
    local = ahora.astimezone(ajustes.ZONA_SV)
    meses = [(local.month, local.year)]
    if local.day <= 2:
        meses.append((12, local.year - 1) if local.month == 1 else (local.month - 1, local.year))
    return meses


def fuentes_por_defecto() -> list:
    return [f for f in FUENTES if f["activa"]] + consultas_google_news()


def correr(fuentes: list = None, db_path: Path = None, lock_path: Path = None, ahora: datetime = None) -> dict:
    lock_path = lock_path or ajustes.LOCK_PATH
    if not adquirir_bloqueo(lock_path):
        log.info("Ya hay una corrida en curso; se cancela esta.")
        return {"ok": False, "motivo": "en_curso"}
    try:
        fuentes = fuentes if fuentes is not None else fuentes_por_defecto()
        ahora = ahora or datetime.now(timezone.utc)
        store.init_db(db_path)
        corrida = store.iniciar_corrida(db_path)

        with ThreadPoolExecutor(max_workers=MAX_PARALELO) as ex:
            resultados = list(ex.map(recolectar, fuentes))

        articulos, fuentes_ok, fuentes_error = [], 0, 0
        for fuente, (encontrados, error) in zip(fuentes, resultados):
            ok = error is None and bool(encontrados)
            fuentes_ok += ok
            fuentes_error += not ok
            store.registrar_estado_fuente(fuente, ok, len(encontrados), error, db_path)
            articulos.extend(encontrados)

        # INSERT OR IGNORE conserva el primero: así gana la versión del RSS directo.
        articulos.sort(key=lambda a: PRIORIDAD_VIA[a["via"]])
        nuevos = store.guardar_articulos([clasificar(a) for a in articulos], db_path)

        for mes, anio in meses_a_reconstruir(ahora):
            # Se reclasifica para que los cambios en config/ (temas, personajes) apliquen a todo el mes.
            del_mes = [clasificar(a) for a in store.obtener_articulos(mes, anio, db_path)]
            store.reemplazar_noticias(mes, anio, construir_noticias(del_mes), db_path)

        pendientes = store.urls_por_verificar(meses_a_reconstruir(ahora)[0], ENLACES_POR_CORRIDA, db_path)
        store.guardar_estado_enlaces(link_checker.check_urls(pendientes), db_path)
        store.finalizar_corrida(corrida, nuevos, True, db_path)
        log.info("Corrida OK: %d nuevos, %d fuentes OK, %d con error", nuevos, fuentes_ok, fuentes_error)
        return {"ok": True, "nuevos": nuevos, "fuentes_ok": fuentes_ok, "fuentes_error": fuentes_error}
    finally:
        liberar_bloqueo(lock_path)


def _configurar_log() -> None:
    handler = RotatingFileHandler(ajustes.LOG_DIR / "watcher.log", maxBytes=1_000_000, backupCount=5,
                                  encoding="utf-8")
    handlers = [handler]
    if sys.stderr is not None:  # con pythonw.exe (tarea programada) no hay consola
        handlers.append(logging.StreamHandler())
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    for h in handlers:
        h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        raiz.addHandler(h)


if __name__ == "__main__":
    _configurar_log()
    try:
        print(correr())
    except Exception:
        log.exception("La corrida falló")
        raise
