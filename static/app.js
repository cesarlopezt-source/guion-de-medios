const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const MAX_GUION = 12;
const MAX_BRIEF = 40;
const CLAVE_FILTROS = "gm_filtros";
const FILTROS_INICIALES = {
    paises: ["SV"],
    temas: ["Economía", "Inversión", "Finanzas", "Negocios", "Activos Digitales", "Política", "Coyuntura", "Social"],
    personajes: [],
    partidos: [],
    ambitos: [],
    temasConocidos: null,  // temas que existían la última vez; los nuevos se marcan solos
    orden: "importancia",
};

let meta = null;
let noticias = [];                 // lo que devolvió /api/news con los filtros actuales
const seleccion = new Map();       // "pais|titulo" → noticia completa (sobrevive filtros y recargas)
const valoraciones = new Map();    // "pais|titulo" → texto
let filtros = cargarFiltros();
let periodo = null;                // {mes, anio}; null = sigue el mes actual de El Salvador (meta.mes_actual)
let ultimaPeticion = 0;            // solo se pinta la respuesta de la consulta más reciente

// Clave estable entre recálculos: el enlace del artículo más antiguo del grupo (fuentes[0]) no cambia
// aunque llegue una nota con un título más largo.
// En internet la sesión puede vencer: cualquier 401 lleva a la pantalla de contraseña.
async function api(url, opciones) {
    const resp = await fetch(url, opciones);
    if (resp.status === 401) {
        location.href = "/login";
        throw new Error("Sesión expirada");
    }
    return resp;
}

const clave = n => `${n.pais}|${n.fuentes[0] ? n.fuentes[0].url : n.titulo}`;
const urlSegura = u => /^https?:\/\//i.test(u || "") ? u : "#";

function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, c =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// La lista "personajes" de cada noticia trae también los partidos; en la tarjeta van separados.
const partidosDe = n => n.personajes.filter(p => meta.partidos.includes(p));
const personasDe = n => n.personajes.filter(p => !meta.partidos.includes(p));

/* ---------- Filtros (recordados en el navegador) ---------- */

function cargarFiltros() {
    try {
        const guardado = JSON.parse(localStorage.getItem(CLAVE_FILTROS));
        if (guardado && Array.isArray(guardado.paises)) return structuredClone({ ...FILTROS_INICIALES, ...guardado });
    } catch (e) { /* almacenamiento no disponible: se usan los iniciales */ }
    return structuredClone(FILTROS_INICIALES);
}

function guardarFiltros() {
    try { localStorage.setItem(CLAVE_FILTROS, JSON.stringify(filtros)); } catch (e) { /* sin almacenamiento */ }
}

const MENUS = [
    { grupo: "paises", titulo: "Países" },
    { grupo: "temas", titulo: "Temas" },
    { grupo: "personajes", titulo: "Personajes" },
    { grupo: "partidos", titulo: "Partidos" },
    { grupo: "ambitos", titulo: "Ámbito" },
];
// En estos menús no marcar nada = "Sin filtro" (salen todas las noticias); las casillas eligen a quién buscar.
const VACIO_ES_TODOS = ["personajes", "partidos", "ambitos"];
const textoTodos = grupo => VACIO_ES_TODOS.includes(grupo) ? "Sin filtro" : "Todos";

function opcionesDe(grupo) {
    if (grupo === "paises") return meta.paises.map(p => ({ valor: p.codigo, texto: p.nombre }));
    return meta[grupo].map(v => ({ valor: v, texto: v }));
}

function construirMenus() {
    const cont = document.getElementById("menus");
    cont.innerHTML = MENUS.map(({ grupo, titulo }) => `
<div class="dropdown" data-grupo="${grupo}">
  <button class="dd-boton" onclick="abrirMenu('${grupo}', event)" aria-haspopup="true">
    <span class="dd-titulo">${titulo}:</span> <span class="dd-resumen"></span> <span class="dd-flecha">▾</span>
  </button>
  <div class="dd-panel" hidden>
    <label class="dd-opcion dd-todos"><input type="checkbox" data-todos="1"> ${textoTodos(grupo)}</label>
    ${opcionesDe(grupo).map(o => `
    <label class="dd-opcion"><input type="checkbox" value="${escapeHtml(o.valor)}"> ${escapeHtml(o.texto)}</label>`).join("")}
  </div>
</div>`).join("");
    cont.querySelectorAll(".dropdown").forEach(dd => {
        const grupo = dd.dataset.grupo;
        dd.querySelectorAll("input").forEach(chk => {
            chk.onchange = () => chk.dataset.todos
                ? alternarTodos(grupo, opcionesDe(grupo).map(o => o.valor))
                : alternar(grupo, chk.value);
        });
    });
}

