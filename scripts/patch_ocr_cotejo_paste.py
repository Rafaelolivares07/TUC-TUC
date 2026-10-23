# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. Update app/services/vision_facturas.py to classify matched vs unmatched lines
with open('app/services/vision_facturas.py', 'r', encoding='utf-8') as f:
    code = f.read()

old_items_loop = """            items_extraidos.append({
                'texto_detectado': nom_it,
                'cantidad': cant,
                'total_linea': precio_linea,
                'valor_unitario': vu_calc,
                'producto_id': mejor_prod['id'] if mejor_prod else None,
                'producto_nombre': mejor_prod['nombre'] if mejor_prod else nom_it,
                'iva_pct': float(mejor_prod.get('iva_pct') or 0) if mejor_prod else 0.0,
                'match_confianza': round(mejor_score * 100, 1) if mejor_prod else 0.0
            })

    return {
        'ok': True,
        'datos': {
            'fecha': fecha_detectada,
            'documento_numero': num_doc_detectado,
            'total': total_factura,
            'proveedor_id': proveedor_id,
            'proveedor_nombre': proveedor_nombre,
            'lineas': items_extraidos,
            'total_lineas_detectadas': len(items_extraidos),
            'lineas_crudas': lineas_texto_completas
        }
    }"""

new_items_loop = """            item_data = {
                'texto_detectado': nom_it,
                'cantidad': cant,
                'total_linea': precio_linea,
                'valor_unitario': vu_calc,
                'producto_id': mejor_prod['id'] if mejor_prod else None,
                'producto_nombre': mejor_prod['nombre'] if mejor_prod else nom_it,
                'iva_pct': float(mejor_prod.get('iva_pct') or 0) if mejor_prod else 0.0,
                'match_confianza': round(mejor_score * 100, 1) if mejor_prod else 0.0,
                'identificado': bool(mejor_prod is not None)
            }
            items_extraidos.append(item_data)

    lineas_identificadas = [it for it in items_extraidos if it['identificado']]
    lineas_no_identificadas = [it for it in items_extraidos if not it['identificado']]

    return {
        'ok': True,
        'datos': {
            'fecha': fecha_detectada,
            'documento_numero': num_doc_detectado,
            'total': total_factura,
            'proveedor_id': proveedor_id,
            'proveedor_nombre': proveedor_nombre,
            'lineas': lineas_identificadas,
            'lineas_no_identificadas': lineas_no_identificadas,
            'total_lineas_detectadas': len(items_extraidos),
            'lineas_crudas': lineas_texto_completas
        }
    }"""

