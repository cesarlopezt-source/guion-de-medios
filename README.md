# Guion de Medios · Centroamérica

Portal local que reúne cada hora las noticias de medios centroamericanos (foco El Salvador), permite filtrarlas por país, tema y personaje, y genera con Gemini un **Guion de medios**: un guion de noticiero de 3 a 5 minutos para grabar en video.

Abrir: acceso directo **Guion de Medios** en el escritorio, o <http://127.0.0.1:5050>. Solo funciona en esta PC.

## Cómo funciona

- **Watcher** (`watcher.py`): la tarea programada `GuionMedios-Watcher` lo corre cada hora. Lee los RSS de los medios, la lectura web de los que no tienen RSS y Google News (una búsqueda por medio y una por personaje). Clasifica, agrupa noticias parecidas, calcula el puntaje y lo guarda todo en la base local.
- **Portal** (`serve.py`): la tarea `GuionMedios-Portal` lo inicia 2 minutos después de iniciar sesión en Windows. Solo lee la base, así que los filtros responden al instante.
- **Estado de fuentes**: enlace en el encabezado del portal; muestra qué medio respondió en la última corrida.

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

La misma aplicación corre también en **Render** (`MODO=nube`, con contraseña) sobre una base **Neon** (Postgres):

- **PC encendida:** cada corrida del watcher baja de Neon lo que la página encontró en vivo, recolecta y sube artículos, noticias, estado de fuentes, enlaces y guiones. Para activarlo basta con poner `DATABASE_URL` en el `.env` de la PC.
- **PC apagada:** si los datos en Neon tienen más de 2 horas, la página de Render busca en vivo (1 a 3 min) y guarda lo encontrado en Neon. El botón Actualizar hace lo mismo.
- Neon guarda las noticias agrupadas para siempre y los artículos sueltos solo del mes actual y el anterior. La PC conserva todo.
- Render gratis se duerme a los 15 min sin uso; no hay ningún cron que lo despierte, así que las horas gratis alcanzan de sobra.
- El estado de la sincronización aparece en **Estado de fuentes** como "Sincronización con la nube".

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