function abrirMenu(grupo, evento) {
    evento.stopPropagation();
    document.querySelectorAll(".dropdown").forEach(dd => {
        const panel = dd.querySelector(".dd-panel");
        panel.hidden = dd.dataset.grupo === grupo ? !panel.hidden : true;
    });
}

document.addEventListener("click", e => {
    if (!e.target.closest(".dropdown")) document.querySelectorAll(".dd-panel").forEach(p => { p.hidden = true; });
});

function resumen(grupo) {
    const marcados = filtros[grupo];
    const total = opcionesDe(grupo).length;
    if (marcados.length === total || (VACIO_ES_TODOS.includes(grupo) && marcados.length === 0)) return "Todos";
    if (marcados.length === 0) return "Ninguno";
    if (marcados.length === 1) {
        return (opcionesDe(grupo).find(o => o.valor === marcados[0]) || { texto: marcados[0] }).texto;
    }
    return `${marcados.length} seleccionados`;
}

function pintarMenus() {
    document.querySelectorAll(".dropdown").forEach(dd => {
        const grupo = dd.dataset.grupo;
        const marcados = filtros[grupo];
        const todos = resumen(grupo) === "Todos";
        const todosMarcado = VACIO_ES_TODOS.includes(grupo) ? marcados.length === 0 : todos;
        dd.querySelectorAll("input").forEach(chk => {
            chk.checked = chk.dataset.todos ? todosMarcado : marcados.includes(chk.value);
        });
        dd.querySelector(".dd-resumen").textContent = todos ? textoTodos(grupo) : resumen(grupo);
        dd.classList.toggle("filtrando", !todos);
    });
}

function alternar(grupo, valor) {
    const lista = filtros[grupo];
    const i = lista.indexOf(valor);
    if (i >= 0) lista.splice(i, 1); else lista.push(valor);
    filtrosCambiaron();
}

function alternarTodos(grupo, valores) {
    if (VACIO_ES_TODOS.includes(grupo)) {
        filtros[grupo] = [];  // "Todos" = no filtrar por este menú
    } else {
        filtros[grupo] = filtros[grupo].length === valores.length ? [] : [...valores];
    }
    filtrosCambiaron();
}

function filtrosCambiaron() {
    guardarFiltros();
    pintarMenus();
    cargarNoticias();
}

function cambiarOrden() {
    filtros.orden = document.getElementById("select-orden").value;
    filtrosCambiaron();
}

function cambiarPeriodo() {
    const [anio, mes] = document.getElementById("select-periodo").value.split("-").map(Number);
    const [anioActual, mesActual] = meta.mes_actual;
    periodo = (anio === anioActual && mes === mesActual) ? null : { anio, mes };
    cargarNoticias();
}

/* ---------- Carga de datos ---------- */

async function cargarMeta() {
    const habia = meta !== null;
    const anterior = habia ? meta.ultima_actualizacion : null;
    const resp = await api("/api/meta");
    meta = await resp.json();
    construirPeriodos();
    pintarUltima();
    // Terminó una corrida (watcher de la PC o búsqueda en vivo): se recarga la lista sola.
    if (habia && meta.ultima_actualizacion !== anterior) cargarNoticias();
}

// Revisa el estado cada 10 s mientras hay una corrida en curso y cada 60 s en reposo.
// Con la pestaña oculta o 30 min sin actividad deja de consultar, para que Render y Supabase
// puedan dormirse y no gasten las horas gratis; al volver retoma sola.
const INACTIVIDAD_MS = 30 * 60 * 1000;
let ultimaActividad = Date.now();
let vigilando = false;
let detenido = false;  // el ciclo se paró por pestaña oculta o inactividad

