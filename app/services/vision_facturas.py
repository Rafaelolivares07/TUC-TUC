# -*- coding: utf-8 -*-
"""
Servicio de Visión por Computadora e Inteligencia Artificial Local para Facturas y Tirillas.
100% autohospedado en el servidor - Sin APIs externas ni costos por imagen.
"""

import os
import re
import cv2
import threading
import gc
import difflib

_ocr_engine = None
_ocr_lock = threading.Lock()

DICCIONARIO_TRADUCCION = {
    'MUSTARD': 'MOSTAZA',
    'PEPPERONI': 'PEPPERONI',
    'PEPPERON1': 'PEPPERONI',
    'CHEESE': 'QUESO',
    'CHEDDAR': 'QUESO CHEDDAR',
    'MOZZARELLA': 'QUESO MOZZARELLA',
    'MILK': 'LECHE',
    'BUTTER': 'MANTEQUILLA',
    'BACON': 'TOCINETA',
    'HAM': 'JAMON',
    'BEEF': 'CARNE RES',
    'PORK': 'CERDO',
    'CHICKEN': 'POLLO',
    'FLOUR': 'HARINA',
    'SUGAR': 'AZUCAR',
    'SALT': 'SAL',
    'OIL': 'ACEITE',
    'YEAST': 'LEVADURA',
    'SAUCE': 'SALSA',
    'TOMATO': 'TOMATE',
    'ONION': 'CEBOLLA',
    'LETTUCE': 'LECHUGA'
}

