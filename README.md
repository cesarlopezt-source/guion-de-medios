# MIXCOM News Monitor · Centroamérica

Portal local que reúne cada hora las noticias de medios centroamericanos (foco El Salvador), permite filtrarlas por país, tema y personaje, y genera con Gemini un **Guion de medios**: un guion de noticiero de 3 a 5 minutos para grabar en video.

Abrir: acceso directo **Guion de Medios** en el escritorio, o <http://127.0.0.1:5050>. Solo funciona en esta PC.

## Cómo funciona

- **Watcher** (`watcher.py`): la tarea programada `GuionMedios-Watcher` lo corre cada hora. Lee los RSS de los medios, la lectura web de los que no tienen RSS y Google News (una búsqueda por medio y una por personaje). Clasifica, agrupa noticias parecidas, calcula el puntaje y lo guarda todo en la base local.
- **Portal** (`serve.py`): la tarea `GuionMedios-Portal` lo inicia 2 minutos después de iniciar sesión en Windows. Solo lee la base, así que los filtros responden al instante.
- **Estado de fuentes**: enlace en el encabezado del portal; muestra qué medio respondió en la última corrida.
- **Enlaces reales**: Google News entrega un enlace intermedio que no abre desde un PDF (error 405). La PC lo cambia por el enlace del medio (`collectors/google_enlaces.py`): hasta 200 nuevos y 100 atrasados por corrida, con 3 s entre pedidos. Si Google bloquea (429 o su página "sorry") se pausa 3 horas; la recolección normal de Google News no se ve afectada. Para convertir de una vez los ya guardados: `python scripts/convertir_enlaces.py`.
- **Resto del mundo** (Estados Unidos, Canadá, México, Caribe, Sudamérica, Unión Europea, Europa, Asia, Medio Oriente): `config/regiones.py`. Solo entran notas cuyo titular nombra la región Y a El Salvador o Centroamérica. Además de las búsquedas en español hay búsquedas en inglés y portugués; esos titulares se traducen al español con Gemini (`traductor.py`).
- **Organismos** (FMI, BID, Banco Mundial, ONU, BCIE, OEA, CEPAL, SICA, Unión Europea): `config/organismos.py`. Tienen menú propio en el portal (sin marcar = sin filtro) y búsquedas propias.
- **Ámbito**: Nacionales = noticias de El Salvador (predeterminado); Internacionales = de otros países y las de El Salvador sobre su relación con otra región.
- **Mini brief**: botón aparte del guion. Por noticia (qué pasó y por qué importa), análisis general o ambos; se descarga en PDF o Word con los links.
- **Exportar**: "Informe completo" o "Solo temas y links" (titular y links de cada noticia) en Word, Excel o PDF.

## Dónde está cada cosa

| Qué | Dónde |
|---|---|
| Código | esta carpeta |
| Base de datos | `%LOCALAPPDATA%\GuionDeMedios\guion.db` (fuera de Google Drive a propósito) |
| Logs del watcher | `%LOCALAPPDATA%\GuionDeMedios\logs\watcher.log` |
| Entorno de Python | `%LOCALAPPDATA%\GuionDeMedios\venv` |
| Clave de Gemini y modelos | `.env` (copiar de `.env.example`; no se sube a git) |

## Ajustar sin tocar código

- **El guion** (tono, duración, saludo, despedida): `config/guion_instrucciones.md`.
- **Medios**: `config/fuentes.py`. `activa=False` apaga la lectura directa, pero el medio sigue entrando por Google News gracias a su `dominio`. Para probar todos: `python scripts/verificar_fuentes.py --todas`.
- **Temas y palabras clave**: `config/temas.py`.
- **Personajes**: `config/personajes.py` (nombre visible → variantes que se buscan).

Después de cambiar la configuración, reinicia el portal: `Stop-ScheduledTask GuionMedios-Portal; Start-ScheduledTask GuionMedios-Portal`.

## En línea (desde cualquier equipo)

La misma aplicación corre también en **Render** (`MODO=nube`, con contraseña) sobre una base **Supabase** (Postgres):

- **PC encendida:** cada corrida del watcher baja de Supabase lo que la página encontró en vivo, recolecta y sube artículos, noticias, estado de fuentes, enlaces y guiones. Para activarlo basta con poner `DATABASE_URL` en el `.env` de la PC.
- **PC apagada:** si los datos en Supabase tienen más de 2 horas, la página de Render busca en vivo (1 a 3 min) y guarda lo encontrado en Supabase. El botón Actualizar hace lo mismo.
- Supabase guarda las noticias agrupadas para siempre y los artículos sueltos solo del mes actual y el anterior. La PC conserva todo.
- Render gratis se duerme a los 15 min sin uso; no hay ningún cron que lo despierte, así que las horas gratis alcanzan de sobra.
- El estado de la sincronización aparece en **Estado de fuentes** como "Sincronización con la nube".

Dirección de Supabase: **Connect → Session pooler** (no "Transaction pooler": la sincronización usa tablas temporales y bloqueos de sesión). Se copia el URI con la contraseña de la base puesta en lugar de `[YOUR-PASSWORD]`.

Publicación: `render.yaml` (Blueprint). En Render se cargan `DATABASE_URL`, `APP_PASSWORD` y `GEMINI_API_KEY`; `FLASK_SECRET_KEY` la genera Render.

Pruebas del motor Postgres: usan `TEST_DATABASE_URL` si está en `.env`; si no, levantan un Postgres local (`pip install -r requirements-dev.txt`).

## Instalación (una vez)

```powershell
python -m venv "$env:LOCALAPPDATA\GuionDeMedios\venv"
& "$env:LOCALAPPDATA\GuionDeMedios\venv\Scripts\python.exe" -m pip install -r requirements.txt
copy .env.example .env   # y poner GEMINI_API_KEY
powershell -ExecutionPolicy Bypass -File scripts\instalar.ps1
```

Pruebas: `& "$env:LOCALAPPDATA\GuionDeMedios\venv\Scripts\python.exe" -m pytest -q`

## Desinstalar

```powershell
Unregister-ScheduledTask GuionMedios-Watcher -Confirm:$false
Unregister-ScheduledTask GuionMedios-Portal -Confirm:$false
```

Luego borra el acceso directo del escritorio y, si quieres, la carpeta `%LOCALAPPDATA%\GuionDeMedios`.
