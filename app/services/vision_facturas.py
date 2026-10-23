# -*- coding: utf-8 -*-
"""
Servicio de Visión por Computadora e Inteligencia Artificial Local para Facturas y Tirillas.
100% autohospedado en el servidor - Sin APIs externas ni costos por imagen.
"""

import os
import re
import cv2
import difflib

_ocr_engine = None

def get_ocr_engine():
    global _ocr_engine
    if _ocr_engine is None:
        from rapidocr_onnxruntime import RapidOCR
        _ocr_engine = RapidOCR()
    return _ocr_engine


def preprocesar_imagen(ruta_origen):
    """
    Mejora contraste, elimina sombras y ajusta resolución para lectura óptima.
    """
    try:
        img = cv2.imread(ruta_origen)
        if img is None:
            return ruta_origen

        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape
        max_dim = 1800
        if max(h, w) > max_dim:
            scale = max_dim / float(max(h, w))
            gray = cv2.resize(gray, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)

        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        contrast_enhanced = clahe.apply(gray)

        ruta_opt = ruta_origen + ".opt.png"
        cv2.imwrite(ruta_opt, contrast_enhanced)
        return ruta_opt
    except Exception as e:
        print(f"Aviso: error en preprocesamiento OpenCV ({e}), usando imagen original.")
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


def agrupar_en_filas_horizontales(bloques, umbral_y=16):
    """Agrupa bloques de texto que pertenecen a la misma línea horizontal en la factura."""
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


