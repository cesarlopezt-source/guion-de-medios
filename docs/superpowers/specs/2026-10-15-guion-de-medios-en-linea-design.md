# Guion de Medios en línea — Diseño

**Fecha:** 2026-10-15
**Estado:** En revisión
**Parte de:** `2026-10-15-guion-de-medios-design.md` (portal local ya implementado en la rama `implementacion`)

---

## Objetivo

Poder abrir Guion de Medios **desde cualquier equipo y lugar**, aunque la PC esté apagada, sin pagar nada:

- **PC encendida:** el watcher sigue guardando el histórico en la PC cada hora y además lo sube a una base en la nube. La página en internet muestra todo.
- **PC apagada:** la página en internet muestra lo último guardado y, si tiene más de 2 horas, **busca en vivo** y guarda lo encontrado en la nube.
- **PC se enciende:** el watcher baja lo que la nube encontró en vivo, recolecta y sube todo.

**Criterios de éxito:**
- La página en internet abre con contraseña desde un celular o cualquier PC, con la PC apagada.
- Con la PC apagada y datos de más de 2 h, la página busca en vivo y muestra noticias nuevas en menos de 3 minutos.
- Al encender la PC, las noticias encontradas en vivo aparecen en la base local.
- Costo $0: Render gratis, Neon gratis, sin cron externo que mantenga despierto a Render.

---

## Arquitectura

```
PC encendida:   watcher (cada hora) → SQLite PC  ⇄  Neon (Postgres) ← Render (portal en internet) lo lee
PC apagada:     Render → ¿última actualización > 2 h? → búsqueda en vivo (segundo plano) → Neon
PC se enciende: watcher → baja de Neon lo encontrado en vivo → recolecta → sube a Neon
```

**Un solo código, dos modos** (variable `MODO`):

| | `MODO=pc` (por defecto) | `MODO=nube` |
|---|---|---|
| Dónde | Tu PC (Windows, tareas programadas) | Render (Linux, gunicorn) |
| Base | SQLite en `%LOCALAPPDATA%` | Neon (`DATABASE_URL`) |
| Sincronización | Sí, en cada corrida del watcher, si hay `DATABASE_URL` en `.env` | No aplica |
| Contraseña | No (solo `127.0.0.1`) | Sí, `APP_PASSWORD` |
| Recolección | Tarea programada cada hora | En vivo, en segundo plano, cuando los datos tienen más de 2 h o al presionar Actualizar |
| Verificación de enlaces | Sí (watcher) | No (lee lo que subió la PC) |

---

## Base en la nube (Neon)

Proyecto nuevo de Neon, `guion-de-medios`, separado del de Versa. Plan gratuito de 0,5 GB.

**Tablas:** las mismas de SQLite (`articulos`, `noticias`, `estado_fuentes`, `corridas`, `guiones`, `enlaces`) en Postgres (`jsonb` para listas, `timestamptz` para fechas), con estos cambios:
- `articulos.origen` (`pc` | `nube`): quién lo recolectó.
- `corridas.origen` (`pc` | `nube`). La "última actualización" es la última corrida terminada con éxito, de cualquier origen.
- `guiones.uid` (texto único, UUID): identifica un guion en las dos bases. **SQLite también recibe la columna `uid`**: migración con `ALTER TABLE` si falta, generando UUID para los guiones existentes.

**Espacio:**
- `noticias` (agrupadas) se conservan **para siempre**: unos 2 MB por mes.
- `articulos` se conservan solo del **mes actual y el anterior** (hora de El Salvador). Los más viejos se borran en cada sincronización. La PC los conserva todos.

---

## Acceso a datos

`store.py` se divide en un paquete con la misma interfaz pública para los dos motores:

- `store/__init__.py`: elige el motor según `MODO` y expone las mismas funciones que hoy (`guardar_articulos`, `obtener_articulos`, `reemplazar_noticias`, `obtener_noticias`, `meses_disponibles`, `registrar_estado_fuente`, `obtener_estado_fuentes`, `iniciar_corrida`, `finalizar_corrida`, `ultima_corrida`, `guardar_guion`, `listar_guiones`, `obtener_guion`, `guardar_estado_enlaces`, `obtener_estado_enlaces`, `urls_por_verificar`).
- `store/sqlite.py`: el código actual.
- `store/postgres.py`: lo mismo con `psycopg` (v3).
- Las funciones nuevas que necesita la sincronización (bajar y subir por marca de tiempo, podar, corrida en curso) existen en los dos motores.

El resto del código (clasificador, agrupación, guion, exportación y pantalla) **no cambia**: sigue llamando a `store.<función>`.

---

## Sincronización (`sincronizacion.py`, solo PC)

Se ejecuta **dentro de cada corrida del watcher** si `.env` tiene `DATABASE_URL`:

1. **Bajar** de Neon:
   - los artículos con `origen = 'nube'` y `recolectado` posterior a la marca `bajada_articulos`;
   - los guiones cuyo `uid` no existe en la PC.

   Se insertan en SQLite sin duplicar: los artículos por URL, los guiones por `uid`.
2. **Recolectar, clasificar y reconstruir:** como hoy. Los artículos bajados entran en la reconstrucción del mes.
3. **Subir** a Neon:
   - los artículos locales con `recolectado` posterior a la marca `subida_articulos` (`ON CONFLICT (url) DO NOTHING`);
   - las `noticias` de los meses reconstruidos (reemplazo por mes, en una transacción);
   - el estado de fuentes;
   - los enlaces verificados desde la marca `subida_enlaces`;
   - los guiones locales que no estén en Neon;
   - la corrida, con `origen = 'pc'`.
4. **Podar** en Neon los artículos anteriores al mes previo.

