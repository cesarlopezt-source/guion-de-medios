import hmac
import logging
import os
import secrets
import subprocess
import sys
import threading
from datetime import datetime, timedelta, timezone

from flask import Flask, Response, jsonify, redirect, render_template, request, session

import ajustes
import exporter
import guionista
import store
import valorador
import watcher
from config.paises import PAISES
from config.partidos import PARTIDOS
from config.personajes import PERSONAJES
from config.temas import TEMAS
from ia import ConfigError, IASaturada
from noticias import filtrar, ordenar

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
app.config.update(
    SESSION_COOKIE_SECURE=ajustes.MODO == "nube",  # en internet la página va por https
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(days=30),
)
store.init_db()
log = logging.getLogger("portal")

VIVO_HORAS = 2           # en la nube, si los datos son más viejos, se busca en vivo
REINTENTO_MIN = 30       # tras un intento (aunque haya fallado) no se relanza solo antes de esto
MAX_FALLOS_LOGIN = 5     # intentos fallidos por IP antes de bloquear
BLOQUEO_LOGIN_MIN = 15
_fallos_login = {}       # ip → [momentos de intentos fallidos]; un solo proceso (gunicorn --workers 1)
_buscando = threading.Event()  # una sola búsqueda en vivo por proceso

TEMAS_UI = list(TEMAS) + ["Otras"]
MIME = {
    "word": ("application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
    "excel": ("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "pdf": ("application/pdf", "pdf"),
}


def _csv(nombre: str) -> set:
    return {x.strip() for x in request.args.get(nombre, "").split(",") if x.strip()}


def _archivo(contenido: bytes, formato: str, base: str) -> Response:
    mime, ext = MIME[formato]
    return Response(contenido, mimetype=mime,
                    headers={"Content-Disposition": f"attachment; filename={base}.{ext}"})


def _manejar_ia(funcion):
    """Errores de IA → 400 (entrada), 503 (sin clave o Gemini saturado) o 500 (otro)."""
    try:
        return funcion()
    except (ConfigError, IASaturada) as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # noqa: BLE001 — se informa al usuario en la pantalla
        return jsonify({"error": str(e)}), 500


def _en_nube() -> bool:
    return ajustes.MODO == "nube"


# ---------- Contraseña (solo en la nube) ----------

@app.before_request
def exigir_sesion():
    if not _en_nube() or session.get("ok") or request.path == "/login" or request.path.startswith("/static/"):
        return None
    if request.path.startswith("/api/"):
        return jsonify({"error": "Sesión expirada"}), 401
    return redirect("/login")


def _ip_cliente() -> str:
    # Render pone la IP real del visitante en X-Forwarded-For.
    return (request.headers.get("X-Forwarded-For") or request.remote_addr or "?").split(",")[0].strip()


def _fallos_recientes(ip: str) -> list:
    limite = datetime.now(timezone.utc) - timedelta(minutes=BLOQUEO_LOGIN_MIN)
    recientes = [t for t in _fallos_login.get(ip, []) if t > limite]
    _fallos_login[ip] = recientes
    return recientes


@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        ip = _ip_cliente()
        if len(_fallos_recientes(ip)) >= MAX_FALLOS_LOGIN:
            return render_template(
                "login.html", error=f"Demasiados intentos. Espera {BLOQUEO_LOGIN_MIN} minutos."), 429
        clave = os.environ.get("APP_PASSWORD", "")
        if clave and hmac.compare_digest(request.form.get("password", ""), clave):
            _fallos_login.pop(ip, None)
            session.clear()
            session["ok"] = True
            session.permanent = True
            return redirect("/")
        _fallos_login.setdefault(ip, []).append(datetime.now(timezone.utc))
        error = "Contraseña incorrecta"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ---------- Búsqueda en vivo (solo en la nube) ----------

def _buscar() -> None:
    try:
        watcher.correr(origen="nube", verificar_enlaces=False)
    except Exception:  # noqa: BLE001 — queda en el log de Render; la corrida se cierra con ok = False
        log.exception("Falló la búsqueda en vivo")
    finally:
        _buscando.clear()


def lanzar_busqueda_en_vivo() -> bool:
    if _buscando.is_set() or store.corrida_en_curso() is not None:
        return False
    _buscando.set()
    threading.Thread(target=_buscar, daemon=True).start()
    return True


def _intento_reciente() -> bool:
    intento = store.ultimo_intento()
    return bool(intento) and datetime.now(timezone.utc) - datetime.fromisoformat(intento) < timedelta(minutes=REINTENTO_MIN)


def _datos_viejos(ultima) -> bool:
    if not ultima:
        return True
    fin = datetime.fromisoformat(ultima["fin"])
    return datetime.now(timezone.utc) - fin > timedelta(hours=VIVO_HORAS)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/fuentes")
def fuentes():
    estado = store.obtener_estado_fuentes()
    return render_template("fuentes.html", estado=estado, paises=PAISES)


@app.route("/api/meta")
def api_meta():
    ultima = store.ultima_corrida()
    if _en_nube():
        if _datos_viejos(ultima) and not _intento_reciente():
            lanzar_busqueda_en_vivo()
        en_curso = store.corrida_en_curso()
        origen_en_curso = en_curso["origen"] if en_curso else ("nube" if _buscando.is_set() else None)
    else:
        origen_en_curso = "pc" if watcher.esta_bloqueado(ajustes.LOCK_PATH) else None
    return jsonify({
        "paises": [{"codigo": c, "nombre": n} for c, n in PAISES.items()],
        "temas": TEMAS_UI,
        "personajes": list(PERSONAJES),
        "partidos": list(PARTIDOS),
        "ultima_actualizacion": ultima["fin"] if ultima else None,
        "meses": [list(m) for m in store.meses_disponibles()],
        "en_curso": origen_en_curso is not None,
        "origen_en_curso": origen_en_curso,
        "mes_actual": [_hoy_sv().year, _hoy_sv().month],
    })


def _hoy_sv() -> datetime:
    return datetime.now(ajustes.ZONA_SV)


@app.route("/api/news")
def api_news():
    ahora = _hoy_sv()
    try:
        mes = int(request.args.get("mes") or ahora.month)
        anio = int(request.args.get("anio") or ahora.year)
    except ValueError:
        return jsonify({"error": "Mes o año inválido"}), 400
    if not 1 <= mes <= 12:
        return jsonify({"error": "Mes inválido"}), 400

    noticias = filtrar(store.obtener_noticias(mes, anio), _csv("paises"), _csv("temas"), _csv("personajes"), _csv("partidos"))
    noticias = ordenar(noticias, request.args.get("orden", "importancia"))

    if (mes, anio) != (ahora.month, ahora.year):
        # El watcher verifica los enlaces archivados por tandas; aquí solo se lee lo ya verificado.
        estados = store.obtener_estado_enlaces([f["url"] for n in noticias for f in n["fuentes"]])
        for n in noticias:
            for f in n["fuentes"]:
                if f["url"] in estados:
                    f["activa"] = estados[f["url"]]
    return jsonify(noticias)


@app.route("/api/actualizar", methods=["POST"])
def api_actualizar():
    if _en_nube():
        if lanzar_busqueda_en_vivo():
            return jsonify({"iniciado": True})
        return jsonify({"iniciado": False, "motivo": "en_curso"})
    if watcher.esta_bloqueado(ajustes.LOCK_PATH):
        return jsonify({"iniciado": False, "motivo": "en_curso"})
    subprocess.Popen(
        [sys.executable, str(ajustes.RAIZ / "watcher.py")],
        cwd=ajustes.RAIZ, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    return jsonify({"iniciado": True})


@app.route("/api/valorar", methods=["POST"])
def api_valorar():
    items = (request.get_json(silent=True) or {}).get("items", [])
    return _manejar_ia(lambda: jsonify(valorador.generar_valoraciones(items)))


@app.route("/api/export", methods=["POST"])
def api_export():
    data = request.get_json(silent=True) or {}
    formato = data.get("format", "pdf").lower()
    formato = formato if formato in MIME else "pdf"
    funcion = {"word": exporter.export_word, "excel": exporter.export_excel, "pdf": exporter.export_pdf}[formato]
    return _archivo(funcion(data.get("items", [])), formato, "noticias_centroamerica")


@app.route("/api/guion", methods=["POST"])
def api_guion():
    noticias = (request.get_json(silent=True) or {}).get("noticias", [])

    def generar():
        g = guionista.generar_guion(noticias)
        g["id"] = store.guardar_guion(noticias, g["texto"], g["palabras"], g["minutos"])
        return jsonify(g)
    return _manejar_ia(generar)


@app.route("/api/guiones")
def api_guiones():
    return jsonify(store.listar_guiones())


@app.route("/api/guiones/<int:guion_id>")
def api_guion_detalle(guion_id):
    g = store.obtener_guion(guion_id)
    if g is None:
        return jsonify({"error": "Guion no encontrado"}), 404
    return jsonify(g)


@app.route("/api/guion/export", methods=["POST"])
def api_guion_export():
    data = request.get_json(silent=True) or {}
    texto = data.get("texto", "")
    if data.get("formato") == "word":
        return _archivo(exporter.export_guion_word(texto), "word", "guion_de_medios")
    return _archivo(exporter.export_guion_pdf(texto), "pdf", "guion_de_medios")
