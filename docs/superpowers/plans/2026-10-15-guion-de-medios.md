# Guion de Medios · Centroamérica — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portal Flask local que recolecta cada hora noticias de medios centroamericanos (foco El Salvador), las filtra con botones de check por país/tema/personaje y genera con Gemini un "Guion de medios" de noticiero de 3–5 min.

**Architecture:** Un watcher (tarea programada de Windows, cada hora) recolecta por RSS, Google News y lectura web; clasifica, agrupa por país, puntúa y guarda en SQLite local. El portal Flask (waitress, `127.0.0.1:5050`) solo lee SQLite. Se copian y adaptan módulos del proyecto Flask "Monitor de Noticias Ecuador" (`G:\Mi unidad\Proyect Claude\Monitor de Noticias Ecuador`, en adelante **ECU**).

**Tech Stack:** Python 3.12, Flask 3, SQLite, feedparser, requests, beautifulsoup4, python-docx, openpyxl, reportlab, google-genai, python-dotenv, waitress, pytest.

**Spec:** `docs/superpowers/specs/2026-10-15-guion-de-medios-design.md`

## Global Constraints

- Raíz del proyecto: `G:\Mi unidad\Proyect Claude\Guion de Medios`. Todo el código en la raíz (sin paquete `src/`), igual que ECU.
- Datos fuera de Google Drive: `DATA_DIR` = env `DATA_DIR` o `%LOCALAPPDATA%\GuionDeMedios`. Ahí: `guion.db`, `logs\`, `watcher.lock`, `venv\`.
- Python del venv: `$LOCALAPPDATA/GuionDeMedios/venv/Scripts/python.exe` (en adelante **`PY`**). Tests: `PY -m pytest -q`.
- Portal escucha **solo** en `127.0.0.1`, puerto env `PORT` (default `5050`). Sin login.
- Códigos de país: `SV GT HN NI CR PA REG`; nombres: El Salvador, Guatemala, Honduras, Nicaragua, Costa Rica, Panamá, Regional (orden fijo).
- Temas (orden fijo): Economía, Inversión, Política, Coyuntura, Social, Mujeres, Inclusión, Seguridad, Salud, Internacional, Deportes, Cultura, Turismo, Medio Ambiente, Otras.
- Estado inicial UI: países `{SV}`; temas `{Economía, Inversión, Política, Coyuntura, Social}`; personajes `{}`.
- Fuentes: timeout 15 s, User-Agent de navegador, máx. 8 en paralelo, fallo de una fuente = se omite.
- Prioridad de deduplicación: `rss` > `web` > `google_news`.
- Agrupación difflib umbral `0.70`, **solo dentro del mismo país**. Puntaje `(n_fuentes × 40) + (recencia × 60)`, 1–5 estrellas (fórmulas de ECU `scorer.py`).
- Gemini: `GEMINI_MODEL` (default `gemini-2.5-flash`) para el guion; `GEMINI_MODEL_VALORAR` (default `gemini-2.5-flash-lite`) para valorar. Sin clave → HTTP 503; otro error → 500.
- Guion: 1 a 12 noticias; minutos = palabras / 150 (1 decimal).
- Todo texto visible para el usuario, en español.
- Commits terminan con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Tildes y mayúsculas en palabras clave** ("economia" vs "Economía", "BUKELE"): la clasificación debe coincidir igual → test en Task 2.
2. **Títulos de Google News con sufijo " - Medio"** y URL de redirección: el sufijo se quita y el medio sale de `source`, para que agrupe con la misma nota del RSS directo → test en Task 4.
3. **Resúmenes RSS con HTML** (`<p>`, `<img>`, `&nbsp;`): se limpian antes de clasificar y mostrar → test en Task 4.
4. **Fechas ausentes, futuras o sin zona horaria** en feeds: ausente → ahora, futura → ahora, naive → UTC → test en Task 4.
5. **Selección que sobrevive al recálculo horario y al cambio de filtros**: la clave de selección es `pais|titulo`, no el `id` de BD (que cambia en cada corrida) → verificación manual en Task 10, y el guion recibe los objetos completos (test en Task 9).

---

## Estructura de archivos

```
ajustes.py              rutas DATA_DIR/DB/LOG/LOCK, PORT, modelos Gemini (lee .env)
config/__init__.py
config/paises.py        PAISES, PAIS_KEYWORDS, EL_SALVADOR_KEYWORDS
config/temas.py         TEMAS (dict ordenado tema → palabras clave)
config/personajes.py    PERSONAJES (dict nombre → variantes)
config/fuentes.py       FUENTES (lista de dicts) + consultas_google_news()
config/guion_instrucciones.md
texto.py                normalizar(), limpiar_html()
classifier.py           clasificar(articulo) → articulo enriquecido
collectors/__init__.py  recolectar(fuente) → (articulos, error)
collectors/rss.py
collectors/google_news.py
collectors/web.py
noticias.py             construir_noticias(), filtrar(), ordenar()  (agrupa + puntúa)
clusterer.py, scorer.py copiados de ECU con claves en español
store.py                SQLite
watcher.py              corrida + bloqueo + CLI
ia.py                   cliente Gemini compartido, ConfigError
valorador.py, guionista.py
exporter.py             noticias Word/Excel/PDF + guion Word/PDF
link_checker.py         copiado de ECU sin cambios
app.py                  Flask
serve.py                waitress
templates/index.html, templates/fuentes.html
static/app.js, static/style.css
scripts/verificar_fuentes.py, scripts/instalar.ps1
tests/...
```

**Forma de un artículo** (dict, usada en todo el plan):
`{titulo, resumen, url, fuente, pais, publicado: datetime UTC aware, via: "rss"|"web"|"google_news"}`; tras `clasificar` añade `temas: list[str]`, `personajes: list[str]`, `menciona_sv: bool`.

**Forma de una noticia** (lo que devuelve la API):
`{id, titulo, resumen, pais, temas, personajes, menciona_sv, fuentes: [{nombre, url}], publicado: str ISO, n_fuentes, puntaje, estrellas}`.

**Forma de una fuente:** `{nombre, pais, tipo: "rss"|"google_news"|"web", url, activa: bool, selectores?: {item, titulo, enlace, resumen?, fecha?}}`.

---

### Task 1: Esqueleto, entorno y utilidades de texto

**Files:**
- Create: `requirements.txt`, `.env.example`, `ajustes.py`, `texto.py`, `config/__init__.py`, `collectors/__init__.py` (vacío por ahora), `tests/__init__.py`, `tests/conftest.py`, `tests/test_texto.py`, `tests/test_ajustes.py`
- Copy desde ECU sin cambios: `link_checker.py`, `tests/test_link_checker.py`

**Interfaces:**
- Produces: `ajustes.DATA_DIR: Path`, `ajustes.DB_PATH`, `ajustes.LOG_DIR`, `ajustes.LOCK_PATH`, `ajustes.PORT: int`, `ajustes.GEMINI_MODEL`, `ajustes.GEMINI_MODEL_VALORAR`; `texto.normalizar(s: str) -> str` (minúsculas, sin tildes vía `unicodedata` NFD, conserva ñ→n), `texto.limpiar_html(s: str) -> str` (quita etiquetas, decodifica entidades, colapsa espacios); fixture pytest `db_path(tmp_path)` → `tmp_path / "t.db"`.

- [ ] **Step 1: Crear venv e instalar dependencias**

`requirements.txt`: `flask==3.0.3`, `feedparser==6.0.11`, `requests>=2.31.0`, `beautifulsoup4>=4.12`, `python-docx==1.1.2`, `openpyxl==3.1.3`, `reportlab==4.2.2`, `google-genai>=2.0.0`, `python-dotenv>=1.0.0`, `waitress>=3.0`, `pytest==8.2.2`.

Run: `python -m venv "$LOCALAPPDATA/GuionDeMedios/venv" && PY -m pip install -r requirements.txt`
Expected: instalación sin errores. `.env.example` con `GEMINI_API_KEY=`, `GEMINI_MODEL=gemini-2.5-flash`, `GEMINI_MODEL_VALORAR=gemini-2.5-flash-lite`, `PORT=5050`, `DATA_DIR=`.

- [ ] **Step 2: Escribir tests que fallan**

```python
# tests/test_texto.py
def test_normalizar_quita_tildes_y_mayusculas():
    assert normalizar("Economía BUKELE Inversión") == "economia bukele inversion"
