const MESES = ["Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"];
const MAX_GUION = 12;
const CLAVE_FILTROS = "gm_filtros";
const FILTROS_INICIALES = {
    paises: ["SV"],
    temas: ["Economía", "Inversión", "Política", "Coyuntura", "Social"],
    personajes: [],
    orden: "importancia",
};

let meta = null;
let noticias = [];                 // lo que devolvió /api/news con los filtros actuales
const seleccion = new Map();       // "pais|titulo" → noticia completa (sobrevive filtros y recargas)
const valoraciones = new Map();    // "pais|titulo" → texto
let filtros = cargarFiltros();
let periodo = null;                // {mes, anio}; null = mes actual
let ultimaPeticion = 0;            // solo se pinta la respuesta de la consulta más reciente

const clave = n => `${n.pais}|${n.titulo}`;

function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, c =>
        ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

/* ---------- Filtros (recordados en el navegador) ---------- */

function cargarFiltros() {
    try {
        const guardado = JSON.parse(localStorage.getItem(CLAVE_FILTROS));
        if (guardado && Array.isArray(guardado.paises)) return { ...FILTROS_INICIALES, ...guardado };
    } catch (e) { /* almacenamiento no disponible: se usan los iniciales */ }
    return structuredClone(FILTROS_INICIALES);
}

function guardarFiltros() {
    try { localStorage.setItem(CLAVE_FILTROS, JSON.stringify(filtros)); } catch (e) { /* sin almacenamiento */ }
}

function construirFila(idFila, grupo, opciones) {
    const fila = document.getElementById(idFila);
    fila.querySelectorAll(".chip").forEach(b => b.remove());
    const todos = document.createElement("button");
    todos.className = "chip todos";
    todos.dataset.grupo = grupo;
    todos.dataset.todos = "1";
    todos.onclick = () => alternarTodos(grupo, opciones.map(o => o.valor));
    fila.appendChild(todos);
    for (const o of opciones) {
        const b = document.createElement("button");
        b.className = "chip";
        b.dataset.grupo = grupo;
        b.dataset.valor = o.valor;
        b.textContent = o.texto;
        b.onclick = () => alternar(grupo, o.valor);
        fila.appendChild(b);
    }
}

function pintarChips() {
    document.querySelectorAll(".chip").forEach(b => {
        const marcados = filtros[b.dataset.grupo];
        if (b.dataset.todos) {
            const total = document.querySelectorAll(`.chip[data-grupo="${b.dataset.grupo}"]:not(.todos)`).length;
            const on = marcados.length === total;
            b.classList.toggle("on", on);
            b.textContent = `${on ? "☑" : "☐"} Todos`;
        } else {
            const on = marcados.includes(b.dataset.valor);
            b.classList.toggle("on", on);
            b.textContent = `${on ? "☑" : "☐"} ${b.textContent.replace(/^[☑☐] /, "")}`;
        }
    });
}

function alternar(grupo, valor) {
    const lista = filtros[grupo];
    const i = lista.indexOf(valor);
    if (i >= 0) lista.splice(i, 1); else lista.push(valor);
    filtrosCambiaron();
}

function alternarTodos(grupo, valores) {
    filtros[grupo] = filtros[grupo].length === valores.length ? [] : [...valores];
    filtrosCambiaron();
}

function filtrosCambiaron() {
    guardarFiltros();
    pintarChips();
    cargarNoticias();
}

function cambiarOrden() {
    filtros.orden = document.getElementById("select-orden").value;
    filtrosCambiaron();
}

function cambiarPeriodo() {
    const [anio, mes] = document.getElementById("select-periodo").value.split("-").map(Number);
    const hoy = new Date();
    periodo = (anio === hoy.getFullYear() && mes === hoy.getMonth() + 1) ? null : { anio, mes };
    cargarNoticias();
}

/* ---------- Carga de datos ---------- */

