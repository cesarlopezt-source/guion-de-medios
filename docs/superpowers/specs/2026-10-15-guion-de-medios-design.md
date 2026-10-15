# Guion de Medios · Centroamérica — Diseño

**Fecha:** 2026-10-15
**Estado:** En revisión
**Base:** Copia y adaptación del proyecto Flask "Monitor de Noticias Ecuador" (no de la "Version Versa" en Vercel).

---

## Objetivo

Un portal web local que reúne cada hora las noticias importantes de medios **centroamericanos gratuitos**, con **El Salvador como foco principal**. Permite filtrarlas por país, tema y personaje político con botones de check, seleccionar las que interesan y generar con IA un **"Guion de medios"**: un guion de noticiero de 3 a 5 minutos para que César lo grabe personalmente en video.

**Criterios de éxito:**
- Al abrir el portal, las noticias ya están descargadas: un clic en un país o tema responde de inmediato desde la base de datos local, sin búsquedas en vivo.
- El watcher actualiza todo cada hora sin intervención.
- Hay noticias de los 6 países, con mayor cobertura en El Salvador.
- Con unas pocas noticias seleccionadas, "Generar Guion de medios" entrega un guion listo para leer a cámara, editable y descargable.

---

## Arquitectura

```
Tarea programada de Windows (cada 1 hora)
        │  python watcher.py
        ▼
Watcher: recolecta (RSS + Google News + lectura web)
        → clasifica (país, temas, personajes)
        → agrupa noticias similares → puntúa
        → guarda en SQLite local (artículos, noticias agrupadas, estado de fuentes)
        ▼
Portal Flask local (http://127.0.0.1:5050, se inicia al encender la PC)
        │  GET /api/news?paises=..&temas=..&personajes=..  → solo lee SQLite
        ▼
Navegador: botones con check → tarjetas → selección
        → Valorar ✦ / Word · Excel · PDF / 🎬 Generar Guion de medios (Gemini)
```

**Stack:** Python 3 + Flask, SQLite, feedparser, requests + BeautifulSoup (lectura web), python-docx / openpyxl / reportlab (exportación), google-genai (Gemini), waitress (servidor WSGI que funciona en Windows, en lugar de gunicorn), pytest.

**Ubicación:**
- Código en `G:\Mi unidad\Proyect Claude\Guion de Medios` (repositorio git).
- **La base de datos y el entorno virtual van en `%LOCALAPPDATA%\GuionDeMedios\`**, no en G:. G: es Google Drive y sincronizar un SQLite en uso puede corromperlo. Es el mismo criterio que se aplicó al proyecto de Trading.

---

## Fuentes y recolección

Cada fuente se declara en `config/fuentes.py` con: `nombre`, `pais` (SV, GT, HN, NI, CR, PA o REG para regionales), `tipo` (`rss` | `google_news` | `web`), `url` y, si es `web`, los selectores CSS para extraer titular, enlace, fecha y resumen.

**Tres formas de recolección, todas activas; se usa lo que funcione:**
1. **RSS** (`collectors/rss.py`): feeds públicos de cada medio, con feedparser, como en Ecuador.
2. **Google News RSS** (`collectors/google_news.py`): búsquedas `news.google.com/rss/search?q=...&hl=es-419&gl=<PAIS>&ceid=<PAIS>:es-419`, una por país × grupo de temas y una por personaje. El país de la noticia es el de la búsqueda. El enlace lleva al medio original y el nombre del medio sale del campo `source` del feed.
3. **Lectura web** (`collectors/web.py`): solo para medios sin RSS o con RSS roto. Descarga la portada o la sección de economía y política, y extrae los titulares con los selectores configurados.

**Reglas comunes:**
- Timeout de 15 s por fuente y User-Agent de navegador. Si una fuente falla, se omite sin detener las demás.
- Las fuentes se consultan en paralelo con un máximo de 8 a la vez.
- Se deduplica por URL. Si el mismo artículo llega por RSS y por Google News, se guarda una sola vez y se prioriza la versión del RSS directo.
- Cada corrida registra por fuente: hora, éxito o error y número de artículos. Eso alimenta la vista **"Estado de fuentes"**.

**Lista inicial de medios (se verifica uno por uno al implementar; los que no respondan se marcan como inactivos o cambian de tipo):**

| País | Medios |
|---|---|
| El Salvador | La Prensa Gráfica, El Diario de Hoy (elsalvador.com), Diario El Mundo, Diario Co Latino, El Faro, Diario El Salvador, La Página, Revista Factum, GatoEncerrado |
| Guatemala | Prensa Libre, Soy502, República, La Hora, Plaza Pública, Agencia Ocote |
| Honduras | La Prensa, El Heraldo, Proceso Digital, La Tribuna, Criterio.hn, Contracorriente |
| Nicaragua | La Prensa, Confidencial, 100% Noticias, Artículo 66, Divergentes, El 19 Digital |
| Costa Rica | La Nación, CRHoy, El Financiero, Teletica, Delfino, Semanario Universidad |
| Panamá | La Prensa, La Estrella de Panamá, Panamá América, TVN Noticias, Telemetro |
| Regional (REG) | Estrategia & Negocios, Revista Summa, Forbes Centroamérica |

Las noticias de medios regionales se asignan al país que mencionan; si no mencionan ninguno, quedan como "Regional". Regional aparece como botón adicional en la fila de países.

---

## Clasificación (`classifier.py`)

Cada artículo recibe:
- **`pais`**: el de su fuente o búsqueda (regionales: según menciones).
- **`temas`**: lista con **varios temas posibles** a la vez, por coincidencia de palabras clave en título y resumen. Es un cambio respecto a Ecuador, donde cada noticia tenía una sola categoría. Si no coincide con ningún tema, queda en `["Otras"]`.
- **`personajes`**: personajes detectados por nombre (con variantes, p. ej. "Bukele", "Nayib Bukele").
- **`menciona_sv`**: verdadero si una noticia de otro país menciona a El Salvador. Usa las palabras clave de la pestaña El Salvador del proyecto de Ecuador.

**Temas (`config/temas.py`, cada uno con su lista de palabras clave):** Economía, Inversión, Política, Coyuntura (económico-política), Social, Mujeres, Inclusión, Seguridad, Salud, Internacional, Deportes, Cultura, Turismo, Medio Ambiente, Otras.

Las palabras clave se adaptan a Centroamérica: por ejemplo bitcoin, remesas, maquila, CAFTA, Canal de Panamá, FMI, bonos, Asamblea Legislativa, régimen de excepción.

**Personajes iniciales (`config/personajes.py`, editable):** Nayib Bukele, Félix Ulloa, Gustavo Villatoro, Alexandra Hill Tinoco, Jerson Posada, Ernesto Castro, Christian Guevara, Claudia Ortiz, Marcela Villatoro y figuras del FMLN. **Los cargos se verifican contra noticias actuales al implementar.**

---

## Agrupación y puntaje

Se reutilizan `clusterer.py` y `scorer.py` de Ecuador:
- Agrupación por similitud de títulos (difflib) **dentro del mismo país**. Un cluster une los temas y personajes de todos sus artículos.
- Puntaje `(nº_fuentes × 40) + (factor_recencia × 60)` y de 1 a 5 estrellas.

El watcher **recalcula los clusters del mes en curso** en cada corrida y los guarda ya listos en la tabla `noticias`. Los meses cerrados quedan congelados, sin recalcular.

---

## Base de datos (SQLite)

```
articulos      id, titulo, resumen, url UNIQUE, fuente, pais, temas (JSON), personajes (JSON),
               menciona_sv, publicado, recolectado, via (rss|google_news|web)
