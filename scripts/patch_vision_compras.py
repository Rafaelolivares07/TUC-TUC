# -*- coding: utf-8 -*-
import sys
sys.stdout.reconfigure(encoding='utf-8')

# 1. Patch app/blueprints/inventarios.py
with open('app/blueprints/inventarios.py', 'r', encoding='utf-8') as f:
    code = f.read()

endpoint_code = """@bp.route('/api/inventario/<int:negocio_id>/escanear-factura', methods=['POST'])
def api_inventario_escanear_factura(negocio_id):
    if 'usuario_id' not in session:
        return jsonify({'ok': False, 'error': 'No autenticado'}), 401
    
    if 'imagen' not in request.files:
        return jsonify({'ok': False, 'error': 'No se recibió ninguna imagen'}), 400
        
    archivo = request.files['imagen']
    if not archivo.filename:
        return jsonify({'ok': False, 'error': 'Archivo vacío'}), 400
        
    import tempfile
    import os
    from app.services.vision_facturas import extraer_datos_factura
    
    conn = get_db_connection()
    try:
        suffix = os.path.splitext(archivo.filename)[1] or '.png'
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            archivo.save(tmp.name)
            tmp_path = tmp.name
            
        try:
            res = extraer_datos_factura(tmp_path, conn=conn, negocio_id=negocio_id)
            return jsonify(res)
        finally:
            if os.path.exists(tmp_path):
                try: os.remove(tmp_path)
                except: pass
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'ok': False, 'error': f'Error procesando imagen: {str(e)}'}), 500
    finally:
        conn.close()

"""

anchor_inv = "@bp.route('/api/inventario/<int:negocio_id>/entrada', methods=['POST'])"
if anchor_inv in code and "def api_inventario_escanear_factura" not in code:
    code = code.replace(anchor_inv, endpoint_code + "\n" + anchor_inv, 1)
    with open('app/blueprints/inventarios.py', 'w', encoding='utf-8') as f:
        f.write(code)
    print("1. Endpoint escanear-factura added to inventarios.py")
else:
    print("WARNING 1: anchor not found or already added in inventarios.py")


# 2. Patch templates/inventario_admin.html
with open('templates/inventario_admin.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Replace header in #tab-entradas to add the scanner button
old_header_html = """    <div class="flex items-center justify-between gap-3 mb-2 flex-wrap">
      <div class="flex items-center gap-3">
        <h2 class="font-bold text-gray-700">Registrar entrada de mercancía</h2>
        <span id="indicador-auto-guardado-borrador" class="hidden text-[11px] font-bold text-emerald-600 font-mono transition-all"></span>
      </div>
      <button type="button" onclick="abrirModalGestionPresentaciones()"
              class="px-3.5 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs rounded-xl border border-indigo-200 flex items-center gap-1.5 transition shadow-2xs">
        <span>📦</span> Unidades de Empaque / Presentaciones
      </button>
    </div>"""

new_header_html = """    <div class="flex items-center justify-between gap-3 mb-2 flex-wrap">
      <div class="flex items-center gap-3">
        <h2 class="font-bold text-gray-700">Registrar entrada de mercancía</h2>
        <span id="indicador-auto-guardado-borrador" class="hidden text-[11px] font-bold text-emerald-600 font-mono transition-all"></span>
      </div>
      <div class="flex items-center gap-2">
        <button type="button" onclick="document.getElementById('input-escanear-factura').click()"
                id="btn-escanear-factura-ia"
                class="px-3.5 py-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-700 hover:to-teal-700 active:scale-95 text-white font-extrabold text-xs rounded-xl shadow-sm flex items-center gap-1.5 transition cursor-pointer">
          <span class="text-sm">📷</span> <span>Escanear Factura (IA)</span>
        </button>
        <input type="file" id="input-escanear-factura" accept="image/*" capture="environment" class="hidden" onchange="escanearFacturaConIA(this)">
        <button type="button" onclick="abrirModalGestionPresentaciones()"
                class="px-3.5 py-1.5 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 font-bold text-xs rounded-xl border border-indigo-200 flex items-center gap-1.5 transition shadow-2xs cursor-pointer">
          <span>📦</span> <span class="hidden sm:inline">Unidades de Empaque /</span> Presentaciones
        </button>
      </div>
    </div>

    <!-- Banner de Escaneo con IA en curso -->
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

if old_header_html in html:
    html = html.replace(old_header_html, new_header_html, 1)
    print("2. Scanner button and banner added to tab-entradas")
else:
    print("WARNING 2: old_header_html not found")

# Add the JS function escanearFacturaConIA
js_func = """
async function escanearFacturaConIA(input) {
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
}
"""

anchor_js = "async function registrarEntrada() {"
if anchor_js in html and "async function escanearFacturaConIA" not in html:
    html = html.replace(anchor_js, js_func + "\n" + anchor_js, 1)
    with open('templates/inventario_admin.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("3. escanearFacturaConIA JS function added to inventario_admin.html")
else:
    print("WARNING 3: anchor_js not found or already added")

print("Finished patch_vision_compras.py")