async function cargarMeta() {
    const resp = await fetch("/api/meta");
    meta = await resp.json();
    construirFila("fila-paises", "paises", meta.paises.map(p => ({ valor: p.codigo, texto: p.nombre })));
    construirFila("fila-temas", "temas", meta.temas.map(t => ({ valor: t, texto: t })));
    construirFila("fila-personajes", "personajes", meta.personajes.map(p => ({ valor: p, texto: p })));
    // Descarta del estado guardado opciones que ya no existen en la configuración.
    filtros.paises = filtros.paises.filter(p => meta.paises.some(x => x.codigo === p));
    filtros.temas = filtros.temas.filter(t => meta.temas.includes(t));
    filtros.personajes = filtros.personajes.filter(p => meta.personajes.includes(p));
    pintarChips();
    document.getElementById("select-orden").value = filtros.orden;
    construirPeriodos();
    pintarUltima();
}

function construirPeriodos() {
    const hoy = new Date();
    const actual = [hoy.getFullYear(), hoy.getMonth() + 1];
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
    if (meta.en_curso) { el.textContent = "Actualizando…"; return; }
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
        personajes: filtros.personajes.join(","), orden: filtros.orden,
    });
    if (periodo) { params.set("mes", periodo.mes); params.set("anio", periodo.anio); }
    cont.innerHTML = periodo ? '<p class="status-msg">Cargando y verificando enlaces…</p>' : cont.innerHTML;
    try {
        const resp = await fetch(`/api/news?${params}`);
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
            return `<a href="${escapeHtml(f.url)}" target="_blank" rel="noopener">${escapeHtml(f.nombre)}</a>${estado}`;
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
  ${n.personajes.length ? `<div class="personajes">👤 ${n.personajes.map(escapeHtml).join(", ")}</div>` : ""}
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
}

function seleccionadasConValoracion() {
    return [...seleccion.entries()].map(([k, n]) => ({ ...n, valoracion: valoraciones.get(k) || "" }));
}

/* ---------- Acciones ---------- */

async function actualizar() {
    const btn = document.getElementById("btn-refresh");
    btn.disabled = true;
    document.getElementById("ultima").textContent = "Actualizando…";
    await fetch("/api/actualizar", { method: "POST" });
    const espera = setInterval(async () => {
        await cargarMeta();
        if (!meta.en_curso) {
            clearInterval(espera);
            cargarNoticias();
        }
    }, 10000);
}

async function valorarSeleccionadas() {
    const btn = document.getElementById("btn-valorar");
    btn.disabled = true;
    btn.textContent = "Valorando…";
    try {
        const items = [...seleccion.values()];
        const resp = await fetch("/api/valorar", {
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
    const resp = await fetch(url, {
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
    descargar("/api/export", { items: seleccionadasConValoracion(), format: formato }, `noticias_centroamerica.${ext}`);
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
        const resp = await fetch("/api/guion", {
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
    const guiones = await (await fetch("/api/guiones")).json();
    lista.innerHTML = guiones.length ? guiones.map(g => `
        <li onclick="abrirGuion(${g.id})">
            ${escapeHtml(g.titulos.slice(0, 3).join(" · "))}${g.titulos.length > 3 ? " …" : ""}
            <small>${new Date(g.creado).toLocaleString("es-SV")} · ${g.titulos.length} noticias · ≈ ${g.minutos} min</small>
        </li>`).join("") : "<li>Todavía no hay guiones.</li>";
}

async function abrirGuion(id) {
    const g = await (await fetch(`/api/guiones/${id}`)).json();
    cerrarModal("modal-historial");
    mostrarGuion(g.texto, `Guion del ${new Date(g.creado).toLocaleString("es-SV")}.`);
}

document.addEventListener("keydown", e => {
    if (e.key === "Escape") { cerrarModal("modal-guion"); cerrarModal("modal-historial"); }
});

/* ---------- Inicio ---------- */

(async function iniciar() {
    try {
        await cargarMeta();
        actualizarContador();
        await cargarNoticias();
        setInterval(async () => { await cargarMeta(); }, 60000);
    } catch (err) {
        document.getElementById("news-container").innerHTML =
            `<p class="error-msg">No se pudo conectar con el servidor: ${escapeHtml(err.message)}</p>`;
    }
})();