function pausado() {
    return document.hidden || Date.now() - ultimaActividad > INACTIVIDAD_MS;
}

function vigilar() {
    if (vigilando) return;
    vigilando = true;
    setTimeout(async () => {
        vigilando = false;
        if (pausado()) { detenido = true; return; }  // se reanuda con reanudar()
        try { await cargarMeta(); } catch (e) { /* sin conexión: se reintenta */ }
        vigilar();
    }, meta && meta.en_curso ? 10000 : 60000);
}

async function reanudar() {
    ultimaActividad = Date.now();
    if (!detenido || document.hidden) return;
    detenido = false;
    try { await cargarMeta(); } catch (e) { /* sin conexión */ }
    vigilar();
}

["click", "keydown", "scroll", "touchstart"].forEach(ev =>
    document.addEventListener(ev, reanudar, { passive: true }));
document.addEventListener("visibilitychange", () => { if (!document.hidden) reanudar(); });

function construirPeriodos() {
    const actual = meta.mes_actual;  // en hora de El Salvador, no la del navegador
    const meses = meta.meses.some(([a, m]) => a === actual[0] && m === actual[1]) ? meta.meses : [actual, ...meta.meses];
    const sel = document.getElementById("select-periodo");
    const elegido = periodo ? `${periodo.anio}-${periodo.mes}` : `${actual[0]}-${actual[1]}`;
    sel.innerHTML = meses.map(([a, m]) =>
        `<option value="${a}-${m}" ${`${a}-${m}` === elegido ? "selected" : ""}>${MESES[m - 1]} ${a}</option>`).join("");
}

function pintarUltima() {
    const el = document.getElementById("ultima");
    const btn = document.getElementById("btn-refresh");
    btn.disabled = meta.en_curso;
    if (meta.en_curso) {
        el.textContent = meta.origen_en_curso === "nube" ? "Buscando noticias en vivo…" : "Actualizando…";
        return;
    }
    if (!meta.ultima_actualizacion) { el.textContent = "Sin actualizaciones todavía"; return; }
    const min = Math.round((Date.now() - new Date(meta.ultima_actualizacion)) / 60000);
    el.textContent = `Última actualización: ${min < 1 ? "hace instantes" : min < 60 ? `hace ${min} min`
        : `hace ${Math.floor(min / 60)} h ${min % 60} min`}`;
}

async function cargarNoticias() {
    const cont = document.getElementById("news-container");
    const peticion = ++ultimaPeticion;
    if (!filtros.paises.length || !filtros.temas.length) {
        noticias = [];
        document.getElementById("result-count").textContent = "";
        cont.innerHTML = '<p class="status-msg">Marca al menos un país y un tema.</p>';
        return;
    }
    const params = new URLSearchParams({
        paises: filtros.paises.join(","), temas: filtros.temas.join(","),
        personajes: (resumen("personajes") === "Todos" ? [] : filtros.personajes).join(","),
        partidos: (resumen("partidos") === "Todos" ? [] : filtros.partidos).join(","),
        ambitos: (resumen("ambitos") === "Todos" ? [] : filtros.ambitos).join(","), orden: filtros.orden,
    });
    const [anio, mes] = periodo ? [periodo.anio, periodo.mes] : meta.mes_actual;
    params.set("mes", mes);
    params.set("anio", anio);
    try {
        const resp = await api(`/api/news?${params}`);
        if (!resp.ok) throw new Error(`Error del servidor: ${resp.status}`);
        const datos = await resp.json();
        if (peticion !== ultimaPeticion) return;  // llegó tarde: ya hay una consulta más nueva
        noticias = datos;
        pintarNoticias();
    } catch (err) {
        if (peticion !== ultimaPeticion) return;
        cont.innerHTML = `<p class="error-msg">Error al cargar noticias: ${escapeHtml(err.message)}</p>`;
    }
}

/* ---------- Tarjetas ---------- */

function nombrePais(codigo) {
    return (meta.paises.find(p => p.codigo === codigo) || { nombre: codigo }).nombre;
}

