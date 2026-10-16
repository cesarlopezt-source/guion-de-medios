"""Motor Postgres de store (Supabase, en la nube). Misma interfaz que store.sqlite.

El parámetro `db_path` es el DSN de conexión; None = ajustes.DATABASE_URL.
Se abre una conexión por llamada: Supabase cierra las conexiones ociosas.
"""
import uuid
from datetime import datetime, timedelta, timezone

import psycopg
from psycopg.conninfo import conninfo_to_dict
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

import ajustes

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS articulos (
    id SERIAL PRIMARY KEY,
    titulo TEXT NOT NULL,
    resumen TEXT,
    url TEXT UNIQUE NOT NULL,
    fuente TEXT NOT NULL,
    pais TEXT NOT NULL,
    temas JSONB NOT NULL,
    personajes JSONB NOT NULL,
    menciona_sv BOOLEAN NOT NULL DEFAULT FALSE,
    publicado TIMESTAMPTZ NOT NULL,
    recolectado TIMESTAMPTZ NOT NULL,
    via TEXT NOT NULL,
    origen TEXT NOT NULL DEFAULT 'pc'
);
CREATE INDEX IF NOT EXISTS idx_articulos_publicado ON articulos(publicado);
CREATE INDEX IF NOT EXISTS idx_articulos_recolectado ON articulos(recolectado);
CREATE TABLE IF NOT EXISTS noticias (
    id SERIAL PRIMARY KEY,
    mes INTEGER NOT NULL,
    anio INTEGER NOT NULL,
    titulo TEXT NOT NULL,
    resumen TEXT,
    pais TEXT NOT NULL,
    temas JSONB NOT NULL,
    personajes JSONB NOT NULL,
    menciona_sv BOOLEAN NOT NULL DEFAULT FALSE,
    fuentes JSONB NOT NULL,
    publicado TIMESTAMPTZ NOT NULL,
    n_fuentes INTEGER NOT NULL,
    puntaje DOUBLE PRECISION NOT NULL,
    estrellas INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_noticias_periodo ON noticias(anio, mes);
CREATE TABLE IF NOT EXISTS estado_fuentes (
    fuente TEXT PRIMARY KEY,
    pais TEXT,
    tipo TEXT,
    ultima_corrida TIMESTAMPTZ,
    ok BOOLEAN,
    n_articulos INTEGER,
    error TEXT
);
CREATE TABLE IF NOT EXISTS corridas (
    id SERIAL PRIMARY KEY,
    inicio TIMESTAMPTZ NOT NULL,
    fin TIMESTAMPTZ,
    n_articulos_nuevos INTEGER,
    ok BOOLEAN,
    origen TEXT NOT NULL DEFAULT 'pc'
);
CREATE TABLE IF NOT EXISTS enlaces (
    url TEXT PRIMARY KEY,
    activa BOOLEAN,            -- NULL = el sitio bloquea la verificación
    verificado TIMESTAMPTZ NOT NULL
);
CREATE TABLE IF NOT EXISTS guiones (
    id SERIAL PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    creado TIMESTAMPTZ NOT NULL,
    noticias JSONB NOT NULL,
    texto TEXT NOT NULL,
    palabras INTEGER NOT NULL,
    minutos_estimados DOUBLE PRECISION NOT NULL
);
"""

_MES_SV = "to_char((publicado AT TIME ZONE 'UTC') - interval '6 hours', 'YYYY-MM')"  # mes en hora de El Salvador
_CANDADO_CORRIDAS = 4711


def _conectar(db_path=None):
    # keepalives + statement_timeout: si la red se corta en silencio, la consulta falla en ~1-2 min
    # en lugar de quedarse colgada horas (y dejar dos watchers corriendo a la vez).
    dsn = db_path or ajustes.DATABASE_URL
    # Se suman a las opciones que ya traiga la dirección de conexión (no las reemplazan).
    opciones = (conninfo_to_dict(dsn).get("options") or "") + " -c statement_timeout=120000"
    return psycopg.connect(
        dsn, row_factory=dict_row, connect_timeout=15,
        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=3,
        options=opciones.strip(),
    )


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _ts(valor) -> datetime:
    if isinstance(valor, str):
        valor = datetime.fromisoformat(valor)
    return valor.astimezone(timezone.utc)


def _iso(valor):
    return valor.astimezone(timezone.utc).isoformat() if valor is not None else None


def init_db(db_path=None) -> None:
    with _conectar(db_path) as conn:
        conn.execute(_ESQUEMA)


# ---------- Artículos ----------

def guardar_articulos(articulos: list, db_path=None, origen: str = "pc") -> int:
    """Inserta sin duplicar por URL. Un artículo que ya trae origen/recolectado (subido desde la PC) los conserva."""
    if not articulos:
        return 0
    recolectado = _ahora()
    filas = [
        (a["titulo"], a.get("resumen", ""), a["url"], a["fuente"], a["pais"], Jsonb(a.get("temas", [])),
         Jsonb(a.get("personajes", [])), bool(a.get("menciona_sv")), _ts(a["publicado"]),
         _ts(a["recolectado"]) if a.get("recolectado") else recolectado, a["via"], a.get("origen") or origen)
        for a in articulos
    ]
    with _conectar(db_path) as conn:
        # Una tabla temporal y un solo INSERT ... SELECT evita miles de idas y vueltas a Supabase.
        conn.execute("CREATE TEMP TABLE tmp_articulos (LIKE articulos INCLUDING DEFAULTS) ON COMMIT DROP")
        with conn.cursor() as cur:
            with cur.copy(
                "COPY tmp_articulos (titulo, resumen, url, fuente, pais, temas, personajes, menciona_sv, "
                "publicado, recolectado, via, origen) FROM STDIN"
            ) as copia:
                for fila in filas:
                    copia.write_row(fila)
            cur.execute(
                "INSERT INTO articulos (titulo, resumen, url, fuente, pais, temas, personajes, menciona_sv, "
                "publicado, recolectado, via, origen) "
                "SELECT DISTINCT ON (url) titulo, resumen, url, fuente, pais, temas, personajes, menciona_sv, "
                "publicado, recolectado, via, origen FROM tmp_articulos "
                "ON CONFLICT (url) DO NOTHING"
            )
            return cur.rowcount


def _articulo(f: dict) -> dict:
    a = dict(f)
    if "recolectado" in a:
        a["recolectado"] = _iso(a["recolectado"])
    return a


_COLS_ARTICULO = "titulo, resumen, url, fuente, pais, temas, personajes, menciona_sv, publicado, via"


def obtener_articulos(mes: int, anio: int, db_path=None) -> list:
    with _conectar(db_path) as conn:
        filas = conn.execute(
            f"SELECT {_COLS_ARTICULO} FROM articulos WHERE {_MES_SV} = %s", (f"{anio:04d}-{mes:02d}",)
        ).fetchall()
    return [_articulo(f) for f in filas]


def articulos_desde(marca, db_path=None, origen: str = None) -> list:
    """Artículos recolectados después de `marca` (todos si es None), opcionalmente de un origen."""
    condiciones, params = [], []
    if marca:
        condiciones.append("recolectado > %s")
        params.append(_ts(marca))
    if origen:
        condiciones.append("origen = %s")
        params.append(origen)
    where = f"WHERE {' AND '.join(condiciones)}" if condiciones else ""
    with _conectar(db_path) as conn:
        filas = conn.execute(
            f"SELECT {_COLS_ARTICULO}, recolectado, origen FROM articulos {where} ORDER BY recolectado, id", params
        ).fetchall()
    return [_articulo(f) for f in filas]


def podar_articulos(antes_de: str, db_path=None) -> int:
    with _conectar(db_path) as conn:
        return conn.execute("DELETE FROM articulos WHERE publicado < %s", (_ts(antes_de),)).rowcount


# ---------- Noticias ----------

def reemplazar_noticias(mes: int, anio: int, noticias: list, db_path=None) -> None:
    with _conectar(db_path) as conn:
        conn.execute("DELETE FROM noticias WHERE mes = %s AND anio = %s", (mes, anio))
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO noticias (mes, anio, titulo, resumen, pais, temas, personajes, menciona_sv, fuentes, "
                "publicado, n_fuentes, puntaje, estrellas) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                [
                    (mes, anio, x["titulo"], x.get("resumen", ""), x["pais"], Jsonb(x["temas"]),
                     Jsonb(x["personajes"]), bool(x["menciona_sv"]), Jsonb(x["fuentes"]), _ts(x["publicado"]),
                     x["n_fuentes"], x["puntaje"], x["estrellas"])
                    for x in noticias
                ],
            )


def obtener_noticias(mes: int, anio: int, db_path=None) -> list:
    with _conectar(db_path) as conn:
        filas = conn.execute(
            "SELECT id, titulo, resumen, pais, temas, personajes, menciona_sv, fuentes, publicado, n_fuentes, "
            "puntaje, estrellas FROM noticias WHERE mes = %s AND anio = %s", (mes, anio),
        ).fetchall()
    for f in filas:
        f["publicado"] = _iso(f["publicado"])
    return filas


def meses_disponibles(db_path=None) -> list:
    with _conectar(db_path) as conn:
        filas = conn.execute("SELECT DISTINCT anio, mes FROM noticias ORDER BY anio DESC, mes DESC").fetchall()
    return [(f["anio"], f["mes"]) for f in filas]


# ---------- Estado de fuentes ----------

def registrar_estado_fuente(fuente: dict, ok: bool, n: int, error, db_path=None) -> None:
    with _conectar(db_path) as conn:
        conn.execute(
            "INSERT INTO estado_fuentes (fuente, pais, tipo, ultima_corrida, ok, n_articulos, error) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (fuente) DO UPDATE SET pais = EXCLUDED.pais, "
            "tipo = EXCLUDED.tipo, ultima_corrida = EXCLUDED.ultima_corrida, ok = EXCLUDED.ok, "
            "n_articulos = EXCLUDED.n_articulos, error = EXCLUDED.error",
            (fuente["nombre"], fuente["pais"], fuente["tipo"], _ahora(), bool(ok), n, error),
        )


def obtener_estado_fuentes(db_path=None) -> list:
    with _conectar(db_path) as conn:
        filas = conn.execute(
            "SELECT fuente, pais, tipo, ultima_corrida, ok, n_articulos, error FROM estado_fuentes ORDER BY pais, fuente"
        ).fetchall()
    for f in filas:
        f["ultima_corrida"] = _iso(f["ultima_corrida"])
        f["ok"] = bool(f["ok"])
    return filas


# ---------- Corridas ----------

def iniciar_corrida(db_path=None, origen: str = "pc") -> int:
    with _conectar(db_path) as conn:
        return conn.execute(
            "INSERT INTO corridas (inicio, origen) VALUES (%s, %s) RETURNING id", (_ahora(), origen)
        ).fetchone()["id"]


def intentar_iniciar_corrida(origen: str, db_path=None, bloqueo_min: int = 15):
    """Abre una corrida si no hay otra abierta de hace menos de `bloqueo_min`; si la hay, devuelve None."""
    limite = _ahora() - timedelta(minutes=bloqueo_min)
    with _conectar(db_path) as conn:
        conn.execute("SELECT pg_advisory_xact_lock(%s)", (_CANDADO_CORRIDAS,))
        abierta = conn.execute(
            "SELECT 1 FROM corridas WHERE fin IS NULL AND inicio > %s LIMIT 1", (limite,)
        ).fetchone()
        if abierta:
            return None
        return conn.execute(
            "INSERT INTO corridas (inicio, origen) VALUES (%s, %s) RETURNING id", (_ahora(), origen)
        ).fetchone()["id"]


def corrida_en_curso(db_path=None, bloqueo_min: int = 15):
    limite = _ahora() - timedelta(minutes=bloqueo_min)
    with _conectar(db_path) as conn:
        fila = conn.execute(
            "SELECT inicio, origen FROM corridas WHERE fin IS NULL AND inicio > %s ORDER BY id DESC LIMIT 1", (limite,)
        ).fetchone()
    if not fila:
        return None
    return {"inicio": _iso(fila["inicio"]), "origen": fila["origen"]}


def finalizar_corrida(corrida_id: int, n_nuevos: int, ok: bool, db_path=None) -> None:
    with _conectar(db_path) as conn:
        conn.execute(
            "UPDATE corridas SET fin = %s, n_articulos_nuevos = %s, ok = %s WHERE id = %s",
            (_ahora(), n_nuevos, bool(ok), corrida_id),
        )


def ultima_corrida(db_path=None):
    with _conectar(db_path) as conn:
        fila = conn.execute(
            "SELECT inicio, fin, n_articulos_nuevos, origen FROM corridas WHERE fin IS NOT NULL AND ok "
            "ORDER BY fin DESC LIMIT 1"
        ).fetchone()
    if not fila:
        return None
    return {**fila, "inicio": _iso(fila["inicio"]), "fin": _iso(fila["fin"])}


# ---------- Enlaces ----------

def guardar_estado_enlaces(estados: dict, db_path=None, verificado: str = None) -> None:
    """estados: url → True / False / None (desconocido). `verificado` permite conservar la fecha original."""
    if not estados:
        return
    cuando = _ts(verificado) if verificado else _ahora()
    with _conectar(db_path) as conn:
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO enlaces (url, activa, verificado) VALUES (%s, %s, %s) "
                "ON CONFLICT (url) DO UPDATE SET activa = EXCLUDED.activa, verificado = EXCLUDED.verificado",
                [(u, v, cuando) for u, v in estados.items()],
            )


def obtener_estado_enlaces(urls: list, db_path=None) -> dict:
    if not urls:
        return {}
    with _conectar(db_path) as conn:
        filas = conn.execute(
            "SELECT url, activa FROM enlaces WHERE activa IS NOT NULL AND url = ANY(%s)", (list(dict.fromkeys(urls)),)
        ).fetchall()
    return {f["url"]: f["activa"] for f in filas}


def enlaces_desde(marca, db_path=None) -> dict:
    """url → (activa, verificado) de los enlaces verificados después de `marca` (todos si es None)."""
    with _conectar(db_path) as conn:
        if marca:
            filas = conn.execute("SELECT url, activa, verificado FROM enlaces WHERE verificado > %s", (_ts(marca),))
        else:
            filas = conn.execute("SELECT url, activa, verificado FROM enlaces")
        return {f["url"]: (f["activa"], _iso(f["verificado"])) for f in filas.fetchall()}


def urls_por_verificar(mes_actual: tuple, limite: int, db_path=None, dias: int = 7) -> list:
    """Enlaces de meses anteriores sin verificar o verificados hace más de `dias`; sin redirecciones de Google News."""
    mes, anio = mes_actual
    with _conectar(db_path) as conn:
        filas = conn.execute(
            "SELECT u.url FROM (SELECT f->>'url' AS url, n.anio, n.mes FROM noticias n, "
            "jsonb_array_elements(n.fuentes) f WHERE NOT (n.mes = %s AND n.anio = %s)) u "
            "LEFT JOIN enlaces e ON e.url = u.url "
            "WHERE u.url NOT LIKE 'https://news.google.com/%%' AND (e.url IS NULL OR e.verificado < %s) "
            "GROUP BY u.url ORDER BY MAX(u.anio) DESC, MAX(u.mes) DESC, u.url LIMIT %s",
            (mes, anio, _ahora() - timedelta(days=dias), limite),
        ).fetchall()
    return [f["url"] for f in filas]


# ---------- Guiones ----------

def guardar_guion(noticias: list, texto: str, palabras: int, minutos: float, db_path=None) -> int:
    with _conectar(db_path) as conn:
        return conn.execute(
            "INSERT INTO guiones (uid, creado, noticias, texto, palabras, minutos_estimados) "
            "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (uuid.uuid4().hex, _ahora(), Jsonb(noticias), texto, palabras, minutos),
        ).fetchone()["id"]


def listar_guiones(db_path=None) -> list:
    with _conectar(db_path) as conn:
        filas = conn.execute(
            "SELECT id, uid, creado, palabras, minutos_estimados, noticias FROM guiones ORDER BY creado DESC, id DESC"
        ).fetchall()
    return [
        {"id": f["id"], "uid": f["uid"], "creado": _iso(f["creado"]), "palabras": f["palabras"],
         "minutos": f["minutos_estimados"], "titulos": [x["titulo"] for x in f["noticias"]]}
        for f in filas
    ]


def obtener_guion(guion_id: int, db_path=None):
    with _conectar(db_path) as conn:
        fila = conn.execute(
            "SELECT id, uid, creado, noticias, texto, palabras, minutos_estimados FROM guiones WHERE id = %s",
            (guion_id,),
        ).fetchone()
    if not fila:
        return None
    fila["creado"] = _iso(fila["creado"])
    fila["minutos"] = fila.pop("minutos_estimados")
    return fila


def uids_guiones(db_path=None) -> set:
    with _conectar(db_path) as conn:
        return {f["uid"] for f in conn.execute("SELECT uid FROM guiones").fetchall()}


def guiones_por_uid(uids: set, db_path=None) -> list:
    if not uids:
        return []
    with _conectar(db_path) as conn:
        filas = conn.execute(
            "SELECT uid, creado, noticias, texto, palabras, minutos_estimados FROM guiones WHERE uid = ANY(%s)",
            (list(uids),),
        ).fetchall()
    return [
        {"uid": f["uid"], "creado": _iso(f["creado"]), "noticias": f["noticias"], "texto": f["texto"],
         "palabras": f["palabras"], "minutos": f["minutos_estimados"]}
        for f in filas
    ]


def insertar_guiones(guiones: list, db_path=None) -> int:
    """Inserta guiones de otra base conservando uid y fecha; ignora los que ya existen."""
    nuevos = 0
    with _conectar(db_path) as conn:
        for g in guiones:
            nuevos += conn.execute(
                "INSERT INTO guiones (uid, creado, noticias, texto, palabras, minutos_estimados) "
                "VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT (uid) DO NOTHING",
                (g["uid"], _ts(g["creado"]), Jsonb(g["noticias"]), g["texto"], g["palabras"], g["minutos"]),
            ).rowcount
    return nuevos


def ultimo_intento(db_path=None):
    """Inicio de la última corrida, haya terminado bien, mal o siga abierta."""
    with _conectar(db_path) as conn:
        fila = conn.execute("SELECT inicio FROM corridas ORDER BY inicio DESC LIMIT 1").fetchone()
    return _iso(fila["inicio"]) if fila else None
