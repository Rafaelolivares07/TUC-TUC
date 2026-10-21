import os

config_html_path = r"C:\Users\RAFAEL OLIVARES\Documents\tuctucv2\templates\negocio_config.html"
with open(config_html_path, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Insert UI in Parámetros de Facturación
target_html = """    <!-- Toggle Permitir Forzar Inventario Negativo -->
    <div class="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
      <label class="flex items-center justify-between gap-3 cursor-pointer">
        <div>
          <span class="text-xs font-bold text-gray-800 uppercase tracking-wide block">Permitir forzar inventario negativo</span>
          <p class="text-xs text-gray-500 leading-snug">Si está desactivado, oculta el botón de forzar negativos en la caja. El cajero deberá realizar el ajuste físico, omitir el componente o cancelar la venta.</p>
        </div>
        <div class="relative inline-flex items-center shrink-0">
          <input type="checkbox" id="permitir-inventario-negativo" class="sr-only peer" onchange="cambiarPermitirInventarioNegativo(this.checked)">
          <div class="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
        </div>
      </label>
    </div>
  </div>"""

new_sections_html = """    <!-- Toggle Permitir Forzar Inventario Negativo -->
    <div class="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
      <label class="flex items-center justify-between gap-3 cursor-pointer">
        <div>
          <span class="text-xs font-bold text-gray-800 uppercase tracking-wide block">Permitir forzar inventario negativo</span>
          <p class="text-xs text-gray-500 leading-snug">Si está desactivado, oculta el botón de forzar negativos en la caja. El cajero deberá realizar el ajuste físico, omitir el componente o cancelar la venta.</p>
        </div>
        <div class="relative inline-flex items-center shrink-0">
          <input type="checkbox" id="permitir-inventario-negativo" class="sr-only peer" onchange="cambiarPermitirInventarioNegativo(this.checked)">
          <div class="w-11 h-6 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
        </div>
      </label>
    </div>

    <!-- Configuración de Impresión de Tipo de Entrega por Centro de Utilidad -->
    <div class="bg-slate-50 border border-slate-200 rounded-xl p-3.5 space-y-3">
      <div class="border-b border-slate-200/80 pb-2">
        <span class="text-xs font-bold text-gray-800 uppercase tracking-wide flex items-center gap-1.5">
          <span>📦</span> Impresión de Tipo de Entrega por Sede / Centro
        </span>
        <p class="text-xs text-gray-500 mt-0.5">Elige para cada centro de utilidad si se imprime o notifica el "Tipo de Entrega" en los comprobantes y alertas.</p>
      </div>

      <div id="lista-centros-entrega" class="space-y-2">
        <p class="text-xs text-gray-400 italic">Cargando sedes y centros de utilidad...</p>
      </div>
    </div>

    <!-- Modalidades y Textos de Entrega -->
    <div class="bg-indigo-50/40 border border-indigo-200/80 rounded-xl p-3.5 space-y-3">
      <div class="border-b border-indigo-100 pb-2">
        <span class="text-xs font-extrabold text-indigo-900 uppercase tracking-wide flex items-center gap-1.5">
          <span>🏷️</span> Modalidades y Textos Personalizados de Entrega
        </span>
        <p class="text-xs text-slate-600 mt-0.5">Personaliza los textos que se imprimen y notifican según la modalidad en la que se registre la venta.</p>
      </div>

      <div class="space-y-3">
        <!-- 1. Venta en Caja / Mostrador -->
        <div class="bg-white border border-slate-200 rounded-xl p-3 space-y-2 shadow-2xs">
          <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
            <div class="flex items-center gap-2">
              <span class="text-base">🏪</span>
              <span class="text-xs font-bold text-gray-800">Venta en Caja / Mostrador (caja)</span>
              <span class="bg-emerald-100 text-emerald-800 text-[10px] font-extrabold px-2 py-0.5 rounded-md">Venta Directa</span>
            </div>
            <label class="inline-flex items-center gap-1.5 cursor-pointer">
              <input type="checkbox" id="texto-caja-incluir-cajero" class="w-3.5 h-3.5 accent-indigo-600 rounded">
              <span class="text-[11px] font-semibold text-gray-600">Incluir cajero (Atendió: Nombre)</span>
            </label>
          </div>
          <p class="text-[11px] text-gray-500 leading-snug">
            <b>¿Cuándo sale?:</b> Se genera automáticamente cuando la orden se procesa de forma presencial desde la pantalla de <b>Caja POS tradicional</b> o en <b>Venta Flash</b>.
          </p>
          <div>
            <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Texto a imprimir / notificar</label>
            <input type="text" id="texto-entrega-caja" placeholder="Entrega en el local / caja."
                   class="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-indigo-400 font-medium text-gray-800">
          </div>
        </div>

        <!-- 2. Entrega a Domicilio -->
        <div class="bg-white border border-slate-200 rounded-xl p-3 space-y-2 shadow-2xs">
          <div class="flex items-center gap-2">
            <span class="text-base">🛵</span>
            <span class="text-xs font-bold text-gray-800">Entrega a Domicilio (domicilio)</span>
            <span class="bg-sky-100 text-sky-800 text-[10px] font-extrabold px-2 py-0.5 rounded-md">Envío</span>
          </div>
          <p class="text-[11px] text-gray-500 leading-snug">
            <b>¿Cuándo sale?:</b> Se genera cuando el cliente pide con envío a su ubicación desde la carta digital / catálogo público o se registra un domicilio en caja.
          </p>
          <div>
            <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Prefijo de texto (se añade la dirección del cliente al final)</label>
            <input type="text" id="texto-entrega-domicilio" placeholder="Domicilio. Llevar a:"
                   class="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-indigo-400 font-medium text-gray-800">
          </div>
        </div>

        <!-- 3. Para Recoger en Local -->
        <div class="bg-white border border-slate-200 rounded-xl p-3 space-y-2 shadow-2xs">
          <div class="flex items-center gap-2">
            <span class="text-base">🛍️</span>
            <span class="text-xs font-bold text-gray-800">Para Recoger en Tienda (recoger)</span>
            <span class="bg-amber-100 text-amber-800 text-[10px] font-extrabold px-2 py-0.5 rounded-md">Takeaway</span>
          </div>
          <p class="text-[11px] text-gray-500 leading-snug">
            <b>¿Cuándo sale?:</b> Se genera cuando el cliente realiza el pedido por la web seleccionando la modalidad de recoger personalmente en el local.
          </p>
          <div>
            <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Texto a imprimir / notificar</label>
            <input type="text" id="texto-entrega-recoger" placeholder="Cliente recoge en el local."
                   class="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-indigo-400 font-medium text-gray-800">
          </div>
        </div>

        <!-- 4. Consumo en Mesa / Salón -->
        <div class="bg-white border border-slate-200 rounded-xl p-3 space-y-2 shadow-2xs">
          <div class="flex items-center gap-2">
            <span class="text-base">🍽️</span>
            <span class="text-xs font-bold text-gray-800">Servicio en Mesa / Salón (mesa)</span>
            <span class="bg-purple-100 text-purple-800 text-[10px] font-extrabold px-2 py-0.5 rounded-md">Restaurante</span>
          </div>
          <p class="text-[11px] text-gray-500 leading-snug">
            <b>¿Cuándo sale?:</b> Se genera en órdenes con asignación de mesa o consumo interno en salón.
          </p>
          <div>
            <label class="block text-[10px] font-bold text-gray-500 uppercase mb-1">Prefijo de texto (se añade el nombre/número de mesa al final)</label>
            <input type="text" id="texto-entrega-mesa" placeholder="Consumo en mesa:"
                   class="w-full text-xs border border-gray-200 rounded-lg px-2.5 py-1.5 outline-none focus:border-indigo-400 font-medium text-gray-800">
          </div>
        </div>
      </div>
    </div>
  </div>"""

if target_html in html:
    html = html.replace(target_html, new_sections_html)

# 2. Update cargar() in JS
target_js_cargar = """    const negInp = document.getElementById('permitir-inventario-negativo');
    if (negInp) negInp.checked = d.config.permitir_inventario_negativo !== false;

    actualizarConfigDomicilioVisible();"""

new_js_cargar = """    const negInp = document.getElementById('permitir-inventario-negativo');
    if (negInp) negInp.checked = d.config.permitir_inventario_negativo !== false;

    // Renderizar centros de utilidad para toggle de imprimir entrega
    const centrosEntrega = d.config.centros_utilidad || [];
    const cList = document.getElementById('lista-centros-entrega');
    if (cList) {
      if (!centrosEntrega.length) {
        cList.innerHTML = '<p class="text-xs text-gray-400 italic">No hay sedes ni centros de utilidad activos registrados para este negocio.</p>';
      } else {
        cList.innerHTML = centrosEntrega.map(c => {
          const esMovil = (c.tipo === 'movil');
          const icon = esMovil ? '🛵' : '🏪';
          const color = c.color_badge || (esMovil ? '#0284c7' : '#10b981');
          const checked = c.imprimir_tipo_entrega !== false ? 'checked' : '';
          return `
            <div class="flex items-center justify-between p-2.5 rounded-xl border border-slate-200 bg-white">
              <div class="flex items-center gap-2 min-w-0">
                <span class="text-lg">${icon}</span>
                <div class="min-w-0">
                  <div class="flex items-center gap-1.5">
                    <span class="text-[9px] font-mono font-bold px-1.5 py-0.5 rounded text-white shrink-0" style="background:${color};">${c.codigo}</span>
                    <span class="text-xs font-bold text-gray-800 truncate">${c.nombre}</span>
                  </div>
                  <span class="text-[10px] text-gray-400">${esMovil ? 'Punto Móvil' : 'Sede Fija'}</span>
                </div>
              </div>
              <label class="flex items-center gap-2 cursor-pointer shrink-0">
                <span class="text-[11px] font-bold text-slate-700 hidden sm:inline">Imprimir Tipo de Entrega</span>
                <div class="relative inline-flex items-center">
                  <input type="checkbox" id="toggle-centro-${c.id}" class="sr-only peer toggle-centro-entrega" data-centro-id="${c.id}" ${checked}>
                  <div class="w-10 h-5 bg-gray-300 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-emerald-600"></div>
                </div>
              </label>
            </div>
          `;
        }).join('');
      }
    }

    // Cargar textos personalizados de entrega
    const txts = d.config.textos_entrega || {};
    const cajaCfg = txts.caja || {};
    const domCfg = txts.domicilio || {};
    const recCfg = txts.recoger || {};
    const mesaCfg = txts.mesa || {};

    const inCaja = document.getElementById('texto-entrega-caja');
    if (inCaja) inCaja.value = cajaCfg.texto || 'Entrega en el local / caja.';

    const inCajaCajero = document.getElementById('texto-caja-incluir-cajero');
    if (inCajaCajero) inCajaCajero.checked = cajaCfg.incluir_cajero !== false;

    const inDom = document.getElementById('texto-entrega-domicilio');
    if (inDom) inDom.value = domCfg.texto || 'Domicilio. Llevar a:';

    const inRec = document.getElementById('texto-entrega-recoger');
    if (inRec) inRec.value = recCfg.texto || 'Cliente recoge en el local.';

    const inMesa = document.getElementById('texto-entrega-mesa');
    if (inMesa) inMesa.value = mesaCfg.texto || 'Consumo en mesa:';

    actualizarConfigDomicilioVisible();"""

if target_js_cargar in html:
    html = html.replace(target_js_cargar, new_js_cargar)

# 3. Update guardar() in JS
target_js_save = """      facturacion_copias: Number(document.getElementById('facturacion-copias')?.value || 1),
      mostrar_productos_precio_cero: document.getElementById('mostrar-precio-cero')?.checked ?? true,
      permitir_inventario_negativo: document.getElementById('permitir-inventario-negativo')?.checked ?? true,
      telegram_chat_id: document.getElementById('telegram-chat-id')?.value?.trim() || ''
    };"""

new_js_save = """      facturacion_copias: Number(document.getElementById('facturacion-copias')?.value || 1),
      mostrar_productos_precio_cero: document.getElementById('mostrar-precio-cero')?.checked ?? true,
      permitir_inventario_negativo: document.getElementById('permitir-inventario-negativo')?.checked ?? true,
      telegram_chat_id: document.getElementById('telegram-chat-id')?.value?.trim() || '',
      centros_entrega: [...document.querySelectorAll('.toggle-centro-entrega')].map(inp => ({
        id: parseInt(inp.getAttribute('data-centro-id')),
        imprimir_tipo_entrega: inp.checked
      })),
      textos_entrega: {
        caja: {
          texto: (document.getElementById('texto-entrega-caja')?.value || '').trim() || 'Entrega en el local / caja.',
          incluir_cajero: document.getElementById('texto-caja-incluir-cajero')?.checked ?? true
        },
        domicilio: {
          texto: (document.getElementById('texto-entrega-domicilio')?.value || '').trim() || 'Domicilio. Llevar a:'
        },
        recoger: {
          texto: (document.getElementById('texto-entrega-recoger')?.value || '').trim() || 'Cliente recoge en el local.'
        },
        mesa: {
          texto: (document.getElementById('texto-entrega-mesa')?.value || '').trim() || 'Consumo en mesa:'
        }
      }
    };"""

if target_js_save in html:
    html = html.replace(target_js_save, new_js_save)

with open(config_html_path, "w", encoding="utf-8") as f:
    f.write(html)

print("negocio_config.html updated successfully.")