function pintarNoticias() {
    const cont = document.getElementById("news-container");
    document.getElementById("result-count").textContent = `${noticias.length} noticias`;
    if (!noticias.length) {
        cont.innerHTML = '<p class="status-msg">No hay noticias con estos filtros en este periodo.</p>';
        return;
    }
    cont.innerHTML = noticias.map((n, i) => {
        const k = clave(n);
        const sel = seleccion.has(k);
        const valoracion = valoraciones.get(k) || "";
        const fuentes = n.fuentes.map(f => {
            const estado = f.activa === undefined ? "" : f.activa
                ? ' <span class="link-status active">● activa</span>'
                : ' <span class="link-status inactive">● no disponible</span>';
            return `<a href="${escapeHtml(urlSegura(f.url))}" target="_blank" rel="noopener">${escapeHtml(f.nombre)}</a>${estado}`;
        }).join("");
        const fecha = new Date(n.publicado).toLocaleString("es-SV", { dateStyle: "medium", timeStyle: "short" });
        return `
<div class="news-card ${sel ? "sel" : ""}" data-pais="${n.pais}">
  <div class="card-header">
    <span class="stars">${"★".repeat(n.estrellas)}${"☆".repeat(5 - n.estrellas)}</span>
    <span class="pais-badge ${n.pais}">${escapeHtml(nombrePais(n.pais))}</span>
    ${n.temas.map(t => `<span class="tema-badge">${escapeHtml(t)}</span>`).join("")}
    ${n.menciona_sv ? '<span class="sv-badge">Menciona El Salvador</span>' : ""}
    <span class="card-meta">${n.n_fuentes} medio${n.n_fuentes > 1 ? "s" : ""} · ${fecha}</span>
    <input type="checkbox" class="select-chk" data-i="${i}" ${sel ? "checked" : ""} onchange="alternarSeleccion(this)">
  </div>
  <div class="news-title">${escapeHtml(n.titulo)}</div>
  ${n.resumen ? `<div class="news-summary">${escapeHtml(n.resumen)}</div>` : ""}
  ${personasDe(n).length ? `<div class="personajes">👤 ${personasDe(n).map(escapeHtml).join(", ")}</div>` : ""}
  ${partidosDe(n).length ? `<div class="personajes">🏛️ ${partidosDe(n).map(escapeHtml).join(", ")}</div>` : ""}
  <div class="card-sources">${fuentes}</div>
  ${sel && valoracion ? `
  <div class="card-valoracion">
    <span class="valoracion-label">📝 Valoración:</span>
    <textarea class="valoracion-text" rows="2" data-k="${escapeHtml(k)}" oninput="editarValoracion(this)">${escapeHtml(valoracion)}</textarea>
  </div>` : ""}
</div>`;
    }).join("");
}

function alternarSeleccion(chk) {
    const n = noticias[Number(chk.dataset.i)];
    if (chk.checked) seleccion.set(clave(n), n); else seleccion.delete(clave(n));
    actualizarContador();
    pintarNoticias();
}

function seleccionarVisibles() {
    noticias.forEach(n => seleccion.set(clave(n), n));
    actualizarContador();
    pintarNoticias();
}

function quitarSeleccion() {
    seleccion.clear();
    actualizarContador();
    pintarNoticias();
}

function editarValoracion(textarea) {
    valoraciones.set(textarea.dataset.k, textarea.value);
}

function actualizarContador() {
    const n = seleccion.size;
    document.getElementById("selected-count").textContent =
        `${n} noticia${n === 1 ? "" : "s"} seleccionada${n === 1 ? "" : "s"}${n > MAX_GUION ? ` · máximo ${MAX_GUION} para el guion` : ""}`;
    document.getElementById("btn-valorar").disabled = n === 0;
    const btnGuion = document.getElementById("btn-guion");
    btnGuion.disabled = n === 0 || n > MAX_GUION;
    btnGuion.title = n > MAX_GUION ? `Máximo ${MAX_GUION} noticias` : "";
    const btnBrief = document.getElementById("btn-brief");
    btnBrief.disabled = n === 0 || n > MAX_BRIEF;
    btnBrief.title = n > MAX_BRIEF ? `Máximo ${MAX_BRIEF} noticias` : "";
}

function seleccionadasConValoracion() {
    return [...seleccion.entries()].map(([k, n]) => ({ ...n, valoracion: valoraciones.get(k) || "" }));
}

/* ---------- Acciones ---------- */

