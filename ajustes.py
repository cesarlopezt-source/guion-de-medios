import os
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).parent
load_dotenv(RAIZ / ".env")

DATA_DIR = Path(os.environ.get("DATA_DIR") or Path(os.environ.get("LOCALAPPDATA", RAIZ)) / "GuionDeMedios")
DB_PATH = DATA_DIR / "guion.db"
LOG_DIR = DATA_DIR / "logs"
LOCK_PATH = DATA_DIR / "watcher.lock"
PORT = int(os.environ.get("PORT") or 5050)
GEMINI_MODEL = os.environ.get("GEMINI_MODEL") or "gemini-2.5-flash"
GEMINI_MODEL_VALORAR = os.environ.get("GEMINI_MODEL_VALORAR") or "gemini-2.5-flash-lite"

LOG_DIR.mkdir(parents=True, exist_ok=True)
