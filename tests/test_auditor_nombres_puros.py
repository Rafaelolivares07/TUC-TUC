# -*- coding: utf-8 -*-
"""Auditor: nombres de tipo y numeros puros, sin slug (10/11).

Caso Rafa: al abrir /auditor-documentos con consulta externa
(?tipo_documento=RELACION DE DESEMBOLSOS&documento_numero=GASTO_DE_ENTREGAS-11)
la pantalla mostraba el codigo interno GASTO_DE_ENTREGAS (slug disenado por un
agente) y el numero concatenado. Ahora se ven: nombre vigente del tipo (si el
usuario lo renombra, ese sale), consecutivo/numero puro, y la URL queda limpia.
El valor crudo solo viaja al backend para localizar el documento.
Uso: python tests/test_auditor_nombres_puros.py (raiz TucTucV2)
"""
import os
import re
import subprocess
import sys
import tempfile

fails = []
total = [0]


def check(nombre, cond, extra=''):
    total[0] += 1
    print(('PASS ' if cond else 'FAIL ') + nombre + (f' [{extra}]' if extra and not cond else ''))
    if not cond:
        fails.append(nombre)


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = open(os.path.join(ROOT, 'app', 'blueprints', 'inventarios.py'), encoding='utf-8').read()
TPL = open(os.path.join(ROOT, 'templates', 'auditor_documentos.html'), encoding='utf-8').read()
MAN = open(os.path.join(ROOT, 'templates', 'mantenimiento_admin.html'), encoding='utf-8').read()
KDX = open(os.path.join(ROOT, 'templates', 'partials', 'kardex_js.html'), encoding='utf-8').read()

# 1. Backend: nombre puro del tipo (el vigente, renombres incluidos)
check('helper _nombre_tipo_doc', 'def _nombre_tipo_doc(' in PY)
_a0 = PY.find('def api_mantenimiento_documentos_tercero(')
_a1 = PY.find('def _num_documento_limpio(')
check('tercero resuelve nombre puro', _a0 >= 0 and '_nombre_tipo_doc(' in PY[_a0:_a1])
_b0 = PY.find('def api_mantenimiento_documentos_recientes(')
_b1 = PY.find('def api_mantenimiento_tipos_documentos(')
check('recientes resuelve nombre puro', _b0 >= 0 and '_nombre_tipo_doc(' in PY[_b0:_b1])

# 2. Backend: auditar expone numero puro y localiza con el
_c0 = PY.find('def api_auditar_documento(')
_c1 = PY.find('def api_anular_documento(')
_aud = PY[_c0:_c1] if _c0 >= 0 and _c1 > _c0 else ''
check('auditar responde documento_numero_puro', "'documento_numero_puro'" in _aud)
check('auditar calcula puro con codigo del tipo', '_num_documento_limpio(num_doc' in _aud)
check('variantes puro->prefijo codigo', 'f"{tipo_doc_codigo}-{_v}"' in _aud)
check('variantes puro->prefijo nombre', 'f"{tipo_doc_nombre}-{_v}"' in _aud)

# 3. Frontend: helpers puros
check('existe numDocPuro', 'function numDocPuro(' in TPL)
check('existe nombreTipoPuro', 'function nombreTipoPuro(' in TPL)
check('existe seleccionarTipoExterno', 'function seleccionarTipoExterno(' in TPL)
check('existe limpiarUrlAuditor', 'function limpiarUrlAuditor(' in TPL)

# 4. Frontend: tabla muestra puro, boton manda crudo
check('fila prefiere numero puro',
      'const numDoc = doc.documento_numero || numDocPuro(numDocRaw);' in TPL)
check('boton Auditar manda crudo + id',
      "auditarDocumentoDirecto('${tipoParam}', '${numDocRaw}'" in TPL)
check('fila tipo sin slug', 'nombreTipoPuro(doc.tipo_documento)' in TPL)
check('combo expone codigo', 'data-codigo="${t.codigo' in TPL)

# 5. Frontend: detalle + init con consulta externa
check('header numero puro', 'd.documento_numero_puro || numDocPuro(numero)' in TPL)
check('header tipo puro', 'nombreTipoPuro(detTipoRaw)' in TPL)
check('init purifica qNum', 'const qNumPuro = numDocPuro(qNum);' in TPL)
check('init empareja tipo externo', 'seleccionarTipoExterno(qTipo);' in TPL)
check('init limpia URL', 'limpiarUrlAuditor(qNumPuro);' in TPL)

# 6. node --check del JS (neutralizando Jinja)
try:
    ini = TPL.index('<script>') + len('<script>')
    fin = TPL.rindex('</script>')
    js = TPL[ini:fin].replace('{{ negocio_id }}', '59')
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(js)
        tmp = f.name
    r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True, timeout=60)
    os.unlink(tmp)
    check('node --check JS', r.returncode == 0, (r.stderr or '')[:200])
except Exception as e:
    check('node --check JS', False, f'{type(e).__name__}: {e}')