**Marcas:** tabla `sync_marcas (clave, valor)` en SQLite. Cada marca avanza **solo si su paso terminó bien**.

**Fallos:** si Neon no responde o falla a mitad de camino, la corrida local se completa igual. El error queda en `watcher.log` y en `estado_fuentes` como la fuente "Sincronización con la nube", y se reintenta en la siguiente corrida. Si no se puede tomar el bloqueo en Neon por falta de conexión, la PC recolecta igual, solo en local. Como las inserciones son idempotentes (por URL o `uid`), repetir un paso no duplica nada.

---

## Búsqueda en vivo (`MODO=nube`)

- `GET /api/meta` informa `ultima_actualizacion` y `en_curso`. Si la última actualización tiene **más de 2 horas** y no hay corrida en curso, arranca la búsqueda en un **hilo en segundo plano** y responde `en_curso: true`. El botón **Actualizar** hace lo mismo sin esperar las 2 horas.
- La búsqueda es la misma `watcher.correr` (recolectar → clasificar → guardar → reconstruir los meses), sobre Neon, con `origen = 'nube'` y **sin verificar enlaces**.
- **Bloqueo:** en lugar del archivo `watcher.lock`, una corrida con `fin` vacío e `inicio` de hace menos de 15 minutos cuenta como "en curso". Sirve tanto para la PC como para la nube. Una corrida abandonada por más de 15 minutos deja de bloquear. `watcher.correr` recibe el bloqueo como parámetro: archivo en la PC y base de datos en la nube. La PC usa los dos (primero el archivo y, si sincroniza, también el de la base) para no recolectar al mismo tiempo que la nube.
- La pantalla ya muestra "Actualizando…" y refresca al terminar. El texto cambia a **"Buscando noticias en vivo…"** cuando la corrida es de la nube.

---

## Contraseña (`MODO=nube`)

- Se porta el login del proyecto de Ecuador: `templates/login.html`, `GET/POST /login`, `GET /logout` y sesión Flask firmada con `FLASK_SECRET_KEY`.
- Sin sesión, las páginas redirigen a `/login` y las rutas `/api/*` responden **401** `{error}`. La pantalla, al recibir 401, redirige a `/login`.
- Cookie de sesión `Secure`, `HttpOnly` y `SameSite=Lax`.
- `MODO=pc` no pide contraseña.

---

## Publicación

- **Repositorio privado en GitHub:** `cesarlopezt-source/guion-de-medios` (rama `master`). Render se vuelve a desplegar en cada push. Crear el repo y hacer push requiere la confirmación de César en el momento.
- **`render.yaml`:** servicio web `guion-de-medios`, plan `free`, Python 3.12.
  - Build: `pip install -r requirements.txt`.
  - Start: `gunicorn app:app --workers 1 --threads 4 --timeout 120`. Un solo proceso, para que el hilo de búsqueda en vivo sea único.
  - Variables: `MODO=nube`, y `DATABASE_URL`, `APP_PASSWORD`, `GEMINI_API_KEY` sin valor en el archivo (se pegan en Render). `FLASK_SECRET_KEY` la genera Render.
- **`requirements.txt`** suma `psycopg[binary]` y `gunicorn`.
- **PC:** `.env` suma `DATABASE_URL`. La sincronización empieza en la siguiente corrida.
- **Sin cron externo hacia Render:** solo se despierta cuando alguien abre la página, así que el uso queda muy por debajo de las 750 h gratis. César revisa y apaga el cron de cron-job.org del proyecto de Ecuador, si existe.

**Pasos de César** (no se pueden automatizar: crear cuentas o servicios e ingresar claves):
1. Neon: crear el proyecto `guion-de-medios` y una rama `test`, y copiar las dos direcciones de conexión.
2. Render: New → Blueprint → elegir el repo. Pegar `DATABASE_URL`, `APP_PASSWORD` y `GEMINI_API_KEY`.
3. Poner `DATABASE_URL` en el `.env` de la PC y `TEST_DATABASE_URL` (rama `test`) para las pruebas.
4. Revisar el cron de Ecuador en cron-job.org.

---

## Pruebas

- **Contrato de datos:** las pruebas de `store` corren **con los dos motores**. Postgres usa `TEST_DATABASE_URL` (rama `test` de Neon); si no está definida, esas pruebas se saltan con un aviso.
- **Sincronización:**
  - bajar y subir con dos bases de prueba (SQLite + Postgres de prueba);
  - repetir no duplica;
  - un fallo a mitad no avanza la marca;
  - la poda borra solo artículos de meses viejos;
  - los guiones se cruzan por `uid`;
  - migración de `uid` en una base SQLite existente.
- **Búsqueda en vivo:**
  - con datos de más de 2 h, `/api/meta` arranca un solo hilo y no arranca otro si ya hay uno en curso;
  - el bloqueo por base expira a los 15 min.
- **Login:**
  - sin sesión, `/` redirige y `/api/news` responde 401;
  - con contraseña correcta funciona e incorrecta muestra error;
  - `MODO=pc` no pide nada.
- **Prueba real al final:** desactivar la tarea del watcher (simula la PC apagada) → abrir la página publicada → ver la búsqueda en vivo → reactivar el watcher → comprobar que las noticias encontradas en vivo están en la base de la PC.

---

## Fuera de alcance

- Dominio propio (se usa `guion-de-medios.onrender.com`).
- Plan pago de Render o mantenerlo despierto.
- Partidos políticos y "Pulso en redes".
- Varios usuarios o contraseñas distintas.
- Los pendientes menores de la revisión anterior (recarga automática de la lista, enlaces de Google News, estrellas en el PDF).