def test_limpiar_html():
    assert limpiar_html('<p>Hola&nbsp;<b>mundo</b></p><img src="x">') == "Hola mundo"
# tests/test_ajustes.py
def test_data_dir_respeta_env(monkeypatch, tmp_path):
    monkeypatch.setenv("DATA_DIR", str(tmp_path)); importlib.reload(ajustes)
    assert ajustes.DB_PATH == tmp_path / "guion.db"
```

- [ ] **Step 3: Verificar que fallan** — Run: `PY -m pytest -q` → Expected: FAIL (ImportError).
- [ ] **Step 4: Implementar `ajustes.py` y `texto.py`** — `ajustes` carga `.env` de la raíz con `load_dotenv`, crea `DATA_DIR` y `LOG_DIR` con `mkdir(parents=True, exist_ok=True)`.
- [ ] **Step 5: Verificar** — Run: `PY -m pytest -q` → Expected: todos PASS (incluido `test_link_checker.py`).
- [ ] **Step 6: Commit** — `git add -A && git commit -m "chore: esqueleto, entorno y utilidades de texto"`

---

### Task 2: Configuración de países, temas, personajes y clasificador

**Files:**
- Create: `config/paises.py`, `config/temas.py`, `config/personajes.py`, `classifier.py`, `tests/test_classifier.py`

**Interfaces:**
- Consumes: `texto.normalizar`.
- Produces: `PAISES: dict[str,str]` (código → nombre, orden de Global Constraints); `PAIS_KEYWORDS: dict[str, list[str]]` (SV..PA, p. ej. GT: guatemala, guatemalteco, arévalo; PA: panamá, panameño, canal de panamá…); `EL_SALVADOR_KEYWORDS` (lista de ECU `classifier.py` + "salvadoreños"); `TEMAS: dict[str, list[str]]` sin "Otras"; `PERSONAJES: dict[str, list[str]]`; `clasificar(articulo: dict) -> dict` (devuelve copia con `temas`, `personajes`, `menciona_sv` y, si `pais == "REG"`, el país detectado).

Palabras clave mínimas por tema (se comparan normalizadas, como subcadena):
- Economía: economía, inflación, dólar, banco, impuestos, presupuesto, pib, deuda, remesas, exportaciones, importaciones, aranceles, bitcoin, empleo, salario, canasta básica, maquila, cafta
- Inversión: inversión, inversionista, inversión extranjera, proyecto de inversión, bonos, bolsa de valores, zona franca, concesión, licitación, emprendimiento, startup
- Política: gobierno, presidente, asamblea legislativa, congreso, diputado, ministro, decreto, elecciones, partido, candidato, oposición, nuevas ideas, arena, fmln
- Coyuntura: fmi, crisis, reforma, régimen de excepción, deuda pública, calificación de riesgo, déficit, subsidio, ley de presupuesto, medidas económicas
- Social: pobreza, educación, vivienda, comunidad, migración, desempleo, bienestar, protesta, derechos humanos
- Mujeres: mujer, mujeres, género, feminicidio, igualdad, violencia contra la mujer, lideresa, maternidad, brecha salarial
- Inclusión: inclusión, discapacidad, accesibilidad, lgbti, indígena, afrodescendiente, adulto mayor, diversidad
- Seguridad: policía, pandilla, crimen, homicidio, narcotráfico, detenido, fiscalía, cárcel, seguridad
- Salud: salud, hospital, médico, vacuna, enfermedad, dengue, paciente, minsal, seguro social
- Internacional: estados unidos, onu, embajada, cancillería, diplomacia, tratado, oea, sica, trump
- Deportes: fútbol, selección, liga, gol, torneo, deporte, atleta, concacaf, mundial
- Cultura: arte, música, cine, festival, patrimonio, teatro, literatura, cultura, concierto
- Turismo: turismo, turista, hotel, playa, surf city, vuelo, aerolínea, destino, crucero
- Medio Ambiente: clima, lluvias, tormenta, sequía, ambiental, contaminación, deforestación, volcán

Personajes (nombre → variantes): Nayib Bukele → [nayib bukele, bukele]; Félix Ulloa → [félix ulloa]; Gustavo Villatoro → [gustavo villatoro, ministro villatoro]; Alexandra Hill Tinoco → [alexandra hill]; Jerson Posada → [jerson posada]; Ernesto Castro → [ernesto castro]; Christian Guevara → [christian guevara]; Claudia Ortiz → [claudia ortiz]; Marcela Villatoro → [marcela villatoro]; FMLN → [fmln, farabundo martí]. (Cargos y variantes se verifican en Task 6.)

- [ ] **Step 1: Escribir tests que fallan**

```python
def art(t, r="", pais="SV"): return {"titulo": t, "resumen": r, "pais": pais}
def test_multitema():
    a = clasificar(art("Programa de créditos para mujeres emprendedoras", "inversión de BANDESAL"))
    assert {"Mujeres", "Inversión"} <= set(a["temas"])
