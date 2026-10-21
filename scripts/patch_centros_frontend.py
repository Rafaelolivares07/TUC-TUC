import sys, os

def patch_restaurante_admin():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\restaurante_admin.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add input in restaurant card
    target_card = """                    <div id="historial-{{ r.slug }}" class="hidden mt-2"></div>
                </div>"""
    
    replacement_card = """                    <div id="historial-{{ r.slug }}" class="hidden mt-2"></div>
                </div>
                <!-- Centros de Utilidad / Sedes -->
                <div class="mt-2 pt-2 border-t border-amber-200 flex items-center justify-between flex-wrap gap-2">
                    <div class="flex items-center gap-2">
                        <span class="text-xs font-bold text-gray-700">🏢 Centros de Utilidad:</span>
                        <input type="number" id="max-centros-{{ r.slug }}" value="{{ r.max_centros_utilidad or 1 }}" min="1"
                               class="border border-gray-300 rounded px-2 py-1 text-xs w-16 text-center font-bold text-gray-800">
                        <button onclick="guardarMaxCentrosRest('{{ r.slug }}')"
                                class="bg-amber-600 hover:bg-amber-700 text-white text-xs px-3 py-1 rounded font-semibold transition">
                            Guardar Cupo
                        </button>
                    </div>
                    <span id="msg-max-centros-{{ r.slug }}" class="text-xs font-semibold"></span>
                </div>"""

    if target_card in content and 'guardarMaxCentrosRest' not in content:
        content = content.replace(target_card, replacement_card, 1)
        print("restaurante_admin.html: card updated with max-centros input")
    else:
        print("restaurante_admin.html: card already updated or target not found")

    # 2. Add JS function
    js_code = """
async function guardarMaxCentrosRest(slug) {
    const input = document.getElementById(`max-centros-${slug}`);
    const msg = document.getElementById(`msg-max-centros-${slug}`);
    const val = parseInt(input.value);
    if (!val || val < 1) return toast('Ingresa un número válido (mínimo 1)', false);
    if (msg) msg.textContent = 'Guardando...';
    try {
        const r = await fetch(`/api/admin/restaurante/${slug}/max-centros`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ max_centros_utilidad: val })
        });
        const data = await r.json();
        if (data.ok) {
            toast(`Cupo actualizado a ${data.max_centros_utilidad} centros`);
            if (msg) {
                msg.textContent = '✓ Guardado';
                msg.className = 'text-xs text-green-600 font-bold';
                setTimeout(() => { msg.textContent = ''; }, 3000);
            }
        } else {
            toast(data.error || 'Error al guardar', false);
            if (msg) msg.textContent = '';
        }
    } catch (e) {
        toast('Error de conexión', false);
        if (msg) msg.textContent = '';
    }
}
"""
    if 'function guardarMaxCentrosRest' not in content:
        target_js = "// ===== VISITANTES ====="
        if target_js in content:
            content = content.replace(target_js, js_code + "\n\n" + target_js, 1)
            print("restaurante_admin.html: JS function added")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_tienda_admin():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\tienda_admin.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Add input in store card
    target_card = """                <button onclick="event.stopPropagation(); agregarDias('{{ t.slug }}')"
                        class="bg-rose-500 hover:bg-rose-600 text-white text-xs px-3 py-1.5 rounded font-bold whitespace-nowrap">
                    + Agregar
                </button>
            </div>"""

    replacement_card = """                <button onclick="event.stopPropagation(); agregarDias('{{ t.slug }}')"
                        class="bg-rose-500 hover:bg-rose-600 text-white text-xs px-3 py-1.5 rounded font-bold whitespace-nowrap">
                    + Agregar
                </button>
            </div>
            <!-- Centros de Utilidad / Cupo -->
            <div class="flex items-center justify-between gap-2 mt-2 pt-2 border-t flex-wrap" onclick="event.stopPropagation()">
                <div class="flex items-center gap-2">
                    <span class="text-xs font-bold text-gray-700">🏢 Centros de Utilidad:</span>
                    <input type="number" id="max-centros-{{ t.slug }}" value="{{ t.max_centros_utilidad or 1 }}" min="1"
                           class="border border-gray-300 rounded px-2 py-1 text-xs w-16 text-center font-bold text-gray-800">
                    <button onclick="event.stopPropagation(); guardarMaxCentrosTienda('{{ t.slug }}')"
                            class="bg-rose-600 hover:bg-rose-700 text-white text-xs px-3 py-1.5 rounded font-bold whitespace-nowrap transition">
                        Guardar Cupo
                    </button>
                </div>
                <span id="msg-max-centros-{{ t.slug }}" class="text-xs font-semibold"></span>
            </div>"""

    if target_card in content and 'guardarMaxCentrosTienda' not in content:
        content = content.replace(target_card, replacement_card, 1)
        print("tienda_admin.html: card updated with max-centros input")
    else:
        print("tienda_admin.html: card already updated or target not found")

    # 2. Add JS function
    js_code = """
async function guardarMaxCentrosTienda(slug) {
    const input = document.getElementById(`max-centros-${slug}`);
    const msg = document.getElementById(`msg-max-centros-${slug}`);
    const val = parseInt(input.value);
    if (!val || val < 1) return alert('Ingresa un número válido (mínimo 1)');
    if (msg) msg.textContent = 'Guardando...';
    try {
        const r = await fetch(`/api/admin/tienda/${slug}/max-centros`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ max_centros_utilidad: val })
        });
        const data = await r.json();
        if (data.ok) {
            if (msg) {
                msg.textContent = '✓ Guardado (' + data.max_centros_utilidad + ')';
                msg.className = 'text-xs text-green-600 font-bold';
                setTimeout(() => { msg.textContent = ''; }, 3000);
            }
        } else {
            alert(data.error || 'Error al guardar');
            if (msg) msg.textContent = '';
        }
    } catch (e) {
        alert('Error de conexión');
        if (msg) msg.textContent = '';
    }
}
"""
    if 'function guardarMaxCentrosTienda' not in content:
        target_js = "async function agregarDias(slug)"
        if target_js in content:
            content = content.replace(target_js, js_code + "\n" + target_js, 1)
            print("tienda_admin.html: JS function added")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def patch_inventario_admin():
    path = r'C:\Users\RAFAEL OLIVARES\Documents\TucTucV2\templates\inventario_admin.html'
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 1. Update global variable MAX_CENTROS_UTILIDAD
    old_vars = "let CENTROS_UTILIDAD = {{ centros_utilidad | tojson if centros_utilidad else '[]' }};"
    new_vars = """let CENTROS_UTILIDAD = {{ centros_utilidad | tojson if centros_utilidad else '[]' }};
let MAX_CENTROS_UTILIDAD = {{ max_centros_utilidad if max_centros_utilidad is defined and max_centros_utilidad else 1 }};"""
    if old_vars in content and 'let MAX_CENTROS_UTILIDAD' not in content:
        content = content.replace(old_vars, new_vars, 1)
        print("inventario_admin.html: MAX_CENTROS_UTILIDAD variable added")

    # 2. Header of #overlay-centros-utilidad: add Quota badge and "+ Nueva Sede / Centro" button
    old_header = """    <div class="flex-shrink-0 flex items-center justify-between pb-3 border-b border-gray-100">
      <div>
        <div class="flex items-center gap-2">
          <span class="text-xl">🏢</span>
          <h3 class="text-base font-extrabold text-gray-800">Centros de Utilidad y Bodegas</h3>
        </div>
        <p class="text-xs text-gray-500 mt-0.5">Selecciona el punto de operación activo para inventario, kardex y ventas.</p>
      </div>
      <button onclick="cerrarModalCentrosUtilidad()" class="text-gray-400 hover:text-gray-600 p-1.5 rounded-xl hover:bg-gray-100 transition text-lg">&times;</button>
    </div>"""

    new_header = """    <div class="flex-shrink-0 flex items-center justify-between pb-3 border-b border-gray-100 flex-wrap gap-2">
      <div>
        <div class="flex items-center gap-2">
          <span class="text-xl">🏢</span>
          <h3 class="text-base font-extrabold text-gray-800">Centros de Utilidad y Bodegas</h3>
          <span id="cu-quota-badge" class="text-[11px] font-bold px-2.5 py-0.5 rounded-full bg-indigo-50 text-indigo-700 border border-indigo-200">
            Cupo: <span id="cu-quota-count">0</span> de <span id="cu-quota-max">1</span> sedes
          </span>
        </div>
        <p class="text-xs text-gray-500 mt-0.5">Selecciona el punto de operación activo para inventario, kardex y ventas.</p>
      </div>
      <div class="flex items-center gap-2">
        <button id="cu-btn-crear-centro" onclick="abrirModalCrearCentro()" class="text-xs font-bold bg-indigo-600 hover:bg-indigo-700 text-white px-3 py-1.5 rounded-xl shadow-sm transition flex items-center gap-1.5">
          <span>➕</span> Nueva Sede
        </button>
        <button onclick="cerrarModalCentrosUtilidad()" class="text-gray-400 hover:text-gray-600 p-1.5 rounded-xl hover:bg-gray-100 transition text-lg">&times;</button>
      </div>
    </div>"""

    if old_header in content:
        content = content.replace(old_header, new_header, 1)
        print("inventario_admin.html: modal header updated with quota and new sede button")

    # 3. Modal #overlay-editar-centro: add phone and address fields, and title id
    old_modal_edit = """<!-- ── MODAL EDITAR CENTRO DE UTILIDAD ───────────────────────────────── -->
<div id="overlay-editar-centro" class="overlay hidden" onclick="if(event.target===this)cerrarModalEditarCentro()">
  <div class="modal shadow-2xl border border-gray-100" style="max-width: 480px;">
    <div class="flex items-center justify-between pb-3 border-b border-gray-100 mb-4">
      <div class="flex items-center gap-2">
        <span class="text-xl">✏️</span>
        <h3 class="text-sm font-bold text-gray-800">Modificar Centro de Utilidad</h3>
      </div>
      <button onclick="cerrarModalEditarCentro()" class="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
    </div>
    <form onsubmit="guardarEdicionCentro(event)" class="space-y-3">
      <input type="hidden" id="edit-centro-id">
      <div>
        <label class="block text-xs font-bold text-gray-700 mb-1">Nombre del Centro de Utilidad</label>
        <input type="text" id="edit-centro-nombre" required class="text-xs font-semibold" placeholder="Ej: Local Comercial / Sede Principal">
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-bold text-gray-700 mb-1">Código</label>
          <input type="text" id="edit-centro-codigo" required class="text-xs font-semibold uppercase" placeholder="Ej: LOC-01">
        </div>
        <div>
          <label class="block text-xs font-bold text-gray-700 mb-1">Tipo de Operación</label>
          <select id="edit-centro-tipo" class="text-xs font-semibold">
            <option value="local">Sede Fija / Local Comercial</option>
            <option value="movil">Operación Móvil / Neveras</option>
          </select>
        </div>
      </div>
      <div>
        <label class="block text-xs font-bold text-gray-700 mb-1">Color Distintivo</label>
        <div class="flex items-center gap-2">
          <input type="color" id="edit-centro-color" class="h-9 w-14 rounded-lg cursor-pointer border border-gray-200 p-1">
          <span class="text-xs text-gray-500">Color de identificación en cabecera y reportes</span>
        </div>
      </div>
      <div class="pt-3 flex justify-end gap-2 border-t border-gray-100">
        <button type="button" onclick="cerrarModalEditarCentro()" class="px-3.5 py-2 border border-gray-200 rounded-xl hover:bg-gray-50 text-xs font-semibold text-gray-600">Cancelar</button>
        <button type="submit" id="btn-guardar-edit-centro" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-sm flex items-center gap-1.5">
          💾 Guardar Cambios
        </button>
      </div>
    </form>
  </div>
</div>"""

    new_modal_edit = """<!-- ── MODAL CREAR / EDITAR CENTRO DE UTILIDAD ───────────────────────── -->
<div id="overlay-editar-centro" class="overlay hidden" onclick="if(event.target===this)cerrarModalEditarCentro()">
  <div class="modal shadow-2xl border border-gray-100" style="max-width: 480px;">
    <div class="flex items-center justify-between pb-3 border-b border-gray-100 mb-4">
      <div class="flex items-center gap-2">
        <span class="text-xl" id="modal-centro-icono">✏️</span>
        <h3 class="text-sm font-bold text-gray-800" id="modal-centro-titulo">Modificar Centro de Utilidad</h3>
      </div>
      <button onclick="cerrarModalEditarCentro()" class="text-gray-400 hover:text-gray-600 text-lg">&times;</button>
    </div>
    <form onsubmit="guardarEdicionCentro(event)" class="space-y-3">
      <input type="hidden" id="edit-centro-id">
      <div>
        <label class="block text-xs font-bold text-gray-700 mb-1">Nombre del Centro de Utilidad</label>
        <input type="text" id="edit-centro-nombre" required class="text-xs font-semibold" placeholder="Ej: Local Comercial / Sede Principal">
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-bold text-gray-700 mb-1">Código</label>
          <input type="text" id="edit-centro-codigo" class="text-xs font-semibold uppercase" placeholder="Ej: LOC-01 (opcional)">
        </div>
        <div>
          <label class="block text-xs font-bold text-gray-700 mb-1">Tipo de Operación</label>
          <select id="edit-centro-tipo" class="text-xs font-semibold">
            <option value="local">Sede Fija / Local Comercial</option>
            <option value="movil">Operación Móvil / Neveras</option>
          </select>
        </div>
      </div>
      <div class="grid grid-cols-2 gap-3">
        <div>
          <label class="block text-xs font-bold text-gray-700 mb-1">📱 Celular / WhatsApp</label>
          <input type="text" id="edit-centro-telefono" class="text-xs font-semibold" placeholder="Ej: 3001234567">
        </div>
        <div>
          <label class="block text-xs font-bold text-gray-700 mb-1">📍 Dirección</label>
          <input type="text" id="edit-centro-direccion" class="text-xs font-semibold" placeholder="Ej: Calle 10 # 40-20">
        </div>
      </div>
      <div>
        <label class="block text-xs font-bold text-gray-700 mb-1">Color Distintivo</label>
        <div class="flex items-center gap-2">
          <input type="color" id="edit-centro-color" value="#0284c7" class="h-9 w-14 rounded-lg cursor-pointer border border-gray-200 p-1">
          <span class="text-xs text-gray-500">Color de identificación en cabecera y reportes</span>
        </div>
      </div>
      <div class="pt-3 flex justify-end gap-2 border-t border-gray-100">
        <button type="button" onclick="cerrarModalEditarCentro()" class="px-3.5 py-2 border border-gray-200 rounded-xl hover:bg-gray-50 text-xs font-semibold text-gray-600">Cancelar</button>
        <button type="submit" id="btn-guardar-edit-centro" class="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold shadow-sm flex items-center gap-1.5">
          <span id="btn-guardar-edit-centro-text">💾 Guardar Cambios</span>
        </button>
      </div>
    </form>
  </div>
</div>"""

    if old_modal_edit in content:
        content = content.replace(old_modal_edit, new_modal_edit, 1)
        print("inventario_admin.html: modal edit/create replaced")

    # 4. In JS: update abrirModalCentrosUtilidad to show quota, phone, address, and add abrirModalCrearCentro, and update guardarEdicionCentro
    old_card_body = """          <h4 class="text-sm font-extrabold text-gray-900 mb-1">${c.nombre}</h4>
          <p class="text-xs text-gray-500 mb-3">${c.direccion || (esMovil ? 'Ruta de neveras móviles en puntos de venta' : 'Sede y cocina principal')}</p>"""

    new_card_body = """          <h4 class="text-sm font-extrabold text-gray-900 mb-1">${c.nombre}</h4>
          <div class="space-y-0.5 mb-3 text-xs text-gray-500">
            <p class="flex items-center gap-1.5"><span>📍</span> <span>${c.direccion || (esMovil ? 'Ruta móvil' : 'Sin dirección configurada')}</span></p>
            ${c.telefono ? `<p class="flex items-center gap-1.5"><span>📱</span> <span class="font-semibold text-gray-700">${c.telefono}</span></p>` : ''}
          </div>"""

    if old_card_body in content:
        content = content.replace(old_card_body, new_card_body, 1)
        print("inventario_admin.html: card body updated with phone and address icons")

    # Update quota in abrirModalCentrosUtilidad
    old_modal_open_end = """  const modal = document.getElementById('overlay-centros-utilidad');
  if (modal) modal.classList.remove('hidden');"""

    new_modal_open_end = """  // Actualizar indicador de cupo
  const countEl = document.getElementById('cu-quota-count');
  const maxEl = document.getElementById('cu-quota-max');
  const btnCrear = document.getElementById('cu-btn-crear-centro');
  if (countEl) countEl.textContent = CENTROS_UTILIDAD.length;
  if (maxEl) maxEl.textContent = MAX_CENTROS_UTILIDAD || 1;
  if (btnCrear) {
    if (CENTROS_UTILIDAD.length >= (MAX_CENTROS_UTILIDAD || 1)) {
      btnCrear.classList.remove('bg-indigo-600', 'hover:bg-indigo-700');
      btnCrear.classList.add('bg-gray-400', 'cursor-not-allowed');
      btnCrear.title = `Has alcanzado el límite de sedes permitidas (${MAX_CENTROS_UTILIDAD}). Contacta al administrador para ampliar tu cupo.`;
    } else {
      btnCrear.classList.remove('bg-gray-400', 'cursor-not-allowed');
      btnCrear.classList.add('bg-indigo-600', 'hover:bg-indigo-700');
      btnCrear.title = `Crear nueva sede (${CENTROS_UTILIDAD.length}/${MAX_CENTROS_UTILIDAD})`;
    }
  }

  const modal = document.getElementById('overlay-centros-utilidad');
  if (modal) modal.classList.remove('hidden');"""

    if old_modal_open_end in content:
        content = content.replace(old_modal_open_end, new_modal_open_end, 1)
        print("inventario_admin.html: quota indicator update logic added to abrirModalCentrosUtilidad")

    # Update abrirModalEditarCentro to populate telefono & direccion
    old_abrir_edit = """function abrirModalEditarCentro(centroId) {
  const c = CENTROS_UTILIDAD.find(x => String(x.id) === String(centroId));
  if (!c) return;
  document.getElementById('edit-centro-id').value = c.id;
  document.getElementById('edit-centro-nombre').value = c.nombre || '';
  document.getElementById('edit-centro-codigo').value = c.codigo || '';
  document.getElementById('edit-centro-tipo').value = c.tipo || 'local';
  document.getElementById('edit-centro-color').value = c.color_badge || '#0284c7';

  const modal = document.getElementById('overlay-editar-centro');
  if (modal) modal.classList.remove('hidden');
}"""

    new_abrir_edit = """function abrirModalCrearCentro() {
  if (CENTROS_UTILIDAD.length >= (MAX_CENTROS_UTILIDAD || 1)) {
    toast(`Has alcanzado el límite de sedes permitidas (${MAX_CENTROS_UTILIDAD}). Solicita a administración ampliar tu cupo.`, false);
    return;
  }
  document.getElementById('modal-centro-icono').textContent = '➕';
  document.getElementById('modal-centro-titulo').textContent = 'Nueva Sede / Centro de Utilidad';
  document.getElementById('btn-guardar-edit-centro-text').textContent = '✨ Crear Centro';
  document.getElementById('edit-centro-id').value = '';
  document.getElementById('edit-centro-nombre').value = '';
  document.getElementById('edit-centro-codigo').value = '';
  document.getElementById('edit-centro-tipo').value = 'local';
  document.getElementById('edit-centro-telefono').value = '';
  document.getElementById('edit-centro-direccion').value = '';
  document.getElementById('edit-centro-color').value = '#0284c7';

  const modal = document.getElementById('overlay-editar-centro');
  if (modal) modal.classList.remove('hidden');
}

function abrirModalEditarCentro(centroId) {
  const c = CENTROS_UTILIDAD.find(x => String(x.id) === String(centroId));
  if (!c) return;
  document.getElementById('modal-centro-icono').textContent = '✏️';
  document.getElementById('modal-centro-titulo').textContent = 'Modificar Centro de Utilidad';
  document.getElementById('btn-guardar-edit-centro-text').textContent = '💾 Guardar Cambios';
  document.getElementById('edit-centro-id').value = c.id;
  document.getElementById('edit-centro-nombre').value = c.nombre || '';
  document.getElementById('edit-centro-codigo').value = c.codigo || '';
  document.getElementById('edit-centro-tipo').value = c.tipo || 'local';
  document.getElementById('edit-centro-telefono').value = c.telefono || '';
  document.getElementById('edit-centro-direccion').value = c.direccion || '';
  document.getElementById('edit-centro-color').value = c.color_badge || '#0284c7';

  const modal = document.getElementById('overlay-editar-centro');
  if (modal) modal.classList.remove('hidden');
}"""

    if old_abrir_edit in content:
        content = content.replace(old_abrir_edit, new_abrir_edit, 1)
        print("inventario_admin.html: abrirModalCrearCentro and abrirModalEditarCentro updated")

    # Update guardarEdicionCentro to handle both create and edit
    old_guardar_edit = """async function guardarEdicionCentro(e) {
  e.preventDefault();
  const centroId = document.getElementById('edit-centro-id').value;
  const nombre = document.getElementById('edit-centro-nombre').value.trim();
  const codigo = document.getElementById('edit-centro-codigo').value.trim().toUpperCase();
  const tipo = document.getElementById('edit-centro-tipo').value;
  const color = document.getElementById('edit-centro-color').value;

  if (!nombre || !codigo) {
    toast('Nombre y código son obligatorios', false);
    return;
  }

  const btn = document.getElementById('btn-guardar-edit-centro');
  if (btn) btn.disabled = true;

  try {
    const res = await fetch(`/api/centros_utilidad/${centroId}/editar`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        negocio_id: NEGOCIO_ID,
        nombre: nombre,
        codigo: codigo,
        tipo: tipo,
        color_badge: color
      })
    });
    const data = await res.json();
    if (data.ok) {
      toast(data.mensaje || 'Centro de utilidad actualizado', true);
      const idx = CENTROS_UTILIDAD.findIndex(x => String(x.id) === String(centroId));
      if (idx !== -1) {
        CENTROS_UTILIDAD[idx].nombre = nombre;
        CENTROS_UTILIDAD[idx].codigo = codigo;
        CENTROS_UTILIDAD[idx].tipo = tipo;
        CENTROS_UTILIDAD[idx].color_badge = color;
      }
      if (CENTRO_ACTIVO && String(CENTRO_ACTIVO.id) === String(centroId)) {
        CENTRO_ACTIVO.nombre = nombre;
        CENTRO_ACTIVO.codigo = codigo;
        CENTRO_ACTIVO.tipo = tipo;
        CENTRO_ACTIVO.color_badge = color;
        actualizarHeaderCentroActivo();
      }
      cerrarModalEditarCentro();
      abrirModalCentrosUtilidad();
    } else {
      toast(data.error || 'Error al guardar cambios', false);
    }
  } catch (err) {
    toast('Error de conexión al guardar centro', false);
  } finally {
    if (btn) btn.disabled = false;
  }
}"""

    new_guardar_edit = """async function guardarEdicionCentro(e) {
  e.preventDefault();
  const centroId = document.getElementById('edit-centro-id').value;
  const nombre = document.getElementById('edit-centro-nombre').value.trim();
  const codigo = document.getElementById('edit-centro-codigo').value.trim().toUpperCase();
  const tipo = document.getElementById('edit-centro-tipo').value;
  const telefono = document.getElementById('edit-centro-telefono').value.trim();
  const direccion = document.getElementById('edit-centro-direccion').value.trim();
  const color = document.getElementById('edit-centro-color').value;

  if (!nombre) {
    toast('El nombre del centro es obligatorio', false);
    return;
  }

  const btn = document.getElementById('btn-guardar-edit-centro');
  if (btn) btn.disabled = true;

  try {
    const esCrear = !centroId;
    const url = esCrear ? '/api/centros_utilidad/crear' : `/api/centros_utilidad/${centroId}/editar`;
    const payload = {
      negocio_id: NEGOCIO_ID,
      nombre: nombre,
      codigo: codigo,
      tipo: tipo,
      telefono: telefono,
      direccion: direccion,
      color_badge: color
    };

    const res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (data.ok) {
      toast(data.mensaje || (esCrear ? 'Centro creado exitosamente' : 'Centro actualizado'), true);
      if (esCrear && data.centro) {
        CENTROS_UTILIDAD.push(data.centro);
      } else {
        const idx = CENTROS_UTILIDAD.findIndex(x => String(x.id) === String(centroId));
        if (idx !== -1) {
          CENTROS_UTILIDAD[idx].nombre = nombre;
          CENTROS_UTILIDAD[idx].codigo = codigo || CENTROS_UTILIDAD[idx].codigo;
          CENTROS_UTILIDAD[idx].tipo = tipo;
          CENTROS_UTILIDAD[idx].telefono = telefono;
          CENTROS_UTILIDAD[idx].direccion = direccion;
          CENTROS_UTILIDAD[idx].color_badge = color;
        }
        if (CENTRO_ACTIVO && String(CENTRO_ACTIVO.id) === String(centroId)) {
          CENTRO_ACTIVO.nombre = nombre;
          CENTRO_ACTIVO.codigo = codigo || CENTRO_ACTIVO.codigo;
          CENTRO_ACTIVO.tipo = tipo;
          CENTRO_ACTIVO.telefono = telefono;
          CENTRO_ACTIVO.direccion = direccion;
          CENTRO_ACTIVO.color_badge = color;
          actualizarHeaderCentroActivo();
        }
      }
      cerrarModalEditarCentro();
      abrirModalCentrosUtilidad();
    } else {
      toast(data.error || 'Error al guardar centro', false);
    }
  } catch (err) {
    toast('Error de conexión al guardar centro', false);
  } finally {
    if (btn) btn.disabled = false;
  }
}"""

    if old_guardar_edit in content:
        content = content.replace(old_guardar_edit, new_guardar_edit, 1)
        print("inventario_admin.html: guardarEdicionCentro updated for both create and edit")

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


if __name__ == '__main__':
    patch_restaurante_admin()
    patch_tienda_admin()
    patch_inventario_admin()
    print("Frontend template patching finished.")