def extraer_datos_factura(ruta_imagen, conn=None, negocio_id=None):
    """
    Ejecuta el pipeline de visión y extrae:
    - Proveedor sugerido (cruzado con tabla terceros)
    - Número de factura
    - Fecha
    - Total de la factura
    - Líneas de productos con sugerencias del catálogo
    """
    engine = get_ocr_engine()
    ruta_proc = preprocesar_imagen(ruta_imagen)
    
    try:
        result, elapse_list = engine(ruta_proc)
    finally:
        if ruta_proc != ruta_imagen and os.path.exists(ruta_proc):
            try: os.remove(ruta_proc)
            except: pass

    if not result:
        return {
            'ok': False,
            'error': 'No se detectó texto en la imagen. Asegúrate de que la foto tenga buena iluminación.'
        }

    bloques = []
    for item in result:
        box, text, score = item
        if not text or score < 0.40:
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

    # Reconstruir en filas horizontales de lectura
    filas = agrupar_en_filas_horizontales(bloques)
    lineas_texto_completas = [" ".join(b['texto'] for b in f) for f in filas]

    # 1. FECHA
    fecha_detectada = None
    for l_txt in lineas_texto_completas:
        m1 = re.search(r'(\d{1,2})[/.-](\d{1,2})[/.-](\d{2,4})', l_txt)
        if m1:
            d, m, y = m1.group(1), m1.group(2), m1.group(3)
            if len(y) == 2: y = "20" + y
            if int(m) <= 12 and int(d) <= 31:
                fecha_detectada = f"{y}-{int(m):02d}-{int(d):02d}"
                break
        m2 = re.search(r'(\d{4})[/.-](\d{1,2})[/.-](\d{1,2})', l_txt)
        if m2:
            y, m, d = m2.group(1), m2.group(2), m2.group(3)
            if int(m) <= 12 and int(d) <= 31:
                fecha_detectada = f"{y}-{int(m):02d}-{int(d):02d}"
                break

    # 2. NÚMERO DE DOCUMENTO
    num_doc_detectado = ""
    patrones_doc = [
        r'(?:FAC|FACTURA|FACT|TICKET|COMPROBANTE|DOC|REMISION|No\.?|N°)\s*[:#-]?\s*([A-Za-z0-9-]+)',
        r'#\s*([0-9]{3,})',
        r'(?:FAC|FE|POS)\s*([0-9]{3,})'
    ]
    for l_txt in lineas_texto_completas:
        for pat in patrones_doc:
            m = re.search(pat, l_txt, re.IGNORECASE)
            if m:
                cand = m.group(1).strip()
                if len(cand) >= 2 and not cand.lower() in ('de', 'del', 'la', 'venta', 'electronica', 'turno'):
                    num_doc_detectado = cand
                    break
        if num_doc_detectado:
            break

    # 3. TOTAL FACTURA
    total_factura = 0.0
    for i, fila in enumerate(filas):
        texto_fila = " ".join(b['texto'] for b in fila).upper()
        if "TOTAL" in texto_fila and not any(k in texto_fila for k in ["VENTAS", "TRANSACCIONES", "SUBTOTAL", "UNIDADES"]):
            # Buscar en esta fila y en las 2 siguientes
            filas_candidatas = [fila] + filas[i+1:min(i+3, len(filas))]
            for fc in filas_candidatas:
                for b in reversed(fc): # El monto suele estar a la derecha
                    m_din = re.search(r'\$?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)', b['texto'])
                    if m_din:
                        val = _limpiar_monto(m_din.group(1))
                        if val > 100:
                            total_factura = max(total_factura, val)

    # 4. PROVEEDOR (Cruce con tabla terceros)
    proveedor_id = None
    proveedor_nombre = ""
    terceros_db = []
    if conn:
        try:
            t_rows = conn.execute("SELECT id, nombre, tipo_tercero FROM terceros ORDER BY id ASC").fetchall()
            terceros_db = [dict(r) for r in t_rows]
        except Exception as e:
            print("Aviso terceros:", e)

    mejores_coincidencias = []
    for l_txt in lineas_texto_completas[:8]:
        txt_clean = re.sub(r'[^a-zA-Z0-9\s]', '', l_txt).strip().upper()
        if len(txt_clean) < 3: continue
        for terc in terceros_db:
            nom_terc = re.sub(r'[^a-zA-Z0-9\s]', '', terc['nombre']).strip().upper()
            ratio = difflib.SequenceMatcher(None, txt_clean, nom_terc).ratio()
            if nom_terc in txt_clean or txt_clean in nom_terc:
                ratio = max(ratio, 0.85)
            if ratio > 0.60:
                mejores_coincidencias.append((ratio, terc['id'], terc['nombre']))

    if mejores_coincidencias:
        mejores_coincidencias.sort(key=lambda x: x[0], reverse=True)
        proveedor_id = mejores_coincidencias[0][1]
        proveedor_nombre = mejores_coincidencias[0][2]
    else:
        for l in lineas_texto_completas[:4]:
            if len(l) > 3 and not any(p in l.upper() for p in ['FACTURA', 'TICKET', 'RESUMEN', 'NIT', 'FECHA']):
                proveedor_nombre = l
                break

    # 5. CATÁLOGO DE PRODUCTOS
    productos_db = []
    if conn and negocio_id:
        try:
            p_rows = conn.execute("""
                SELECT id, nombre, costo, precio, iva_pct
                FROM productos
                WHERE negocio_id = %s
                ORDER BY nombre ASC
            """, (negocio_id,)).fetchall()
            productos_db = [dict(r) for r in p_rows]
        except Exception as e:
            print("Aviso productos:", e)

    # 6. ÍTEMS DETECTADOS (Fila por fila)
    items_extraidos = []
    for fila in filas:
        texto_fila = " ".join(b['texto'] for b in fila).strip()
        # Detectar patrón de cantidad y producto
        # Ej: "17X SANDWICH POLLO TOCINETA $170.000"
        m_it = re.match(r'^(\d+(?:[.,]\d+)?)\s*(?:[xX*]|UND|KG|GR|PAQ)?\s+(.+)$', texto_fila)
        if m_it:
            cant_str = m_it.group(1).replace(',', '.')
            try: cant = float(cant_str)
            except: cant = 1.0
            resto = m_it.group(2).strip()
            
            # Extraer precio de la derecha de la fila si existe
            precio_linea = 0.0
            for b in reversed(fila):
                m_p = re.search(r'\$?\s*([0-9]{1,3}(?:[.,][0-9]{3})*(?:[.,][0-9]{2})?)', b['texto'])
                if m_p:
                    p_val = _limpiar_monto(m_p.group(1))
                    if p_val > 0 and p_val != cant:
                        precio_linea = p_val
                        break
            
            # Limpiar nombre del ítem quitándole el precio si estaba pegado
            nom_it = re.sub(r'\$?\s*[0-9]{1,3}(?:[.,][0-9]{3})*.*$', '', resto).strip()
            if not nom_it: nom_it = resto

            # Cruzar con catálogo de productos
            mejor_prod = None
            mejor_score = 0.0
            nom_upper = nom_it.upper()
            for p in productos_db:
                p_nom = p['nombre'].upper()
                score = difflib.SequenceMatcher(None, nom_upper, p_nom).ratio()
                if p_nom in nom_upper or nom_upper in p_nom:
                    score = max(score, 0.80)
                if score > mejor_score and score >= 0.45:
                    mejor_score = score
                    mejor_prod = p

            vu_calc = round(precio_linea / cant, 2) if (cant > 0 and precio_linea > 0) else 0.0
            item_data = {
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
    }