def test_sin_tema_es_otras():
    assert clasificar(art("Hoy amaneció nublado sin más"))["temas"] == ["Otras"]
def test_tildes_y_mayusculas():
    assert "Economía" in clasificar(art("LA ECONOMIA crece"))["temas"]
def test_personaje_por_variante():
    assert clasificar(art("Bukele inaugura obra"))["personajes"] == ["Nayib Bukele"]
def test_menciona_sv_solo_fuera_de_sv():
    assert clasificar(art("Acuerdo con El Salvador", pais="GT"))["menciona_sv"] is True
    assert clasificar(art("Acuerdo con El Salvador", pais="SV"))["menciona_sv"] is False
def test_regional_asigna_pais_mencionado():
    assert clasificar(art("Exportaciones de Guatemala crecen", pais="REG"))["pais"] == "GT"
    assert clasificar(art("Exportaciones del istmo crecen", pais="REG"))["pais"] == "REG"
def test_temas_en_orden_de_config():
    t = clasificar(art("Gobierno y economía", ""))["temas"]
    assert t == ["Economía", "Política"]
def test_no_muta_entrada():
    a = art("Bukele"); clasificar(a); assert "temas" not in a
```

- [ ] **Step 2: Verificar que fallan** — `PY -m pytest tests/test_classifier.py -q` → FAIL.
- [ ] **Step 3: Implementar config y `clasificar`** — texto = `normalizar(titulo + " " + resumen)`; las palabras clave también se normalizan una vez al importar. Regional: país con más coincidencias de `PAIS_KEYWORDS`; empate o cero → `REG`.
- [ ] **Step 4: Verificar** — `PY -m pytest tests/test_classifier.py -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: países, temas, personajes y clasificador multitema"`

---

### Task 3: Almacenamiento SQLite

**Files:**
- Create: `store.py`, `tests/test_store.py`

**Interfaces:**
- Consumes: `ajustes.DB_PATH` (default de todos los `db_path=None`).
- Produces (todas aceptan `db_path: Path = None`):
  - `init_db()` — tablas `articulos`, `noticias`, `estado_fuentes` (PK `fuente`), `corridas`, `guiones` según el spec; JSON en columnas `temas`, `personajes`, `fuentes`, `noticias`; fechas como ISO UTC.
  - `guardar_articulos(articulos: list[dict]) -> int` — `INSERT OR IGNORE` por `url`; devuelve nuevos.
  - `obtener_articulos(mes: int, anio: int) -> list[dict]` — `publicado` vuelve como datetime aware.
  - `reemplazar_noticias(mes: int, anio: int, noticias: list[dict]) -> None` — borra y reinserta ese mes en una transacción.
  - `obtener_noticias(mes: int, anio: int) -> list[dict]` — forma "noticia".
  - `meses_disponibles() -> list[tuple[int,int]]` — `(anio, mes)` desc.
  - `registrar_estado_fuente(fuente: dict, ok: bool, n: int, error: str|None) -> None` — upsert.
  - `obtener_estado_fuentes() -> list[dict]` — `{fuente, pais, tipo, ultima_corrida, ok, n_articulos, error}` ordenado por país y nombre.
  - `iniciar_corrida() -> int`, `finalizar_corrida(id: int, n_nuevos: int, ok: bool) -> None`, `ultima_corrida() -> dict|None` (la última **finalizada** con `ok`: `{inicio, fin, n_articulos_nuevos}`).
  - `guardar_guion(noticias: list[dict], texto: str, palabras: int, minutos: float) -> int`, `listar_guiones() -> list[dict]` (`{id, creado, palabras, minutos, titulos: [..]}` desc), `obtener_guion(id: int) -> dict|None`.

- [ ] **Step 1: Escribir tests que fallan** — `test_dedup_por_url` (guardar 2 veces el mismo → `1` y luego `0`), `test_articulos_por_mes` (uno en sep y otro en oct, `obtener_articulos(10, 2026)` devuelve 1 con `publicado.tzinfo` no nulo y `temas` como lista), `test_reemplazar_noticias_solo_ese_mes` (septiembre intacto tras reemplazar octubre), `test_meses_disponibles_desc`, `test_estado_fuente_upsert` (dos registros de la misma fuente → 1 fila con el último `ok`), `test_ultima_corrida_ignora_en_curso`, `test_guion_roundtrip` (`listar_guiones()[0]["titulos"] == ["A"]`).
- [ ] **Step 2: Verificar que fallan** — `PY -m pytest tests/test_store.py -q` → FAIL.
- [ ] **Step 3: Implementar `store.py`** — basado en ECU `store.py` (WAL, `row_factory`), con conexión por llamada.
- [ ] **Step 4: Verificar** — PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: almacenamiento SQLite"`

---

### Task 4: Colectores RSS y Google News

