import calendar
from datetime import datetime, timezone


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def fecha_segura(dt) -> datetime:
    """Fecha ausente o futura → ahora; sin zona → UTC."""
    if dt is None:
        return ahora()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt = dt.astimezone(timezone.utc)
    return min(dt, ahora())


def fecha_de_entrada(entry) -> datetime:
    t = entry.get("published_parsed") or entry.get("updated_parsed")
    if not t:
        return ahora()
    return fecha_segura(datetime.fromtimestamp(calendar.timegm(t), tz=timezone.utc))


def articulo(titulo, resumen, url, fuente, pais, publicado, via) -> dict:
    return {
        "titulo": titulo, "resumen": resumen, "url": url, "fuente": fuente,
        "pais": pais, "publicado": publicado, "via": via,
    }
