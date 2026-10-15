from datetime import datetime, timezone


def factor_recencia(publicado: datetime) -> float:
    if publicado.tzinfo is None:
        publicado = publicado.replace(tzinfo=timezone.utc)
    horas = (datetime.now(timezone.utc) - publicado).total_seconds() / 3600
    if horas < 2:
        return 1.0
    if horas < 6:
        return 0.75
    if horas < 12:
        return 0.5
    if horas < 24:
        return 0.25
    return 0.1


def puntuar(cluster: list) -> float:
    n_fuentes = len({a["fuente"] for a in cluster})
    mas_reciente = max(a["publicado"] for a in cluster)
    return float((n_fuentes * 40) + (factor_recencia(mas_reciente) * 60))


def estrellas(puntaje: float, maximo: float) -> int:
    if maximo == 0:
        return 1
    return max(1, min(5, round(puntaje / maximo * 5)))