**Files:**
- Create: `collectors/rss.py`, `collectors/google_news.py`, `collectors/__init__.py`, `config/fuentes.py`, `tests/fixtures/rss_simple.xml`, `tests/fixtures/google_news.xml`, `tests/test_collectors.py`

**Interfaces:**
- Consumes: `texto.limpiar_html`, `config.temas`, `config.personajes`.
- Produces:
  - `collectors.HEADERS` (User-Agent Chrome de escritorio), `collectors.TIMEOUT = 15`.
  - `collectors.descargar(url: str) -> bytes` — `requests.get` con HEADERS/TIMEOUT, `raise_for_status`.
  - `rss.parsear(contenido: bytes, fuente: dict) -> list[dict]` y `google_news.parsear(contenido: bytes, fuente: dict) -> list[dict]` — devuelven artículos (forma del plan, `via` según tipo).
  - `collectors.recolectar(fuente: dict) -> tuple[list[dict], str|None]` — despacha por `tipo` (`web` se agrega en Task 5); captura toda excepción y devuelve `([], "mensaje")`.
  - `config.fuentes.FUENTES: list[dict]` (lista inicial del spec con las URL candidatas de abajo, `tipo="rss"`, `activa=True`) y `consultas_google_news() -> list[dict]`.
- Fechas: usar `published_parsed` o `updated_parsed`; ausente o futura → `datetime.now(UTC)`.
- Google News: el título viene como `"Titular - Medio"`, se quita el sufijo `" - " + source.title`; `fuente = entry.source.title`; si no hay `source`, el nombre de la consulta.
- `consultas_google_news()`: por cada país `SV GT HN NI CR PA` y cada grupo `{"Economía": "economía OR inversión OR remesas OR exportaciones", "Política": "política OR gobierno OR asamblea OR congreso", "Coyuntura": "FMI OR deuda OR presupuesto OR reforma", "Social": "mujeres OR inclusión OR género OR discapacidad"}` → `{nombre: "Google News · SV · Economía", pais, tipo: "google_news", activa: True, url}`, más una por personaje (`'"Nayib Bukele"'`, país SV). URL: `https://news.google.com/rss/search?q=<quote(consulta + " when:1d")>&hl=es-419&gl=<PAIS>&ceid=<PAIS>:es-419`.

URL candidatas de `FUENTES` (se verifican en Task 6):
SV — La Prensa Gráfica `https://www.laprensagrafica.com/arc/outboundfeeds/rss/?outputType=xml`; El Diario de Hoy `https://www.elsalvador.com/feed/`; Diario El Mundo `https://diario.elmundo.sv/feed`; Diario Co Latino `https://www.diariocolatino.com/feed/`; El Faro `https://elfaro.net/rss`; Diario El Salvador `https://diarioelsalvador.com/feed/`; La Página `https://www.lapagina.com.sv/feed/`; Revista Factum `https://www.revistafactum.com/feed/`; GatoEncerrado `https://gatoencerrado.news/feed/`.
GT — Prensa Libre `https://www.prensalibre.com/feed/`; Soy502 `https://www.soy502.com/rss`; República `https://republica.gt/feed`; La Hora `https://lahora.gt/feed/`; Plaza Pública `https://www.plazapublica.com.gt/rss.xml`; Agencia Ocote `https://www.agenciaocote.com/feed/`.
HN — La Prensa `https://www.laprensa.hn/rss`; El Heraldo `https://www.elheraldo.hn/rss`; Proceso Digital `https://proceso.hn/feed/`; La Tribuna `https://www.latribuna.hn/feed/`; Criterio.hn `https://criterio.hn/feed/`; Contracorriente `https://contracorriente.red/feed/`.
NI — La Prensa `https://www.laprensani.com/feed/`; Confidencial `https://confidencial.digital/feed/`; 100% Noticias `https://100noticias.com.ni/feed/`; Artículo 66 `https://www.articulo66.com/feed/`; Divergentes `https://www.divergentes.com/feed/`; El 19 Digital `https://www.el19digital.com/rss`.
CR — La Nación `https://www.nacion.com/arc/outboundfeeds/rss/?outputType=xml`; CRHoy `https://www.crhoy.com/feed/`; El Financiero `https://www.elfinancierocr.com/arc/outboundfeeds/rss/?outputType=xml`; Teletica `https://www.teletica.com/rss`; Delfino `https://delfino.cr/feed`; Semanario Universidad `https://semanariouniversidad.com/feed/`.
PA — La Prensa `https://www.prensa.com/arc/outboundfeeds/rss/?outputType=xml`; La Estrella de Panamá `https://www.laestrella.com.pa/rss`; Panamá América `https://www.panamaamerica.com.pa/rss.xml`; TVN Noticias `https://www.tvn-2.com/rss`; Telemetro `https://www.telemetro.com/rss`.
REG — Estrategia & Negocios `https://www.estrategiaynegocios.net/rss`; Revista Summa `https://revistasumma.com/feed/`; Forbes Centroamérica `https://forbescentroamerica.com/feed`.

- [ ] **Step 1: Crear fixtures** — `rss_simple.xml`: 3 items (uno con `<description>` HTML `<p>Texto&nbsp;<img src="a.jpg"></p>`, uno sin fecha y uno con fecha en 2030). `google_news.xml`: 2 items con `<source url="...">La Prensa Gráfica</source>` y título `"Remesas crecen 5% - La Prensa Gráfica"`.
- [ ] **Step 2: Escribir tests que fallan**