if old_items_loop in code:
    code = code.replace(old_items_loop, new_items_loop, 1)
    with open('app/services/vision_facturas.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("1. vision_facturas.py updated to separate identified and unidentified lines")
else:
    print("WARNING 1: old_items_loop not found")


# 2. Update templates/inventario_admin.html with:
# - Paste support (Ctrl+V)
# - Visual cotejo badge
# - Notification of unlinked/discarded items
with open('templates/inventario_admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Update banner to add paste hint and warning container for omitted items
old_banner_html = """    <!-- Banner de Escaneo con IA en curso -->
    <div id="banner-escaner-ia-cargando" class="hidden mb-3 p-3.5 bg-gradient-to-r from-teal-50 to-emerald-50 border border-teal-200 rounded-2xl flex items-center justify-between gap-3 text-xs shadow-xs animate-pulse">
      <div class="flex items-center gap-2.5">
        <span class="text-2xl animate-spin">⚙️</span>
        <div>
          <div class="font-extrabold text-teal-950 text-sm">
            Analizando factura con Visión e IA Local...
          </div>
          <div class="text-teal-700 font-medium">
            Extrayendo proveedor, fecha, número de documento y productos del comprobante.
          </div>
        </div>
      </div>
      <span class="text-xs font-mono font-bold text-teal-800 bg-teal-100/80 px-2.5 py-1 rounded-xl">CPU Local</span>
    </div>"""

new_banner_html = """    <!-- Banner de Escaneo con IA en curso -->
    <div id="banner-escaner-ia-cargando" class="hidden mb-3 p-3.5 bg-gradient-to-r from-teal-50 to-emerald-50 border border-teal-200 rounded-2xl flex items-center justify-between gap-3 text-xs shadow-xs animate-pulse">
      <div class="flex items-center gap-2.5">
        <span class="text-2xl animate-spin">⚙️</span>
        <div>
          <div class="font-extrabold text-teal-950 text-sm">
            Analizando factura con Visión e IA Local...
          </div>
          <div class="text-teal-700 font-medium">
            Extrayendo proveedor, fecha, número de documento y cotejando productos.
          </div>
        </div>
      </div>
      <span class="text-xs font-mono font-bold text-teal-800 bg-teal-100/80 px-2.5 py-1 rounded-xl">CPU Local</span>
    </div>

    <!-- Banner de Ítems No Identificados Omitidos -->
    <div id="banner-items-omitidos-ocr" class="hidden mb-3 p-3 bg-amber-50 border border-amber-300 rounded-2xl text-xs text-amber-900 shadow-xs">
      <div class="flex items-start justify-between gap-2">
        <div class="flex items-start gap-2">
          <span class="text-base">⚠️</span>
          <div>
            <span class="font-black text-amber-950 block">Ítems de la factura no encontrados en el catálogo (omitidos):</span>
            <div id="lista-items-omitidos-ocr" class="mt-1 space-y-0.5 text-[11px] text-amber-800 font-medium"></div>
          </div>
        </div>
        <button type="button" onclick="this.closest('#banner-items-omitidos-ocr').classList.add('hidden')" class="text-amber-600 hover:text-amber-800 font-bold p-1">&times;</button>
      </div>
    </div>"""

if old_banner_html in html:
    html = html.replace(old_banner_html, new_banner_html, 1)
    print("2. Warning banner for omitted items added")
else:
    print("WARNING 2: old_banner_html not found")

# Add cotejo badge next to Factura Exacta
old_cuadre_box = """          <button type="button" onclick="cuadrarConTotalFactura()" class="px-2 py-0.5 bg-gray-100 hover:bg-gray-200 active:scale-95 text-gray-700 font-bold rounded text-[11px] border border-gray-300 cursor-pointer" title="Cuadrar centavos con el total digitado">

            Cuadrar

          </button>

        </div>"""

new_cuadre_box = """          <button type="button" onclick="cuadrarConTotalFactura()" class="px-2 py-0.5 bg-gray-100 hover:bg-gray-200 active:scale-95 text-gray-700 font-bold rounded text-[11px] border border-gray-300 cursor-pointer" title="Cuadrar centavos con el total digitado">

            Cuadrar

          </button>

        </div>

        <!-- Badge de Cotejo Automático con la Factura -->
        <span id="entrada-cotejo-badge" class="hidden text-xs font-bold px-2.5 py-1 rounded-xl shadow-2xs transition"></span>"""

if old_cuadre_box in html:
    html = html.replace(old_cuadre_box, new_cuadre_box, 1)
    print("3. Cotejo badge added next to Factura Exacta")
else:
    print("WARNING 3: old_cuadre_box not found")

# Update JS function to support paste and cotejo
old_js_func = """async function escanearFacturaConIA(input) {
  if (!input.files || !input.files[0]) return;
  const archivo = input.files[0];
  
  const banner = document.getElementById('banner-escaner-ia-cargando');
  const btnScan = document.getElementById('btn-escanear-factura-ia');
  
  if (banner) banner.classList.remove('hidden');
  if (btnScan) {
    btnScan.disabled = true;
    btnScan.classList.add('opacity-60');
  }

  const formData = new FormData();
  formData.append('imagen', archivo);

  try {
    const resp = await fetch(`/api/inventario/${NEGOCIO_ID}/escanear-factura`, {
      method: 'POST',
      body: formData
    });
    const res = await resp.json();

    if (!res.ok) {
      toast(res.error || 'No se pudo leer la factura', false);
      return;
    }

    const d = res.datos || {};
    
    // 1. Número de documento
    if (d.documento_numero) {
      const inpDoc = document.getElementById('entrada-num-doc');
      if (inpDoc) inpDoc.value = d.documento_numero;
    }

    // 2. Fecha documento
    if (d.fecha) {
      const inpFecha = document.getElementById('entrada-fecha-doc');
      if (inpFecha) inpFecha.value = d.fecha;
    }

    // 3. Proveedor
    if (d.proveedor_id) {
      const inpProvId = document.getElementById('entrada-proveedor-id');
      const inpProvNom = document.getElementById('entrada-proveedor');
      if (inpProvId) inpProvId.value = d.proveedor_id;
      if (inpProvNom) inpProvNom.value = d.proveedor_nombre || '';
    } else if (d.proveedor_nombre) {
      const inpProvNom = document.getElementById('entrada-proveedor');
      if (inpProvNom) inpProvNom.value = d.proveedor_nombre;
      const btnCrearProv = document.getElementById('btn-crear-proveedor');
      if (btnCrearProv) btnCrearProv.classList.remove('hidden');
    }

    // 4. Total Factura Esperado (para cuadre exacto de centavos)
    if (d.total && d.total > 0) {
      const inpTotExp = document.getElementById('entrada-total-factura-esperado');
      if (inpTotExp) inpTotExp.value = Math.round(d.total);
    }

    // 5. Líneas de productos
    const lineas = d.lineas || [];
    if (lineas.length > 0) {
      const cont = document.getElementById('entrada-lineas');
      if (cont && entradaLineas.length <= 1) {
        cont.innerHTML = '';
        entradaLineas = [];
      }

      lineas.forEach(l => {
        const prodId = l.producto_id || '';
        const prodNom = l.producto_nombre || l.texto_detectado || '';
        const cant = l.cantidad || 1;
        const vu = l.valor_unitario || 0;
        const ivaPct = l.iva_pct || 0;
        const tot = l.total_linea || (cant * vu);

        agregarLineaEntradaConDatos(
          prodId,
          prodNom,
          cant,
          vu,
          ivaPct,
          defaultPresentacionId || null,
          'Unidad',
          1.0,
          cant,
          vu,
          tot
        );
      });

      calcularTotalesEntrada();
      toast(`✅ ¡Factura escaneada! Se cargaron ${lineas.length} productos detectados.`);
    } else {
      toast('ℹ️ Factura leída, pero no se reconocieron líneas de productos específicas. Revisa los datos.');
    }

  } catch (err) {
    console.error('Error escaneando factura:', err);
    toast('Error de conexión al procesar la imagen de la factura', false);
  } finally {
    if (banner) banner.classList.add('hidden');
    if (btnScan) {
      btnScan.disabled = false;
      btnScan.classList.remove('opacity-60');
    }
    input.value = '';
  }
}"""

new_js_func = """function escanearFacturaConIA(input) {
  if (!input.files || !input.files[0]) return;
  const archivo = input.files[0];
  escanearFacturaArchivo(archivo);
  input.value = '';
}

async function escanearFacturaArchivo(archivo) {
  const banner = document.getElementById('banner-escaner-ia-cargando');
  const btnScan = document.getElementById('btn-escanear-factura-ia');
  const bannerOmitidos = document.getElementById('banner-items-omitidos-ocr');
  const listaOmitidos = document.getElementById('lista-items-omitidos-ocr');
  
  if (banner) banner.classList.remove('hidden');
  if (bannerOmitidos) bannerOmitidos.classList.add('hidden');
  if (btnScan) {
    btnScan.disabled = true;
    btnScan.classList.add('opacity-60');
  }

  const formData = new FormData();
  formData.append('imagen', archivo);

  try {
    const resp = await fetch(`/api/inventario/${NEGOCIO_ID}/escanear-factura`, {
      method: 'POST',
      body: formData
    });
    const res = await resp.json();

    if (!res.ok) {
      toast(res.error || 'No se pudo leer la factura', false);
      return;
    }

    const d = res.datos || {};
    
    // 1. Número de documento
    if (d.documento_numero) {
      const inpDoc = document.getElementById('entrada-num-doc');
      if (inpDoc) inpDoc.value = d.documento_numero;
    }

    // 2. Fecha documento
    if (d.fecha) {
      const inpFecha = document.getElementById('entrada-fecha-doc');
      if (inpFecha) inpFecha.value = d.fecha;
    }

    // 3. Proveedor
    if (d.proveedor_id) {
      const inpProvId = document.getElementById('entrada-proveedor-id');
      const inpProvNom = document.getElementById('entrada-proveedor');
      if (inpProvId) inpProvId.value = d.proveedor_id;
      if (inpProvNom) inpProvNom.value = d.proveedor_nombre || '';
    } else if (d.proveedor_nombre) {
      const inpProvNom = document.getElementById('entrada-proveedor');
      if (inpProvNom) inpProvNom.value = d.proveedor_nombre;
      const btnCrearProv = document.getElementById('btn-crear-proveedor');
      if (btnCrearProv) btnCrearProv.classList.remove('hidden');
    }

    // 4. Total Factura Esperado (para cotejo y cuadre)
    if (d.total && d.total > 0) {
      const inpTotExp = document.getElementById('entrada-total-factura-esperado');
      if (inpTotExp) inpTotExp.value = Math.round(d.total);
    }

    // 5. Líneas de productos identificados
    const lineas = d.lineas || [];
    if (lineas.length > 0) {
      const cont = document.getElementById('entrada-lineas');
      if (cont && entradaLineas.length <= 1) {
        cont.innerHTML = '';
        entradaLineas = [];
      }

      lineas.forEach(l => {
        const prodId = l.producto_id;
        const prodNom = l.producto_nombre;
        const cant = l.cantidad || 1;
        const vu = l.valor_unitario || 0;
        const ivaPct = l.iva_pct || 0;
        const tot = l.total_linea || (cant * vu);

        agregarLineaEntradaConDatos(
          prodId,
          prodNom,
          cant,
          vu,
          ivaPct,
          defaultPresentacionId || null,
          'Unidad',
          1.0,
          cant,
          vu,
          tot
        );
      });

      calcularTotalesEntrada();
      actualizarCotejoFactura();
      toast(`✅ ¡Factura escaneada! Se cargaron ${lineas.length} productos identificados.`);
    } else {
      toast('ℹ️ Factura leída, pero no se reconocieron productos vinculados al catálogo.', false);
    }

    // 6. Aviso de productos NO identificados (omitidos)
    const noIdent = d.lineas_no_identificadas || [];
    if (noIdent.length > 0 && bannerOmitidos && listaOmitidos) {
      listaOmitidos.innerHTML = noIdent.map(ni => `
        <div class="flex items-center justify-between border-b border-amber-200/60 py-0.5 last:border-0">
          <span>• <b>${ni.cantidad}x</b> ${ni.texto_detectado}</span>
          <span class="font-mono font-bold">$${(ni.total_linea || 0).toLocaleString('es-CO')}</span>
        </div>
      `).join('');
      bannerOmitidos.classList.remove('hidden');
    }

  } catch (err) {
    console.error('Error escaneando factura:', err);
    toast('Error de conexión al procesar la imagen de la factura', false);
  } finally {
    if (banner) banner.classList.add('hidden');
    if (btnScan) {
      btnScan.disabled = false;
      btnScan.classList.remove('opacity-60');
    }
  }
}

// Función de Cotejo Automático: Compara total esperado de la factura con el total calculado de los ítems
function actualizarCotejoFactura() {
  const inpExp = document.getElementById('entrada-total-factura-esperado');
  const badge = document.getElementById('entrada-cotejo-badge');
  if (!inpExp || !badge) return;
  
  const esperado = parseFloat(inpExp.value.replace(/[^0-9.-]/g, '')) || 0;
  if (esperado <= 0) {
    badge.classList.add('hidden');
    return;
  }

  // Calcular total actual de las líneas
  const cont = document.getElementById('entrada-lineas');
  const divs = cont ? [...cont.querySelectorAll('.grid')] : [];
  let subtotal = 0;
  let ivaTotal = 0;
  divs.forEach(div => {
    const totalInput = div.querySelector('input[id^="ent-total-"]');
    const ivaSelect = div.querySelector('select[id^="ent-iva-pct-"]');
    const cantBaseInput = div.querySelector('input[id^="ent-cant-base-"]');
    const vuInput = div.querySelector('input[id^="ent-vu-"]');
    if (ivaSelect) {
      const totalVal = totalInput ? (parseFloat(totalInput.value) || 0) : 0;
      const cantBase = cantBaseInput ? (parseFloat(cantBaseInput.value) || 0) : 0;
      const vu = vuInput ? (parseFloat(vuInput.value) || 0) : 0;
      const ivaPct = parseFloat(ivaSelect.value) || 0;
      const lineSubtotal = totalVal > 0 ? totalVal : (cantBase * vu);
      subtotal += lineSubtotal;
      ivaTotal += lineSubtotal * (ivaPct / 100);
    }
  });

  const actual = Math.round(subtotal + ivaTotal);
  const diff = Math.round(esperado - actual);

  badge.classList.remove('hidden');
  if (Math.abs(diff) === 0) {
    badge.className = "text-xs font-bold px-2.5 py-1 rounded-xl shadow-2xs transition bg-emerald-100 text-emerald-800 border border-emerald-300 flex items-center gap-1";
    badge.innerHTML = "<span>✅</span> <span>Coincide exacto con la factura</span>";
  } else if (diff > 0) {
    badge.className = "text-xs font-bold px-2.5 py-1 rounded-xl shadow-2xs transition bg-amber-100 text-amber-900 border border-amber-300 flex items-center gap-1";
    badge.innerHTML = `<span>⚠️</span> <span>Faltan $${diff.toLocaleString('es-CO')} para igualar factura</span>`;
  } else {
    badge.className = "text-xs font-bold px-2.5 py-1 rounded-xl shadow-2xs transition bg-rose-100 text-rose-900 border border-rose-300 flex items-center gap-1";
    badge.innerHTML = `<span>⚠️</span> <span>Supera factura por $${Math.abs(diff).toLocaleString('es-CO')}</span>`;
  }
}

// Soporte para Copiar y Pegar imagen con Ctrl + V
window.addEventListener('paste', function(e) {
  const tabEntradas = document.getElementById('tab-entradas');
  if (!tabEntradas || tabEntradas.classList.contains('hidden')) return;

  const items = (e.clipboardData || e.originalEvent?.clipboardData)?.items || [];
  for (const item of items) {
    if (item.type && item.type.indexOf('image') !== -1) {
      e.preventDefault();
      const blob = item.getAsFile();
      if (blob) {
        toast('📋 Imagen detectada del portapapeles. Iniciando escaneo con IA...');
        escanearFacturaArchivo(blob);
      }
      break;
    }
  }
});
"""

if old_js_func in html:
    html = html.replace(old_js_func, new_js_func, 1)
    print("4. JS updated with Ctrl+V support, unlinked alert, and total cotejo")
else:
    print("WARNING 4: old_js_func not found")

# Hook actualizarCotejoFactura inside calcularTotalesEntrada
old_calc_tot = """  calcularTotalesEntrada();"""
# Let's ensure actualizarCotejoFactura is called whenever calcularTotalesEntrada runs
if "function calcularTotalesEntrada()" in html and "actualizarCotejoFactura();" not in html:
    html = html.replace(
        "function calcularTotalesEntrada() {",
        "function calcularTotalesEntrada() {\n  setTimeout(actualizarCotejoFactura, 50);",
        1
    )
    print("5. Hooked actualizarCotejoFactura inside calcularTotalesEntrada")

with open('templates/inventario_admin.html', 'w', encoding='utf-8') as f:
    f.write(html)

print("Finished applying all enhancements!")
