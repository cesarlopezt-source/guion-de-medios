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


def correr(fuentes: list = None, db_path: Path = None, lock_path: Path = None, ahora: datetime = None,
           origen: str = "pc", verificar_enlaces: bool = True, sincronizar=None) -> dict:
    """Una corrida completa. En la PC (origen="pc") usa además el archivo de bloqueo; en la nube solo el de la base.

    `sincronizar` (opcional, ver sincronizacion.py) recibe antes(), despues(meses) y al_final(ok).
    """
    usa_archivo = origen == "pc"
    lock_path = lock_path or ajustes.LOCK_PATH
    if usa_archivo and not adquirir_bloqueo(lock_path):
        log.info("Ya hay una corrida en curso; se cancela esta.")
        return {"ok": False, "motivo": "en_curso"}
    try:
        store.init_db(db_path)
        if sincronizar is not None and not sincronizar.antes():
            log.info("La nube está buscando noticias; se cancela esta corrida.")
            return {"ok": False, "motivo": "en_curso"}
        corrida = store.intentar_iniciar_corrida(origen, db_path)
        if corrida is None:
            if sincronizar is not None:
                sincronizar.al_final(False)
            log.info("Ya hay una corrida abierta en la base; se cancela esta.")
            return {"ok": False, "motivo": "en_curso"}
        nuevos, ok = 0, False
        try:
            resultado = _recolectar_y_guardar(fuentes, db_path, ahora or datetime.now(timezone.utc), origen,
                                              verificar_enlaces, sincronizar)
            nuevos, ok = resultado["nuevos"], True
            return resultado
        finally:
            store.finalizar_corrida(corrida, nuevos, ok, db_path)
            if sincronizar is not None:
                sincronizar.al_final(ok)
    finally:
        if usa_archivo:
            liberar_bloqueo(lock_path)


def _recolectar_y_guardar(fuentes, db_path, ahora, origen, verificar_enlaces, sincronizar) -> dict:
    fuentes = fuentes if fuentes is not None else fuentes_por_defecto()
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
    nuevos = store.guardar_articulos([clasificar(a) for a in articulos], db_path, origen=origen)

    meses = meses_a_reconstruir(ahora)
    for mes, anio in meses:
        # Se reclasifica para que los cambios en config/ (temas, personajes) apliquen a todo el mes.
        del_mes = [clasificar(a) for a in store.obtener_articulos(mes, anio, db_path)]
        store.reemplazar_noticias(mes, anio, construir_noticias(del_mes), db_path)

    if verificar_enlaces:
        pendientes = store.urls_por_verificar(meses[0], ENLACES_POR_CORRIDA, db_path)
        store.guardar_estado_enlaces(link_checker.check_urls(pendientes), db_path)
    if sincronizar is not None:
        sincronizar.despues(meses)
    log.info("Corrida OK (%s): %d nuevos, %d fuentes OK, %d con error", origen, nuevos, fuentes_ok, fuentes_error)
    return {"ok": True, "nuevos": nuevos, "fuentes_ok": fuentes_ok, "fuentes_error": fuentes_error}


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


def _sincronizacion_por_defecto():
    """En la PC, si .env tiene DATABASE_URL, cada corrida se sincroniza con la nube."""
    if ajustes.MODO != "pc" or not ajustes.DATABASE_URL:
        return None
    from sincronizacion import Sincronizacion
    return Sincronizacion()


if __name__ == "__main__":
    _configurar_log()
    try:
        print(correr(sincronizar=_sincronizacion_por_defecto()))
    except Exception:
        log.exception("La corrida falló")
        raise