```python
F = {"nombre": "Medio X", "pais": "SV", "tipo": "rss", "url": "u", "activa": True}
def test_rss_campos_y_limpieza():
    a = rss.parsear(leer("rss_simple.xml"), F)
    assert len(a) == 3 and a[0]["fuente"] == "Medio X" and a[0]["via"] == "rss"
    assert a[0]["resumen"] == "Texto"
def test_rss_fechas_ausente_y_futura_son_ahora():
    a = rss.parsear(leer("rss_simple.xml"), F); ahora = datetime.now(timezone.utc)
    assert all(x["publicado"] <= ahora and x["publicado"].tzinfo for x in a)
def test_google_news_quita_sufijo_y_usa_source():
    a = google_news.parsear(leer("google_news.xml"), {**F, "tipo": "google_news"})
    assert a[0]["titulo"] == "Remesas crecen 5%" and a[0]["fuente"] == "La Prensa Gráfica"
    assert a[0]["via"] == "google_news"
def test_recolectar_fuente_caida(monkeypatch):
    monkeypatch.setattr(collectors, "descargar", lambda u: (_ for _ in ()).throw(requests.Timeout("t")))
    assert collectors.recolectar(F) == ([], "t")
def test_consultas_google_news():
    q = consultas_google_news()
    assert any(c["nombre"] == "Google News · SV · Economía" for c in q)
    assert all("ceid=" in c["url"] and c["tipo"] == "google_news" for c in q)
    assert any("Nayib+Bukele" in c["url"] or "Nayib%20Bukele" in c["url"] for c in q)
def test_fuentes_paises_validos():
    assert {f["pais"] for f in FUENTES} == {"SV","GT","HN","NI","CR","PA","REG"}
```

- [ ] **Step 3: Verificar que fallan** — `PY -m pytest tests/test_collectors.py -q` → FAIL.
- [ ] **Step 4: Implementar colectores y `config/fuentes.py`** — `feedparser.parse(contenido)`; en `recolectar` el error devuelto es `str(exc)[:200]`.
- [ ] **Step 5: Verificar** — PASS.
- [ ] **Step 6: Commit** — `git commit -m "feat: colectores RSS y Google News con lista inicial de fuentes"`

---

### Task 5: Colector de lectura web

**Files:**
- Create: `collectors/web.py`, `tests/fixtures/portada.html`, `tests/test_web.py`
- Modify: `collectors/__init__.py` (despachar `tipo="web"`)

**Interfaces:**
- Consumes: `collectors.descargar`, `texto.limpiar_html`.
- Produces: `web.parsear(contenido: bytes, fuente: dict) -> list[dict]` — BeautifulSoup `html.parser`; para cada `select(selectores["item"])` toma `titulo` (texto de `select_one(selectores["titulo"])`), `enlace` (`href` de `select_one(selectores["enlace"])` resuelto con `urljoin(fuente["url"], href)`), `resumen` opcional y `fecha` opcional (atributo `datetime` o texto ISO; si falla → ahora). Descarta items sin título o sin enlace y deduplica por URL dentro de la página.

- [ ] **Step 1: Fixture** — `portada.html` con 3 `<article class="nota">`: uno completo con `<time datetime="2026-10-14T10:00:00-06:00">`, uno con enlace relativo `/economia/nota-2` y sin fecha, uno sin `<a>`.
- [ ] **Step 2: Escribir tests que fallan** — `test_web_extrae_validos` (2 artículos, `via == "web"`), `test_web_enlace_relativo_absoluto` (`url == "https://medio.sv/economia/nota-2"` con `fuente["url"] = "https://medio.sv/"`), `test_web_fecha_con_zona_a_utc` (`publicado == datetime(2026,10,14,16,0,tzinfo=UTC)`), `test_recolectar_despacha_web` (monkeypatch `descargar` → contenido del fixture).
- [ ] **Step 3: Verificar que fallan** — FAIL.
- [ ] **Step 4: Implementar** — `requirements.txt` ya incluye bs4.
- [ ] **Step 5: Verificar** — `PY -m pytest -q` → PASS.
- [ ] **Step 6: Commit** — `git commit -m "feat: colector de lectura web por selectores"`

---

### Task 6: Verificación real de fuentes y personajes (con red)

**Files:**
- Create: `scripts/verificar_fuentes.py`
- Modify: `config/fuentes.py`, `config/personajes.py`

**Interfaces:**
- Consumes: `collectors.recolectar`, `config.fuentes.FUENTES`, `consultas_google_news()`.
- Produces: `FUENTES` verificada. `scripts/verificar_fuentes.py [--todas]` imprime una tabla `país | nombre | tipo | ok | n | error`, con `--todas` incluye las consultas de Google News, y devuelve exit 0.

- [ ] **Step 1: Escribir y ejecutar el script** — Run: `PY scripts/verificar_fuentes.py --todas` → Expected: tabla impresa.
- [ ] **Step 2: Reparar cada fuente con `ok=False` o `n=0`**, en este orden: (a) probar variantes `/feed`, `/feed/`, `/rss`, `/rss.xml`, `/arc/outboundfeeds/rss/?outputType=xml` o el enlace `<link rel="alternate" type="application/rss+xml">` de su portada; (b) si no hay RSS, pasarla a `tipo="web"` con `selectores` de su portada o sección de economía o política; (c) si nada funciona, `activa=False` con un comentario `# 2026-10-XX: sin RSS ni HTML legible`.
- [ ] **Step 3: Verificar el criterio de cobertura** — Run de nuevo. Expected: El Salvador con ≥5 fuentes directas (`rss` o `web`) activas con `n>0`; los demás países con ≥2; todas las consultas de Google News con `n>0` o sin error (puede haber 0 noticias en `when:1d`).
- [ ] **Step 4: Verificar personajes** — con búsquedas de Google News y noticias recientes, confirmar el cargo actual de cada personaje de `config/personajes.py`; quitar o reemplazar a quien ya no tenga alta mención y anotar el cargo como comentario. Agregar variantes frecuentes (p. ej. "presidente Bukele").
- [ ] **Step 5: Verificar** — `PY -m pytest -q` → PASS (`test_fuentes_paises_validos` sigue en verde).
- [ ] **Step 6: Commit** — `git commit -m "chore: fuentes y personajes verificados contra la red"`

---

### Task 7: Agrupación y puntaje por país

**Files:**
- Create: `clusterer.py`, `scorer.py` (copiados de ECU y adaptados a claves en español: `titulo`, `fuente`, `publicado`), `noticias.py`, `tests/test_noticias.py`, `tests/test_scorer.py` (adaptado del de ECU)

