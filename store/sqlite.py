"""Motor SQLite de store (base local de la PC)."""
import json
import sqlite3
import uuid
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
    via TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'pc'
);
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
    ok INTEGER,
    origen TEXT NOT NULL DEFAULT 'pc'
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
    minutos_estimados REAL NOT NULL,
    uid TEXT
);
CREATE TABLE IF NOT EXISTS sync_marcas (
    clave TEXT PRIMARY KEY,
    valor TEXT
);
"""

# Se crean después de migrar, porque usan columnas que una base vieja puede no tener.
_INDICES = """
CREATE INDEX IF NOT EXISTS idx_articulos_publicado ON articulos(publicado);
CREATE INDEX IF NOT EXISTS idx_articulos_recolectado ON articulos(recolectado);
CREATE UNIQUE INDEX IF NOT EXISTS idx_guiones_uid ON guiones(uid);
"""

_COLUMNAS_NUEVAS = [
    ("articulos", "origen", "TEXT NOT NULL DEFAULT 'pc'"),
    ("corridas", "origen", "TEXT NOT NULL DEFAULT 'pc'"),
    ("guiones", "uid", "TEXT"),
]


def _ahora() -> str:
    return datetime.now(timezone.utc).isoformat()


def _iso(valor) -> str:
    """datetime o texto ISO → texto ISO en UTC (formato comparable como cadena)."""
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    return valor.astimezone(timezone.utc).isoformat()


def _conectar(db_path: Path = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or ajustes.DB_PATH, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = None) -> None:
    conn = _conectar(db_path)
    conn.executescript(_ESQUEMA)
    _migrar(conn)
    conn.executescript(_INDICES)
    conn.commit()
    conn.close()


def _migrar(conn: sqlite3.Connection) -> None:
    """Agrega las columnas nuevas a una base creada con una versión anterior."""
    for tabla, columna, tipo in _COLUMNAS_NUEVAS:
        existentes = {f["name"] for f in conn.execute(f"PRAGMA table_info({tabla})")}
        if columna not in existentes:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {tipo}")
    for fila in conn.execute("SELECT id FROM guiones WHERE uid IS NULL").fetchall():
        conn.execute("UPDATE guiones SET uid = ? WHERE id = ?", (uuid.uuid4().hex, fila["id"]))


def guardar_articulos(articulos: list, db_path: Path = None, origen: str = "pc") -> int:
    """Inserta sin duplicar por URL. Un artículo que ya trae origen/recolectado (bajado de la nube) los conserva."""
    conn = _conectar(db_path)
    recolectado = _ahora()
    nuevos = 0
    for a in articulos:
        cur = conn.execute(
            "INSERT OR IGNORE INTO articulos (titulo, resumen, url, fuente, pais, temas, personajes, "
            "menciona_sv, publicado, recolectado, via, origen) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                a["titulo"], a.get("resumen", ""), a["url"], a["fuente"], a["pais"],
                json.dumps(a.get("temas", []), ensure_ascii=False),
                json.dumps(a.get("personajes", []), ensure_ascii=False),
                int(bool(a.get("menciona_sv"))),
                _iso(a["publicado"]), _iso(a["recolectado"]) if a.get("recolectado") else recolectado,
                a["via"], a.get("origen") or origen,
            ),
        )
        nuevos += cur.rowcount
    conn.commit()
    conn.close()
    return nuevos


def _articulo(fila) -> dict:
    a = dict(fila)
    a["temas"] = json.loads(a["temas"])
    a["personajes"] = json.loads(a["personajes"])
    a["menciona_sv"] = bool(a["menciona_sv"])
    a["publicado"] = datetime.fromisoformat(a["publicado"])
    return a


def articulos_desde(marca, db_path: Path = None, origen: str = None) -> list:
    """Artículos recolectados después de `marca` (todos si es None), opcionalmente de un origen."""
    condiciones, params = [], []
    if marca:
        condiciones.append("recolectado > ?")
        params.append(_iso(marca))
    if origen:
        condiciones.append("origen = ?")
        params.append(origen)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT titulo, resumen, url, fuente, pais, temas, personajes, menciona_sv, publicado, via, "
        f"recolectado, origen FROM articulos {where} ORDER BY recolectado, id", params,
    ).fetchall()
    conn.close()
    return [_articulo(f) for f in filas]


def podar_articulos(antes_de: str, db_path: Path = None) -> int:
    conn = _conectar(db_path)
    with conn:
        cur = conn.execute("DELETE FROM articulos WHERE publicado < ?", (_iso(antes_de),))
    conn.close()
    return cur.rowcount


def obtener_articulos(mes: int, anio: int, db_path: Path = None) -> list:
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT titulo, resumen, url, fuente, pais, temas, personajes, menciona_sv, publicado, via "
        "FROM articulos WHERE strftime('%Y-%m', publicado, '-6 hours') = ?",  # mes en hora de El Salvador
        (f"{anio:04d}-{mes:02d}",),
    ).fetchall()
    conn.close()
    return [_articulo(f) for f in filas]


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


def iniciar_corrida(db_path: Path = None, origen: str = "pc") -> int:
    conn = _conectar(db_path)
    with conn:
        cur = conn.execute("INSERT INTO corridas (inicio, origen) VALUES (?, ?)", (_ahora(), origen))
    conn.close()
    return cur.lastrowid


def _limite_bloqueo(bloqueo_min: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=bloqueo_min)).isoformat()


def intentar_iniciar_corrida(origen: str, db_path: Path = None, bloqueo_min: int = 15):
    """Abre una corrida si no hay otra abierta de hace menos de `bloqueo_min`; si la hay, devuelve None."""
    conn = _conectar(db_path)
    conn.isolation_level = None
    try:
        conn.execute("BEGIN IMMEDIATE")
        abierta = conn.execute(
            "SELECT 1 FROM corridas WHERE fin IS NULL AND inicio > ? LIMIT 1", (_limite_bloqueo(bloqueo_min),)
        ).fetchone()
        if abierta:
            conn.execute("ROLLBACK")
            return None
        cur = conn.execute("INSERT INTO corridas (inicio, origen) VALUES (?, ?)", (_ahora(), origen))
        conn.execute("COMMIT")
        return cur.lastrowid
    finally:
        conn.close()


def corrida_en_curso(db_path: Path = None, bloqueo_min: int = 15):
    conn = _conectar(db_path)
    fila = conn.execute(
        "SELECT inicio, origen FROM corridas WHERE fin IS NULL AND inicio > ? ORDER BY id DESC LIMIT 1",
        (_limite_bloqueo(bloqueo_min),),
    ).fetchone()
    conn.close()
    return dict(fila) if fila else None


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
        "SELECT inicio, fin, n_articulos_nuevos, origen FROM corridas WHERE fin IS NOT NULL AND ok = 1 "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return dict(fila) if fila else None


def guardar_estado_enlaces(estados: dict, db_path: Path = None, verificado: str = None) -> None:
    """estados: url → True / False / None (desconocido). `verificado` permite conservar la fecha original."""
    conn = _conectar(db_path)
    ahora = _iso(verificado) if verificado else _ahora()
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


def enlaces_desde(marca, db_path: Path = None) -> dict:
    """url → (activa, verificado) de los enlaces verificados después de `marca` (todos si es None)."""
    conn = _conectar(db_path)
    if marca:
        filas = conn.execute("SELECT url, activa, verificado FROM enlaces WHERE verificado > ?", (_iso(marca),))
    else:
        filas = conn.execute("SELECT url, activa, verificado FROM enlaces")
    resultado = {f["url"]: (None if f["activa"] is None else bool(f["activa"]), f["verificado"]) for f in filas}
    conn.close()
    return resultado


def guardar_guion(noticias: list, texto: str, palabras: int, minutos: float, db_path: Path = None) -> int:
    conn = _conectar(db_path)
    with conn:
        cur = conn.execute(
            "INSERT INTO guiones (creado, noticias, texto, palabras, minutos_estimados, uid) VALUES (?, ?, ?, ?, ?, ?)",
            (_ahora(), json.dumps(noticias, ensure_ascii=False), texto, palabras, minutos, uuid.uuid4().hex),
        )
    conn.close()
    return cur.lastrowid


def listar_guiones(db_path: Path = None) -> list:
    conn = _conectar(db_path)
    filas = conn.execute(
        "SELECT id, uid, creado, palabras, minutos_estimados, noticias FROM guiones ORDER BY creado DESC, id DESC"
    ).fetchall()
    conn.close()
    return [
        {
            "id": f["id"], "uid": f["uid"], "creado": f["creado"], "palabras": f["palabras"],
            "minutos": f["minutos_estimados"],
            "titulos": [x["titulo"] for x in json.loads(f["noticias"])],
        }
        for f in filas
    ]


def obtener_guion(guion_id: int, db_path: Path = None):
    conn = _conectar(db_path)
    fila = conn.execute(
        "SELECT id, uid, creado, noticias, texto, palabras, minutos_estimados FROM guiones WHERE id = ?",
        (guion_id,),
    ).fetchone()
    conn.close()
    if not fila:
        return None
    g = dict(fila)
    g["noticias"] = json.loads(g["noticias"])
    g["minutos"] = g.pop("minutos_estimados")
    return g


def uids_guiones(db_path: Path = None) -> set:
    conn = _conectar(db_path)
    uids = {f["uid"] for f in conn.execute("SELECT uid FROM guiones")}
    conn.close()
    return uids


def guiones_por_uid(uids: set, db_path: Path = None) -> list:
    if not uids:
        return []
    conn = _conectar(db_path)
    lista = list(uids)
    filas = conn.execute(
        f"SELECT uid, creado, noticias, texto, palabras, minutos_estimados FROM guiones "
        f"WHERE uid IN ({','.join('?' * len(lista))})", lista,
    ).fetchall()
    conn.close()
    return [
        {"uid": f["uid"], "creado": f["creado"], "noticias": json.loads(f["noticias"]), "texto": f["texto"],
         "palabras": f["palabras"], "minutos": f["minutos_estimados"]}
        for f in filas
    ]


def insertar_guiones(guiones: list, db_path: Path = None) -> int:
    """Inserta guiones de otra base conservando uid y fecha; ignora los que ya existen."""
    conn = _conectar(db_path)
    nuevos = 0
    with conn:
        for g in guiones:
            cur = conn.execute(
                "INSERT OR IGNORE INTO guiones (uid, creado, noticias, texto, palabras, minutos_estimados) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (g["uid"], _iso(g["creado"]), json.dumps(g["noticias"], ensure_ascii=False), g["texto"],
                 g["palabras"], g["minutos"]),
            )
            nuevos += cur.rowcount
    conn.close()
    return nuevos


def obtener_marca(clave: str, db_path: Path = None):
    conn = _conectar(db_path)
    fila = conn.execute("SELECT valor FROM sync_marcas WHERE clave = ?", (clave,)).fetchone()
    conn.close()
    return fila["valor"] if fila else None


def guardar_marca(clave: str, valor: str, db_path: Path = None) -> None:
    conn = _conectar(db_path)
    with conn:
        conn.execute(
            "INSERT INTO sync_marcas (clave, valor) VALUES (?, ?) "
            "ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor", (clave, valor),
        )
    conn.close()


def ultimo_intento(db_path: Path = None):
    """Inicio de la última corrida, haya terminado bien, mal o siga abierta."""
    conn = _conectar(db_path)
    fila = conn.execute("SELECT inicio FROM corridas ORDER BY inicio DESC LIMIT 1").fetchone()
    conn.close()
    return fila["inicio"] if fila else None
