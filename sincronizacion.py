"""Sincronización entre la base de la PC (SQLite) y la de la nube (Neon), dentro de cada corrida del watcher.

antes():     toma el bloqueo en la nube y baja lo que la página encontró en vivo (artículos y guiones).
despues():   sube artículos, noticias del mes, estado de fuentes, enlaces y guiones; poda la nube.
al_final():  cierra la corrida en la nube y deja el resultado en "Estado de fuentes".

Si la nube no responde, la corrida local sigue igual y se reintenta en la siguiente hora.
Las marcas (sync_marcas) avanzan solo cuando su paso terminó bien; repetir un paso no duplica.
"""
import logging
from collections import defaultdict
from datetime import datetime, timezone

import ajustes
from store import postgres, sqlite

log = logging.getLogger("sincronizacion")

FUENTE_SYNC = {"nombre": "Sincronización con la nube", "pais": "REG", "tipo": "nube"}


def _primer_dia_mes_anterior_utc(mes: int, anio: int) -> str:
    """1.º del mes anterior a las 00:00 en El Salvador (06:00 UTC): lo anterior se poda en la nube."""
    mes_ant, anio_ant = (12, anio - 1) if mes == 1 else (mes - 1, anio)
    return datetime(anio_ant, mes_ant, 1, 6, tzinfo=timezone.utc).isoformat()


class Sincronizacion:
    def __init__(self, local=None, nube=None):
        self.local = local
        self.nube = nube or ajustes.DATABASE_URL
        self.activa = False
        self.corrida_remota = None
        self.error = None
        self.subidos = 0

    # ---------- Pasos que llama watcher.correr ----------

    def antes(self) -> bool:
        """False = la nube está buscando en este momento (la corrida se cancela). True = seguir."""
        try:
            postgres.init_db(self.nube)
            self.corrida_remota = postgres.intentar_iniciar_corrida("pc", self.nube)
        except Exception as e:  # noqa: BLE001 — sin conexión: se sigue solo en local
            self._fallo("No se pudo conectar con la nube", e)
            return True
        if self.corrida_remota is None:
            return False
        self.activa = True
        try:
            self._bajar()
        except Exception as e:  # noqa: BLE001
            self._fallo("Falló la bajada desde la nube", e)
        return True

    def despues(self, meses: list) -> None:
        if not self.activa:
            return
        try:
            self._subir(meses)
            postgres.podar_articulos(_primer_dia_mes_anterior_utc(*meses[0]), self.nube)
        except Exception as e:  # noqa: BLE001
            self._fallo("Falló la subida a la nube", e)

    def al_final(self, ok: bool) -> None:
        if self.corrida_remota is not None:
            try:
                postgres.finalizar_corrida(self.corrida_remota, self.subidos, ok and self.error is None, self.nube)
            except Exception as e:  # noqa: BLE001
                self._fallo("No se pudo cerrar la corrida en la nube", e)
        sqlite.registrar_estado_fuente(FUENTE_SYNC, self.error is None, self.subidos, self.error, self.local)
        if self.error is None:
            log.info("Sincronización OK: %d artículos subidos", self.subidos)

    # ---------- Detalle ----------

    def _fallo(self, que: str, e: Exception) -> None:
        self.error = f"{que}: {str(e)[:200]}"
        log.warning(self.error)

    def _bajar(self) -> None:
        marca = sqlite.obtener_marca("bajada_articulos", self.local)
        nuevos = postgres.articulos_desde(marca, self.nube, origen="nube")
        if nuevos:
            sqlite.guardar_articulos(nuevos, self.local)
            sqlite.guardar_marca("bajada_articulos", nuevos[-1]["recolectado"], self.local)
        faltan = postgres.uids_guiones(self.nube) - sqlite.uids_guiones(self.local)
        sqlite.insertar_guiones(postgres.guiones_por_uid(faltan, self.nube), self.local)
        log.info("Bajados de la nube: %d artículos, %d guiones", len(nuevos), len(faltan))

    def _subir(self, meses: list) -> None:
        marca = sqlite.obtener_marca("subida_articulos", self.local)
        articulos = sqlite.articulos_desde(marca, self.local)
        if articulos:
            self.subidos = postgres.guardar_articulos(articulos, self.nube)
            sqlite.guardar_marca("subida_articulos", articulos[-1]["recolectado"], self.local)

        # La primera vez se sube todo el histórico; después, solo los meses reconstruidos en la corrida.
        inicial = sqlite.obtener_marca("subida_noticias_inicial", self.local) is None
        meses_a_subir = sorted(set(meses) | {(m, a) for a, m in sqlite.meses_disponibles(self.local)}) if inicial else meses
        for mes, anio in meses_a_subir:
            postgres.reemplazar_noticias(mes, anio, sqlite.obtener_noticias(mes, anio, self.local), self.nube)
        if inicial:
            sqlite.guardar_marca("subida_noticias_inicial", datetime.now(timezone.utc).isoformat(), self.local)

        for e in sqlite.obtener_estado_fuentes(self.local):
            if e["fuente"] == FUENTE_SYNC["nombre"]:
                continue
            fuente = {"nombre": e["fuente"], "pais": e["pais"], "tipo": e["tipo"]}
            postgres.registrar_estado_fuente(fuente, e["ok"], e["n_articulos"], e["error"], self.nube)

        marca_enlaces = sqlite.obtener_marca("subida_enlaces", self.local)
        enlaces = sqlite.enlaces_desde(marca_enlaces, self.local)
        if enlaces:
            por_fecha = defaultdict(dict)
            for url, (activa, verificado) in enlaces.items():
                por_fecha[verificado][url] = activa
            for verificado, estados in por_fecha.items():
                postgres.guardar_estado_enlaces(estados, self.nube, verificado=verificado)
            sqlite.guardar_marca("subida_enlaces", max(por_fecha), self.local)

        faltan = sqlite.uids_guiones(self.local) - postgres.uids_guiones(self.nube)
        postgres.insertar_guiones(sqlite.guiones_por_uid(faltan, self.local), self.nube)