**Interfaces:**
- Consumes: forma de artículo clasificado.
- Produces:
  - `clusterer.agrupar(articulos: list) -> list[list]` (algoritmo ECU, umbral 0.70).
  - `scorer.puntuar(cluster) -> float`, `scorer.estrellas(puntaje, maximo) -> int`, `scorer.factor_recencia(dt) -> float` (valores de ECU).
  - `noticias.construir_noticias(articulos: list) -> list[dict]` — agrupa **por país**; por cluster: título más largo, resumen más largo, `temas` = unión en el orden de `TEMAS` (sin "Otras" si hay otro tema; `["Otras"]` si queda vacío), `personajes` = unión en el orden de `PERSONAJES`, `menciona_sv` = any, `fuentes` únicas por nombre, `n_fuentes`, `puntaje`, `estrellas` (relativo al máximo de toda la corrida), `publicado` = más reciente en ISO.
  - `noticias.filtrar(noticias, paises: set, temas: set, personajes: set) -> list` — regla del spec (personajes vacío = no filtra).
  - `noticias.ordenar(noticias, orden: str) -> list` — `"importancia"` (puntaje desc, luego fecha desc) o `"recientes"` (fecha desc).

- [ ] **Step 1: Escribir tests que fallan**

```python
def test_no_agrupa_entre_paises():
    a = [mk("Sube el precio del café", "SV"), mk("Sube el precio del café", "GT")]
    assert len(construir_noticias(a)) == 2
def test_agrupa_mismo_pais_y_cuenta_fuentes():
    a = [mk("Remesas crecen 5% en septiembre", "SV", fuente="LPG"),
         mk("Remesas crecen 5% en septiembre 2026", "SV", fuente="EDH")]
    n = construir_noticias(a); assert len(n) == 1 and n[0]["n_fuentes"] == 2
def test_union_de_temas_sin_otras():
    a = [mk("X igual", "SV", temas=["Otras"]), mk("X igual!", "SV", temas=["Mujeres"])]
    assert construir_noticias(a)[0]["temas"] == ["Mujeres"]
def test_filtro_personajes_vacio_no_filtra():
    ns = [nt("SV", ["Economía"], []), nt("SV", ["Economía"], ["Nayib Bukele"])]
    assert len(filtrar(ns, {"SV"}, {"Economía"}, set())) == 2
    assert len(filtrar(ns, {"SV"}, {"Economía"}, {"Nayib Bukele"})) == 1
def test_filtro_pais_y_tema():
    ns = [nt("SV", ["Deportes"], []), nt("GT", ["Economía"], []), nt("SV", ["Economía","Mujeres"], [])]
    assert len(filtrar(ns, {"SV"}, {"Mujeres", "Política"}, set())) == 1
def test_ordenar_importancia():
    assert [n["puntaje"] for n in ordenar([p(10), p(90), p(50)], "importancia")] == [90, 50, 10]
```

- [ ] **Step 2: Verificar que fallan** — FAIL.
- [ ] **Step 3: Implementar**
- [ ] **Step 4: Verificar** — `PY -m pytest -q` → PASS.
- [ ] **Step 5: Commit** — `git commit -m "feat: agrupación por país, puntaje, filtro y orden"`

---

### Task 8: Watcher con bloqueo

**Files:**
- Create: `watcher.py`, `tests/test_watcher.py`

**Interfaces:**
- Consumes: `collectors.recolectar`, `classifier.clasificar`, `store.*`, `noticias.construir_noticias`, `config.fuentes`, `ajustes.LOCK_PATH`, `ajustes.LOG_DIR`.
- Produces:
  - `watcher.adquirir_bloqueo(lock_path: Path, max_edad_min: int = 50) -> bool` — crea el archivo con PID y hora; si existe y tiene menos de `max_edad_min`, devuelve `False`; si es más viejo, lo reemplaza. `liberar_bloqueo(lock_path)`. `esta_bloqueado(lock_path, max_edad_min=50) -> bool`.
  - `watcher.correr(fuentes: list|None = None, db_path=None, lock_path=None, ahora: datetime|None = None) -> dict` — `{"ok": bool, "nuevos": int, "fuentes_ok": int, "fuentes_error": int}`, o `{"ok": False, "motivo": "en_curso"}` si no obtiene el bloqueo. Pasos: `init_db` → `iniciar_corrida` → `recolectar` en `ThreadPoolExecutor(max_workers=8)` sobre fuentes activas + `consultas_google_news()` → `registrar_estado_fuente` por cada una → ordenar artículos por prioridad de `via` (rss, web, google_news) → `clasificar` → `guardar_articulos` → `reemplazar_noticias(mes, anio, construir_noticias(obtener_articulos(mes, anio)))` del mes de `ahora` → `finalizar_corrida` → liberar el bloqueo en `finally`.
  - CLI `python watcher.py`: corre y registra en `LOG_DIR/watcher.log` (`RotatingFileHandler`, 1 MB × 5).

- [ ] **Step 1: Escribir tests que fallan** — con `recolectar` simulado: `test_correr_guarda_y_construye` (2 fuentes, `obtener_noticias` del mes con ≥1 noticia, `ultima_corrida()` no nula), `test_fuente_que_falla_no_detiene` (una fuente devuelve `([], "boom")` → `fuentes_error == 1`, `estado_fuentes` con `ok=False, error="boom"`), `test_prioridad_rss_sobre_google_news` (mismo `url` por ambas vías → se guarda con `via="rss"`), `test_bloqueo_activo_cancela` (lock reciente → `{"ok": False, "motivo": "en_curso"}`), `test_bloqueo_viejo_se_reemplaza` (lock con `mtime` de hace 2 h → corre), `test_libera_bloqueo_si_falla` (`clasificar` lanza excepción → el lock ya no existe).
- [ ] **Step 2: Verificar que fallan** — FAIL.
- [ ] **Step 3: Implementar**
- [ ] **Step 4: Verificar** — `PY -m pytest -q` → PASS.
- [ ] **Step 5: Prueba real** — Run: `PY watcher.py` → Expected: termina en menos de 5 min, `watcher.log` con el resumen y `nuevos > 0`.
- [ ] **Step 6: Commit** — `git commit -m "feat: watcher horario con bloqueo"`

---