noticias       id, mes, anio, titulo, resumen, pais, temas (JSON), personajes (JSON),
               menciona_sv, fuentes (JSON [{nombre,url}]), publicado, n_fuentes, puntaje, estrellas
estado_fuentes fuente, pais, tipo, ultima_corrida, ok, n_articulos, error
corridas       id, inicio, fin, n_articulos_nuevos, ok
guiones        id, creado, noticias (JSON), texto, palabras, minutos_estimados
```

---

## Watcher (`watcher.py`)

- Una corrida: recolectar → clasificar → guardar artículos → recalcular las noticias del mes en curso → registrar la corrida y el estado de fuentes.
- **Archivo de bloqueo:** si ya hay una corrida en marcha, la nueva se cancela, para que nunca corran dos watchers a la vez.
- **Tarea programada de Windows "GuionMedios-Watcher"**: cada hora, con "ejecutar lo antes posible si se perdió una ejecución" para ponerse al día cuando la PC se enciende.
- Log rotativo en `%LOCALAPPDATA%\GuionDeMedios\logs\`.

---

## Portal (`app.py`)

**Arranque:** la tarea programada "GuionMedios-Portal" inicia waitress al iniciar sesión en Windows. Escucha **solo en `127.0.0.1:5050`**, así que no es accesible desde fuera de la PC. Un acceso directo en el escritorio abre el navegador en esa dirección.

**Login:** como el portal solo escucha localmente, en esta versión **no hay login**. Si más adelante se publica en internet, se reactiva el login de Ecuador.

**Rutas:**

| Ruta | Función |
|---|---|
| `GET /` | Portal |
| `GET /api/meta` | Listas de países, temas y personajes, hora de la última actualización y meses disponibles |
| `GET /api/news?paises=&temas=&personajes=&mes=&anio=&orden=` | Noticias filtradas desde la tabla `noticias` |
| `POST /api/actualizar` | Lanza el watcher en segundo plano (respeta el bloqueo) |
| `GET /api/fuentes` | Estado de fuentes |
| `POST /api/valorar` | Valoración de 2 líneas con Gemini (como en Ecuador) |
| `POST /api/export` | Word, Excel o PDF de las noticias seleccionadas (como en Ecuador) |
| `POST /api/guion` | Genera un Guion de medios y lo guarda en `guiones` |
| `GET /api/guiones`, `GET /api/guiones/<id>` | Historial de guiones |
| `POST /api/guion/export` | Guion en Word o PDF |

**Lógica del filtro:** una noticia aparece si su país está entre los marcados **y** tiene al menos un tema marcado **y**, si hay personajes marcados, al menos uno de esos personajes. Sin personajes marcados, esa fila no filtra.

**Meses anteriores:** se mantiene la verificación de enlaces de Ecuador (`link_checker.py`) para indicar qué fuentes siguen activas.

---

## Pantalla (`templates/index.html`, `static/app.js`, `static/style.css`)

Se parte del HTML, CSS y JS de Ecuador. De arriba hacia abajo:

1. **Encabezado:** "Guion de Medios · Centroamérica", "Última actualización: hace X min", botón **Actualizar ↺** y enlace **Estado de fuentes**.
2. **Fila Países:** `Todos` · El Salvador · Guatemala · Honduras · Nicaragua · Costa Rica · Panamá · Regional.
3. **Fila Temas:** `Todos` · los 15 temas.
4. **Fila Personajes:** `Todos` · personajes configurados.
5. **Periodo y orden:** mes y año, orden por importancia o por más recientes, contador de noticias y "Seleccionar todo".
6. **Tarjetas:** checkbox, estrellas, etiqueta de país, etiquetas de tema, título, resumen, fuentes con enlace y marca "Menciona El Salvador" cuando aplica.
7. **Barra inferior fija:** "N seleccionadas" · Valorar ✦ · Word · Excel · PDF · **🎬 Generar Guion de medios** (botón principal).

**Comportamiento de los botones:** cada botón es un interruptor con check (☑/☐). Varios pueden estar activos a la vez. "Todos" marca o desmarca toda su fila. Al cambiar un botón, se vuelve a pedir `/api/news`, que responde al instante desde SQLite. Las noticias seleccionadas **se conservan entre filtros**.

**Estado inicial:** El Salvador marcado, con Economía, Inversión, Política, Coyuntura y Social. Ningún personaje marcado. El último estado de los botones se recuerda en el navegador.

---

## Guion de medios (`guionista.py`)

- **Entrada:** las noticias seleccionadas, con título, resumen, país, temas y fuentes. Mínimo 1 y máximo 12.
- **Instrucciones** en `config/guion_instrucciones.md`, editables sin tocar código: tono, duración objetivo, saludo y despedida propios, y reglas de estilo.
- **Formato inicial (opción A), un solo guion de noticiero de 3 a 5 minutos:**
  - **Apertura:** saludo y adelanto de los temas.
  - **Bloques por noticia:** contexto, dato clave, por qué importa y fuente citada ("según La Prensa Gráfica…").
  - **Transiciones** entre bloques.
  - **Cierre:** resumen y despedida.
- **Reglas del prompt:** usar solo la información entregada, sin inventar cifras ni declaraciones; citar siempre el medio; español neutro con cercanía salvadoreña.
- **Modelo:** Gemini, configurable en `.env` (`GEMINI_MODEL`, por defecto `gemini-2.5-flash`). Reintento único ante fallo y errores claros (503 sin clave, 500 otros), como en el valorador de Ecuador.
- **Salida:** texto con marcas de sección. El servidor calcula las palabras y los minutos estimados (150 palabras por minuto).
- **Interfaz:** ventana editable con el guion, tiempo estimado, **Copiar**, **Descargar Word**, **Descargar PDF** y **Regenerar**. Se guarda en el historial, accesible desde un botón "Guiones anteriores".

---

## Configuración (`.env`)

```
GEMINI_API_KEY=
GEMINI_MODEL=gemini-2.5-flash
PORT=5050
DATA_DIR=          # por defecto %LOCALAPPDATA%\GuionDeMedios
```

---

## Pruebas

pytest por módulo, sin red:
- Colectores con XML y HTML de ejemplo guardados en `tests/fixtures/`, incluido el caso de fuente caída.
- Clasificador: varios temas, personajes, `menciona_sv` y regionales.
- Clusterer y scorer: los tests de Ecuador adaptados al agrupamiento por país.
- Store: tablas, deduplicación por URL y recálculo del mes en curso.
- Watcher: bloqueo contra corridas simultáneas y fuentes que fallan.
- App: filtros combinados de país, tema y personaje, y la regla de personajes vacíos.
- Guionista y valorador con Gemini simulado: prompt, reintento y errores.
- Exportación del guion a Word y PDF.

Además, una **prueba manual de humo** con red real: correr el watcher una vez, revisar el estado de fuentes y generar un guion con 3 noticias.

---

## Fuera de alcance (esta versión)

- **Pulso en redes** (Google Trends, YouTube, Reddit, Bluesky): queda para la **etapa 2**.
- Publicación en internet y login.
- Datos de X/Twitter, Facebook, Instagram y TikTok (no hay acceso gratuito).
- Otros formatos de guion (reels o shorts por noticia): se agregan después como ajuste.
- Interfaz para administrar fuentes o personajes: se editan en `config/`.
