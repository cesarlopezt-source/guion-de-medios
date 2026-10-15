"""Servidor del portal (solo accesible desde esta PC). Lo inicia la tarea programada al iniciar sesión."""
from waitress import serve

import ajustes
from app import app

if __name__ == "__main__":
    serve(app, host="127.0.0.1", port=ajustes.PORT, threads=8)
