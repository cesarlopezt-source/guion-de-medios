import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ajustes

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS articulos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    titulo TEXT NOT NULL,
    resumen TEXT,
    url TEXT UNIQUE NOT NULL,
    fuente TEXT NOT NULL,
    pais TEXT NOT NULL,
    temas TEXT NOT NULL,
    personajes TEXT NOT NULL,
    menciona_sv INTEGER NOT NULL DEFAULT 0,
    publicado TEXT NOT NULL,
    recolectado TEXT NOT NULL,
    via TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_articulos_publicado ON articulos(publicado);
CREATE TABLE IF NOT EXISTS noticias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mes INTEGER NOT NULL,
    anio INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    resumen TEXT,
    pais TEXT NOT NULL,
    temas TEXT NOT NULL,
    personajes TEXT NOT NULL,
    menciona_sv INTEGER NOT NULL DEFAULT 0,
    fuentes TEXT NOT NULL,
    publicado TEXT NOT NULL,
    n_fuentes INTEGER NOT NULL,
    puntaje REAL NOT NULL,
    estrellas INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_noticias_periodo ON noticias(anio, mes);
CREATE TABLE IF NOT EXISTS estado_fuentes (
    fuente TEXT PRIMARY KEY,
    pais TEXT,
    tipo TEXT,
    ultima_corrida TEXT,
    ok INTEGER,
    n_articulos INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS corridas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    inicio TEXT NOT NULL,
    fin TEXT,
    n_articulos_nuevos INTEGER,
    ok INTEGER
);
CREATE TABLE IF NOT EXISTS enlaces (
    url TEXT PRIMARY KEY,
    activa INTEGER,            -- NULL = el sitio bloquea la verificación
    verificado TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS guiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    creado TEXT NOT NULL,
    noticias TEXT NOT NULL,
    texto TEXT NOT NULL,
    palabras INTEGER NOT NULL,
    minutos_estimados REAL NOT NULL
);
"""


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _conectar(db_path: Path = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or ajustes.DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = None) -> None:
    conn = _conectar(db_path)
    conn.executescript(_ESQUEMA)
    conn.commit()
    conn.close()


def guardar_articulos(articulos: list, db_path: Path = None) -> int:
    conn = _conectar(db_path)
    recolectado = _ahora()
    nuevos = 0
    for a in articulos:
        cur = conn.execute(
            "INSERT OR IGNORE INTO articulos (titulo, resumen, url, fuente, pais, temas, personajes, "
            "menciona_sv, publicado, recolectado, via) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                a["titulo"], a.get("resumen", ""), a["url"], a["fuente"], a["pais"],
                json.dumps(a.get("temas", []), ensure_ascii=False),
                json.dumps(a.get("personajes", []), ensure_ascii=False),
                int(bool(a.get("menciona_sv"))),
                a["publicado"].astimezone(timezone.utc).isoformat(), recolectado, a["via"],
            ),
        )
        nuevos += cur.rowcount
    conn.commit()
    conn.close()
    return nuevos


def obtener_articulos(mes: int, anio: int, db_path: Path = None) -> list:
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT titulo, resumen, url, fuente, pais, temas, personajes, menciona_sv, publicado, via "
        "FROM articulos WHERE strftime('%Y-%m', publicado, '-6 hours') = ?",  # mes en hora de El Salvador
        (f"{anio:04d}-{mes:02d}",),
    ).fetchall()
    conn.close()
    resultado = []
    for fila in filas:
        a = dict(fila)
        a["temas"] = json.loads(a["temas"])
        a["personajes"] = json.loads(a["personajes"])
        a["menciona_sv"] = bool(a["menciona_sv"])
        a["publicado"] = datetime.fromisoformat(a["publicado"])
        resultado.append(a)
    return resultado


def reemplazar_noticias(mes: int, anio: int, noticias: list, db_path: Path = None) -> None:
    conn = _conectar(db_path)
    with conn:
        conn.execute("DELETE FROM noticias WHERE mes = ? AND anio = ?", (mes, anio))
        conn.executemany(
            "INSERT INTO noticias (mes, anio, titulo, resumen, pais, temas, personajes, menciona_sv, "
            "fuentes, publicado, n_fuentes, puntaje, estrellas) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    mes, anio, x["titulo"], x.get("resumen", ""), x["pais"],
                    json.dumps(x["temas"], ensure_ascii=False),
                    json.dumps(x["personajes"], ensure_ascii=False),
                    int(bool(x["menciona_sv"])),
                    json.dumps(x["fuentes"], ensure_ascii=False),
                    x["publicado"], x["n_fuentes"], x["puntaje"], x["estrellas"],
                )
                for x in noticias
            ],
        )
    conn.close()


def obtener_noticias(mes: int, anio: int, db_path: Path = None) -> list:
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT id, titulo, resumen, pais, temas, personajes, menciona_sv, fuentes, publicado, "
        "n_fuentes, puntaje, estrellas FROM noticias WHERE mes = ? AND anio = ?",
        (mes, anio),
    ).fetchall()
    conn.close()
    resultado = []
    for fila in filas:
        x = dict(fila)
        for campo in ("temas", "personajes", "fuentes"):
            x[campo] = json.loads(x[campo])
        x["menciona_sv"] = bool(x["menciona_sv"])
        resultado.append(x)
    return resultado


def meses_disponibles(db_path: Path = None) -> list:
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT DISTINCT anio, mes FROM noticias ORDER BY anio DESC, mes DESC"
    ).fetchall()
    conn.close()
    return [(f["anio"], f["mes"]) for f in filas]


def registrar_estado_fuente(fuente: dict, ok: bool, n: int, error, db_path: Path = None) -> None:
    conn = _conectar(db_path)
    with conn:
        conn.execute(
            "INSERT INTO estado_fuentes (fuente, pais, tipo, ultima_corrida, ok, n_articulos, error) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(fuente) DO UPDATE SET pais=excluded.pais, "
            "tipo=excluded.tipo, ultima_corrida=excluded.ultima_corrida, ok=excluded.ok, "
            "n_articulos=excluded.n_articulos, error=excluded.error",
            (fuente["nombre"], fuente["pais"], fuente["tipo"], _ahora(), int(ok), n, error),
        )
    conn.close()


def obtener_estado_fuentes(db_path: Path = None) -> list:
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT fuente, pais, tipo, ultima_corrida, ok, n_articulos, error FROM estado_fuentes "
        "ORDER BY pais, fuente"
    ).fetchall()
    conn.close()
    resultado = []
    for fila in filas:
        x = dict(fila)
        x["ok"] = bool(x["ok"])
        resultado.append(x)
    return resultado


def iniciar_corrida(db_path: Path = None) -> int:
    conn = _conectar(db_path)
    with conn:
        cur = conn.execute("INSERT INTO corridas (inicio) VALUES (?)", (_ahora(),))
    conn.close()
    return cur.lastrowid


def finalizar_corrida(corrida_id: int, n_nuevos: int, ok: bool, db_path: Path = None) -> None:
    conn = _conectar(db_path)
    with conn:
        conn.execute(
            "UPDATE corridas SET fin = ?, n_articulos_nuevos = ?, ok = ? WHERE id = ?",
            (_ahora(), n_nuevos, int(ok), corrida_id),
        )
    conn.close()


def ultima_corrida(db_path: Path = None):
    conn = _conectar(db_path)
    fila = conn.execute(
        "SELECT inicio, fin, n_articulos_nuevos FROM corridas WHERE fin IS NOT NULL AND ok = 1 "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(fila) if fila else None


def guardar_estado_enlaces(estados: dict, db_path: Path = None) -> None:
    """estados: url → True / False / None (desconocido)."""
    conn = _conectar(db_path)
    ahora = _ahora()
    with conn:
        conn.executemany(
            "INSERT INTO enlaces (url, activa, verificado) VALUES (?, ?, ?) "
            "ON CONFLICT(url) DO UPDATE SET activa=excluded.activa, verificado=excluded.verificado",
            [(u, None if v is None else int(v), ahora) for u, v in estados.items()],
        )
    conn.close()


def obtener_estado_enlaces(urls: list, db_path: Path = None) -> dict:
    """url → bool, solo para los enlaces ya verificados con resultado conocido."""
    if not urls:
        return {}
    conn = _conectar(db_path)
    resultado = {}
    unicas = list(dict.fromkeys(urls))
    for i in range(0, len(unicas), 500):
        lote = unicas[i:i + 500]
        filas = conn.execute(
            f"SELECT url, activa FROM enlaces WHERE activa IS NOT NULL AND url IN ({','.join('?' * len(lote))})",
            lote,
        ).fetchall()
        resultado.update({f["url"]: bool(f["activa"]) for f in filas})
    conn.close()
    return resultado


def urls_por_verificar(mes_actual: tuple, limite: int, db_path: Path = None, dias: int = 7) -> list:
    """Enlaces de meses anteriores sin verificar o verificados hace más de `dias`; sin redirecciones de Google News."""
    mes, anio = mes_actual
    limite_fecha = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT u.url FROM (SELECT DISTINCT json_extract(j.value, '$.url') AS url, n.anio, n.mes "
        "FROM noticias n, json_each(n.fuentes) j WHERE NOT (n.mes = ? AND n.anio = ?)) u "
        "LEFT JOIN enlaces e ON e.url = u.url "
        "WHERE u.url NOT LIKE 'https://news.google.com/%' AND (e.url IS NULL OR e.verificado < ?) "
        "GROUP BY u.url ORDER BY MAX(u.anio) DESC, MAX(u.mes) DESC LIMIT ?",
        (mes, anio, limite_fecha, limite),
    ).fetchall()
    conn.close()
    return [f["url"] for f in filas]


def guardar_guion(noticias: list, texto: str, palabras: int, minutos: float, db_path: Path = None) -> int:
    conn = _conectar(db_path)
    with conn:
        cur = conn.execute(
            "INSERT INTO guiones (creado, noticias, texto, palabras, minutos_estimados) VALUES (?, ?, ?, ?, ?)",
            (_ahora(), json.dumps(noticias, ensure_ascii=False), texto, palabras, minutos),
        )
    conn.close()
    return cur.lastrowid


def listar_guiones(db_path: Path = None) -> list:
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT id, creado, palabras, minutos_estimados, noticias FROM guiones ORDER BY id DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": f["id"], "creado": f["creado"], "palabras": f["palabras"],
            "minutos": f["minutos_estimados"],
            "titulos": [x["titulo"] for x in json.loads(f["noticias"])],
        }
        for f in filas
    ]


def obtener_guion(guion_id: int, db_path: Path = None):
    conn = _conectar(db_path)
    fila = conn.execute(
        "SELECT id, creado, noticias, texto, palabras, minutos_estimados FROM guiones WHERE id = ?",
        (guion_id,),
    ).fetchone()
    conn.close()
    if not fila:
        return None
    g = dict(fila)
    g["noticias"] = json.loads(g["noticias"])
    g["minutos"] = g.pop("minutos_estimados")
    return g