### Task 9: API Flask, IA y exportación

**Files:**
- Create: `app.py`, `ia.py`, `valorador.py`, `guionista.py`, `exporter.py`, `config/guion_instrucciones.md`, `tests/test_app.py`, `tests/test_guionista.py`, `tests/test_valorador.py`, `tests/test_exporter.py`

**Interfaces:**
- Consumes: `store.*`, `noticias.filtrar`, `noticias.ordenar`, `watcher.esta_bloqueado`, `link_checker.check_urls`, `config.*`, `ajustes.*`.
- Produces:
  - `ia.ConfigError(Exception)`; `ia.obtener_cliente() -> genai.Client` (lanza `ConfigError("GEMINI_API_KEY no configurada")`); `ia.generar(prompt: str, modelo: str, client=None) -> str`.
  - `valorador.generar_valoraciones(items, client=None) -> list[{"titulo","valoracion"}]` — ECU `valorador.py` con prompt "analista de noticias centroamericanas", claves `titulo`/`resumen`, modelo `GEMINI_MODEL_VALORAR`, mismo reintento único.
  - `guionista.generar_guion(noticias: list[dict], instrucciones: str|None = None, client=None) -> dict` → `{"texto", "palabras", "minutos"}`; lanza `ValueError` si `len` no está entre 1 y 12. El prompt incluye las instrucciones de `config/guion_instrucciones.md`, cada noticia con país, título, resumen, temas y fuentes, y estas reglas: usar solo esa información, citar el medio y usar las marcas de sección `[APERTURA]`, `[NOTICIA n · País]`, `[TRANSICIÓN]`, `[CIERRE]`, cada una en su propia línea. `contar_palabras(texto) -> int` excluye las líneas de marca. Un reintento si la respuesta no trae `[APERTURA]` y `[CIERRE]`.
  - `config/guion_instrucciones.md`: duración objetivo de 3 a 5 min (450–750 palabras), tono cercano y profesional, saludo "¡Hola! Bienvenidos a Guion de Medios…" y despedida editables, oraciones cortas para leer a cámara y sin viñetas.
  - `exporter.export_word/export_excel/export_pdf(items) -> bytes` — ECU `exporter.py` agrupando por país (orden `PAISES`) con columnas País, Temas, Estrellas, Título, Resumen, Valoración, Medios, Publicado, Fuentes; `exporter.export_guion_word(texto: str) -> bytes`, `export_guion_pdf(texto: str) -> bytes` (las marcas de sección como subtítulos, encabezado "Guion de medios · dd/mm/aaaa").
  - Rutas (según la tabla del spec). `GET /api/news` acepta `paises`, `temas`, `personajes` (CSV), `mes`, `anio` (default: mes actual) y `orden` (default `importancia`); en meses anteriores añade `activa` a cada fuente con `check_urls`. `GET /api/meta` → `{paises: [{codigo,nombre}], temas, personajes, ultima_actualizacion: ISO|null, meses: [[anio,mes]], en_curso: bool}`. `POST /api/actualizar` → `{"iniciado": true}`, o `{"iniciado": false, "motivo": "en_curso"}` si está bloqueado; lanza `subprocess.Popen([sys.executable, watcher.py], creationflags=CREATE_NO_WINDOW)`. `GET /fuentes` renderiza `templates/fuentes.html` con `obtener_estado_fuentes()`. `POST /api/guion` body `{noticias: [...]}` → 200 `{id, texto, palabras, minutos}` / 400 `{error}` / 503 / 500. `POST /api/guion/export` body `{texto, formato: "word"|"pdf"}` → archivo `guion_de_medios.docx|.pdf`.
  - `POST /api/export` → archivos `noticias_centroamerica.docx|xlsx|pdf`.

- [ ] **Step 1: Escribir tests que fallan**

```python
# test_app.py (cliente Flask, DB temporal con noticias sembradas vía store)
def test_news_filtra_por_query(client):
    r = client.get("/api/news?paises=SV&temas=Economía").get_json()
    assert all(n["pais"] == "SV" and "Economía" in n["temas"] for n in r) and r
def test_news_personajes_vacio_no_filtra(client):
    base = client.get("/api/news?paises=SV&temas=Economía").get_json()
    assert client.get("/api/news?paises=SV&temas=Economía&personajes=").get_json() == base
def test_meta_listas(client):
    m = client.get("/api/meta").get_json()
    assert [p["codigo"] for p in m["paises"]] == ["SV","GT","HN","NI","CR","PA","REG"]
    assert m["temas"][-1] == "Otras"
def test_actualizar_en_curso(client, monkeypatch):
    monkeypatch.setattr(app_mod.watcher, "esta_bloqueado", lambda *a, **k: True)
    assert client.post("/api/actualizar").get_json() == {"iniciado": False, "motivo": "en_curso"}
def test_guion_sin_noticias_400(client):
    assert client.post("/api/guion", json={"noticias": []}).status_code == 400
def test_guion_sin_clave_503(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert client.post("/api/guion", json={"noticias": [N1]}).status_code == 503
def test_guion_guarda_historial(client, monkeypatch):
    monkeypatch.setattr(app_mod.guionista, "generar_guion", lambda ns, **k: {"texto": "[APERTURA]\nHola", "palabras": 1, "minutos": 0.0})
    client.post("/api/guion", json={"noticias": [N1]})
    assert client.get("/api/guiones").get_json()[0]["titulos"] == [N1["titulo"]]
# test_guionista.py (client falso que devuelve texto fijo y registra el prompt)
def test_prompt_incluye_fuentes_y_noticias_completas(): ...  # medio y país de cada noticia en el prompt
def test_contar_palabras_excluye_marcas():
    assert contar_palabras("[APERTURA]\nHola a todos\n[CIERRE]\nAdiós") == 4
def test_minutos_150_ppm(): ...  # 300 palabras → 2.0
def test_mas_de_12_lanza(): ...
def test_reintenta_sin_marcas(): ...  # primera respuesta sin marcas, segunda válida → 2 llamadas
# test_exporter.py
def test_export_excel_columnas(): ...  # fila 1 == ["País","Temas","Estrellas","Título","Resumen","Valoración","Medios","Publicado","Fuentes"]
def test_export_guion_word_y_pdf_no_vacios(): ...  # bytes que empiezan con b"PK" / b"%PDF"
```

