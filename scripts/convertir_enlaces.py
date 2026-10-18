"""Una vez: pone el enlace real del medio a los artículos de Google News ya guardados en la PC,
reconstruye las noticias de todos los meses y deja marcado que se vuelvan a subir todas a la nube.

Uso: python scripts/convertir_enlaces.py
Se puede cortar y volver a correr: sigue donde quedó.
"""
import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import ajustes  # noqa: E402
import watcher  # noqa: E402
from classifier import clasificar  # noqa: E402
from collectors import google_enlaces  # noqa: E402
from noticias import construir_noticias  # noqa: E402
from store import postgres, sqlite  # noqa: E402

TANDA = 200


def main() -> int:
    sqlite.init_db()
    nube = bool(ajustes.DATABASE_URL)
    if nube:
        try:
            postgres.init_db()
        except Exception as e:  # noqa: BLE001
            print(f"  (nube no disponible: {e})")
            nube = False
    intentadas = set()  # las que fallaron por red no se repiten en esta corrida
    while pendientes := [u for u in sqlite.urls_sin_enlace(100_000) if u not in intentadas][:TANDA]:
        if google_enlaces.en_pausa():
            print("Google pidió esperar (429); se reintenta en 5 minutos…", flush=True)
            time.sleep(300)
            continue
        enlaces = watcher.resolver_enlaces(pendientes, max_paralelo=2)
        intentadas.update(u for u in pendientes if u in enlaces or not google_enlaces.en_pausa())
        sqlite.poner_enlaces(enlaces)
        if nube:  # los artículos del mes actual y el anterior también están en la nube
            try:
                postgres.poner_enlaces({u: e for u, e in enlaces.items() if e})
            except Exception as e:  # noqa: BLE001
                print(f"  (nube no disponible: {e})")
        print(f"{len(intentadas)} revisados · tanda: {sum(1 for e in enlaces.values() if e)} convertidos, "
              f"{sum(1 for e in enlaces.values() if not e)} sin enlace, {len(pendientes) - len(enlaces)} para después",
              flush=True)

    for anio, mes in sqlite.meses_disponibles():
        del_mes = [clasificar(a) for a in sqlite.obtener_articulos(mes, anio)]
        sqlite.reemplazar_noticias(mes, anio, construir_noticias(del_mes))
        print(f"Noticias de {mes:02d}/{anio} reconstruidas", flush=True)

    # La próxima corrida del watcher vuelve a subir todos los meses a la nube.
    conn = sqlite3.connect(ajustes.DB_PATH)
    with conn:
        conn.execute("DELETE FROM sync_marcas WHERE clave = 'subida_noticias_inicial'")
    conn.close()
    print("Listo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