async function actualizar() {
    const btn = document.getElementById("btn-refresh");
    btn.disabled = true;
    document.getElementById("ultima").textContent = "Actualizando…";
    await api("/api/actualizar", { method: "POST" });
    await cargarMeta();  // vigilar() pasa a revisar cada 10 s y recarga la lista al terminar
}

async function valorarSeleccionadas() {
    const btn = document.getElementById("btn-valorar");
    btn.disabled = true;
    btn.textContent = "Valorando…";
    try {
        const items = [...seleccion.values()];
        const resp = await api("/api/valorar", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ items }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || resp.status);
        for (const v of data) {
            const n = items.find(x => x.titulo === v.titulo);
            if (n && v.valoracion) valoraciones.set(clave(n), v.valoracion);
        }
        pintarNoticias();
    } catch (err) {
        alert(`No se pudo valorar: ${err.message}`);
    } finally {
        btn.textContent = "Valorar ✦";
        actualizarContador();
    }
}

async function descargar(url, cuerpo, nombre) {
    const resp = await api(url, {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(cuerpo),
    });
    if (!resp.ok) { alert("No se pudo generar el archivo."); return; }
    const a = document.createElement("a");
    a.href = URL.createObjectURL(await resp.blob());
    a.download = nombre;
    a.click();
    URL.revokeObjectURL(a.href);
}

function exportar(formato) {
    if (!seleccion.size) { alert("Selecciona al menos una noticia."); return; }
    const ext = { word: "docx", excel: "xlsx", pdf: "pdf" }[formato];
    const modo = document.getElementById("select-contenido").value;
    const nombre = modo === "links" ? "temas_y_links" : "noticias_centroamerica";
    descargar("/api/export", { items: seleccionadasConValoracion(), format: formato, modo }, `${nombre}.${ext}`);
}

/* ---------- Guion de medios ---------- */

function abrirModal(id) { document.getElementById(id).hidden = false; }
function cerrarModal(id) { document.getElementById(id).hidden = true; }

function contarPalabras(texto) {
    return texto.split("\n").filter(l => !/^\s*\[[^\]]+\]\s*$/.test(l))
        .reduce((total, l) => total + l.split(/\s+/).filter(Boolean).length, 0);
}

function recalcularTiempo() {
    const palabras = contarPalabras(document.getElementById("guion-texto").value);
    document.getElementById("guion-tiempo").textContent =
        `≈ ${(palabras / 150).toFixed(1)} min · ${palabras} palabras`;
}

function mostrarGuion(texto, estado) {
    document.getElementById("guion-texto").value = texto;
    document.getElementById("guion-estado").textContent = estado || "";
    recalcularTiempo();
    abrirModal("modal-guion");
}

async function generarGuion() {
    const items = seleccionadasConValoracion();
    if (!items.length || items.length > MAX_GUION) return;
    mostrarGuion("", `Escribiendo el guion con ${items.length} noticia${items.length > 1 ? "s" : ""}…`);
    const btn = document.getElementById("btn-guion");
    btn.disabled = true;
    try {
        const resp = await api("/api/guion", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ noticias: items }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || resp.status);
        mostrarGuion(data.texto, "Puedes editar el texto antes de copiarlo o descargarlo.");
    } catch (err) {
        mostrarGuion("", `No se pudo generar el guion: ${err.message}`);
    } finally {
        actualizarContador();
    }
}

async function copiarGuion() {
    const texto = document.getElementById("guion-texto").value;
    try {
        await navigator.clipboard.writeText(texto);
        document.getElementById("guion-estado").textContent = "Copiado al portapapeles.";
    } catch (e) {
        document.getElementById("guion-texto").select();
        document.execCommand("copy");
    }
}

function descargarGuion(formato) {
    const texto = document.getElementById("guion-texto").value;
    descargar("/api/guion/export", { texto, formato }, `guion_de_medios.${formato === "word" ? "docx" : "pdf"}`);
}