- [ ] **Step 2: Verificar que fallan** — FAIL.
- [ ] **Step 3: Implementar `ia.py`, `valorador.py`, `guionista.py`, `exporter.py` e instrucciones**
- [ ] **Step 4: Implementar `app.py`** — `ConfigError` → 503, `ValueError` → 400, otras excepciones → 500 `{error}`; `store.init_db()` al importar.
- [ ] **Step 5: Verificar** — `PY -m pytest -q` → PASS.
- [ ] **Step 6: Commit** — `git commit -m "feat: API Flask, valoración, guion de medios y exportación"`

---

### Task 10: Pantalla del portal

**Files:**
- Create: `templates/index.html`, `templates/fuentes.html`, `static/app.js`, `static/style.css` (a partir de ECU `templates/index.html`, `static/style.css`, `static/app.js`), `serve.py`

**Interfaces:**
- Consumes: las rutas de Task 9.
- Produces: `serve.py` → `waitress.serve(app, host="127.0.0.1", port=ajustes.PORT)`.

Comportamiento (a partir del de ECU):
- Al cargar: `GET /api/meta` → construye las 3 filas de botones (`.chip` con `☐`/`☑`, clase `on`), el selector de mes y año y "Última actualización: hace X min" (o "Actualizando…" si `en_curso`).
- Estado `filtros = {paises: Set, temas: Set, personajes: Set, orden}`, guardado en `localStorage["gm_filtros"]` dentro de try/catch; si no existe, se usa el estado inicial de Global Constraints.
- "Todos": si todos los de su fila están marcados, desmarca todos; si no, marca todos. Si la fila de países o temas queda vacía, se muestra "Marca al menos un país y un tema".
- Cada cambio → `GET /api/news?...` → renderiza las tarjetas (como ECU, más etiqueta de país, etiquetas de tema y "Menciona El Salvador").
- Selección: `Map` con clave `` `${pais}|${titulo}` `` → objeto noticia completo; se conserva entre filtros, meses y recargas de `/api/news`. Valoraciones: `Map` con la misma clave (textarea editable como en ECU).
- Barra inferior: contador, Valorar ✦, Word, Excel, PDF y **🎬 Generar Guion de medios** (deshabilitado con 0 o más de 12 seleccionadas y aviso "Máximo 12 noticias").
- Guion: ventana modal con `<textarea>` editable, "≈ N min · M palabras" recalculado al editar, y los botones Copiar, Descargar Word, Descargar PDF, Regenerar y Cerrar. "Guiones anteriores" abre una lista (`GET /api/guiones`) y al hacer clic carga el guion en la misma ventana.
- Actualizar ↺ → `POST /api/actualizar`; consulta `/api/meta` cada 10 s hasta que `en_curso` sea `false` y recarga las noticias.
- `fuentes.html`: tabla por país con ✅/❌, número de artículos, error y hora; enlace de vuelta al portal.

- [ ] **Step 1: Implementar plantillas, JS, CSS y `serve.py`**
- [ ] **Step 2: Verificar que los tests siguen en verde** — `PY -m pytest -q` → PASS.
- [ ] **Step 3: Verificación manual en navegador** (con datos de la prueba real de Task 8) — Run: `PY serve.py` y abrir `http://127.0.0.1:5050`. Checklist:
  - Al abrir aparecen El Salvador y los 5 temas por defecto marcados, con noticias.
  - Marcar Guatemala agrega sus noticias; "Todos" en países muestra los 7.
  - Seleccionar 2 de SV, cambiar a solo Panamá y seleccionar 1 → contador en 3. Volver a SV → las 2 siguen marcadas.
  - Presionar Actualizar ↺ con 3 seleccionadas → al terminar, la selección sigue en 3.
  - Generar Guion de medios con las 3 → aparecen las marcas `[APERTURA]`…`[CIERRE]`, los minutos estimados y la descarga Word/PDF abre bien.
  - "Guiones anteriores" muestra el guion generado.
  - `/fuentes` muestra la tabla.
  - Ancho de celular (DevTools a 390 px): los botones se acomodan en varias líneas y no hay scroll horizontal.
- [ ] **Step 4: Commit** — `git commit -m "feat: portal con botones de país, tema y personaje y ventana de guion"`

---

### Task 11: Instalación en Windows

**Files:**
- Create: `scripts/instalar.ps1`, `README.md`

**Interfaces:**
- Consumes: `watcher.py`, `serve.py`, venv de Task 1.
- Produces: tareas programadas `GuionMedios-Watcher` (cada 1 h, `StartWhenAvailable`, `MultipleInstances IgnoreNew`, ejecuta `pythonw.exe watcher.py` con el directorio de trabajo en la raíz del proyecto) y `GuionMedios-Portal` (al iniciar sesión, ejecuta `pythonw.exe serve.py`); acceso directo `Guion de Medios.url` en el escritorio → `http://127.0.0.1:5050`. El script es idempotente (`Unregister-ScheduledTask` previo si ya existen).

- [ ] **Step 1: Escribir `instalar.ps1` y `README.md`** — el README explica en español la instalación, cómo editar `config/` y `config/guion_instrucciones.md`, dónde están la base y los logs, y cómo desinstalar.
- [ ] **Step 2: Ejecutar** — Run: `powershell -ExecutionPolicy Bypass -File scripts/instalar.ps1` → Expected: `Get-ScheduledTask GuionMedios-*` lista 2 tareas en estado `Ready`.
- [ ] **Step 3: Prueba de humo** — `Start-ScheduledTask GuionMedios-Portal` y `Start-ScheduledTask GuionMedios-Watcher`; abrir el acceso directo → el portal carga, y tras la corrida "Última actualización" muestra la hora nueva. Confirmar que el watcher no abre ventanas de consola.
- [ ] **Step 4: Commit** — `git commit -m "chore: instalación en Windows con tareas programadas"`
