"""Acceso a datos. El motor depende de MODO: SQLite en la PC, Postgres (Supabase) en la nube.

Los dos motores (store.sqlite y store.postgres) tienen la misma interfaz; el resto del código
llama a store.<función> sin saber cuál está activo.
"""
import ajustes

if ajustes.MODO == "nube":
    from store import postgres as _motor
else:
    from store import sqlite as _motor

_PUBLICAS = [
    "init_db", "guardar_articulos", "obtener_articulos", "articulos_desde", "podar_articulos",
    "urls_existentes", "urls_sin_enlace", "poner_enlaces",
    "reemplazar_noticias", "obtener_noticias", "meses_disponibles",
    "registrar_estado_fuente", "obtener_estado_fuentes",
    "iniciar_corrida", "intentar_iniciar_corrida", "corrida_en_curso", "finalizar_corrida", "ultima_corrida", "ultimo_intento",
    "guardar_estado_enlaces", "obtener_estado_enlaces", "urls_por_verificar", "enlaces_desde",
    "guardar_guion", "listar_guiones", "obtener_guion", "uids_guiones", "guiones_por_uid", "insertar_guiones",
]
globals().update({nombre: getattr(_motor, nombre) for nombre in _PUBLICAS})
__all__ = _PUBLICAS
