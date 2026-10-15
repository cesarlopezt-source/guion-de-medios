import subprocess
import sys
from datetime import datetime, timezone

from flask import Flask, Response, jsonify, render_template, request

import ajustes
import exporter
import guionista
import link_checker
import store
import valorador
import watcher
from config.paises import PAISES
from config.personajes import PERSONAJES
from config.temas import TEMAS
from ia import ConfigError
from noticias import filtrar, ordenar

app = Flask(__name__)
store.init_db()

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
    """Errores de IA → 400 (entrada), 503 (sin clave) o 500 (otro)."""
    try:
        return funcion()
    except ConfigError as e:
        return jsonify({"error": str(e)}), 503
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:  # noqa: BLE001 — se informa al usuario en la pantalla
        return jsonify({"error": str(e)}), 500


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
    return jsonify({
        "paises": [{"codigo": c, "nombre": n} for c, n in PAISES.items()],
        "temas": TEMAS_UI,
        "personajes": list(PERSONAJES),
        "ultima_actualizacion": ultima["fin"] if ultima else None,
        "meses": [list(m) for m in store.meses_disponibles()],
        "en_curso": watcher.esta_bloqueado(ajustes.LOCK_PATH),
    })


@app.route("/api/news")
def api_news():
    ahora = datetime.now(timezone.utc)
    try:
        mes = int(request.args.get("mes") or ahora.month)
        anio = int(request.args.get("anio") or ahora.year)
    except ValueError:
        return jsonify({"error": "Mes o año inválido"}), 400
    if not 1 <= mes <= 12:
        return jsonify({"error": "Mes inválido"}), 400

    noticias = filtrar(store.obtener_noticias(mes, anio), _csv("paises"), _csv("temas"), _csv("personajes"))
    noticias = ordenar(noticias, request.args.get("orden", "importancia"))

    if (mes, anio) != (ahora.month, ahora.year):
        activos = link_checker.check_urls([f["url"] for n in noticias for f in n["fuentes"]])
        for n in noticias:
            for f in n["fuentes"]:
                f["activa"] = activos.get(f["url"], False)
    return jsonify(noticias)


@app.route("/api/actualizar", methods=["POST"])
def api_actualizar():
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