def traducir_texto(texto):
    if not texto: return texto
    palabras = texto.upper().split()
    trad = []
    for p in palabras:
        p_clean = re.sub(r'[^A-Z0-9]', '', p)
        if p_clean in DICCIONARIO_TRADUCCION:
            trad.append(DICCIONARIO_TRADUCCION[p_clean])
        else:
            trad.append(p)
    return " ".join(trad)

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        import os
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def preprocesar_imagen(ruta_origen):
    """
    Normaliza tamaño de imagen si es excesivamente grande para acelerar inferencia.
    Escribe en JPEG rápido y libera memoria inmediatamente.
    """
    try:
        img = cv2.imread(ruta_origen)
        if img is None:
            return ruta_origen

        h, w = img.shape[:2]
        max_dim = 1200
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            img_resized = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            ruta_opt = ruta_origen + ".opt.jpg"
            cv2.imwrite(ruta_opt, img_resized, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
            del img
            del img_resized
            return ruta_opt
        del img
        return ruta_origen
    except Exception as e:
        print(f"Aviso en preprocesamiento OpenCV ({e}), usando imagen directa.")
        return ruta_origen


def _limpiar_monto(texto_monto):
    """Convierte cadenas tipo '$170.000', '170,000.00', '45.000' en float."""
    if not texto_monto:
        return 0.0
    t = str(texto_monto).replace('$', '').strip()
    t = re.sub(r'[^\d.,]', '', t)
    if not t:
        return 0.0
    
    if '.' in t and ',' in t:
        if t.find('.') < t.find(','):
            t = t.replace('.', '').replace(',', '.')
        else:
            t = t.replace(',', '')
    elif '.' in t:
        partes = t.split('.')
        if len(partes[-1]) == 2:
            t = ''.join(partes[:-1]) + '.' + partes[-1]
        else:
            t = t.replace('.', '')
    elif ',' in t:
        partes = t.split(',')
        if len(partes[-1]) == 2:
            t = ''.join(partes[:-1]) + '.' + partes[-1]
        else:
            t = t.replace(',', '')
            
    try:
        return float(t)
    except:
        return 0.0


def _parse_entero_limpio(v_str):
    if not v_str:
        return 0.0
    t = re.sub(r'[^\d]', '', str(v_str))
    try:
        return float(t)
    except:
        return 0.0


def agrupar_en_filas_horizontales(bloques, umbral_y=10):
    """Agrupa bloques de texto que pertenecen a la misma línea horizontal."""
    filas = []
    bloques_ordenados = sorted(bloques, key=lambda b: b['centro_y'])
    for b in bloques_ordenados:
        asignado = False
        for f in filas:
            centro_fila = sum(item['centro_y'] for item in f) / len(f)
            if abs(b['centro_y'] - centro_fila) <= umbral_y:
                f.append(b)
                asignado = True
                break
        if not asignado:
            filas.append([b])
    
    for f in filas:
        f.sort(key=lambda item: item['min_x'])
    filas.sort(key=lambda f: f[0]['centro_y'])
    return filas



def _obtener_referencia_item(conn, negocio_id, proveedor_id, producto, cant, vu):
    """
    Obtiene la presentación previa, precio histórico de referencia y cantidad habitual.
    Calcula además los porcentajes de variación para avisos preventivos.
    """
    pres_id = None
    pres_nombre = "Unidad"
    pres_equiv = 1.0
    precio_ref = None
    cant_ref = None

    if not conn or not producto or not negocio_id:
        return pres_id, pres_nombre, pres_equiv, precio_ref, cant_ref, None, None

    try:
        c_row = None
        if proveedor_id:
            c_row = conn.execute("""
                SELECT c.presentacion_id, pres.nombre, pres.equivalencia, c.precio
                FROM cotizaciones_compras c
                JOIN presentaciones pres ON pres.id = c.presentacion_id
                WHERE c.negocio_id = %s AND c.tercero_id = %s AND c.item_id = %s
                ORDER BY c.fecha_cotizacion DESC NULLS LAST, c.id DESC
                LIMIT 1
            """, (negocio_id, proveedor_id, producto['id'])).fetchone()

        if not c_row:
            c_row = conn.execute("""
                SELECT c.presentacion_id, pres.nombre, pres.equivalencia, c.precio
                FROM cotizaciones_compras c
                JOIN presentaciones pres ON pres.id = c.presentacion_id
                WHERE c.negocio_id = %s AND c.item_id = %s
                ORDER BY c.fecha_cotizacion DESC NULLS LAST, c.id DESC
                LIMIT 1
            """, (negocio_id, producto['id'])).fetchone()

        if c_row:
            pres_id = c_row['presentacion_id']
            pres_nombre = c_row['nombre']
            pres_equiv = float(c_row['equivalencia']) if (c_row['equivalencia'] and float(c_row['equivalencia']) > 0) else 1.0
            if c_row['precio'] is not None and float(c_row['precio']) > 0:
                precio_ref = float(c_row['precio'])

        # Cantidad de referencia desde últimos movimientos de entrada
        m_row = None
        if proveedor_id:
            m_row = conn.execute("""
                SELECT cantidad, presentacion_id, valor_unitario
                FROM movimientos_inventario
                WHERE negocio_id = %s AND proveedor_id = %s AND producto_id = %s AND tipo = 'entrada'
                ORDER BY id DESC LIMIT 1
            """, (negocio_id, proveedor_id, producto['id'])).fetchone()
        if not m_row:
            m_row = conn.execute("""
                SELECT cantidad, presentacion_id, valor_unitario
                FROM movimientos_inventario
                WHERE negocio_id = %s AND producto_id = %s AND tipo = 'entrada'
                ORDER BY id DESC LIMIT 1
            """, (negocio_id, producto['id'])).fetchone()

        if m_row and m_row['cantidad']:
            cant_ref = round(float(m_row['cantidad']) / pres_equiv, 2)
            if precio_ref is None and m_row['valor_unitario']:
                precio_ref = round(float(m_row['valor_unitario']) * pres_equiv, 2)

    except Exception as e:
        print("Aviso referencia cotización previa:", e)

    if precio_ref is None and producto.get('costo'):
        precio_ref = round(float(producto['costo']) * pres_equiv, 2)

    var_precio_pct = None
    if precio_ref and precio_ref > 0 and vu and vu > 0:
        var_precio_pct = round(((vu - precio_ref) / precio_ref) * 100, 1)

    var_cant_pct = None
    if cant_ref and cant_ref > 0 and cant and cant > 0:
        var_cant_pct = round(((cant - cant_ref) / cant_ref) * 100, 1)

    return pres_id, pres_nombre, pres_equiv, precio_ref, cant_ref, var_precio_pct, var_cant_pct


def _buscar_en_alias(alias_map, texto, codigo=None):
    """
    Busca coincidencias en la memoria de alias del proveedor:
    1. Por código (barcode o plu exacto).
    2. Por texto exacto (insensible a mayúsculas/minúsculas y normalizando espacios múltiples).
    NO realiza coincidencias parciales ni eliminación de espacios para evitar falsos positivos.
    """
    if not alias_map:
        return None

    # 1. Por código (barcode o plu exacto)
    if codigo:
        cod_clean = str(codigo).strip()
        if cod_clean:
            for al in alias_map:
                c_orig = str(al.get('codigo_origen') or '').strip()
                if c_orig and (c_orig == cod_clean or c_orig.lstrip('0') == cod_clean.lstrip('0')):
                    return al

    # 2. Por texto exacto
    if texto:
        txt_clean = " ".join(texto.upper().split())
        if txt_clean:
            for al in alias_map:
                al_orig = " ".join((al.get('texto_origen') or '').upper().split())
                if al_orig and al_orig == txt_clean:
                    return al

    return None


def extraer_datos_factura(ruta_imagen, conn=None, negocio_id=None):
    """
    Ejecuta el pipeline de visión y extrae:
    - Proveedor sugerido (cruzado con tabla terceros)
    - Número de factura
    - Fecha
    - Total de la factura
    - Líneas de productos con sugerencias del catálogo
    """
    acquired = _ocr_lock.acquire(timeout=45)
    if not acquired:
        return {
            'ok': False,
            'error': 'El servidor está procesando otro escaneo. Por favor espera unos segundos e intenta nuevamente.'
        }

    engine = get_ocr_engine()
    ruta_proc = ruta_imagen
    try:
        ruta_proc = preprocesar_imagen(ruta_imagen)
        result, elapse_list = engine(ruta_proc)
    finally:
        if ruta_proc != ruta_imagen and os.path.exists(ruta_proc):
            try: os.remove(ruta_proc)
            except Exception: pass
        _ocr_lock.release()
        gc.collect()

    if not result:
        return {
            'ok': False,
            'error': 'No se detectó texto en la imagen. Asegúrate de que la foto tenga buena iluminación.'
        }

    bloques = []
    for item in result:
        box, text, score = item
        if not text or score < 0.35:
            continue
        xs = [pt[0] for pt in box]
        ys = [pt[1] for pt in box]
        bloques.append({
            'texto': text.strip(),
            'score': float(score),
            'min_x': min(xs),
            'max_x': max(xs),
            'min_y': min(ys),
            'max_y': max(ys),
            'centro_y': (min(ys) + max(ys)) / 2.0
        })

    if not bloques:
        return {'ok': False, 'error': 'No se detectó texto legible.'}

    filas = agrupar_en_filas_horizontales(bloques)
    lineas_texto_completas = [" ".join(b['texto'] for b in f) for f in filas]

    # =========================================================================
    # 1. FECHA
    # =========================================================================
    fecha_detectada = None
    for b in bloques:
        txt = b['texto']
        if any(k in txt.lower() for k in ["resolucion", "vigencia", "vence"]):
            continue
        m1 = re.search(r'(?:generacion|fecha|focha|expedicion|emision)?\s*[:#-]?\s*(\d{4})[\s/.-]+(\d{1,2})[\s/.-]+(\d{1,2})', txt, re.IGNORECASE)
        if m1:
            y, m, d = m1.group(1), int(m1.group(2)), int(m1.group(3))
            if 1 <= m <= 12 and 1 <= d <= 31 and 2020 <= int(y) <= 2035:
                fecha_detectada = f"{y}-{m:02d}-{d:02d}"
                break
        m2 = re.search(r'(?:generacion|fecha|expedicion|emision)?\s*[:#-]?\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})', txt, re.IGNORECASE)
        if m2:
            d, m, y = int(m2.group(1)), int(m2.group(2)), m2.group(3)
            if 1 <= m <= 12 and 1 <= d <= 31 and 2020 <= int(y) <= 2035:
                fecha_detectada = f"{y}-{m:02d}-{d:02d}"
                break

    # =========================================================================
    # 2. NÚMERO DE DOCUMENTO / FACTURA
    # =========================================================================
    num_doc_detectado = ""

    # Prioridad 00: Detección especializada de Facturas Electrónicas DIAN con prefijo (ej: PG - 198374, FE-1234, SETP556)
    # Inspeccionar líneas completas y bloques que contengan prefijo alfanumérico junto a 'Factura' o en cabecera
    for l_txt in lineas_texto_completas[:15]:
        if any(k in l_txt.lower() for k in ["resolucion", "vigencia", "rango", "autoriza", "cufe", "telefono", "tel:", "cel:", "nit", "cliente"]):
            continue
        # Buscar patrón de prefijo alfanumérico DIAN de 1-4 letras seguido de guión/espacio y 4-10 dígitos
        m_dian = re.search(r'\b([A-Z]{1,4})\s*[-–]\s*(\d{4,10})\b', l_txt)
        if m_dian:
            cand_pref = m_dian.group(1).upper()
            cand_num = m_dian.group(2)
            if cand_pref not in ('TEL', 'NIT', 'RES', 'PAG', 'CEL', 'HORA', 'DIA', 'MES', 'ANO', 'AÑO'):
                num_doc_detectado = f"{cand_pref}-{cand_num}"
                break

    # Prioridad 0A: Factura Electrónica de Venta directa con prefijo alfanumérico (ej: PG-198374, SETP556, FEV1234)
    for b in bloques:
        txt = b['texto']
        m_fev_direct = re.search(r'Factura\s*Electronica\s*(?:de\s*Venta)?\s*[-:]?\s*([A-Za-z0-9]{1,5}\s*[-]?\s*[0-9]{3,10})', txt, re.IGNORECASE)
        if m_fev_direct:
            cand = m_fev_direct.group(1).upper().replace(' ', '')
            if not cand.lower() in ('caja', 'turno', 'terminal', 'tpv', 'pos'):
                num_doc_detectado = cand
                break

    # Prioridad 0: Buscar bloque 'Factura electronica de venta' o 'Factura de venta' y tomar el código que le sigue
    if not num_doc_detectado:
      for i, b in enumerate(bloques):
        t_clean = re.sub(r'[^A-Z0-9\s]', '', b['texto'].upper())
        if 'FACTURA' in t_clean and any(k in t_clean for k in ['ELECTRONICA', 'VENTA', 'POS', 'NO', 'NUMERO']):
            # Revisar el bloque actual y los siguientes 4 bloques
            for cand_b in bloques[i:i+5]:
                t = cand_b['texto'].strip()
                # Excluir explícitamente teléfonos, clientes, resoluciones o fechas
                if any(k in t.upper() for k in ['FECHA', 'HORA', 'RESOLUCION', 'RANGO', 'VIGENCIA', 'TELEFONO', 'TEL:', 'CEL:', 'WHATSAPP', 'CC', 'NIT', 'VENDEDOR', 'DIRECCION']):
                    continue
                # Buscar patrón alfanumérico de factura (ej: IAAC16741, FEV1234, SETP556, FOP9988, PG-198374, PG 198374)
                m = re.search(r'\b([A-Z]{1,5}\s*[-]?\s*\d{3,10})\b', t, re.I)
                if m:
                    cand_doc = re.sub(r'\s+', '', m.group(1)).upper()
                    if not any(k in cand_doc for k in ['FACT', 'VENT', 'ELEC', 'POS', 'DIAN', 'RES', 'CAJA', 'TURNO']):
                        num_doc_detectado = cand_doc
                        break
            if num_doc_detectado:
                break

    # Prioridad 1: Patrones regex directos en cualquier bloque
    if not num_doc_detectado:
        for b in bloques:
            txt = b['texto']
            if any(k in txt.upper() for k in ['TELEFONO', 'TEL:', 'CEL:', 'WHATSAPP', 'NIT:', 'CC:']):
                continue
            m_fev = re.search(r'Factura\s+Electronica\s+de\s+Venta\s+([A-Za-z0-9]+)', txt, re.IGNORECASE)
            if m_fev:
                cand = m_fev.group(1).upper()
                cand = re.sub(r'^F0([A-Z0-9])', r'FO\1', cand)
                if len(cand) >= 4 and not cand.lower() in ('caja', 'turno', 'terminal', 'tpv', 'pos'):
                    num_doc_detectado = cand
                    break

            m_pref = re.search(r'\b([0-9]{1,2}[A-Z]{2,4}\d{4,}|F[0O]P\d{4,}|SETP\d{4,}|FE\d{4,}|POS\d{4,})\b', txt, re.IGNORECASE)
            if m_pref:
                cand = m_pref.group(1).upper().replace('F0P', 'FOP')
                if not cand.lower() in ('caja', 'turno', 'terminal', 'tpv', 'pos'):
                    num_doc_detectado = cand
                    break

    if not num_doc_detectado:
        patrones_doc = [
            r'(?:Nro(?:\s+de)?\s+recibo|No\.?\s*de\s*recibo|Recibo)\s*[:#-]?\s*([0-9A-Za-z-]+)',
            r'Comprobante\s+de\s+Entrega\s*[:#-]?\s*([0-9\s]+)',
            r'(?:FACTURA|COMPROBANTE|REMISION)\s*[:#-]?\s*([A-Za-z0-9-]+)',
            r'#\s*([0-9]{3,})',
            r'(?:FE|POS)\s*([0-9]{3,})'
        ]
        for l_txt in lineas_texto_completas:
            if any(k in l_txt.lower() for k in ["resolucion", "dian", "carrera", "cra", "calle", "clle", "sur", "av", "diagonal", "transversal", "telefono", "tel:", "cel:"]):
                continue
            for pat in patrones_doc:
                m = re.search(pat, l_txt, re.IGNORECASE)
                if m:
                    cand = m.group(1).replace(' ', '').strip()
                    # Si tiene 10 dígitos y empieza por 3, es un teléfono colombiano, descartarlo
                    if len(cand) == 10 and cand.startswith('3'):
                        continue
                    if re.match(r'^(?:202\d|203\d)', cand):
                        continue
                    if len(cand) >= 2 and not cand.lower() in ('de', 'del', 'la', 'venta', 'electronica', 'cadena', 'turno', 'caja', 'terminal', 'tpv', 'pos'):
                        num_doc_detectado = cand
                        break
            if num_doc_detectado:
                break

    # =========================================================================
    # 3. TOTAL FACTURA
    # =========================================================================
    total_factura = 0.0
    # Prioridad 1: Filas que expresamente indiquen TOTAL FACTURA, TOTAL A PAGAR, TOTAL COMPRA
    for fila in filas:
        texto_fila = " ".join(b['texto'] for b in fila).upper()
        if any(k in texto_fila for k in ["RECOMPENSA", "PUNTOS", "PREMIO", "AHORRO"]):
            continue
        if any(k in texto_fila for k in ["TOTAL FACTURA", "TOTAL A PAGAR", "TOTAL COMPRA", "VALOR A PAGAR", "TOTAL A CANCELAR"]) and not any(k in texto_fila for k in ["EFECTIVO", "CAMBIO", "VUELTAS", "ITEMS", "DESCUENTO"]):
            for b in reversed(fila):
                m_din = re.search(r'\$?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)', b['texto'])
                if m_din:
                    val = _limpiar_monto(m_din.group(1))
                    if val > 100:
                        total_factura = val
                        break
            if total_factura > 0:
                break

    # Prioridad 2: Buscar fila con 'TOTAL' excluyendo montos de EFECTIVO, CAMBIO, VUELTAS y RECOMPENSAS
    if total_factura == 0.0:
        for i, fila in enumerate(filas):
            texto_fila = " ".join(b['texto'] for b in fila).upper()
            if any(k in texto_fila for k in ["RECOMPENSA", "PUNTOS", "PREMIO", "AHORRO", "BASE", "SUBTOTAL", "ANUAL", "ACUMULAD"]):
                continue
            if "TOTAL" in texto_fila and not any(k in texto_fila for k in ["VENTAS", "TRANSACCIONES", "UNIDADES", "ITEMS", "DESCUENTO", "EFECTIVO", "CAMBIO", "VUELTAS", "ANUAL", "RECOMPENSA"]):
                for b in reversed(fila):
                    m_din = re.search(r'\$?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)', b['texto'])
                    if m_din:
                        val = _limpiar_monto(m_din.group(1))
                        if val > 100:
                            total_factura = val
                            break
                if total_factura > 0:
                    break

    # =========================================================================
    # =========================================================================
    # 3B. MÉTODO DE PAGO DETECTADO EN FACTURA / TIRILLA
    # =========================================================================
    metodo_pago_detectado = None
    for b in bloques:
        tu = b['texto'].upper()
        if any(k in tu for k in ['TARJETA DEBITO', 'DEBITO', 'TARJETA CREDITO', 'CREDITO', 'EFECTIVO', 'TRANSFERENCIA', 'NEQUI', 'DAVIPLATA']):
            if 'TARJETA DEBITO' in tu or 'DEBITO' in tu:
                metodo_pago_detectado = 'TARJETA DEBITO'
                break
            elif 'TARJETA CREDITO' in tu:
                metodo_pago_detectado = 'TARJETA CREDITO'
                break
            elif 'EFECTIVO' in tu:
                metodo_pago_detectado = 'EFECTIVO'
                break
            elif 'TRANSFERENCIA' in tu:
                metodo_pago_detectado = 'TRANSFERENCIA'
                break
            elif 'NEQUI' in tu:
                metodo_pago_detectado = 'NEQUI'
                break
            elif 'DAVIPLATA' in tu:
                metodo_pago_detectado = 'DAVIPLATA'
                break

    # 4. PROVEEDOR (Cruce con tabla terceros)
    # =========================================================================
    proveedor_id = None
    proveedor_nombre = ""
    terceros_db = []
    if conn:
        try:
            if negocio_id:
                t_rows = conn.execute("""
                    SELECT t.id, t.nombre, t.tipo_tercero,
                           COUNT(m.id) as total_compras
                    FROM terceros t
                    LEFT JOIN movimientos_inventario m ON m.proveedor_id = t.id AND m.tipo = 'entrada' AND m.negocio_id = %s
                    GROUP BY t.id, t.nombre, t.tipo_tercero
                    ORDER BY total_compras DESC, t.id ASC
                """, (negocio_id,)).fetchall()
            else:
                t_rows = conn.execute("SELECT id, nombre, tipo_tercero, 0 as total_compras FROM terceros ORDER BY id ASC").fetchall()
            terceros_db = [dict(r) for r in t_rows]
        except Exception as e:
            print("Aviso terceros:", e)

    mejores_coincidencias = []
    for b in bloques[:18]:
        txt_raw = b['texto'].upper()
        # Excluir bloques del cliente/comprador, teléfonos o direcciones para no confundir comprador con proveedor
        if any(k in txt_raw for k in ['CLIENTE', 'CONSUMIDOR', 'ADQUIRIENTE', 'COMPRADOR', 'SEÑOR', 'DIRECCION', 'TELEFONO', 'TEL:', 'CEL:']):
            continue
        txt_clean = re.sub(r'[^A-Z0-9\s]', '', txt_raw).strip()
        if len(txt_clean) < 2:
            continue
        palabras_doc = txt_clean.split()
        for terc in terceros_db:
            nom_terc = re.sub(r'[^A-Z0-9\s]', '', terc['nombre'].upper()).strip()
            if not nom_terc:
                continue
            has_history = terc.get('total_compras', 0) > 0
            w = 1.1 if has_history else 1.0

            # Nombres cortos (<= 4 letras como D1) requieren coincidencia de palabra completa, nunca subcadena cruda
            if len(nom_terc) <= 4:
                if nom_terc in palabras_doc or nom_terc == txt_clean:
                    mejores_coincidencias.append((1.0 * w, terc['id'], terc['nombre']))
            else:
                if nom_terc in palabras_doc or nom_terc == txt_clean:
                    mejores_coincidencias.append((1.0 * w, terc['id'], terc['nombre']))
                elif nom_terc in txt_clean:
                    mejores_coincidencias.append((0.85 * w, terc['id'], terc['nombre']))
                else:
                    ratio = difflib.SequenceMatcher(None, txt_clean, nom_terc).ratio()
                    if ratio >= 0.70:
                        mejores_coincidencias.append((ratio * w, terc['id'], terc['nombre']))

    # Buscar en dominios de correo o webs de la factura (ej: panperman.com -> PERMAN)
    for b in bloques:
        txt_u = b['texto'].upper()
        if '@' in txt_u or '.COM' in txt_u or 'WWW.' in txt_u:
            for terc in terceros_db:
                nom_terc = re.sub(r'[^A-Z0-9\s]', '', terc['nombre'].upper()).strip()
                palabras_clave = [p for p in nom_terc.split() if len(p) >= 4 and p not in ('INDUSTRIAS', 'ALIMENTICIAS', 'DISTRIBUIDORA', 'COMERCIALIZADORA')]
                for pk in palabras_clave:
                    if pk in txt_u:
                        w = 1.25 if terc.get('total_compras', 0) > 0 else 1.0
                        mejores_coincidencias.append((0.95 * w, terc['id'], terc['nombre']))

    if mejores_coincidencias:
        mejores_coincidencias.sort(key=lambda x: x[0], reverse=True)
        proveedor_id = mejores_coincidencias[0][1]
        proveedor_nombre = mejores_coincidencias[0][2]
    else:
        for l in lineas_texto_completas[:4]:
            if len(l) > 3 and not any(p in l.upper() for p in ['FACTURA', 'TICKET', 'RESUMEN', 'NIT', 'FECHA']):
                proveedor_nombre = l
                break

    # =========================================================================
    # 5. CATÁLOGO DE PRODUCTOS (Para cruce y sugerencias)
    # =========================================================================
    productos_db = []
    if conn and negocio_id:
        try:
            p_rows = conn.execute("""
                SELECT id, nombre, costo, precio, iva_pct, codigo_barra
                FROM productos
                WHERE negocio_id = %s
                ORDER BY nombre ASC
            """, (negocio_id,)).fetchall()
            productos_db = [dict(r) for r in p_rows]
        except Exception as e:
            print("Aviso productos:", e)

    # 5B. MEMORIA DE MAPEOS Y APRENDIZAJE DE ESTE PROVEEDOR
    alias_map = []
    if conn and negocio_id and proveedor_id:
        try:
            a_rows = conn.execute("""
                SELECT a.id as alias_id, a.texto_origen, a.codigo_origen,
                       COALESCE(a.tipo_destino, 'inventario') as tipo_destino,
                       a.producto_id, a.presentacion_id, a.cuenta_id,
                       p.nombre as producto_nombre, p.iva_pct,
                       pr.nombre as pres_nombre, pr.equivalencia as pres_equiv,
                       c.codigo as cuenta_codigo, c.nombre as cuenta_nombre
                FROM proveedores_productos_alias a
                LEFT JOIN productos p ON p.id = a.producto_id
                LEFT JOIN presentaciones pr ON pr.id = a.presentacion_id
                LEFT JOIN cuentas_puc c ON c.id = a.cuenta_id
                WHERE a.negocio_id = %s AND (a.proveedor_id = %s OR a.proveedor_id IS NULL)
                ORDER BY a.veces_usado DESC
            """, (negocio_id, proveedor_id)).fetchall()
            alias_map = [dict(r) for r in a_rows]
        except Exception as e:
            print("Aviso alias_map:", e)

    # 5C. DETECCIÓN PREVENTIVA DE FACTURA DUPLICADA O YA REGISTRADA (Ventana máxima 2 días en duplicados por valor)
    posible_duplicada = None
    if conn and negocio_id and proveedor_id:
        try:
            prov_nombre_final = proveedor_nombre
            if not prov_nombre_final:
                row_p = conn.execute("SELECT nombre FROM terceros WHERE id = %s", (proveedor_id,)).fetchone()
                if row_p:
                    prov_nombre_final = row_p['nombre']

            if num_doc_detectado:
                exist_mov = conn.execute("""
                    SELECT m.id, m.documento_fecha, m.documento_numero, m.documento_total, m.tipo_documento_id,
                           t.nombre as tipo_doc_nombre, t.codigo as tipo_doc_codigo
                    FROM movimientos_inventario m
                    LEFT JOIN tipos_documento_negocio t ON t.id = m.tipo_documento_id
                    WHERE m.negocio_id = %s AND m.tipo = 'entrada' AND m.proveedor_id = %s
                      AND (
                          UPPER(TRIM(m.documento_numero)) = UPPER(TRIM(%s))
                          OR (
                              LENGTH(REGEXP_REPLACE(m.documento_numero, '[^0-9]', '', 'g')) >= 4
                              AND REGEXP_REPLACE(m.documento_numero, '[^0-9]', '', 'g') = REGEXP_REPLACE(%s, '[^0-9]', '', 'g')
                          )
                      )
                    LIMIT 1
                """, (negocio_id, proveedor_id, num_doc_detectado, num_doc_detectado)).fetchone()
                if exist_mov:
                    f_str = str(exist_mov['documento_fecha']) if exist_mov['documento_fecha'] else 'Fecha previa'
                    posible_duplicada = {
                        'existe': True,
                        'tipo': 'NUMERO_DOCUMENTO',
                        'movimiento_id': exist_mov['id'],
                        'documento_numero': exist_mov['documento_numero'],
                        'tipo_documento_id': exist_mov['tipo_documento_id'],
                        'tipo_documento_codigo': exist_mov.get('tipo_doc_codigo') or 'FC',
                        'tipo_documento_nombre': exist_mov.get('tipo_doc_nombre') or 'Factura Proveedor',
                        'proveedor_id': proveedor_id,
                        'proveedor_nombre': prov_nombre_final or '',
                        'fecha': f_str,
                        'total': float(exist_mov['documento_total'] or 0),
                        'mensaje': f"⚠️ ¡Atención! La factura/recibo N° {exist_mov['documento_numero']} ya fue ingresada el {f_str} para este proveedor."
                    }
            if not posible_duplicada and total_factura > 0:
                exist_tot = conn.execute("""
                    SELECT m.id, m.documento_fecha, m.documento_numero, m.documento_total, m.tipo_documento_id,
                           t.nombre as tipo_doc_nombre, t.codigo as tipo_doc_codigo
                    FROM movimientos_inventario m
                    LEFT JOIN tipos_documento_negocio t ON t.id = m.tipo_documento_id
                    WHERE m.negocio_id = %s AND m.tipo = 'entrada' AND m.proveedor_id = %s
                      AND ABS(m.documento_total - %s) <= 50
                      AND m.created_at >= (CURRENT_DATE - INTERVAL '2 days')
                    LIMIT 1
                """, (negocio_id, proveedor_id, total_factura)).fetchone()
                if exist_tot:
                    f_str = str(exist_tot['documento_fecha']) if exist_tot['documento_fecha'] else 'Reciente'
                    posible_duplicada = {
                        'existe': True,
                        'tipo': 'TOTAL_RECIENTE',
                        'movimiento_id': exist_tot['id'],
                        'documento_numero': exist_tot['documento_numero'],
                        'tipo_documento_id': exist_tot['tipo_documento_id'],
                        'tipo_documento_codigo': exist_tot.get('tipo_doc_codigo') or 'FC',
                        'tipo_documento_nombre': exist_tot.get('tipo_doc_nombre') or 'Factura Proveedor',
                        'proveedor_id': proveedor_id,
                        'proveedor_nombre': prov_nombre_final or '',
                        'fecha': f_str,
                        'total': float(exist_tot['documento_total'] or 0),
                        'mensaje': f"⚠️ Posible factura duplicada: Ya existe una entrada registrada el {f_str} por el mismo valor exacto (${total_factura:,.0f})."
                    }
        except Exception as e:
            print("Aviso detección duplicada:", e)

# =========================================================================
    # 6. EXTRACCIÓN DE ÍTEMS
    # =========================================================================
    y_top_items = 180
    y_bot_items = 999999
    for b in bloques:
        if "DESCRIPCION" in b['texto'].upper():
            y_top_items = max(y_top_items, b['min_y'])
        if b['texto'].strip().upper() == "TOTAL":
            y_bot_items = min(y_bot_items, b['min_y'])
            break

    bloques_en_zona_items = [b for b in bloques if y_top_items <= b['centro_y'] <= y_bot_items]
    barcode_blocks = [b for b in bloques_en_zona_items if re.search(r'(770\d{10}|0\d{12}|\d{13})', b['texto'])]

    items_extraidos = []

    # CASO A: FACTURAS RETAIL / D1 CON CÓDIGOS DE BARRA ANCLADOS
    if len(barcode_blocks) >= 2:
        barcode_blocks.sort(key=lambda b: b['centro_y'])
        right_blocks = [b for b in bloques_en_zona_items if b['min_x'] > 410]
        # left_blocks: solo bloques a la izquierda (< 180) que NO sean barcode_blocks
        left_blocks = [b for b in bloques_en_zona_items if b['min_x'] < 180 and b not in barcode_blocks]

        for b in barcode_blocks:
            cy = b['centro_y']
            text = b['texto']

            # A1. Total de la línea
            # Separar precio y código de barras si vienen pegados (ej: 16,9907700304775071 -> 16,990 7700304775071)
            text = re.sub(r'([0-9.,]+)(770\d{10})', r'\1 \2', text)

            total_line = 0.0
            m_end_tot = re.search(r'([0-9]{1,3}(?:[.,][0-9]{3})+|[0-9]{3,})[A-Za-z0-9]?$', text)
            if m_end_tot:
                val_end = _parse_entero_limpio(m_end_tot.group(1))
                if val_end > 0 and len(str(int(val_end))) <= 7:
                    total_line = val_end
                    text_without_total = text[:m_end_tot.start()].strip()
                else:
                    text_without_total = text
            else:
                text_without_total = text

            if total_line == 0.0:
                c_right = None
                min_dist_r = 999
                for rb in right_blocks:
                    dist = abs(rb['centro_y'] - cy)
                    if dist < min_dist_r and dist < 18:
                        min_dist_r = dist
                        c_right = rb
                if c_right:
                    m_tot = re.search(r'([0-9]{1,3}(?:[.,][0-9]{3})+|[0-9]{2,})', c_right['texto'])
                    if m_tot:
                        total_line = _parse_entero_limpio(m_tot.group(1))

            # A2. Código de barras y Descripción
            m_bc = re.search(r'(770\d{10}|07\d{11}|0\d{12}|\d{13})', text_without_total)
            if m_bc:
                bc = m_bc.group(1)
                desc_part = text_without_total[m_bc.end():].strip()
                pre_part = text_without_total[:m_bc.start()].strip()
            else:
                bc = ""
                desc_part = text_without_total
                pre_part = ""

            m_vu = re.search(r'([0-9]{1,3}(?:[.,][0-9]{3})*|[0-9]{3,})', pre_part)
            vu = _parse_entero_limpio(m_vu.group(1)) if m_vu else 0.0

            # A3. Cantidad: Búsqueda y Reconciliación
            cant = None
            # 1. Si el bloque mismo empieza por cantidad UN (ej: "91UN" -> 1 UN)
            m_start_cant = re.search(r'^(?:[0-9]{1,2})?\s*([0-9]+)\s*UN', text_without_total)
            if m_start_cant:
                cant = float(m_start_cant.group(1))

            # 2. Si no, buscar en bloque izquierdo (columna UN más cercana)
            if cant is None:
                c_left = None
                min_dist_l = 999
                for lb in left_blocks:
                    dist = abs(lb['centro_y'] - cy)
                    if dist < min_dist_l and dist < 20:
                        min_dist_l = dist
                        c_left = lb
                if c_left:
                    m_c = re.search(r'([0-9]+)\s*(?:/|\s)*([0-9]*)\s*UN', c_left['texto'])
                    if m_c:
                        if m_c.group(2): cant = float(m_c.group(2))
                        else: cant = float(m_c.group(1))
                    elif 'UN' in c_left['texto'].upper():
                        cant = 1.0

            # 3. Reconciliación aritmética solo si aún no se determinó la cantidad
            if cant is None and total_line > 0 and vu > 0:
                cant_calc = round(total_line / vu)
                if 1 <= cant_calc <= 20 and abs((cant_calc * vu) - total_line) < 5:
                    cant = float(cant_calc)

            if cant is None or cant == 0:
                cant = 1.0

            # Limpiezas de OCR
            desc = desc_part.strip()
            desc = re.sub(r'\bH0RTADELA\b', 'MORTADELA', desc)
            desc = re.sub(r'\bALIHENTO\b', 'ALIMENTO', desc)
            desc = re.sub(r'^[0-9\s.,]+', '', desc).strip()

            if cant > 0 and total_line > 0:
                vu = round(total_line / cant, 2)
            elif total_line == 0.0 and cant > 0 and vu > 0:
                total_line = round(vu * cant, 2)

            # Cruzar con catálogo de productos y memoria del proveedor:
            mejor_prod = None
            mejor_score = 0.0
            pres_id, pres_nombre, pres_equiv = None, "Unidad", 1.0
            matched_alias = None
            es_gasto = False
            descartado = False
            cuenta_id = None
            cuenta_codigo = None
            cuenta_nombre = None
            tipo_destino = 'inventario'

            # Prioridad 0: Memoria aprendida de este proveedor (Alias)
            matched_alias = _buscar_en_alias(alias_map, desc, bc)
            if matched_alias:
                tipo_dest = matched_alias.get('tipo_destino') or 'inventario'
                tipo_destino = tipo_dest
                if tipo_dest == 'descartar':
                    descartado = True
                elif tipo_dest in ('gasto', 'costo'):
                    es_gasto = True
                    cuenta_id = matched_alias.get('cuenta_id')
                    cuenta_codigo = matched_alias.get('cuenta_codigo')
                    cuenta_nombre = matched_alias.get('cuenta_nombre')
                else:
                    mejor_prod = {'id': matched_alias['producto_id'], 'nombre': matched_alias['producto_nombre'], 'iva_pct': matched_alias.get('iva_pct', 0)}
                    mejor_score = 1.0
                    pres_id = matched_alias.get('presentacion_id')
                    pres_nombre = matched_alias.get('pres_nombre') or "Unidad"
                    pres_equiv = float(matched_alias.get('pres_equiv') or 1.0)

            # Prioridad 1: Coincidencia por código de barras exacto (100% certero)
            if not mejor_prod and not es_gasto and not descartado and bc:
                for p in productos_db:
                    cb_db = str(p.get('codigo_barra') or '').strip()
                    if cb_db and (cb_db == bc or cb_db.lstrip('0') == bc.lstrip('0')):
                        mejor_prod = p
                        mejor_score = 1.0
                        break

            # Prioridad 2: Coincidencia por similitud de texto (umbral estricto >= 0.70)
            if not mejor_prod and not es_gasto and not descartado:
                nom_upper = desc.upper()
                for p in productos_db:
                    p_nom = p['nombre'].upper()
                    if len(p_nom) >= 5 and (p_nom in nom_upper or nom_upper in p_nom):
                        score = 0.85
                    else:
                        score = difflib.SequenceMatcher(None, nom_upper, p_nom).ratio()
                    if score > mejor_score and score >= 0.70:
                        mejor_score = score
                        mejor_prod = p

            # Buscar presentación, empaque previo y tolerancias de precio/cantidad
            pres_ref_id, pres_ref_nom, pres_ref_eq, precio_ref, cant_ref, var_p_pct, var_c_pct = _obtener_referencia_item(
                conn, negocio_id, proveedor_id, mejor_prod, cant, vu
            )
            if not pres_id:
                pres_id = pres_ref_id
                pres_nombre = pres_ref_nom
                pres_equiv = pres_ref_eq

            items_extraidos.append({
                'texto_detectado': desc,
                'codigo_detectado': bc,
                'cantidad': cant,
                'total_linea': total_line,
                'valor_unitario': vu,
                'barcode': bc,
                'producto_id': mejor_prod['id'] if mejor_prod else None,
                'producto_nombre': mejor_prod['nombre'] if mejor_prod else desc,
                'iva_pct': float(mejor_prod.get('iva_pct') or 0) if mejor_prod else 0.0,
                'match_confianza': round(mejor_score * 100, 1) if mejor_prod else 0.0,
                'identificado': bool(mejor_prod is not None),
                'presentacion_id': pres_id,
                'presentacion_nombre': pres_nombre,
                'presentacion_equivalencia': pres_equiv,
                'precio_referencia': precio_ref,
                'cantidad_referencia': cant_ref,
                'variacion_precio_pct': var_p_pct,
                'variacion_cant_pct': var_c_pct,
                'tipo_destino': tipo_destino,
                'es_gasto': es_gasto,
                'descartado': descartado,
                'cuenta_id': cuenta_id,
                'cuenta_codigo': cuenta_codigo,
                'cuenta_nombre': cuenta_nombre
            })

    # CASO B: FACTURAS TRADICIONALES EN COLUMNAS HORIZONTALES (Sin códigos de barras)
    else:
        # Delimitar zona de productos si existen cabeceras y totales
        y_top_pos = None
        y_bot_pos = None
        for b in bloques:
            tu = b['texto'].upper()
            if ('DESCRIPCION' in tu or 'DESCRIPCICN' in tu or 'REG. | ITEM' in tu) and y_top_pos is None:
                y_top_pos = b['min_y']
            if re.search(r'^\s*TOTAL\b', tu) and y_top_pos is not None and y_bot_pos is None:
                if b['min_y'] > y_top_pos:
                    y_bot_pos = b['min_y']
                    break

        en_zona_items = False
        pending_desc = ""

        # Si delimitamos coordenadas exactas, filtramos las filas directamente dentro de la zona
        filas_a_evaluar = filas
        if y_top_pos and y_bot_pos:
            filas_a_evaluar = []
            for f in filas:
                cy = sum(b['centro_y'] for b in f) / len(f)
                if (y_top_pos - 8) <= cy <= (y_bot_pos + 8):
                    filas_a_evaluar.append(f)
            en_zona_items = True

        for fila in filas_a_evaluar:
            texto_fila = " ".join(b['texto'] for b in fila).strip()
            texto_upper = texto_fila.upper()

            # Si no teníamos coordenadas fijas, detectar inicio dinámico de tabla
            if not en_zona_items and any(k in texto_upper for k in ['CANT.U.M', 'DESCRIPCICN', 'DESCRIPCION', 'REG. | ITEM', 'REG.', 'CANT | DESCRIP', 'CANTIDAD']):
                en_zona_items = True
                continue

            # Detectar fin de tabla de productos
            if en_zona_items and not (y_top_pos and y_bot_pos) and any(k in texto_upper for k in ['SUBTOTAL', 'TOTAL ITEMS', 'TOTAL FACTURA', 'TU AHORRO', 'CAMBIO', 'RESUMEN DE IMPUESTOS', 'EFECTIVO', 'VF', 'VISA', 'TOTAL']):
                en_zona_items = False
                break

            if en_zona_items:
                # Omitir filas de metadatos o encabezados de columnas
                if any(k in texto_upper for k in ['FECHA', 'CLIENTE', 'CONSUMIDOR', 'CAJERO', 'CONDICION', 'TPV', 'N.I.T', 'NIT:', 'TELEF0NO', 'CRA', 'CARRERA', 'VENDEDOR', 'RESOLUCION', 'RANGO', 'VIGENCIA', 'PVTA', 'VRTOTAL', 'CANT VRTOTAL', 'DESCRIPCION', 'DESCRIPCICN']):
                    continue

                # Extraer precio de la fila (último bloque con monto válido, excluyendo gramajes)
                total_line = 0.0
                precio_block_idx = None
                for idx in range(len(fila)-1, -1, -1):
                    b_raw = fila[idx]['texto']
                    # Ignorar especificaciones de gramaje/tamaño (ej: X2450gr, 500g, 1000ml)
                    if re.search(r'[xX]?\d+\s*(?:gr|g|ml|kg|oz|cc|cm|mm)\b', b_raw, re.I):
                        continue
                    m_p = re.search(r'[$]?\s*([0-9]{1,3}(?:[.,][0-9]{3})+|[0-9]{4,})\*?', b_raw)
                    if m_p:
                        p_val = _limpiar_monto(m_p.group(1))
                        if p_val > 50:
                            total_line = p_val
                            precio_block_idx = idx
                            break

                # Si no tiene precio pero tiene descripción válida, guardarla como pendiente para la fila siguiente
                if total_line == 0.0:
                    desc_cand = re.sub(r'^[0-9\s#.,-]+', '', texto_fila).strip()
                    if len(desc_cand) >= 4 and not any(k in desc_cand.upper() for k in ['SUBTOTAL', 'TOTAL', 'IVA', 'EXENTA', 'PVTA', 'VRTOTAL', 'DESCRIPCION']):
                        pending_desc = desc_cand
                    continue

                if total_line > 0:
                    cant = 1.0
                    cant_fijada = False
                    cod_proveedor = ""
                    desc_parts = []

                    for idx, b in enumerate(fila):
                        if idx == precio_block_idx:
                            continue
                        b_txt = b['texto'].strip()
                        b_upper = b_txt.upper()

                        # Ignorar tokens de unidad de medida
                        if b_upper in ('UND', 'UN', 'PUN', 'KG', 'KGS', 'GR', 'GRS', 'PAQ', 'CJA', 'BOL'):
                            continue

                        # Revisar si viene código pegado a descripción (ej: 60166PAN -> código 60166, desc PAN)
                        m_split = re.match(r'^(\d{3,7})([A-Z]{2,}.*)$', b_txt, re.I)
                        if m_split:
                            cod_proveedor = m_split.group(1)
                            desc_parts.append(m_split.group(2))
                            continue

                        # Unidad explícita con cantidad (ej: 1.00un, 2 un, 1.5kg, 3 und, 200, etc.)
                        m_cant_unit = re.search(r'^(\d+(?:[.,]\d+)?)\s*(?:un|und|pun|kg|gr|g|lb|paq|x)?$', b_txt, re.IGNORECASE)
                        if m_cant_unit:
                            try:
                                cv = float(m_cant_unit.group(1).replace(',', '.'))
                                if 0 < cv <= 2000 and not cant_fijada:
                                    cant = cv
                                    cant_fijada = True
                                    continue
                            except: pass

                        # Código PLU o alfanumérico (ej: DQU21, 11207, 297888, 4718)
                        m_c = re.search(r'^[A-Z0-9]{3,8}$', b_txt, re.I)
                        if m_c and not cod_proveedor and not any(k in b_upper for k in ['UND', 'PUN', 'KGS', 'VALOR']):
                            cod_proveedor = b_txt
                            continue

                        # Ignorar indicador de impuesto aislado al final
                        if b_upper in ('B', 'A'):
                            continue

                        desc_parts.append(b_txt)

                    nom_it = " ".join(desc_parts).strip()
                    if pending_desc:
                        nom_it = pending_desc
                        pending_desc = ""
                    else:
                        nom_it = nom_it or cod_proveedor

                    nom_it = re.sub(r'^[0-9\s.,#]+', '', nom_it).strip()
                    nom_it = re.sub(r'Pepperon[0-9iIl1]M?', 'Pepperoni ', nom_it, flags=re.I).strip()
                    if not nom_it or len(nom_it) < 2:
                        continue

                    vu_calc = total_line
                    # Reconciliación aritmética: si la columna leída era Vr. Unitario y no Total Línea
                    if total_factura > 0 and cant > 1 and abs((total_line * cant) - total_factura) <= 100:
                        vu_calc = total_line
                        total_line = round(vu_calc * cant, 2)
                    elif cant > 0 and total_line > 0:
                        vu_calc = round(total_line / cant, 2)

                    # ── VINCULACIÓN INTELIGENTE (ALIAS / MEMORIA + DICCIONARIO BILINGÜE) ──
                    mejor_prod = None
                    mejor_score = 0.0
                    pres_id, pres_nombre, pres_equiv = None, "Unidad", 1.0
                    matched_alias = None
                    es_gasto = False
                    descartado = False
                    cuenta_id = None
                    cuenta_codigo = None
                    cuenta_nombre = None
                    tipo_destino = 'inventario'

                    # Prioridad 0: Memoria aprendida de este proveedor (Alias)
                    matched_alias = _buscar_en_alias(alias_map, nom_it, cod_proveedor)
                    if matched_alias:
                        tipo_dest = matched_alias.get('tipo_destino') or 'inventario'
                        tipo_destino = tipo_dest
                        if tipo_dest == 'descartar':
                            descartado = True
                        elif tipo_dest in ('gasto', 'costo'):
                            es_gasto = True
                            cuenta_id = matched_alias.get('cuenta_id')
                            cuenta_codigo = matched_alias.get('cuenta_codigo')
                            cuenta_nombre = matched_alias.get('cuenta_nombre')
                        else:
                            mejor_prod = {'id': matched_alias['producto_id'], 'nombre': matched_alias['producto_nombre'], 'iva_pct': matched_alias.get('iva_pct', 0)}
                            mejor_score = 1.0
                            pres_id = matched_alias.get('presentacion_id')
                            pres_nombre = matched_alias.get('pres_nombre') or "Unidad"
                            pres_equiv = float(matched_alias.get('pres_equiv') or 1.0)

                    # Prioridad 1: Coincidencia por código o PLU exacto en el catálogo
                    if not mejor_prod and not es_gasto and not descartado and cod_proveedor:
                        for p in productos_db:
                            cb_db = str(p.get('codigo_barra') or '').strip()
                            if cb_db and (cb_db == cod_proveedor or cb_db.lstrip('0') == cod_proveedor.lstrip('0')):
                                mejor_prod = p
                                mejor_score = 1.0
                                break

                    # Prioridad 2: Coincidencia por similitud de texto estricta
                    if not mejor_prod and not es_gasto and not descartado:
                        nom_traducido = traducir_texto(nom_it)
                        nom_upper = nom_traducido.upper()

                        for p in productos_db:
                            p_nom = p['nombre'].upper()
                            score = 0.0
                            if len(p_nom) >= 3 and (p_nom in nom_upper or nom_upper in p_nom):
                                score = 0.85
                                # Si coincide con palabras clave del proveedor detectado, máxima confianza
                                if proveedor_nombre and any(pk in p_nom for pk in proveedor_nombre.upper().split() if len(pk) >= 4 and pk not in ('INDUSTRIAS', 'ALIMENTICIAS', 'DISTRIBUIDORA', 'COMERCIALIZADORA')):
                                    score = 0.99
                            else:
                                score = difflib.SequenceMatcher(None, nom_upper, p_nom).ratio()
                            if score > mejor_score and score >= 0.70:
                                mejor_score = score
                                mejor_prod = p

                    # Buscar presentación, empaque previo y tolerancias de precio/cantidad
                    pres_ref_id, pres_ref_nom, pres_ref_eq, precio_ref, cant_ref, var_p_pct, var_c_pct = _obtener_referencia_item(
                        conn, negocio_id, proveedor_id, mejor_prod, cant, vu_calc
                    )
                    if not pres_id:
                        pres_id = pres_ref_id
                        pres_nombre = pres_ref_nom
                        pres_equiv = pres_ref_eq

                    items_extraidos.append({
                        'texto_detectado': nom_it,
                        'codigo_detectado': cod_proveedor,
                        'cantidad': cant,
                        'total_linea': total_line,
                        'valor_unitario': vu_calc,
                        'barcode': cod_proveedor,
                        'producto_id': mejor_prod['id'] if mejor_prod else None,
                        'producto_nombre': mejor_prod['nombre'] if mejor_prod else nom_it,
                        'iva_pct': float(mejor_prod.get('iva_pct') or 0) if mejor_prod else 0.0,
                        'match_confianza': round(mejor_score * 100, 1) if mejor_prod else 0.0,
                        'identificado': bool(mejor_prod is not None),
                        'presentacion_id': pres_id,
                        'presentacion_nombre': pres_nombre,
                        'presentacion_equivalencia': pres_equiv,
                        'precio_referencia': precio_ref,
                        'cantidad_referencia': cant_ref,
                        'variacion_precio_pct': var_p_pct,
                        'variacion_cant_pct': var_c_pct,
                        'tipo_destino': tipo_destino,
                        'es_gasto': es_gasto,
                        'descartado': descartado,
                        'cuenta_id': cuenta_id,
                        'cuenta_codigo': cuenta_codigo,
                        'cuenta_nombre': cuenta_nombre
                    })

    lineas_identificadas = [it for it in items_extraidos if it.get('identificado') and not it.get('es_gasto') and not it.get('descartado')]
    lineas_gastos = [it for it in items_extraidos if it.get('es_gasto')]
    lineas_descartadas = [it for it in items_extraidos if it.get('descartado')]
    lineas_no_identificadas = [it for it in items_extraidos if not it.get('identificado') and not it.get('es_gasto') and not it.get('descartado')]

    return {
        'ok': True,
        'datos': {
            'fecha': fecha_detectada,
            'documento_numero': num_doc_detectado,
            'total': total_factura,
            'proveedor_id': proveedor_id,
            'proveedor_nombre': proveedor_nombre,
            'lineas': lineas_identificadas,
            'lineas_gastos': lineas_gastos,
            'lineas_descartadas': lineas_descartadas,
            'lineas_no_identificadas': lineas_no_identificadas,
            'total_lineas_detectadas': len(items_extraidos),
            'lineas_crudas': lineas_texto_completas,
            'posible_duplicada': posible_duplicada,
            'metodo_pago': metodo_pago_detectado
        }
    }
