/**
 * TucTuc POS / ERP - Calculadora Flotante con Copiado al Portapapeles
 * Botones grandes (200%), pantalla clara y copiado directo de resultados.
 */

(function () {
  let calcState = {
    expr: '',
    current: '0',
    history: [],
    abierta: false,
    minimizada: false,
    drag: { active: false, currentX: 0, currentY: 0, initialX: 0, initialY: 0, xOffset: 0, yOffset: 0 }
  };

  // Cargar historial previo de la sesión
  try {
    const savedHist = sessionStorage.getItem('tuctuc_calc_hist');
    if (savedHist) calcState.history = JSON.parse(savedHist);
  } catch (e) {}

  function ensureWidgetDom() {
    if (document.getElementById('tuctuc-calculadora-container')) return;

    const div = document.createElement('div');
    div.id = 'tuctuc-calculadora-container';
    div.innerHTML = `
      <!-- Widget Flotante de Calculadora (Botones y Fuente 200%) -->
      <div id="tuctuc-calc-widget" 
           class="fixed z-[99999] hidden select-none transition-shadow"
           style="bottom: 24px; right: 24px; width: 380px; max-width: 95vw; font-family: 'Inter', system-ui, sans-serif;">
        
        <div class="bg-white/95 backdrop-blur-md rounded-3xl shadow-2xl border border-gray-200/90 overflow-hidden flex flex-col text-gray-800">
          
          <!-- Barra Superior / Header Arrastrable -->
          <div id="tuctuc-calc-header" 
               class="bg-gradient-to-r from-slate-900 to-indigo-950 text-white px-4 py-3 flex items-center justify-between cursor-move shadow-xs">
            <div class="flex items-center gap-2.5 min-w-0">
              <span class="text-base">🧮</span>
              <span class="font-extrabold text-sm tracking-wide truncate">Calculadora</span>
              <span class="text-[10px] bg-indigo-500/40 text-indigo-200 px-2 py-0.5 rounded-full font-mono font-bold">TucTuc</span>
            </div>
            <div class="flex items-center gap-1 shrink-0">
              <button type="button" onclick="window.toggleHistorialCalculadora()" 
                      class="text-gray-300 hover:text-white p-1.5 rounded-xl hover:bg-white/10 text-sm transition" title="Ver Historial de Cálculos">
                📜
              </button>
              <button type="button" onclick="window.minimizarCalculadoraFlotante()" 
                      class="text-gray-300 hover:text-white p-1.5 rounded-xl hover:bg-white/10 text-sm transition" title="Minimizar">
                ─
              </button>
              <button type="button" onclick="window.cerrarCalculadoraFlotante()" 
                      class="text-gray-300 hover:text-rose-400 p-1.5 rounded-xl hover:bg-white/10 text-base leading-none transition" title="Cerrar">
                &times;
              </button>
            </div>
          </div>

          <!-- Panel de Visualización / Display Grande -->
          <div class="bg-slate-50/90 p-4 border-b border-gray-200/80 flex flex-col items-end justify-center min-h-[90px]">
            <div id="tuctuc-calc-expr" class="text-xs sm:text-sm font-mono text-gray-400 truncate w-full text-right h-5"></div>
            <div class="flex items-center justify-between w-full mt-1 gap-2.5">
              <button type="button" onclick="window.copiarResultadoCalculadora()"
                      id="tuctuc-calc-btn-copy"
                      class="px-2.5 py-1.5 bg-emerald-50 hover:bg-emerald-100 text-emerald-700 border border-emerald-200 rounded-xl text-xs font-bold flex items-center gap-1.5 transition shadow-2xs active:scale-95 cursor-pointer shrink-0"
                      title="Copiar este resultado al portapapeles para pegarlo en cualquier campo">
                <span>📋</span> <span id="tuctuc-calc-copy-lbl">Copiar</span>
              </button>
              <div id="tuctuc-calc-display" class="text-3xl sm:text-4xl font-mono font-black text-gray-900 tracking-tight truncate text-right flex-1">0</div>
            </div>
          </div>

          <!-- Historial Plegable -->
          <div id="tuctuc-calc-hist-panel" class="hidden bg-slate-900 text-white p-3.5 max-h-52 overflow-y-auto custom-scrollbar border-b border-gray-800 text-xs space-y-1.5">
            <div class="flex items-center justify-between text-[11px] text-gray-400 font-bold uppercase tracking-wider pb-1 border-b border-gray-800">
              <span>Historial Reciente</span>
              <button type="button" onclick="window.limpiarHistorialCalculadora()" class="text-rose-400 hover:text-rose-300">Borrar</button>
            </div>
            <div id="tuctuc-calc-hist-items" class="space-y-1">
              <!-- Render Dinámico -->
            </div>
          </div>

          <!-- Teclado Numérico y Operaciones (Botones Grandes 200%) -->
          <div class="p-3 grid grid-cols-4 gap-2 text-xl sm:text-2xl font-black bg-white">
            <button type="button" onclick="window.calcClearAll()" class="py-3.5 sm:py-4 rounded-2xl bg-rose-50 text-rose-700 hover:bg-rose-100 transition active:scale-95 border border-rose-100 flex items-center justify-center font-black">C</button>
            <button type="button" onclick="window.calcBackspace()" class="py-3.5 sm:py-4 rounded-2xl bg-gray-100 text-gray-700 hover:bg-gray-200 transition active:scale-95 flex items-center justify-center font-bold text-xl">⌫</button>
            <button type="button" onclick="window.calcInput('%')" class="py-3.5 sm:py-4 rounded-2xl bg-gray-100 text-gray-700 hover:bg-gray-200 transition active:scale-95 flex items-center justify-center font-bold">%</button>
            <button type="button" onclick="window.calcInput('/')" class="py-3.5 sm:py-4 rounded-2xl bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition active:scale-95 border border-indigo-100 flex items-center justify-center font-black text-2xl">÷</button>

            <button type="button" onclick="window.calcInput('7')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">7</button>
            <button type="button" onclick="window.calcInput('8')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">8</button>
            <button type="button" onclick="window.calcInput('9')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">9</button>
            <button type="button" onclick="window.calcInput('*')" class="py-3.5 sm:py-4 rounded-2xl bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition active:scale-95 border border-indigo-100 flex items-center justify-center font-black text-2xl">×</button>

            <button type="button" onclick="window.calcInput('4')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">4</button>
            <button type="button" onclick="window.calcInput('5')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">5</button>
            <button type="button" onclick="window.calcInput('6')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">6</button>
            <button type="button" onclick="window.calcInput('-')" class="py-3.5 sm:py-4 rounded-2xl bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition active:scale-95 border border-indigo-100 flex items-center justify-center font-black text-2xl">−</button>

            <button type="button" onclick="window.calcInput('1')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">1</button>
            <button type="button" onclick="window.calcInput('2')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">2</button>
            <button type="button" onclick="window.calcInput('3')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">3</button>
            <button type="button" onclick="window.calcInput('+')" class="py-3.5 sm:py-4 rounded-2xl bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition active:scale-95 border border-indigo-100 flex items-center justify-center font-black text-2xl">+</button>

            <button type="button" onclick="window.calcToggleSign()" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-bold text-xl">±</button>
            <button type="button" onclick="window.calcInput('0')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">0</button>
            <button type="button" onclick="window.calcInput('.')" class="py-3.5 sm:py-4 rounded-2xl bg-slate-50 text-gray-800 hover:bg-slate-100 transition active:scale-95 border border-gray-150 flex items-center justify-center font-black">.</button>
            <button type="button" onclick="window.calcEquals()" class="py-3.5 sm:py-4 rounded-2xl bg-emerald-600 hover:bg-emerald-700 text-white font-black transition active:scale-95 shadow-md flex items-center justify-center text-3xl">=</button>
          </div>

        </div>
      </div>

      <!-- Mini Botón Flotante Acoplado (Cuando se minimiza) -->
      <div id="tuctuc-calc-min-badge" 
           onclick="window.abrirCalculadoraFlotante()"
           class="fixed bottom-6 right-6 z-[99998] hidden bg-gradient-to-r from-slate-900 to-indigo-900 text-white px-4 py-2.5 rounded-2xl shadow-xl border border-white/20 flex items-center gap-2 cursor-pointer hover:scale-105 active:scale-95 transition-all select-none">
        <span class="text-lg">🧮</span>
        <span class="font-extrabold text-xs">Calculadora</span>
        <span id="tuctuc-calc-min-val" class="font-mono text-emerald-400 text-sm font-black">0</span>
      </div>
    `;
    document.body.appendChild(div);
    initDrag();
  }

  function updateDisplay() {
    const elDisp = document.getElementById('tuctuc-calc-display');
    const elExpr = document.getElementById('tuctuc-calc-expr');
    const elMinVal = document.getElementById('tuctuc-calc-min-val');
    
    if (elDisp) {
      let val = calcState.current;
      if (val === '' || val === undefined) val = '0';
      elDisp.textContent = val;
    }
    if (elExpr) {
      elExpr.textContent = calcState.expr || '';
    }
    if (elMinVal) {
      elMinVal.textContent = calcState.current || '0';
    }
  }

  window.abrirCalculadoraFlotante = function () {
    ensureWidgetDom();
    const w = document.getElementById('tuctuc-calc-widget');
    const min = document.getElementById('tuctuc-calc-min-badge');
    if (w) w.classList.remove('hidden');
    if (min) min.classList.add('hidden');
    calcState.abierta = true;
    calcState.minimizada = false;
    updateDisplay();
  };

  window.cerrarCalculadoraFlotante = function () {
    const w = document.getElementById('tuctuc-calc-widget');
    const min = document.getElementById('tuctuc-calc-min-badge');
    if (w) w.classList.add('hidden');
    if (min) min.classList.add('hidden');
    calcState.abierta = false;
    calcState.minimizada = false;
  };

  window.minimizarCalculadoraFlotante = function () {
    const w = document.getElementById('tuctuc-calc-widget');
    const min = document.getElementById('tuctuc-calc-min-badge');
    if (w) w.classList.add('hidden');
    if (min) min.classList.remove('hidden');
    calcState.minimizada = true;
  };

  window.toggleCalculadoraFlotante = function () {
    if (calcState.abierta && !calcState.minimizada) {
      window.cerrarCalculadoraFlotante();
    } else {
      window.abrirCalculadoraFlotante();
    }
  };

  window.calcInput = function (char) {
    if (calcState.current === '0' && !isNaN(char) && char !== '.') {
      calcState.current = char;
    } else if (['+', '-', '*', '/', '%'].includes(char)) {
      if (calcState.current !== '') {
        calcState.expr += (calcState.expr ? ' ' : '') + calcState.current + ' ' + char;
        calcState.current = '0';
      }
    } else if (char === '.') {
      if (!calcState.current.includes('.')) {
        calcState.current += '.';
      }
    } else {
      calcState.current += char;
    }
    updateDisplay();
  };

  window.calcClearAll = function () {
    calcState.expr = '';
    calcState.current = '0';
    updateDisplay();
  };

  window.calcBackspace = function () {
    if (calcState.current.length > 1) {
      calcState.current = calcState.current.slice(0, -1);
    } else {
      calcState.current = '0';
    }
    updateDisplay();
  };

  window.calcToggleSign = function () {
    if (calcState.current && calcState.current !== '0') {
      if (calcState.current.startsWith('-')) {
        calcState.current = calcState.current.slice(1);
      } else {
        calcState.current = '-' + calcState.current;
      }
      updateDisplay();
    }
  };

  window.calcEquals = function () {
    try {
      let fullExpr = (calcState.expr + ' ' + (calcState.current || '0')).trim();
      if (!fullExpr) return;

      let sanitized = fullExpr.replace(/×/g, '*').replace(/÷/g, '/');
      sanitized = sanitized.replace(/([0-9.]+)\s*\+\s*([0-9.]+)%/g, '($1 * (1 + $2/100))');
      sanitized = sanitized.replace(/([0-9.]+)\s*-\s*([0-9.]+)%/g, '($1 * (1 - $2/100))');
      sanitized = sanitized.replace(/([0-9.]+)%/g, '($1/100)');

      const res = Function(`'use strict'; return (${sanitized})`)();
      const numRes = typeof res === 'number' ? Math.round(res * 10000) / 10000 : res;

      calcState.history.unshift({
        expr: fullExpr,
        res: String(numRes),
        ts: new Date().toLocaleTimeString('es-CO', { hour: '2-digit', minute: '2-digit' })
      });
      calcState.history = calcState.history.slice(0, 15);
      try {
        sessionStorage.setItem('tuctuc_calc_hist', JSON.stringify(calcState.history));
      } catch (e) {}

      calcState.expr = fullExpr + ' =';
      calcState.current = String(numRes);
      updateDisplay();
      renderHistorial();
    } catch (err) {
      calcState.current = 'Error';
      updateDisplay();
    }
  };

  window.copiarResultadoCalculadora = function (valorCustom) {
    const val = valorCustom !== undefined ? String(valorCustom) : calcState.current;
    if (!val || val === 'Error') return;

    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(val).then(() => mostrarFeedbackCopiado(val)).catch(() => fallbackCopy(val));
    } else {
      fallbackCopy(val);
    }
  };

  function fallbackCopy(text) {
    const textArea = document.createElement("textarea");
    textArea.value = text;
    textArea.style.position = "fixed";
    textArea.style.left = "-999999px";
    document.body.appendChild(textArea);
    textArea.focus();
    textArea.select();
    try {
      document.execCommand('copy');
      mostrarFeedbackCopiado(text);
    } catch (err) {}
    document.body.removeChild(textArea);
  }

  function mostrarFeedbackCopiado(val) {
    const lbl = document.getElementById('tuctuc-calc-copy-lbl');
    const btn = document.getElementById('tuctuc-calc-btn-copy');
    if (lbl && btn) {
      const origText = lbl.textContent;
      lbl.textContent = '¡Copiado!';
      btn.classList.remove('bg-emerald-50', 'text-emerald-700');
      btn.classList.add('bg-emerald-600', 'text-white');
      setTimeout(() => {
        lbl.textContent = origText;
        btn.classList.remove('bg-emerald-600', 'text-white');
        btn.classList.add('bg-emerald-50', 'text-emerald-700');
      }, 1500);
    }

    if (typeof window.toast === 'function') {
      window.toast(`📋 Copiado al portapapeles: ${val}`);
    }
  }

  window.toggleHistorialCalculadora = function () {
    const panel = document.getElementById('tuctuc-calc-hist-panel');
    if (panel) {
      panel.classList.toggle('hidden');
      renderHistorial();
    }
  };

  window.limpiarHistorialCalculadora = function () {
    calcState.history = [];
    try {
      sessionStorage.removeItem('tuctuc_calc_hist');
    } catch (e) {}
    renderHistorial();
  };

  function renderHistorial() {
    const cont = document.getElementById('tuctuc-calc-hist-items');
    if (!cont) return;

    if (!calcState.history.length) {
      cont.innerHTML = `<div class="text-center text-gray-500 py-2 italic text-[11px]">Sin cálculos recientes</div>`;
      return;
    }

    cont.innerHTML = calcState.history.map((h, idx) => `
      <div class="flex items-center justify-between p-2 rounded-xl hover:bg-slate-800 transition cursor-pointer group"
           onclick="window.usarHistorialItem('${h.res}')"
           title="Clic para cargar resultado en pantalla">
        <div class="min-w-0 flex-1">
          <span class="text-gray-400 block text-[11px] truncate">${h.expr}</span>
          <span class="font-mono font-bold text-emerald-400 text-sm">${h.res}</span>
        </div>
        <button type="button" onclick="event.stopPropagation(); window.copiarResultadoCalculadora('${h.res}')" 
                class="opacity-0 group-hover:opacity-100 bg-slate-700 hover:bg-slate-600 text-white px-2.5 py-1 rounded-lg text-xs font-bold transition cursor-pointer"
                title="Copiar solo este número">
          📋 Copiar
        </button>
      </div>
    `).join('');
  }

  window.usarHistorialItem = function (val) {
    calcState.current = String(val);
    calcState.expr = '';
    updateDisplay();
  };

  // ── Drag & Drop de la Ventana Flotante ─────────────────────────────────────
  function initDrag() {
    const header = document.getElementById('tuctuc-calc-header');
    const widget = document.getElementById('tuctuc-calc-widget');
    if (!header || !widget) return;

    let isDragging = false;
    let startX = 0, startY = 0;

    header.addEventListener('mousedown', dragStart);
    header.addEventListener('touchstart', dragStart, { passive: false });

    function dragStart(e) {
      if (e.target.tagName === 'BUTTON' || e.target.closest('button')) return;
      isDragging = true;
      const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
      const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;

      const rect = widget.getBoundingClientRect();
      startX = clientX - rect.left;
      startY = clientY - rect.top;

      document.addEventListener('mousemove', drag);
      document.addEventListener('touchmove', drag, { passive: false });
      document.addEventListener('mouseup', dragEnd);
      document.addEventListener('touchend', dragEnd);
    }

    function drag(e) {
      if (!isDragging) return;
      if (e.cancelable) e.preventDefault();
      const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
      const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;

      let newLeft = clientX - startX;
      let newTop = clientY - startY;

      newLeft = Math.max(10, Math.min(window.innerWidth - widget.offsetWidth - 10, newLeft));
      newTop = Math.max(10, Math.min(window.innerHeight - widget.offsetHeight - 10, newTop));

      widget.style.left = newLeft + 'px';
      widget.style.top = newTop + 'px';
      widget.style.bottom = 'auto';
      widget.style.right = 'auto';
    }

    function dragEnd() {
      isDragging = false;
      document.removeEventListener('mousemove', drag);
      document.removeEventListener('touchmove', drag);
      document.removeEventListener('mouseup', dragEnd);
      document.removeEventListener('touchend', dragEnd);
    }
  }

  // Atajo de teclado global (F4 o Alt+C para abrir/cerrar)
  document.addEventListener('keydown', function (e) {
    if (e.key === 'F4' || (e.altKey && (e.key === 'c' || e.key === 'C'))) {
      e.preventDefault();
      window.toggleCalculadoraFlotante();
    }
  });

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ensureWidgetDom);
  } else {
    ensureWidgetDom();
  }
})();