async function abrirHistorial() {
    const lista = document.getElementById("lista-guiones");
    lista.innerHTML = "<li>Cargando…</li>";
    abrirModal("modal-historial");
    const guiones = await (await api("/api/guiones")).json();
    lista.innerHTML = guiones.length ? guiones.map(g => `
        <li onclick="abrirGuion(${g.id})">
            ${escapeHtml(g.titulos.slice(0, 3).join(" · "))}${g.titulos.length > 3 ? " …" : ""}
            <small>${new Date(g.creado).toLocaleString("es-SV")} · ${g.titulos.length} noticias · ≈ ${g.minutos} min</small>
        </li>`).join("") : "<li>Todavía no hay guiones.</li>";
}

async function abrirGuion(id) {
    const g = await (await api(`/api/guiones/${id}`)).json();
    cerrarModal("modal-historial");
    mostrarGuion(g.texto, `Guion del ${new Date(g.creado).toLocaleString("es-SV")}.`);
}

/* ---------- Mini brief ---------- */

function abrirBrief() {
    const n = seleccion.size;
    document.getElementById("brief-estado").textContent =
        `${n} noticia${n === 1 ? "" : "s"} seleccionada${n === 1 ? "" : "s"}. Elige el contenido y pulsa Generar.`;
    abrirModal("modal-brief");
}

async function generarBrief() {
    const items = [...seleccion.values()];
    if (!items.length || items.length > MAX_BRIEF) return;
    const modo = document.getElementById("select-brief-modo").value;
    const estado = document.getElementById("brief-estado");
    const btn = document.getElementById("btn-brief-generar");
    btn.disabled = true;
    estado.textContent = `Escribiendo con ${items.length} noticia${items.length > 1 ? "s" : ""}…`;
    try {
        const resp = await api("/api/brief", {
            method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ noticias: items, modo }),
        });
        const data = await resp.json();
        if (!resp.ok) throw new Error(data.error || resp.status);
        document.getElementById("brief-texto").value = data.texto;
        estado.textContent = "Puedes editar el texto antes de copiarlo o descargarlo.";
    } catch (err) {
        estado.textContent = `No se pudo generar: ${err.message}`;
    } finally {
        btn.disabled = false;
    }
}

async function copiarBrief() {
    const texto = document.getElementById("brief-texto").value;
    try {
        await navigator.clipboard.writeText(texto);
        document.getElementById("brief-estado").textContent = "Copiado al portapapeles.";
    } catch (e) {
        document.getElementById("brief-texto").select();
        document.execCommand("copy");
    }
}

function descargarBrief(formato) {
    const texto = document.getElementById("brief-texto").value;
    if (!texto.trim()) { alert("Primero genera el mini brief."); return; }
    descargar("/api/brief/export", { texto, formato }, `mini_brief.${formato === "word" ? "docx" : "pdf"}`);
}

document.addEventListener("keydown", e => {
    if (e.key === "Escape") { cerrarModal("modal-guion"); cerrarModal("modal-historial"); cerrarModal("modal-brief"); }
});

/* ---------- Inicio ---------- */

(async function iniciar() {
    try {
        await cargarMeta();
        construirMenus();
        // Descarta del estado guardado opciones que ya no existen en la configuración.
        filtros.paises = filtros.paises.filter(p => meta.paises.some(x => x.codigo === p));
        filtros.temas = filtros.temas.filter(t => meta.temas.includes(t));
        filtros.personajes = filtros.personajes.filter(p => meta.personajes.includes(p));
        filtros.partidos = filtros.partidos.filter(p => meta.partidos.includes(p));
        filtros.ambitos = filtros.ambitos.filter(a => meta.ambitos.includes(a));
        // Temas agregados después de la última visita: se marcan para que se vean.
        // (Sin registro previo, los nuevos son los de octubre de 2026.)
        const conocidos = filtros.temasConocidos
            || meta.temas.filter(t => !["Finanzas", "Negocios", "Activos Digitales"].includes(t));
        meta.temas.filter(t => !conocidos.includes(t) && !filtros.temas.includes(t)).forEach(t => filtros.temas.push(t));
        filtros.temasConocidos = [...meta.temas];
        guardarFiltros();
        pintarMenus();
        document.getElementById("select-orden").value = filtros.orden;
        actualizarContador();
        await cargarNoticias();
        vigilar();
    } catch (err) {
        document.getElementById("news-container").innerHTML =
            `<p class="error-msg">No se pudo conectar con el servidor: ${escapeHtml(err.message)}</p>`;
    }
})();
