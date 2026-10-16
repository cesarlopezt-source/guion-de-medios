# Guion de Medios en línea — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publicar Guion de Medios en Render con contraseña, sobre una base Neon que la PC sincroniza en cada corrida y que la nube llena con búsquedas en vivo cuando la PC está apagada.

**Architecture:** `store` pasa a ser un paquete con dos motores de interfaz idéntica (`store/sqlite.py`, `store/postgres.py`). `MODO=pc` usa SQLite y sincroniza con Neon (`sincronizacion.py`) dentro de `watcher.correr`. `MODO=nube` usa Neon, exige login y lanza `watcher.correr` en un hilo cuando los datos tienen más de 2 h. El bloqueo entre PC y nube es una corrida abierta en Neon.

**Tech Stack:** lo existente + `psycopg[binary]` 3, `gunicorn`, Render (blueprint `render.yaml`), Neon Postgres.

**Spec:** `docs/superpowers/specs/2026-10-15-guion-de-medios-en-linea-design.md` (y el spec base `2026-10-15-guion-de-medios-design.md`)

## Global Constraints

- `MODO` = env `MODO`, valores `pc` (por defecto) o `nube`. `DATABASE_URL` = env (Neon). `TEST_DATABASE_URL` = env (rama `test` de Neon) solo para pruebas.
- Mes en hora de El Salvador (UTC-6) en ambos motores; Postgres: `to_char((publicado AT TIME ZONE 'UTC') - interval '6 hours', 'YYYY-MM')`.
- Neon conserva `articulos` del mes actual y el anterior (hora SV); `noticias` para siempre.
- Búsqueda en vivo: datos con más de **2 h** (`VIVO_HORAS = 2`). Bloqueo: corrida con `fin IS NULL` e `inicio` de hace menos de **15 min** (`BLOQUEO_MIN = 15`).
- `origen` ∈ `{"pc", "nube"}` en `articulos` y `corridas`. `guiones.uid` = `uuid4().hex`.
- Contraseña solo en `MODO=nube`: `APP_PASSWORD`, `FLASK_SECRET_KEY`; cookie `Secure`, `HttpOnly`, `SameSite=Lax`; `/api/*` sin sesión → 401 `{"error": "Sesión expirada"}`.
- Render: `gunicorn app:app --workers 1 --threads 4 --timeout 120`, plan `free`, Python 3.12.
- Sin cron externo hacia Render.
- Todo texto visible, en español. Commits con `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Python del venv: `PY` = `$LOCALAPPDATA/GuionDeMedios/venv/Scripts/python.exe`; pruebas: `PY -m pytest -q -p no:warnings`.

## Review Focus

1. **Corte de conexión con Neon a mitad de la sincronización** (Wi-Fi que se cae): la corrida local termina OK y la marca no avanza → test en Task 4.
2. **Base SQLite existente sin las columnas nuevas** (`origen`, `uid`): `init_db` migra sin perder datos ni guiones → test en Task 1.
3. **Dos pestañas abiertas en internet a la vez con datos viejos**: una sola búsqueda en vivo → test en Task 5.
4. **Corrida colgada** (Render se duerme a mitad de una búsqueda): a los 15 min deja de bloquear → test en Task 1 (contrato) y Task 3.
5. **Sesión vencida con la pantalla abierta**: las llamadas a `/api/*` reciben 401 y la pantalla va a `/login` en vez de mostrar errores → test en Task 5 (servidor) y verificación manual en Task 6.

---

## Estructura de archivos

```
store/__init__.py      motor por defecto según MODO; reexporta la interfaz
store/sqlite.py        store.py actual + columnas origen/uid + funciones de sincronización + migración
store/postgres.py      misma interfaz sobre psycopg
sincronizacion.py      bajar / subir / podar entre store.sqlite y store.postgres
watcher.py             bloqueo por base, origen, verificar, sincronización
app.py                 login, 401, búsqueda en vivo en hilo (MODO=nube)
templates/login.html   copiado de ECU y adaptado
static/app.js          401 → /login; texto "Buscando noticias en vivo…"
render.yaml, requirements.txt, README.md
tests/test_store_contrato.py   corre con ambos motores
tests/test_sincronizacion.py, tests/test_nube.py
```

**Interfaz común de `store/sqlite.py` y `store/postgres.py`** (el parámetro `db_path` es la ruta SQLite o el DSN de Postgres; `None` = `ajustes.DB_PATH` / `ajustes.DATABASE_URL`). Todas las funciones actuales se mantienen con su firma; cambian o se agregan:

- `guardar_articulos(articulos, db_path=None, origen="pc") -> int` — si un artículo trae `origen` o `recolectado`, se respetan (los bajados conservan los suyos).
- `obtener_articulos(mes, anio, db_path=None)` — sin cambios en la firma.
- `articulos_desde(marca: str | None, db_path=None, origen: str | None = None) -> list[dict]` — artículos con `recolectado > marca` (todos si `None`), opcionalmente de un origen, ordenados por `recolectado`; cada uno trae `recolectado` y `origen`.
- `intentar_iniciar_corrida(origen: str, db_path=None, bloqueo_min: int = 15) -> int | None` — crea la corrida si no hay otra abierta de menos de `bloqueo_min`; atómica (`BEGIN IMMEDIATE` en SQLite, `pg_advisory_xact_lock(4711)` en Postgres).
- `corrida_en_curso(db_path=None, bloqueo_min: int = 15) -> dict | None` — `{inicio, origen}` o `None`.
- `iniciar_corrida(db_path=None, origen="pc") -> int` se mantiene (uso sin bloqueo).
- `ultima_corrida(db_path=None)` agrega `origen` al dict.
- `guardar_guion(...)` genera `uid`; `listar_guiones` y `obtener_guion` incluyen `uid`.
- `uids_guiones(db_path=None) -> set[str]`, `guiones_por_uid(uids: set, db_path=None) -> list[dict]` (completos: `uid, creado, noticias, texto, palabras, minutos`), `insertar_guiones(guiones: list, db_path=None) -> int` (respeta `uid` y `creado`, ignora repetidos).
- `enlaces_desde(marca: str | None, db_path=None) -> dict[str, tuple[bool | None, str]]` — url → (activa, verificado); `guardar_estado_enlaces(estados, db_path=None, verificado: str | None = None)`.
- `podar_articulos(antes_de: str, db_path=None) -> int` — borra artículos con `publicado < antes_de` (ISO UTC).
- Solo SQLite: `obtener_marca(clave: str, db_path=None) -> str | None`, `guardar_marca(clave: str, valor: str, db_path=None)` (tabla `sync_marcas`).

---

### Task 1: `store` como paquete, columnas nuevas y funciones de sincronización (SQLite)

**Files:**
- Create: `store/__init__.py`, `store/sqlite.py` (mover `store.py` con `git mv`), `tests/test_store_contrato.py`
- Modify: `ajustes.py` (`MODO`, `DATABASE_URL`, `TEST_DATABASE_URL`), `tests/test_store.py` (sigue funcionando vía `store`)

**Interfaces:**
- Produces: la interfaz común de arriba en `store.sqlite`; `store/__init__.py` reexporta todas las funciones públicas desde `store.sqlite` si `ajustes.MODO == "pc"` y desde `store.postgres` si es `"nube"` (import perezoso del módulo postgres para no exigir psycopg en tests de PC). `ajustes.MODO: str`, `ajustes.DATABASE_URL: str | None`, `ajustes.TEST_DATABASE_URL: str | None`.
- Fixture `motor` en `tests/conftest.py`, parametrizada `["sqlite", "postgres"]`: devuelve `(modulo, destino)`. Para sqlite, `destino = tmp_path/"c.db"`. Para postgres, si no hay `TEST_DATABASE_URL`, `pytest.skip("Sin TEST_DATABASE_URL")`; si hay, crea un esquema temporal `t_<uuid>`, devuelve el DSN con `options=-csearch_path=<esquema>` y lo borra al final.

- [ ] **Step 1: Escribir tests de contrato que fallan** (`tests/test_store_contrato.py`, todos usan `motor`):
  - `test_origen_por_defecto_y_explicito`: `guardar_articulos([a1], d)` y `guardar_articulos([a2], d, origen="nube")` → `articulos_desde(None, d, origen="nube")` devuelve solo `a2` con `origen == "nube"`.
  - `test_articulos_desde_marca`: tras guardar, `m = articulos_desde(None, d)[-1]["recolectado"]`; guardar otro → `articulos_desde(m, d)` devuelve solo el nuevo.
  - `test_guardar_respeta_recolectado_y_origen_del_articulo`: un artículo con `recolectado="2026-10-01T00:00:00+00:00"` y `origen="nube"` vuelve igual.
  - `test_intentar_iniciar_corrida_bloquea`: primera → int; segunda → `None`; tras `finalizar_corrida` → int.
  - `test_corrida_abandonada_expira`: con `bloqueo_min=0` la segunda ya no se bloquea (`int`).
  - `test_corrida_en_curso`: devuelve `{"origen": "nube", ...}` mientras está abierta y `None` al cerrarla.
  - `test_guiones_uid_roundtrip`: `guardar_guion` → `uids_guiones` tiene 1 uid; `guiones_por_uid` lo devuelve completo; `insertar_guiones` de ese mismo guion en otra base → 1, y repetirlo → 0.
  - `test_enlaces_desde_y_verificado_explicito`: `guardar_estado_enlaces({"u": True}, d, verificado="2026-10-01T00:00:00+00:00")` → `enlaces_desde(None, d) == {"u": (True, "2026-10-01T00:00:00+00:00")}`.
  - `test_podar_articulos`: artículos de agosto y octubre; `podar_articulos("2026-09-01T06:00:00+00:00", d) == 1` y queda octubre.
  - `test_mes_en_hora_sv`: el caso del 1 nov 03:00 UTC en octubre (como en `test_store.py`).
  - Solo SQLite: `test_migracion_agrega_origen_y_uid_sin_perder_datos` — crea una base con el esquema viejo (copiar el `CREATE TABLE` de `articulos` y `guiones` sin las columnas nuevas, con 1 fila cada uno), corre `init_db` → la fila sigue, `origen == "pc"`, el guion tiene `uid` no vacío. `test_marcas`: `obtener_marca("x") is None`; `guardar_marca` y leerla.
- [ ] **Step 2: Verificar que fallan** — `PY -m pytest -q -p no:warnings tests/test_store_contrato.py` → FAIL (sqlite) / SKIP (postgres sin `TEST_DATABASE_URL`).
- [ ] **Step 3: Implementar** — `git mv store.py store/sqlite.py`; columnas `articulos.origen TEXT NOT NULL DEFAULT 'pc'`, `corridas.origen TEXT NOT NULL DEFAULT 'pc'`, `guiones.uid TEXT UNIQUE`; tabla `sync_marcas(clave TEXT PRIMARY KEY, valor TEXT)`. La migración en `init_db` revisa `PRAGMA table_info`, hace `ALTER TABLE ... ADD COLUMN` si falta y rellena `uid` con `uuid4().hex`.
- [ ] **Step 4: Verificar** — suite completa → PASS (los tests existentes siguen pasando sin cambios de import).
- [ ] **Step 5: Commit** — `refactor: store como paquete con funciones de sincronización`

---

### Task 2: Motor Postgres

**Files:**
- Create: `store/postgres.py`
- Modify: `requirements.txt` (`psycopg[binary]>=3.2`, `gunicorn>=22`)

**Interfaces:**
- Consumes: la interfaz común (Task 1).
- Produces: `store.postgres` con las mismas funciones y firmas, salvo `obtener_marca`/`guardar_marca`. Esquema creado por `init_db` (`jsonb`, `timestamptz`, `serial`, mismos nombres). `urls_por_verificar` usa `jsonb_array_elements`. Conexión `psycopg.connect(dsn, autocommit=False)`, una por llamada (Neon termina conexiones ociosas); `row_factory=dict_row`.

- [ ] **Step 1: Configurar la rama de prueba** — César crea en Neon el proyecto `guion-de-medios` con una rama `test` y pone `TEST_DATABASE_URL` en `.env`. Verificación: `PY -c "import ajustes; print(bool(ajustes.TEST_DATABASE_URL))"` → `True`.
- [ ] **Step 2: Correr el contrato contra Postgres** — `PY -m pytest -q -p no:warnings tests/test_store_contrato.py -k postgres` → FAIL (no existe `store.postgres`).
- [ ] **Step 3: Implementar `store/postgres.py`.**
- [ ] **Step 4: Verificar** — contrato completo con ambos motores → PASS; suite completa → PASS.
- [ ] **Step 5: Commit** — `feat: motor Postgres para store`

---

### Task 3: Watcher con bloqueo por base, origen y verificación opcional

**Files:**
- Modify: `watcher.py`, `tests/test_watcher.py`

**Interfaces:**
- Consumes: `store.intentar_iniciar_corrida`, `store.finalizar_corrida`.
- Produces: `watcher.correr(fuentes=None, db_path=None, lock_path=None, ahora=None, origen="pc", verificar_enlaces=True, sincronizar=None) -> dict`.
  - `origen="nube"` no usa archivo de bloqueo: usa `store.intentar_iniciar_corrida("nube", db_path)`; si devuelve `None` → `{"ok": False, "motivo": "en_curso"}`.
  - `origen="pc"` mantiene el archivo de bloqueo y crea la corrida local con `intentar_iniciar_corrida("pc", db_path)`.
  - `sincronizar`: objeto opcional con `antes() -> bool` (False = la nube está buscando: la corrida se cancela con `motivo: "en_curso"`), `despues(meses: list[tuple]) -> None` y `al_final(ok: bool) -> None`. Los provee Task 4.
  - En `origen="nube"` los artículos se guardan con `origen="nube"`. Si una corrida falla, se finaliza con `ok=False` antes de propagar la excepción.

- [ ] **Step 1: Tests que fallan** — `test_nube_usa_bloqueo_por_base` (corrida abierta de otro origen → `en_curso`, sin recolectar); `test_nube_guarda_origen_nube`; `test_sin_verificar_enlaces_no_llama_link_checker`; `test_corrida_fallida_se_cierra` (después de la excepción, `corrida_en_curso` es `None`); `test_sincronizar_antes_false_cancela`; `test_sincronizar_recibe_meses_reconstruidos` (`despues` recibe `meses_a_reconstruir(ahora)`).
- [ ] **Step 2: Verificar que fallan.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar** — suite completa → PASS.
- [ ] **Step 5: Commit** — `feat: watcher con bloqueo por base y origen`

---

### Task 4: Sincronización PC ⇄ Neon

**Files:**
- Create: `sincronizacion.py`, `tests/test_sincronizacion.py`
- Modify: `watcher.py` (`__main__`: si `ajustes.DATABASE_URL` y `MODO=pc`, pasa `sincronizar=Sincronizacion(...)`)

**Interfaces:**
- Consumes: `store.sqlite`, `store.postgres` (interfaz común).
- Produces: `class Sincronizacion(local=None, nube=None)` (rutas/DSN; `None` = `ajustes`) con:
  - `antes() -> bool` — abre la corrida remota con `postgres.intentar_iniciar_corrida("pc", nube)`. Si devuelve `None` → `False`. Si hay error de conexión → registra en el log, marca `self.activa = False` y devuelve `True` (la corrida sigue solo en local). Si la corrida remota quedó abierta, **baja**: artículos `origen="nube"` desde la marca `bajada_articulos` → `sqlite.guardar_articulos` (respetando origen y recolectado), y guiones con `uid` que no están en local → `sqlite.insertar_guiones`. La marca avanza al máximo `recolectado` bajado, solo si todo salió bien.
  - `despues(meses) -> None` — si `self.activa`, **sube**: artículos locales desde `subida_articulos`, `reemplazar_noticias` de cada mes, `registrar_estado_fuente` de todas las fuentes, enlaces desde `subida_enlaces` (con su `verificado`) y guiones locales que no están en la nube. Después **poda** la nube con `antes_de` = 1.º del mes anterior a las 06:00 UTC. Cada marca avanza solo si su paso terminó.
  - `al_final(ok) -> None` — cierra la corrida remota; registra en el estado de fuentes local la fuente `{"nombre": "Sincronización con la nube", "pais": "REG", "tipo": "nube"}` con `ok` y el error si lo hubo.
  - Toda excepción de red dentro de `despues` se captura y se registra (no detiene la corrida local).

- [ ] **Step 1: Tests que fallan** (local = SQLite temporal; nube = fixture postgres con `TEST_DATABASE_URL`, o `skip`):
  - `test_baja_articulos_de_la_nube_y_avanza_marca`
  - `test_no_baja_articulos_origen_pc`
  - `test_sube_articulos_noticias_y_guiones`
  - `test_repetir_no_duplica`
  - `test_fallo_al_subir_no_avanza_marca` (monkeypatch `postgres.guardar_articulos` que lanza `psycopg.OperationalError`)
  - `test_sin_conexion_antes_devuelve_true_y_desactiva` (DSN inválido)
  - `test_nube_ocupada_antes_devuelve_false`
  - `test_poda_solo_meses_viejos`
  - `test_guiones_de_la_nube_bajan_a_la_pc`
  - `test_estado_sincronizacion_registrado`
- [ ] **Step 2: Verificar que fallan.**
- [ ] **Step 3: Implementar** — `sincronizacion.py` y el cableado en `watcher.__main__`.
- [ ] **Step 4: Verificar** — suite completa → PASS.
- [ ] **Step 5: Commit** — `feat: sincronización PC ⇄ Neon en cada corrida`

---

### Task 5: Modo nube en el portal: login, 401 y búsqueda en vivo

**Files:**
- Create: `templates/login.html` (de ECU `templates/login.html`, textos "Guion de Medios"), `tests/test_nube.py`
- Modify: `app.py`, `static/app.js`

**Interfaces:**
- Consumes: `store.corrida_en_curso`, `store.ultima_corrida`, `watcher.correr`.
- Produces:
  - En `MODO=nube`, `app.secret_key = FLASK_SECRET_KEY` y `SESSION_COOKIE_SECURE/HTTPONLY/SAMESITE`; `before_request` exige `session["ok"]` salvo en `/login` y `/static/`: páginas → redirect `/login`; `/api/*` → 401 `{"error": "Sesión expirada"}`. Rutas `GET/POST /login` (error "Contraseña incorrecta") y `GET /logout`.
  - `app.lanzar_busqueda_en_vivo() -> bool` — si no hay búsqueda activa en este proceso (`threading.Event` `_buscando`) y `store.corrida_en_curso()` es `None`, marca `_buscando`, lanza `threading.Thread(target=_buscar, daemon=True)` y devuelve `True`. `_buscar` llama a `watcher.correr(origen="nube", verificar_enlaces=False)` y limpia `_buscando` en `finally`. Entre procesos (PC ⇄ nube) protege el bloqueo por base dentro de `correr`.
  - `GET /api/meta` en `MODO=nube`: si `ultima_corrida()` es `None` o tiene más de `VIVO_HORAS`, llama a `lanzar_busqueda_en_vivo()`. `en_curso` = `corrida_en_curso() is not None`. Agrega `origen_en_curso` (`"pc"` | `"nube"` | `null`).
  - `POST /api/actualizar` en `MODO=nube` llama a `lanzar_busqueda_en_vivo()` (sin subprocess).
  - `static/app.js`: helper `api(url, opciones)` que ante 401 hace `location.href = "/login"`, usado en todos los `fetch`; `pintarUltima` muestra "Buscando noticias en vivo…" si `origen_en_curso == "nube"`.

- [ ] **Step 1: Tests que fallan** (`tests/test_nube.py`, con `monkeypatch` de `ajustes.MODO = "nube"`, `APP_PASSWORD = "clave"`, recarga de `app` y `store` apuntando a SQLite temporal para no requerir Postgres):
  - `test_sin_sesion_pagina_redirige_y_api_401`
  - `test_login_correcto_e_incorrecto`
  - `test_logout`
  - `test_meta_con_datos_viejos_lanza_una_sola_busqueda` (monkeypatch `threading.Thread` con un falso que no arranca nada: tras 2 llamadas se cuenta 1 lanzamiento, porque `_buscando` sigue marcado)
  - `test_meta_con_datos_frescos_no_lanza`
  - `test_actualizar_en_nube_no_usa_subprocess`
  - `test_modo_pc_no_pide_login` (en `tests/test_app.py`: `/` → 200 sin sesión)
- [ ] **Step 2: Verificar que fallan.**
- [ ] **Step 3: Implementar.**
- [ ] **Step 4: Verificar** — suite completa → PASS.
- [ ] **Step 5: Commit** — `feat: modo nube con login y búsqueda en vivo`

---

### Task 6: Publicación y prueba real

**Files:**
- Create: `render.yaml`
- Modify: `README.md`, `.env.example` (`MODO`, `DATABASE_URL`, `TEST_DATABASE_URL`, `APP_PASSWORD`, `FLASK_SECRET_KEY`)

**Interfaces:**
- Consumes: todo lo anterior.
- Produces: servicio `guion-de-medios` en Render; PC sincronizando.

- [ ] **Step 1: Escribir `render.yaml`** según Global Constraints (`MODO=nube`; `DATABASE_URL`, `APP_PASSWORD`, `GEMINI_API_KEY` con `sync: false`; `FLASK_SECRET_KEY` con `generateValue: true`; `PYTHON_VERSION=3.12.10`). Actualizar el README con la sección "En línea".
- [ ] **Step 2: Unir la rama a `master`** (decisión de la rama pendiente: se pregunta a César) y **crear el repositorio privado** `cesarlopezt-source/guion-de-medios` con push, **previa confirmación de César**. Verificación: `git ls-remote origin` muestra `master`.
- [ ] **Step 3: Pasos de César** (guiados): crear el proyecto Neon `guion-de-medios` (rama `main`), crear en Render el Blueprint desde el repo y pegar las 3 claves, poner `DATABASE_URL` en el `.env` de la PC y revisar el cron de Ecuador.
- [ ] **Step 4: Primera sincronización** — reiniciar la tarea del watcher. Expected: `watcher.log` con "Sincronización OK" y `/fuentes` muestra "Sincronización con la nube ✅".
- [ ] **Step 5: Prueba real "PC apagada"** — `Disable-ScheduledTask GuionMedios-Watcher`. Abrir `https://guion-de-medios.onrender.com`. Expected: pide contraseña; con la contraseña muestra noticias. Con Actualizar aparece "Buscando noticias en vivo…" y en menos de 3 min la hora de actualización es nueva. Generar un guion desde internet.
- [ ] **Step 6: Prueba real "PC se enciende"** — `Enable-ScheduledTask` y `Start-ScheduledTask GuionMedios-Watcher`. Expected: la base local contiene artículos con `origen = 'nube'` y el guion generado en internet aparece en "Guiones anteriores" del portal local.
- [ ] **Step 7: Prueba de sesión vencida** — en internet, borrar la cookie y tocar un filtro → va a `/login`.
- [ ] **Step 8: Commit** — `chore: publicación en Render`
