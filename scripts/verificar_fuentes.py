"""Prueba cada fuente contra la red e imprime una tabla. Uso: python scripts/verificar_fuentes.py [--todas]"""
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from collectors import recolectar  # noqa: E402
from config.fuentes import FUENTES, consultas_google_news  # noqa: E402


def main() -> int:
    fuentes = [f for f in FUENTES if f["activa"]]
    if "--todas" in sys.argv:
        fuentes += consultas_google_news()
    with ThreadPoolExecutor(max_workers=8) as ex:
        resultados = list(ex.map(recolectar, fuentes))
    print(f"{'país':4} | {'nombre':42} | {'tipo':11} | ok | {'n':>3} | error")
    for f, (articulos, error) in sorted(zip(fuentes, resultados), key=lambda x: (x[0]["pais"], x[0]["nombre"])):
        ok = "sí" if error is None and articulos else "NO"
        print(f"{f['pais']:4} | {f['nombre'][:42]:42} | {f['tipo']:11} | {ok} | {len(articulos):>3} | {error or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
