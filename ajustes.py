import os
import re
from datetime import timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).parent
load_dotenv(RAIZ / ".env")


def limpiar_dsn(dsn):
    """Corrige lo típico al copiar la dirección de Supabase: comillas, espacios y el Transaction pooler
    (puerto 6543, ?pgbouncer=true), que no admite tablas temporales ni bloqueos de sesión."""
    dsn = (dsn or "").strip().strip("\"'").strip()
    if not dsn:
        return None
    base, _, consulta = dsn.partition("?")
    consulta = "&".join(p for p in consulta.split("&") if p and not p.startswith("pgbouncer="))
    base = re.sub(r"(\.pooler\.supabase\.com):6543(?=/)", r"\1:5432", base)
    return f"{base}?{consulta}" if consulta else base


DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(os.environ.get("LOCALAPPDATA", RAIZ)) / "GuionDeMedios")
DB_PATH = DATA_DIR / "guion.db"
LOG_DIR = DATA_DIR / "logs"
LOCK_PATH = DATA_DIR / "watcher.lock"
PORT = int(os.environ.get("PORT") or 5050)
MODO = (os.environ.get("MODO") or "pc").lower()          # "pc" (SQLite local) o "nube" (Render + Supabase)
DATABASE_URL = limpiar_dsn(os.environ.get("DATABASE_URL"))  # Supabase
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL") or None
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
GEMINI_MODEL_VALORAR = os.environ.get("GEMINI_MODEL_VALORAR") or "gemini-2.5-flash-lite"
# Si el modelo está saturado (503) se prueban estos, en orden.
GEMINI_RESPALDOS = [m.strip() for m in (os.environ.get("GEMINI_MODELOS_RESPALDO")
                    or "gemini-2.5-flash-lite,gemini-flash-latest").split(",") if m.strip()]
# Los meses se cuentan en hora de El Salvador (UTC-6, sin horario de verano).
ZONA_SV = timezone(timedelta(hours=-6), "America/El_Salvador")

LOG_DIR.mkdir(parents=True, exist_ok=True)