# 7. Funcional: purificadores sobre el caso Rafa
try:
    ini = TPL.index('function numDocPuro(')
    fin = TPL.index('// Marca en el combo', ini)
    runner = TPL[ini:fin] + """
const casos = [
  ['N', 'GASTO_DE_ENTREGAS-11', '11'],
  ['N', 'VENTA_POS-36', '36'],
  ['N', '0042', '42'],
  ['N', '11', '11'],
  ['T', 'GASTO_DE_ENTREGAS', 'GASTO DE ENTREGAS'],
  ['T', 'RELACION DE DESEMBOLSOS', 'RELACION DE DESEMBOLSOS']
];
for (const [fn, arg, esp] of casos) {
  const got = fn === 'N' ? numDocPuro(arg) : nombreTipoPuro(arg);
  console.log((got === esp ? 'PASS' : 'FAIL') + '|' + fn + '|' + arg + '|' + got);
}
"""
    with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
        f.write(runner)
        tmp = f.name
    r = subprocess.run(['node', tmp], capture_output=True, text=True, timeout=60)
    os.unlink(tmp)
    lineas = [l for l in (r.stdout or '').splitlines() if l.startswith(('PASS|', 'FAIL|'))]
    check('6 casos funcionales', len(lineas) == 6, f'salida={r.stdout[:200]!r} err={r.stderr[:200]!r}')
    for l in lineas:
        ok, fn, arg, got = l.split('|')
        check(f'{"num" if fn == "N" else "tipo"} {arg} -> {got}', ok == 'PASS')
except Exception as e:
    check('harness funcional', False, f'{type(e).__name__}: {e}')

# 8. Ronda 2: badge contable + fisico puros, confirms puros, herramienta vieja
check('badge comprobante puro',
      "'numero_comprobante': _num_documento_limpio(comp_row['numero_comprobante']" in _aud)
check('documento_fisico puro', "'documento_fisico': num_doc_puro" in _aud)
check('estado guarda numeroPuro', 'numeroPuro: detNumStr' in TPL)
check('estado guarda tipoPuro', 'tipoPuro: detTipoStr' in TPL)
check('confirms usan puro', TPL.count('numeroPuro || numero') == 2)
check('vieja etiqueta pura', 'd.documento_numero_puro || numero' in MAN)

# 9. Ronda 3: tipo + numero juntos en una linea (tipo izquierda, numero derecha)
check('thead Documento', '>Documento</th>' in TPL)
check('sin col Consecutivo', '>Consecutivo</th>' not in TPL)
check('fila junta badge+numero', '${typeStr}</span> <span class="font-mono' in TPL)
# Ronda D/C (10/11): Monto Total se partió en Débito+Crédito -> 7 columnas
check('colspans 7', TPL.count('colspan="7"') == 4)
check('sin colspan 6', 'colspan="6"' not in TPL)
check('header junto', '`${detTipoStr} ${detNumStr}`' in TPL)
check('badge tipo oculto', "getElementById('det-doc-tipo-badge').classList.add('hidden')" in TPL)
check('confirms con tipo', TPL.count('"${tipoPuro} ${numeroPuro || numero}"') == 2)
check('vieja theads Documento', MAN.count('>Documento</th>') == 2)
check('vieja main junta', '${typeStr}</span> <span class="font-mono' in MAN)
check('vieja hist junta', '${doc.tipo_documento.toUpperCase()}</span> <span class="font-mono' in MAN)
check('vieja etiqueta espacio', '${d.tipo_documento || tipo} ${d.documento_numero_puro || numero}' in MAN)
check('vieja spans 7+5', MAN.count('colspan="7"') == 4 and MAN.count('colspan="5"') == 2)
check('kardex una linea', 'text-[11px] flex items-center gap-1">` +' in KDX)
check('kardex prettify', "docColTipo.replace(/_/g, ' ')" in KDX)
check('kardex titulo puro', 'title="Auditar documento ${docColTipo} ${docColNum}' in KDX)
check('kardex sin apilado', '${docColTipo}</div>`' not in KDX)
check('tarjeta badge junto', '`${detTipoStr} ${d.contabilidad.numero_comprobante || detNumStr}`' in TPL)
check('tarjeta concepto condicional', 'ccDesc.toLowerCase() !== detTipoStr.toLowerCase()' in TPL)
check('tarjeta vieja badge junto', '`${ccTipoTxt} ${ccNumTxt}`' in MAN)
check('tarjeta vieja concepto condicional', 'ccDesc.toLowerCase() !== ccTipoTxt.toLowerCase()' in MAN)

# 10. node --check del parcial kardex (fragmento sin <script>) y herramienta vieja
for _nombre, _src, _frag in [('kardex', KDX, True), ('vieja', MAN, False)]:
    try:
        if _frag:
            js = _src
        else:
            _blocks = re.findall(r'<script>(.*?)</script>', _src, re.S)
            js = '\n;\n'.join(_blocks)
        js = re.sub(r'\{\{.*?\}\}', '0', js)
        js = re.sub(r'\{%.*?%\}', '', js)
        with tempfile.NamedTemporaryFile('w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(js)
            tmp = f.name
        r = subprocess.run(['node', '--check', tmp], capture_output=True, text=True, timeout=90)
        os.unlink(tmp)
        check(f'node {_nombre}', r.returncode == 0, (r.stderr or '')[:200])
    except Exception as e:
        check(f'node {_nombre}', False, f'{type(e).__name__}: {e}')

# 11. Deep-link tercero: id exacto + historial con saldos (caso Rafa 10/11)
_d0 = PY.find('def api_buscar_terceros(')
_d1 = PY.find('/api/inventario/proveedores/crear', _d0)
check('buscar resuelve id exacto', _d0 >= 0 and 'q.isdigit()' in PY[_d0:_d1])
check('init tercero exacto sin adivinar', '.find(x => String(x.id)' in TPL and '|| dT[0]' not in TPL)
check('historial incluye saldos', _a0 >= 0 and "'origen': 'saldos'" in PY[_a0:_a1])

print(f'--- {total[0] - len(fails)}/{total[0]} ---')
sys.exit(1 if fails else 0)
