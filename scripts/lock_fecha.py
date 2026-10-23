path = 'C:/Users/RAFAEL OLIVARES/Documents/TucTucV2/templates/inventario_admin.html'
with open(path, 'rb') as f:
    raw = f.read()

# Let's decode as utf-8
text = raw.decode('utf-8')
target = '''            <label class="block text-sm font-bold text-slate-600 uppercase tracking-wide mb-1.5">Fecha documento</label>
            <input id="prod-fecha" type="date" class="w-full border-2 border-slate-200 rounded-xl px-3.5 py-2.5 text-sm sm:text-base bg-white font-semibold text-slate-800 outline-none focus:border-rose-500 focus:ring-2 focus:ring-rose-100 transition">'''

replacement = '''            <label class="block text-sm font-bold text-slate-600 uppercase tracking-wide mb-1.5">Fecha documento</label>
            <input id="prod-fecha" type="date" readonly class="w-full border-2 border-slate-200 rounded-xl px-3.5 py-2.5 text-sm sm:text-base bg-slate-100 font-semibold text-slate-700 outline-none cursor-not-allowed" title="Solo fecha actual">
            <p class="mt-1 text-xs text-slate-500 font-medium">🔒 Registrado con fecha actual (no modificable)</p>'''

# Normalize newlines
text_norm = text.replace('\r\n', '\n')
if target in text_norm:
    # Also remove the aviso-prod-reemplazo
    aviso_block = '''            <div id="aviso-prod-reemplazo" class="hidden mt-1.5 text-xs font-bold text-amber-900 bg-amber-50 border border-amber-300 rounded-xl p-2 cursor-pointer hover:bg-amber-100 transition shadow-xs flex items-center justify-between" onclick="aplicarFechaProduccionReemplazo()">
              <span>💡 Reemplazo de producción: Clic para aplicar fecha original (<b id="aviso-prod-reemplazo-fecha"></b>)</span>
              <span class="text-xs bg-amber-200 text-amber-900 px-2 py-0.5 rounded-lg shrink-0">Usar</span>
            </div>'''
    text_norm = text_norm.replace(target, replacement, 1)
    if aviso_block in text_norm:
        text_norm = text_norm.replace(aviso_block, '')
        print('Aviso block removed')
    else:
        print('Aviso block not matched exactly')
    
    with open(path, 'wb') as f:
        f.write(text_norm.replace('\n', '\r\n').encode('utf-8'))
    print('SUCCESS: prod-fecha locked')
else:
    print('Target not found')
