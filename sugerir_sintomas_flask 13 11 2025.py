from flask import Flask, render_template, request, redirect, url_for, jsonify
import sqlite3
import os
import requests
from bs4 import BeautifulSoup
import time
import random
import re
from datetime import datetime

# ========== HUELLA DE VERSIÓN ==========
VERSION_TIMESTAMP = "2025-11-08 OPTIMIZADA v6 - Detección flexible de plurales"
ULTIMA_ACTUALIZACION = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

print(f"\n{'='*70}")
print(f"✅ SUGERIR SÍNTOMAS - VERSIÓN ACTIVA")
print(f"   Timestamp: {VERSION_TIMESTAMP}")
print(f"   Iniciado: {ULTIMA_ACTUALIZACION}")
print(f"   Cambios:")
print(f"   • Template única (sin cambio de página)")
print(f"   • Auto-procesado al pegar (sin botón manual)")
print(f"   • Alerta oculta cuando hay texto")
print(f"   • ✅ Arreglado: Verifica si síntoma existe antes de insertar")
print(f"   • ✅ Diagnósticos existentes ahora habilitados")
print(f"   • ✅ Soporte para anticonceptivos y medicamentos preventivos")
print(f"   • ✅ Cobertura completa de productos de farmacia (90+ categorías)")
print(f"   • ✅ NUEVO: Detección flexible de plurales")
print(f"       - 'hormona' detecta 'hormona' o 'hormonas'")
print(f"       - 'dolor' detecta 'dolor' o 'dolores'")
print(f"       - 'infección' detecta 'infección' o 'infecciones'")
print(f"   • ✅ Saltear scraping chequeado por defecto")
print(f"   • Flujo: Seleccionar → Pegar → Procesa automático → Guardar")
print(f"{'='*70}\n")

app = Flask(__name__)
DB_PATH = os.path.join(os.path.dirname(__file__), "medicamentos.db")

# ---------------------- Helpers DB ----------------------
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------- Templates auto-creación ----------------------
TEMPLATES = {
    "poblacion_medicamentos.html": """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Población de Medicamentos</title>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { font-family: sans-serif; padding: 20px; background: #f5f5f5; }
    .container { max-width: 900px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 8px rgba(0,0,0,0.1); }
    
    h1 { margin-bottom: 20px; color: #333; }
    .link-volver { display: inline-block; margin-bottom: 15px; padding: 8px 12px; background: #f0f0f0; text-decoration: none; border-radius: 4px; color: #007bff; }
    .link-volver:hover { background: #e0e0e0; }
    
    .seccion { margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 6px; background: #fafafa; }
    .seccion-titulo { font-size: 16px; font-weight: bold; margin-bottom: 12px; color: #333; }
    
    .form-group { margin-bottom: 15px; }
    label { display: block; margin-bottom: 6px; font-weight: bold; color: #555; }
    input[type="checkbox"] { margin-right: 8px; cursor: pointer; }
    select { width: 100%; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 4px; }
    textarea { width: 100%; padding: 10px; font-size: 14px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; resize: vertical; }
    
    .alerta { padding: 12px; margin: 10px 0; border-radius: 4px; border-left: 4px solid #ffc107; }
    .alerta-warning { background: #fff3cd; color: #856404; display: none; }
    .alerta-warning.visible { display: block; }
    
    .info-small { font-size: 12px; color: #666; margin-top: 6px; }
    .botones-busqueda { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
    .botones-busqueda a { 
      display: inline-block; 
      padding: 8px 14px; 
      background: #007bff; 
      color: white; 
      text-decoration: none; 
      border-radius: 4px; 
      font-size: 13px;
    }
    .botones-busqueda a:hover { background: #0056b3; }
    
    .item { margin: 8px 0; }
    .item input[type="checkbox"] { cursor: pointer; }
    .item label { display: inline; font-weight: normal; }
    .item-disabled { opacity: 0.6; }
    .item-sintomas { margin-left: 30px; color: #666; font-size: 13px; }
    
    .titulo-seccion { font-size: 16px; font-weight: bold; margin: 15px 0 10px 0; color: #333; }
    .loading { display: none; color: #ff9800; font-weight: bold; }
    .loading.visible { display: inline; }
    
    button { 
      padding: 10px 16px; 
      background: #2b8a3e; 
      color: white; 
      border: none; 
      border-radius: 4px; 
      cursor: pointer; 
      font-size: 14px;
      font-weight: bold;
    }
    button:hover { background: #1f6030; }
    button:disabled { opacity: 0.5; cursor: not-allowed; }
    
    .box { margin-top: 15px; padding: 15px; border: 1px solid #ccc; border-radius: 6px; }
    .error-msg { color: #d9534f; font-size: 12px; margin-top: 6px; }
  </style>
  
  <script>
    // Limpiar textarea cuando carga nueva página
    window.addEventListener('load', function() {
      const textarea = document.getElementById('textoExtraido');
      
      // Limpiar siempre que cargue (para evitar contenido de medicamento anterior)
      if (textarea) {
        // Si el valor viene del server sin contenido de scraping
        if (textarea.value.includes('No se encontró')) {
          textarea.value = '';
          textarea.style.background = '#fff';
        }
      }
      
      // Auto-pegar desde clipboard
      if (textarea && (!textarea.value || textarea.value.trim() === '')) {
        if (navigator.clipboard && navigator.clipboard.readText) {
          navigator.clipboard.readText()
            .then(function(text) {
              if (text && text.trim().length > 20) {
                textarea.value = text;
                textarea.style.background = '#e8f5e9';
                console.log('✅ Texto pegado automáticamente');
                // Procesar automáticamente
                procesarTextoPegado();
              }
            })
            .catch(function(err) {
              console.log('ℹ️ No se pudo acceder al clipboard');
            });
        }
      }
    });
    


    // Auto-pegar desde portapapeles y auto-procesar SOLO al pegar
    function setupAutoProcessing() {
      const textarea = document.getElementById('textoExtraido');
      const alertaWarning = document.querySelector('.alerta-warning');

      if (!textarea) return;

      // 🚀 1) Auto-pegar desde clipboard solo si NO viene de cambio interno
      const cambioInterno = localStorage.getItem('cambioMedicamentoInterno') === '1';
      localStorage.removeItem('cambioMedicamentoInterno'); // limpiar estado

      if (!cambioInterno) {
        if (navigator.clipboard && navigator.clipboard.readText) {
          navigator.clipboard.readText().then(text => {
            text = text.trim();
            // 💡 Nuevo: NO auto-pegar si es IGUAL al contenido actual (evita sobrepegado)
            if (text.length > 20 && textarea.value.trim() !== text) {
              textarea.value = text;
              textarea.style.background = '#e8f5e9';
              console.log('📌 Auto-pegado desde portapapeles (nuevo)');
              procesarTextoPegado();
            }
          }).catch(() => {});
        }
      }



      // 🚀 2) Auto-procesar solo cuando el usuario pega manualmente
      textarea.addEventListener('paste', function() {
        setTimeout(() => {
          const texto = textarea.value.trim();

          if (texto.length > 20) {
            if (alertaWarning) alertaWarning.classList.remove('visible');
            textarea.style.background = '#e8f5e9'; // ✅ resaltado suave
            console.log('✅ Texto pegado → Procesando...');
            procesarTextoPegado();
          } else {
            if (alertaWarning) alertaWarning.classList.add('visible');
          }
        }, 200);
      });
    }

    window.setupAutoProcessing = setupAutoProcessing;

    
    function procesarTextoPegado() {
    
  
      const textarea = document.getElementById('textoExtraido');
      const medId = document.getElementById('medId').value;
      const texto = textarea.value;
      
      if (!texto || texto.trim().length < 20) return;
      
      // ✅ NUEVA VALIDACIÓN: Verificar que el texto corresponda al medicamento
      const terminoBuscado = extraerTerminoBuscado();
      
      if (terminoBuscado.length > 0 && !verificarCorrespondencia(texto, terminoBuscado)) {
        const confirmar = confirm(' El texto pegado no parece corresponder al medicamento seleccionado.\\n¿Deseas procesarlo de todas formas?');

        alert(" No se encontró coincidencia");
        
        if (!confirmar) {
          // Usuario canceló: limpiar textarea
          textarea.value = '';
          textarea.style.background = '#fff';
          return;
        }
      }
      
      // Continuar con procesamiento normal
      const loading = document.getElementById('loading-procesando');
      if (loading) loading.classList.add('visible');
      
      fetch('/sugerir-sintomas/procesar-texto/' + medId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ texto: texto })
      })
      .then(response => response.json())
      .then(data => {
        if (data.success) {
          actualizarDiagnosticos(data.diagnosticos);
          actualizarSintomas(data.sintomas);
        }
        if (loading) loading.classList.remove('visible');
      })
      .catch(error => {
        console.error('Error:', error);
        if (loading) loading.classList.remove('visible');
      });
    }

    window.procesarTextoPegado = procesarTextoPegado;


    function extraerTerminoBuscado() {
      // Extraer tanto el término normalizado como el nombre del medicamento
      const terminos = [];
      
      // 1. Término normalizado del componente activo (del <p><b>)
      const parrafo = document.querySelector('p b');
      if (parrafo) {
        terminos.push(parrafo.textContent.trim().toLowerCase());
      }
      
      // 2. Nombre completo del medicamento (del <h1>)
      const h1 = document.querySelector('h1');
      if (h1) {
        // Extraer solo el texto antes del (ID ...)
        let nombreCompleto = h1.textContent.trim();
        nombreCompleto = nombreCompleto.split('(')[0].trim().toLowerCase();
        
        // Limpiar el nombre: quitar números, "mg", "ml", "caja", etc.
        nombreCompleto = nombreCompleto.replace(/\d+\s*(mg|mcg|ml|g|%)/gi, '');
        nombreCompleto = nombreCompleto.replace(/\b(caja|frasco|tableta|tabletas|capsula|cápsula|x\d+)\b/gi, '');


        nombreCompleto = nombreCompleto.trim();
        
        // Extraer primera palabra (generalmente el componente activo)
        const primeraPalabra = nombreCompleto.split(/\s+/)[0];
        if (primeraPalabra && primeraPalabra.length > 3) {
          terminos.push(primeraPalabra);
        }
      }
      
      return terminos.filter(t => t && t.length > 3); // Solo términos válidos
    }

    function verificarCorrespondencia(texto, terminos) {
      if (!terminos || terminos.length === 0) return true; // Si no hay términos, permitir
      
      const textoNorm = texto.toLowerCase();
      
      // Si encuentra CUALQUIERA de los términos, es válido
      return terminos.some(termino => textoNorm.includes(termino));
    }
    
    function actualizarDiagnosticos(diagnosticos) {
      const container = document.getElementById('diagnosticos-container');
      if (!container) return;
      
      if (diagnosticos.length === 0) {
        container.innerHTML = '<p style="color: #999;">No se detectaron diagnósticos.</p>';
        return;
      }
      
      let html = '<div class="titulo-seccion">Diagnósticos detectados:</div>';
      
      diagnosticos.forEach((dx, idx) => {
        const estado = dx.id ? '(existe)' : '(nuevo)';
        
        html += `
          <div class="item">
            <input type="checkbox" id="diagnostico_${idx}" name="diagnostico" 
                   value="${dx.id ? 'dx:' + dx.id : 'new:' + dx.nombre}" 
                   checked="checked">
            <label for="diagnostico_${idx}"><strong>${dx.nombre}</strong> ${estado}</label>
            ${dx.sintomas.length > 0 ? `
              <div class="item-sintomas">
                <small>Incluye: ${dx.sintomas.join(', ')}</small>
              </div>
            ` : ''}
          </div>
        `;
      });
      
      container.innerHTML = html;
    }
    
    function actualizarSintomas(sintomas) {
      const container = document.getElementById('sintomas-container');
      if (!container) return;
      
      if (sintomas.length === 0) {
        container.innerHTML = '<p style="color: #999;">No se detectaron síntomas.</p>';
        return;
      }
      
      let html = '<div class="titulo-seccion">Síntomas sugeridos:</div>';
      
      sintomas.forEach((s, idx) => {
        const estado = s.id ? '(existe)' : '(nuevo)';
        
        html += `
          <div class="item">
            <input type="checkbox" id="sintoma_${idx}" name="sintoma" 
                   value="${s.id ? 'id:' + s.id : 'new:' + s.label}" 
                   checked="checked">
            <label for="sintoma_${idx}">${s.label} ${estado}</label>
          </div>
        `;
      });
      
      container.innerHTML = html;
    }
    
    // Seleccionar medicamento y recargar
    function irAMedicamento() {
      const select = document.getElementById('medicamentoSelect');
      const medId = select.value;
      if (!medId) return;

      
      // ✅ AGREGAR ESTAS LÍNEAS:
      // Rehabilitar botón y ocultar mensaje al cambiar medicamento
      const btnGuardar = document.getElementById('btn-guardar');
      const mensajeGuardado = document.getElementById('mensaje-guardado');
      
      if (btnGuardar) {
        btnGuardar.disabled = false;
        btnGuardar.textContent = '✅ Guardar seleccionados';
      }
      
      if (mensajeGuardado) {
        mensajeGuardado.style.display = 'none';
      }


      // Limpiar inmediatamente la UI
      const textarea = document.getElementById('textoExtraido');
      if (textarea) {
        textarea.value = "";
        textarea.style.background = "#fff";
      }

      const diagContainer = document.getElementById('diagnosticos-container');
      if (diagContainer) {
        diagContainer.innerHTML = '<p style="color: #999;">Cargando diagnósticos...</p>';
      }

      const sintContainer = document.getElementById('sintomas-container');
      if (sintContainer) {
        sintContainer.innerHTML = '<p style="color: #999;">Detectando síntomas...</p>';
      }

      // Ocultar alerta de warning
      const alertaWarning = document.querySelector('.alerta-warning');
      if (alertaWarning) alertaWarning.classList.remove('visible');

      // Obtener datos del nuevo medicamento vía AJAX
      fetch('/sugerir-sintomas/datos-medicamento/' + medId)
        .then(response => response.json())
        .then(data => {
          if (data.success) {
            // Actualizar título
            const h1 = document.querySelector('h1');
            if (h1) {
              h1.innerHTML = data.med.nombre + ' <small style="color: #999; font-size: 14px;">(ID ' + data.med.id + ')</small>';
            }

            // Actualizar término de búsqueda
            const pTermino = document.querySelector('p b');
            if (pTermino) {
              pTermino.textContent = data.termino;
            }

            // Actualizar selector con nueva lista
            actualizarSelector(data.meds_con_precio, data.meds_sin_precio, data.med.id);

            // Actualizar action del form
            const form = document.querySelector('form[method="post"]');
            if (form) {
              form.action = '/sugerir-sintomas/guardar/' + data.med.id;
            }

            // Actualizar input hidden
            const medIdInput = document.getElementById('medId');
            if (medIdInput) {
              medIdInput.value = data.med.id;
            }

            // Actualizar enlaces de búsqueda
            actualizarEnlacesBusqueda(data.termino);

            // Mostrar alerta
            if (alertaWarning) alertaWarning.classList.add('visible');

            console.log('✅ Medicamento cambiado a:', data.med.nombre);
          }
        })
        .catch(error => {
          console.error('Error al cambiar medicamento:', error);
          alert('Error al cargar el medicamento. Por favor, recarga la página.');
        });
    }

    function actualizarSelector(meds_con_precio, meds_sin_precio, medIdActual) {
      const select = document.getElementById('medicamentoSelect');
      if (!select) return;
      select.innerHTML = '<option value="">-- Seleccione --</option>';

      if (meds_con_precio && meds_con_precio.length > 0) {
        const group1 = document.createElement('optgroup');
        group1.label = "✅ Con precio";
        meds_con_precio.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = `[${m.id}] ${m.nombre}`;
          if (m.id == medIdActual) opt.selected = true;
          group1.appendChild(opt);
        });
        select.appendChild(group1);
      }

      if (meds_sin_precio && meds_sin_precio.length > 0) {
        const group2 = document.createElement('optgroup');
        group2.label = "⚠️ Sin precio";
        meds_sin_precio.forEach(m => {
          const opt = document.createElement('option');
          opt.value = m.id;
          opt.textContent = `[${m.id}] ${m.nombre}`;
          if (m.id == medIdActual) opt.selected = true;
          group2.appendChild(opt);
        });
        select.appendChild(group2);
      }
    }

    function actualizarEnlacesBusqueda(termino) {
      const linkGoogle = document.querySelector('a[href*="google.com"]');
      if (linkGoogle) {
        linkGoogle.href = 'https://www.google.com/search?q=' + encodeURIComponent(termino) + '%20que%20es%20para%20que%20sirve%20no%20muestres%20contraindicaciones';
      }

      const linkWiki = document.querySelector('a[href*="wikipedia.org"]');
      if (linkWiki) {
        linkWiki.href = 'https://es.wikipedia.org/wiki/' + termino.replace(/ /g, '_');
      }
    }


    // Manejar guardado con AJAX
    document.addEventListener('DOMContentLoaded', function() {
      const form = document.getElementById('form-guardar');
      if (form) {
        form.addEventListener('submit', function(e) {
          e.preventDefault();
          guardarSeleccionados();
        });
      }
    });

    function guardarSeleccionados() {
      const form = document.getElementById('form-guardar');
      const btnGuardar = document.getElementById('btn-guardar');
      const mensajeGuardado = document.getElementById('mensaje-guardado');
      const medId = document.getElementById('medId').value;
      
      // Validar que existan los elementos
      if (!form || !btnGuardar || !medId) {
        console.error('Elementos no encontrados:', { form: !!form, btnGuardar: !!btnGuardar, medId: !!medId });
        alert('Error: No se pudo inicializar el formulario. Recarga la página.');
        return;
      }
      
      // Deshabilitar botón mientras guarda
      btnGuardar.disabled = true;
      btnGuardar.textContent = '⏳ Guardando...';
      
      // Recopilar datos del formulario
      const formData = new FormData(form);
      
      fetch('/sugerir-sintomas/guardar/' + medId, {
        method: 'POST',
        body: formData
      })
      .then(response => {
        if (response.ok) {
          // Éxito: mostrar mensaje y mantener botón deshabilitado
          btnGuardar.textContent = '✅ Guardado';
          
          if (mensajeGuardado) {
            mensajeGuardado.style.display = 'block';
            mensajeGuardado.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
          
          // Remover el medicamento guardado del selector
          const select = document.getElementById('medicamentoSelect');
          if (select) {
            // Eliminar la opción del medicamento actual
            const optionToRemove = select.querySelector(`option[value="${medId}"]`);
            if (optionToRemove) {
              optionToRemove.remove();
            }
            
            // Resetear el selector a "-- Seleccione --"
            select.value = "";
            
            // Si no quedan más medicamentos, mostrar mensaje
            if (select.options.length <= 1) {
              alert('¡Felicitaciones! Has completado todos los medicamentos pendientes.');
            }
          }
          
          console.log('✅ Medicamento guardado exitosamente');
        } else {
          throw new Error('Error al guardar');
        }
      })
      .catch(error => {
        console.error('Error:', error);
        alert('Error al guardar. Por favor, intenta de nuevo.');
        
        // Rehabilitar botón en caso de error
        btnGuardar.disabled = false;
        btnGuardar.textContent = '✅ Guardar seleccionados';
      });
    }    


  </script>
</head>
<body>
  <div class="container">
    <a href="/sugerir-sintomas/pendientes" class="link-volver">← Volver a la lista</a>
    
    <!-- SECCIÓN 1: SELECCIONAR MEDICAMENTO -->
    <div class="seccion">
      <div class="seccion-titulo">1️⃣ Seleccionar medicamento</div>
      
      <div class="form-group">
        <label for="medicamentoSelect">Elige el medicamento a procesar:</label>
        <select id="medicamentoSelect" onchange="irAMedicamento()">
          <option value="">-- Seleccione --</option>
          {% for m in meds %}
            <option value="{{ m.id }}" {% if m.id == med.id %}selected{% endif %}>
              [{{ m.id }}] {{ m.nombre }}
            </option>
          {% endfor %}
        </select>
      </div>
      
      <div class="form-group" style="margin-top: 12px;">
        <label>
          <input type="checkbox" id="skipScraping" checked="checked" />
          <strong>⚡ Saltear scraping</strong> (ir directo a búsqueda manual)
        </label>
        <div class="info-small">Activa si el scraping es lento</div>
      </div>
    </div>
    
    {% if med %}
    <h1>{{ med.nombre }} <small style="color: #999; font-size: 14px;">(ID {{ med.id }})</small></h1>
    <p style="color: #666; margin-bottom: 15px;">Buscado por: <b>{{ termino }}</b></p>
    
      <!-- Mensaje de éxito después de guardar -->
      <div id="mensaje-guardado" style="display: none; padding: 12px; margin: 15px 0; background: #d4edda; color: #155724; border: 1px solid #c3e6cb; border-radius: 4px; text-align: center;">
        ✅ <strong>Medicamento actualizado correctamente.</strong> Por favor, selecciona otro medicamento para continuar.
      </div>

    <!-- SECCIÓN 2: PEGAR TEXTO -->
    <div class="seccion">
      <div class="seccion-titulo">2️⃣ Pega el texto del medicamento</div>
      
      <div class="alerta alerta-warning visible" id="alertaWarning">
        <p><strong>⚠️ No se encontró información automática</strong></p>
        <p>Abre Google o Wikipedia, copia y regresa:</p>
        <div class="botones-busqueda">
          <a href="https://www.google.com/search?q={{ termino }}%20que%20es%20para%20que%20sirve%20no%20muestres%20contraindicaciones" target="_blank">
            🔍 Buscar en Google
          </a>
          <a href="https://es.wikipedia.org/wiki/{{ termino | replace(' ', '_') }}" target="_blank">
            📖 Buscar en Wikipedia
          </a>
        </div>
        <div class="info-small">💡 Al volver, el texto se pegará automáticamente</div>
      </div>
      
      <textarea id="textoExtraido" autocomplete="off" placeholder="Pega aquí el contenido que copiaste..." style="height: 200px;">{{ texto }}</textarea>

      <div class="info-small" style="margin-top: 8px;">
        ⏳ <span id="loading-procesando" class="loading">Analizando diagnósticos y síntomas...</span>
      </div>
    </div>
    
    <!-- FORMULARIO PRINCIPAL -->
    <form id="form-guardar" autocomplete="off">
      <input type="hidden" id="medId" value="{{ med.id }}">
      
      <!-- SECCIÓN 3: DIAGNÓSTICOS -->
      <div class="seccion">
        <div id="diagnosticos-container">
          {% if diagnosticos|length > 0 %}
            <div class="titulo-seccion">Diagnósticos detectados:</div>
            {% for dx in diagnosticos %}
              <div class="item {% if dx.id %}item-disabled{% endif %}">
                {% if dx.id %}
                  <input type="checkbox" id="diagnostico_{{ loop.index }}" name="diagnostico" value="dx:{{ dx.id }}" >
                {% else %}
                  <input type="checkbox" id="diagnostico_{{ loop.index }}" name="diagnostico" value="new:{{ dx.nombre }}" checked="checked">
                {% endif %}
                <label for="diagnostico_{{ loop.index }}"><strong>{{ dx.nombre }}</strong> {% if not dx.id %}(nuevo){% else %}(existe){% endif %}</label>
                {% if dx.sintomas|length > 0 %}
                <div class="item-sintomas">
                  <small>Incluye: {{ dx.sintomas | join(', ') }}</small>
                </div>
                {% endif %}
              </div>
            {% endfor %}
          {% else %}
            <p style="color: #999;">Cargando diagnósticos...</p>
          {% endif %}
        </div>
      </div>
      
      <!-- SECCIÓN 4: SÍNTOMAS -->
      <div class="seccion">
        <div id="sintomas-container">
          {% if sugestiones|length > 0 %}
            <div class="titulo-seccion">Síntomas sugeridos:</div>
            {% for s in sugestiones %}
              <div class="item">
                <input type="checkbox" id="sintoma_{{ loop.index }}" name="sintoma" value="{% if s.id %}id:{{ s.id }}{% else %}new:{{ s.label }}{% endif %}" checked="checked">
                <label for="sintoma_{{ loop.index }}">{{ s.label }} {% if s.id %}(existe){% else %}(nuevo){% endif %}</label>
              </div>
            {% endfor %}
          {% else %}
            <p style="color: #999;">Detectando síntomas...</p>
          {% endif %}
        </div>
      </div>
      
      <!-- SECCIÓN 5: AGREGAR SÍNTOMA MANUAL -->
      <div class="seccion">
        <label for="extra">Agregar otro síntoma (texto libre):</label>
        <input id="extra" name="sintoma" type="text" placeholder="ej: dificultad respiratoria severa" />
        <div class="info-small">Escribe un síntoma que no esté en la lista</div>
      </div>
      

      

      <!-- BOTÓN GUARDAR -->
      <button type="submit" id="btn-guardar" style="width: 100%; padding: 12px; margin-top: 20px; font-size: 16px;">
        ✅ Guardar seleccionados
      </button>
    </form>
    
    {% else %}
    <p style="color: #b00; margin-top: 20px;">Por favor, selecciona un medicamento primero.</p>
    {% endif %}
    
    <script>
      // Inicializar auto-procesamiento
      setupAutoProcessing();



    </script>
  </div>
</body>
</html>
"""
}



def ensure_templates():
    tpl_dir = os.path.join(os.path.dirname(__file__), "templates")
    if not os.path.exists(tpl_dir):
        os.makedirs(tpl_dir)
    for name, content in TEMPLATES.items():
        path = os.path.join(tpl_dir, name)
        # SIEMPRE escribir el template (no solo si no existe)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

ensure_templates()

# ---------------------- Scraping helpers (MedlinePlus prioritario) ----------------------
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

# Mapa de slugs MedlinePlus para medicamentos frecuentes (ampliado)
MEDLINE_SLUGS = {
    "fluticasona": "a601125-es.html",
    "amoxicilina": "a685001-es.html",
    "azitromicina": "a697037-es.html",
    "ibuprofeno": "a681029-es.html",
    "clorfenamina": "a682543-es.html",
    "hidrocortisona": "a682795-es.html",
    "cetoconazol": "a682816-es.html",
    "montelukast": "a600032-es.html",
    "mupirocina": "a601132-es.html",
    "salbutamol": "a682042-es.html",
    "amoxicilina acido clavulanico": "a696015-es.html",
    # "diclofenaco": "a688040-es.html",  # No disponible en MedlinePlus español
    "paracetamol": "a681612-es.html",
    "omeprazol": "a681436-es.html",
    "losartan": "a693000-es.html",
    "metformina": "a601426-es.html",
    "lisinopril": "a689052-es.html",
}

def detectar_negacion_en_contexto(texto, diagnostico):
    """
    Detecta si un diagnóstico está mencionado en contexto NEGATIVO.
    Evita falsos positivos como "no funciona contra gripe"
    """
    negaciones = [
        f'no funciona contra {diagnostico}',
        f'no es efectivo para {diagnostico}',
        f'no se usa para {diagnostico}',
        f'no debe usarse para {diagnostico}',
        f'no trata {diagnostico}',
        f'no cura {diagnostico}',
        f'no actúa contra {diagnostico}',
        f'inefectivo contra {diagnostico}',
        f'no funciona en {diagnostico}',
        f'no sirve para {diagnostico}',
    ]
    
    texto_lower = texto.lower()
    for negacion in negaciones:
        if negacion in texto_lower:
            return True  # Está en contexto negativo
    
    return False  # NO está en contexto negativo

def normalizar(s):
    """Convierte cualquier entrada (string, list, etc) a string normalizado en minúsculas"""
    if isinstance(s, list):
        return " ".join(str(x) for x in s).strip().lower()
    return str(s).strip().lower()
    """Convierte cualquier entrada (string, list, etc) a string normalizado en minúsculas"""
    if isinstance(s, list):
        return " ".join(str(x) for x in s).strip().lower()
    return str(s).strip().lower()

# ---------------------- Cargar indicaciones rechazadas ----------------------
def cargar_indicaciones_rechazadas():
    """
    Carga la lista de indicaciones/síntomas a rechazar desde la BD.
    También incluye una lista por defecto hardcoded.
    """
    rechazados = {'dolor'}  # Por defecto, rechazar "dolor" (muy ambiguo)
    
    try:
        db = get_db()
        cur = db.execute('SELECT indicacion_nombre FROM indicaciones_rechazadas')
        for row in cur.fetchall():
            rechazados.add(row[0].lower().strip())
        db.close()
    except Exception as e:
        print(f"⚠️ Error cargando indicaciones_rechazadas: {e}")
    
    return rechazados

# Cargar indicaciones rechazadas al iniciar
INDICACIONES_RECHAZADAS = cargar_indicaciones_rechazadas()
print(f"✅ Indicaciones rechazadas cargadas: {INDICACIONES_RECHAZADAS}")

def normalizar_termino_para_busqueda(texto, modo='completo'):
    """
    Limpia el nombre del producto para obtener un término de búsqueda útil.
    modos:
      - 'completo' mantiene forma farmacéutica si aparece (inhalador, spray)
      - 'activo' intenta quedarse con componente base
    """
    if not texto:
        return ''
    t = texto.lower()
    # reemplazar signos comunes
    t = re.sub(r"\+", " ", t)
    t = re.sub(r"[^a-z0-9áéíóúñ /-]", " ", t)
    # eliminar unidades y cantidades
    t = re.sub(r"\b\d+\s*(mg|mcg|g|ml|iu|%)\b", " ", t)
    t = re.sub(r"\b(caja|frasco|ampolla|tableta|tabletas|tubo|spray|inhala?r|colirio|jarabe)\b", " ", t)
    t = re.sub(r"\s+", " ", t).strip()

    if modo == 'activo':
        # devolver sólo la parte antes de ' / ' ó ' con ' ó ' de ' si existe
        parts = re.split(r"\s+(con|/|de)\s+", t)
        return parts[0].strip()
    return t

def buscar_texto_medlineplus(termino):
    """Intenta primero por slug (mapa), si no, usa la búsqueda del sitio."""
    if not termino:
        return None
    termino_norm = termino.lower()

    # 1) intentar por slug conocido
    for k, slug in MEDLINE_SLUGS.items():
        if k in termino_norm:
            url = f"https://medlineplus.gov/spanish/druginfo/meds/{slug}"
            try:
                r = requests.get(url, headers=HEADERS, timeout=10)
                if r.status_code == 200:
                    soup = BeautifulSoup(r.text, "html.parser")
                    ps = soup.select("div#ency_summary p") or soup.select("div.section p") or soup.select("p")
                    textos = [p.get_text(" ", strip=True) for p in ps[:8]]  # Aumentado de 4 a 8
                    texto_completo = " ".join(textos)
                    
                    # Validación mejorada: debe tener texto real (no solo espacios o palabras vacías)
                    if texto_completo and len(texto_completo) > 100 and len(texto_completo.split()) > 15:
                        return texto_completo
            except Exception:
                pass

    # 2) fallback: usar el buscador del sitio
    try:
        q = termino.replace(" ", "+")
        url = f"https://medlineplus.gov/spanish/search/?q={q}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        link = soup.select_one("a.result-title")
        if link:
            href = link.get('href')
            if not href.startswith('http'):
                href = 'https://medlineplus.org' + href
            r2 = requests.get(href, headers=HEADERS, timeout=10)
            s2 = BeautifulSoup(r2.text, 'html.parser')
            ps = s2.select("div#ency_summary p") or s2.select("div.section p") or s2.select("p")
            textos = [p.get_text(' ', strip=True) for p in ps[:8]]  # Aumentado de 4 a 8
            texto_resultado = ' '.join(textos) if textos else None
            if texto_resultado and len(texto_resultado) > 100 and len(texto_resultado.split()) > 15:
                return texto_resultado
    except Exception:
        pass

    return None

def buscar_texto_drugscom(termino):
    try:
        q = termino.replace(" ", "+")
        url = f"https://www.drugs.com/search.php?searchterm={q}"
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        a = soup.select_one("a.search-result-link")
        if a:
            href = a.get('href')
            if not href.startswith('http'):
                href = 'https://www.drugs.com' + href
            r2 = requests.get(href, headers=HEADERS, timeout=10)
            s2 = BeautifulSoup(r2.text, "html.parser")
            textos = [p.get_text(' ', strip=True) for p in s2.select('div.contentBox p')[:6]]
            return ' '.join(textos) if textos else None
    except Exception:
        return None
    return None

def obtener_texto_indicaciones_preferido(termino):
    # anti-baneo
    time.sleep(random.uniform(0.6, 1.1))
    txt = buscar_texto_medlineplus(termino)
    if txt:
        return txt, 'MedlinePlus'
    txt = buscar_texto_drugscom(termino)
    if txt:
        return txt, 'Drugs.com'
    return None, None

# ---------------------- Detectar efectos secundarios ----------------------
def detectar_efectos_secundarios_en_texto(texto):
    """
    Detecta síntomas que aparecen en CONTEXTO de EFECTOS SECUNDARIOS.
    Retorna un conjunto de síntomas que NO debemos sugerir porque son efectos adversos.
    
    🔖 HUELLA: 2025-11-07 Filtro de efectos secundarios
    """
    if not texto:
        return set()
    
    t = texto.lower()
    efectos_secundarios = set()
    
    # Palabras clave que indican contexto de efectos secundarios
    patrones_efectos = [
        r'puede causar\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'efectos secundarios\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'reacción adversa\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'no debe\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'evitar\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'contraindicado\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'riesgo de\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'peligro de\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
    ]
    
    for patron in patrones_efectos:
        matches = re.finditer(patron, t, re.IGNORECASE)
        for match in matches:
            sintoma_mencionado = match.group(1).strip().lower()
            # Limpiar y agregar
            if sintoma_mencionado and len(sintoma_mencionado) > 2:
                sintoma_norm = normalizar(sintoma_mencionado)
                efectos_secundarios.add(sintoma_norm)
    
    return efectos_secundarios

# ---------------------- MEJORA 1: Extracción de indicaciones del medicamento ----------------------
def extraer_indicaciones_medicamento(texto):
    """
    Extrae las indicaciones médicas del medicamento desde el texto.
    Busca patrones como "se usa para", "indicado para", "tratamiento de", etc.
    """
    if not texto:
        return []
    
    t = texto.lower()
    indicaciones = set()
    
    # Patrones para extraer indicaciones
    patrones = [
        r'se usa para ([^.]+)\.',
        r'indicado para ([^.]+)\.',
        r'para tratar ([^.]+)\.',
        r'tratamiento de ([^.]+)\.',
        r'usado para ([^.]+)\.',
    ]
    
    for patron in patrones:
        matches = re.finditer(patron, t)
        for match in matches:
            indic = match.group(1).strip().lower()
            indic = re.sub(r'[,;:]', '', indic)
            if indic and len(indic) > 3:
                indicaciones.add(indic)
    
    return list(indicaciones)

# ---------------------- MEJORA 2: Normalización y deduplicación de síntomas ----------------------
def normalizar_sintomas_lista(sintomas_lista):
    """
    Normaliza síntomas: elimina duplicados, sinónimos similares.
    Retorna lista limpia.
    """
    if not sintomas_lista:
        return []
    
    sintomas_norm = {}
    
    for s in sintomas_lista:
        s_norm = normalizar(s)
        
        # Mapeo de sinónimos
        sinonimos = {
            'dolor': ['dolor general', 'molestia'],
            'debilidad': ['debilitamiento'],
            'comezón': ['picazón', 'picor'],
            'inflamación': ['hinchazón'],
        }
        
        clave = s_norm
        for principal, lista_sin in sinonimos.items():
            if s_norm == principal or s_norm in [normalizar(x) for x in lista_sin]:
                clave = principal
                break
        
        # Guardar con capitalización correcta
        if clave not in sintomas_norm:
            sintomas_norm[clave] = s.strip().title() if len(s.strip()) > 0 else s
    
    return sorted(list(sintomas_norm.values()))

# ---------------------- MEJORA 3: Validación de diagnóstico ----------------------
def validar_diagnostico(nombre_diagnostico, sintomas_lista):
    """
    Valida que un diagnóstico tenga mínimo 2 síntomas.
    Retorna True si es válido.
    """
    if not sintomas_lista or len(sintomas_lista) < 2:
        return False
    return True

# ---------------------- Reglas de diagnósticos - Categorías médicas completas ----------------------
REGLAS_DIAGNOSTICOS = {
    # ========== RESPIRATORIO ==========
    'bronquitis': ['tos', 'mucosidad', 'dificultad respiratoria', 'producción de flema', 'sibilancias'],
    'neumonía': ['fiebre', 'dolor en el pecho', 'dificultad respiratoria', 'tos productiva', 'escalofríos'],
    'asma': ['dificultad respiratoria', 'sibilancias', 'tos nocturna', 'opresión torácica', 'dificultad para respirar'],
    'epoc': ['dificultad respiratoria', 'tos crónica', 'sibilancias', 'cansancio', 'producción de flema'],
    'rinitis': ['congestión nasal', 'estornudos', 'rinorrea', 'picazón nasal', 'obstrucción nasal'],
    'sinusitis': ['congestión nasal', 'dolor facial', 'mucosidad nasal espesa', 'presión sinusal', 'cefalea sinusal'],
    'faringitis': ['dolor de garganta', 'dificultad al tragar', 'inflamación de garganta', 'garganta irritada', 'enrojecimiento'],
    'amigdalitis': ['dolor de garganta', 'amígdalas inflamadas', 'dificultad al tragar', 'fiebre'],
    'laringitis': ['ronquera', 'pérdida de voz', 'dolor de garganta', 'tos seca', 'dificultad al hablar'],
    'resfriado': ['congestión nasal', 'estornudos', 'tos leve', 'dolor de garganta', 'rinorrea'],
    'gripe': ['fiebre alta', 'dolor muscular', 'cansancio', 'tos', 'dolor de garganta', 'escalofríos'],
    
    # ========== DIGESTIVO/GASTROINTESTINAL ==========
    'gastritis': ['dolor abdominal', 'acidez', 'ardor estomacal', 'náusea', 'vómito'],
    'úlcera péptica': ['dolor abdominal', 'acidez', 'dispepsia', 'ardor estomacal', 'sangrado digestivo'],
    'gastroenteritis': ['diarrea', 'vómito', 'náusea', 'dolor abdominal', 'deshidratación'],
    'diarrea': ['diarrea', 'evacuaciones frecuentes', 'dolor abdominal', 'deshidratación'],
    'estreñimiento': ['estreñimiento', 'dificultad para defecar', 'dolor abdominal', 'distensión abdominal'],
    'colitis': ['diarrea con sangre', 'dolor abdominal', 'cólicos', 'inflamación intestinal'],
    'síndrome de colon irritable': ['dolor abdominal', 'diarrea', 'estreñimiento', 'distensión abdominal', 'gases'],
    'hepatitis': ['ictericia', 'dolor abdominal superior', 'fatiga', 'náusea', 'orina oscura'],
    'pancreatitis': ['dolor abdominal severo', 'náusea', 'vómito', 'fiebre', 'dolor en espalda'],
    
    # ========== CARDIOVASCULAR ==========
    'hipertensión': ['presión arterial elevada', 'dolor de cabeza', 'mareo', 'fatiga', 'dificultad respiratoria'],
    'insuficiencia cardíaca': ['dificultad respiratoria', 'cansancio', 'hinchazón de pies', 'arritmia'],
    'arritmia': ['palpitaciones', 'mareo', 'síncope', 'fatiga', 'dificultad respiratoria'],
    'angina': ['dolor en el pecho', 'opresión torácica', 'dificultad respiratoria', 'mareo', 'sudoración'],
    'trombosis': ['inflamación', 'dolor', 'enrojecimiento', 'calor local', 'hinchazón'],
    'aterosclerosis': ['dolor en el pecho', 'dificultad respiratoria', 'mareo', 'entumecimiento'],
    
    # ========== PREVENCIÓN CARDIOVASCULAR Y ANTICOAGULACIÓN ==========
    'prevención de trombosis': ['prevención de coágulos', 'riesgo trombótico', 'anticoagulación', 'antiplaquetario'],
    'prevención de coágulos': ['prevención de trombosis', 'riesgo de coagulación', 'agregación plaquetaria'],
    'infarto de miocardio': ['ataque cardíaco', 'infarto al corazón', 'dolor torácico', 'evento cardiovascular'],
    'accidente cerebrovascular': ['infarto cerebral', 'ictus', 'derrame cerebral', 'evento cerebrovascular isquémico'],
    'enfermedad arterial periférica': ['problemas de circulación en piernas', 'dolor en piernas al caminar', 'claudicación intermitente'],
    'síndrome coronario agudo': ['angina inestable', 'dolor torácico agudo', 'evento coronario'],
    'riesgo cardiovascular': ['prevención cardiovascular', 'protección cardíaca', 'eventos cardiovasculares'],
    'prevención de eventos cardiovasculares': ['prevención de infarto', 'prevención de ictus', 'protección cardiovascular'],
    'aterotrombosis': ['eventos aterotrombóticos', 'prevención aterotrombótica', 'trombosis arterial'],
    'accidente isquémico transitorio': ['ait', 'mini derrame', 'isquemia cerebral transitoria'],
    
    # ========== NEUROLÓGICO ==========
    'migraña': ['dolor de cabeza severo', 'náusea', 'sensibilidad a luz', 'vómito', 'visión borrosa'],
    'cefalea': ['dolor de cabeza', 'tensión', 'mareo', 'fatiga'],
    'epilepsia': ['convulsiones', 'pérdida de conciencia', 'espasmos musculares', 'confusión'],
    'neuropatía': ['entumecimiento', 'hormigueo', 'dolor neuropático', 'debilidad muscular'],
    'depresión': ['tristeza persistente', 'falta de motivación', 'insomnio', 'fatiga', 'pérdida de apetito'],
    'ansiedad': ['nerviosismo', 'inquietud', 'palpitaciones', 'sudoración', 'temblores'],
    'insomnio': ['insomnio', 'dificultad para dormir', 'sueño no reparador', 'cansancio diurno'],
    'parkinson': ['temblores', 'rigidez muscular', 'lentitud de movimiento', 'inestabilidad'],
    
    # ========== DERMATOLÓGICO ==========
    'dermatitis': ['enrojecimiento', 'comezón', 'inflamación', 'descamación', 'irritación'],
    'eczema': ['comezón intensa', 'enrojecimiento', 'ampollas', 'descamación', 'inflamación'],
    'psoriasis': ['placas gruesas', 'comezón', 'enrojecimiento', 'descamación plateada', 'dolor'],
    'acné': ['pápulas', 'pústulas', 'comedones', 'inflamación', 'enrojecimiento'],
    'infección fúngica': ['comezón', 'enrojecimiento', 'descamación', 'olor característico', 'maceramiento'],
    'infección bacteriana de piel': ['enrojecimiento', 'inflamación', 'pus', 'dolor', 'calor local'],
    'urticaria': ['rash', 'comezón', 'habones', 'enrojecimiento', 'hinchazón'],
    'alopecia': ['pérdida de cabello', 'calvicie', 'debilitamiento del cabello'],
    'herpes': ['ampollas', 'dolor', 'ardor', 'comezón', 'inflamación local'],
    'verrugas': ['crecimientos en piel', 'rugosidad', 'verruga plantar'],
    
    # ========== UROLÓGICO ==========
    'infección urinaria': ['ardor al orinar', 'orina frecuente', 'dolor abdominal bajo', 'urgencia urinaria', 'turbidez'],
    'cistitis': ['ardor al orinar', 'urgencia urinaria', 'dolor suprapúbico', 'orina frecuente'],
    'nefritis': ['dolor en flanco', 'fiebre', 'orina anormal', 'hinchazón', 'fatiga'],
    'prostatitis': ['dolor al orinar', 'dificultad para orinar', 'dolor pélvico', 'fiebre'],
    'incontinencia': ['pérdida involuntaria de orina', 'urgencia urinaria', 'nicturia'],
    
    # ========== ARTICULAR/ÓSEO ==========
    'artritis': ['dolor articular', 'inflamación', 'rigidez matutina', 'limitación de movimiento', 'hinchazón'],
    'artrosis': ['dolor articular', 'rigidez', 'crujidos', 'limitación de movimiento', 'deformidad'],
    'osteoporosis': ['fragilidad ósea', 'dolor óseo', 'fracturas frecuentes', 'pérdida de altura'],
    'gota': ['ácido úrico', 'tofáceos', 'ataque agudo de gota', 'depositos de urato', 'crisis gotosa', 'articulación metatarsofalángica', 'primer dedo del pie'],
    'esguince': ['dolor', 'inflamación', 'hematoma', 'limitación de movimiento', 'inestabilidad'],
    'fractura': ['dolor severo', 'inflamación', 'hematoma', 'deformidad', 'imposibilidad de movimiento'],
    'tendinitis': ['dolor en tendón', 'inflamación', 'debilidad muscular', 'limitación de movimiento'],
    'bursitis': ['dolor articular', 'hinchazón', 'inflamación', 'limitación de movimiento'],
    
    # ========== ENDOCRINO ==========
    'diabetes': ['sed excesiva', 'orina frecuente', 'hambre extrema', 'fatiga', 'visión borrosa', 'pérdida de peso'],
    'hipotiroidismo': ['fatiga', 'aumento de peso', 'depresión', 'intolerancia al frío', 'piel seca'],
    'hipertiroidismo': ['nerviosismo', 'pérdida de peso', 'intolerancia al calor', 'palpitaciones', 'tremor'],
    'obesidad': ['sobrepeso', 'aumento de peso', 'dificultad respiratoria', 'dolor articular'],
    
    # ========== OFTALMOLÓGICO ==========
    'conjuntivitis': ['enrojecimiento ocular', 'comezón', 'secreción ocular', 'lagrimeo', 'sensibilidad a luz'],
    'glaucoma': ['presión ocular elevada', 'visión periférica reducida', 'dolor ocular', 'halos visuales'],
    'cataratas': ['visión borrosa', 'opacidad del cristalino', 'sensibilidad a luz', 'dificultad nocturna'],
    
    # ========== INFECCIONES GENERALES ==========
    'infección bacterial': ['inflamación', 'fiebre', 'pus', 'enrojecimiento', 'dolor'],
    'infección viral': ['fiebre', 'cansancio', 'dolor muscular', 'congestión nasal', 'tos'],
    'infección fúngica general': ['comezón', 'enrojecimiento', 'descamación', 'inflamación'],
    'infección parasitaria': ['dolor abdominal', 'diarrea', 'comezón', 'debilitamiento'],
    'sepsis': ['fiebre alta', 'confusión', 'dolor muscular', 'hipotensión', 'taquicardia'],
    
    # ========== ANESTÉSICOS ==========
    'anestesia local': ['bloqueo de dolor', 'adormecimiento local', 'insensibilidad temporal'],
    'dolor preoperatorio': ['dolor antes de procedimiento', 'ansiedad preoperatoria', 'molestia anticipada'],
    'procedimiento quirúrgico': ['anestesia requerida', 'cirugía menor', 'anestesia local necesaria'],
    'procedimiento oftálmico': ['anestesia ocular', 'procedimiento de ojo', 'anestesia oftálmica'],
    'procedimiento urológico': ['anestesia uretral', 'cateterismo', 'sondaje'],
    'procedimiento dental': ['anestesia dental', 'procedimiento odontológico', 'bloqueo dental'],
    'venopunción': ['inserción de aguja', 'punción venosa', 'canalización intravenosa'],
    
    # ========== PREVENTIVOS Y ESPECIALES ==========
    'anticoncepción': ['prevención de embarazo', 'control natal', 'planificación familiar', 'método anticonceptivo'],
    'control de natalidad': ['prevención de embarazo', 'control natal', 'planificación familiar'],
    'anticonceptivo oral': ['prevención de embarazo', 'control natal', 'píldora anticonceptiva'],
    'anticonceptivo hormonal': ['prevención de embarazo', 'control hormonal', 'regulación menstrual'],
    'contracepción de emergencia': ['prevención de embarazo no deseado', 'anticoncepción postcoital'],
    'prevención cardiovascular': ['prevención de eventos cardiovasculares', 'protección cardíaca'],
    'prevención de trombosis': ['prevención de coágulos', 'anticoagulación preventiva'],
    'prevención de osteoporosis': ['prevención de fracturas', 'fortalecimiento óseo'],
    'suplemento vitamínico': ['prevención de deficiencias', 'suplementación nutricional'],
    'vacunación': ['prevención de infecciones', 'inmunización', 'protección inmunológica'],
    
    # ========== VITAMINAS Y SUPLEMENTOS ==========
    'deficiencia vitamínica': ['carencia nutricional', 'falta de vitaminas', 'déficit vitamínico', 'suplementación vitamínica'],
    'deficiencia de vitamina d': ['deficiencia de vitamina d', 'insuficiencia de vitamina d', 'suplementación de vitamina d'],
    'deficiencia de vitamina b12': ['deficiencia de b12', 'anemia perniciosa', 'suplementación b12'],
    'deficiencia de vitamina c': ['deficiencia de vitamina c', 'escorbuto', 'suplementación vitamina c'],
    'deficiencia de calcio': ['deficiencia de calcio', 'osteopenia', 'suplementación de calcio'],
    'deficiencia de hierro': ['deficiencia de hierro', 'anemia ferropénica', 'suplementación de hierro'],
    'deficiencia de ácido fólico': ['deficiencia de folato', 'anemia megaloblástica', 'suplementación ácido fólico'],
    'suplementación nutricional': ['refuerzo nutricional', 'complemento alimenticio', 'multivitamínico'],
    'fortalecimiento inmunológico': ['refuerzo inmune', 'estimulación inmunológica', 'mejora de defensas'],
    'refuerzo energético': ['energía', 'vitalidad', 'combatir fatiga', 'vigor'],
    'omega 3': ['suplementación omega 3', 'ácidos grasos esenciales', 'salud cardiovascular'],
    'probióticos': ['flora intestinal', 'salud digestiva', 'equilibrio intestinal'],
    'antioxidantes': ['protección celular', 'antienvejecimiento', 'radicales libres'],
    
    # ========== CUIDADO PERSONAL E HIGIENE ==========
    'higiene bucal': ['limpieza dental', 'cuidado de dientes', 'salud bucal', 'prevención de caries'],
    'higiene dental': ['limpieza dental', 'cuidado dental', 'enjuague bucal', 'hilo dental'],
    'mal aliento': ['halitosis', 'aliento desagradable', 'higiene bucal'],
    'sensibilidad dental': ['dientes sensibles', 'dolor dental al frío', 'hipersensibilidad dental'],
    'blanqueamiento dental': ['aclarado dental', 'dientes blancos', 'estética dental'],
    'gingivitis': ['inflamación de encías', 'sangrado de encías', 'enfermedad periodontal'],
    'higiene íntima': ['cuidado íntimo', 'limpieza vaginal', 'higiene genital', 'pH balanceado'],
    'limpieza facial': ['higiene facial', 'cuidado de rostro', 'limpieza de piel'],
    'desodorante': ['control de olor corporal', 'protección contra sudor', 'antitranspirante'],
    'protección solar': ['protección uv', 'protección contra rayos solares', 'prevención de quemaduras solares', 'bloqueador solar'],
    'repelente de piojos': ['prevención de piojos', 'tratamiento antipiojos', 'pediculosis'],
    
    # ========== COSMÉTICOS Y DERMOCOSMÉTICOS ==========
    'antienvejecimiento': ['anti-edad', 'reducción de arrugas', 'rejuvenecimiento', 'líneas de expresión'],
    'hidratación de piel': ['piel seca', 'hidratación cutánea', 'humectación', 'suavidad de piel'],
    'piel seca': ['xerosis', 'sequedad cutánea', 'deshidratación de piel', 'descamación'],
    'piel grasa': ['seborrea', 'exceso de grasa', 'control de brillo', 'piel oleosa'],
    'manchas en la piel': ['hiperpigmentación', 'melasma', 'aclarado de piel', 'uniformidad del tono'],
    'cicatrices': ['marcas en piel', 'cicatrización', 'regeneración cutánea', 'queloides'],
    'estrías': ['marcas de estiramiento', 'prevención de estrías', 'atenuación de estrías'],
    'celulitis': ['piel de naranja', 'lipodistrofia', 'tratamiento de celulitis'],
    'ojeras': ['círculos oscuros', 'bolsas bajo ojos', 'hinchazón periocular'],
    'rosácea': ['enrojecimiento facial', 'rubor facial', 'vasos sanguíneos visibles'],
    'tratamiento capilar': ['cuidado del cabello', 'fortalecimiento capilar', 'salud del cabello'],
    'caída del cabello': ['alopecia', 'pérdida de cabello', 'calvicie', 'debilitamiento capilar'],
    'caspa': ['descamación del cuero cabelludo', 'dermatitis seborreica', 'picazón del cuero cabelludo'],
    'cabello graso': ['exceso de grasa capilar', 'cuero cabelludo graso', 'seborrea capilar'],
    'cabello seco': ['cabello deshidratado', 'cabello quebradizo', 'falta de brillo'],
    'fortalecimiento de uñas': ['uñas débiles', 'uñas quebradizas', 'crecimiento de uñas'],
    'hongos en uñas': ['onicomicosis', 'infección fúngica de uñas', 'uñas amarillas'],
    
    # ========== PRODUCTOS PARA BEBÉS ==========
    'dermatitis del pañal': ['rozadura de pañal', 'irritación por pañal', 'sarpullido de pañal', 'pañalitis'],
    'cuidado del cordón umbilical': ['antisepsia umbilical', 'limpieza del ombligo', 'prevención de onfalitis'],
    'cólico infantil': ['cólicos del lactante', 'dolor abdominal en bebé', 'gases en bebé'],
    'dentición': ['salida de dientes', 'molestias por dentición', 'dolor de encías en bebé'],
    'costra láctea': ['dermatitis seborreica infantil', 'escamas en cuero cabelludo de bebé'],
    'reflujo en bebés': ['regurgitación', 'vómitos en lactante', 'reflujo gastroesofágico'],
    'congestión nasal en bebés': ['mocos en bebé', 'nariz tapada en lactante', 'higiene nasal'],
    'fiebre infantil': ['temperatura elevada en niños', 'antipirético pediátrico'],
    
    # ========== MATERIAL DE CURACIÓN Y ANTISÉPTICOS ==========
    'desinfección de heridas': ['limpieza de heridas', 'antisepsia', 'prevención de infección'],
    'curación de heridas': ['cicatrización', 'regeneración de tejido', 'cierre de heridas'],
    'heridas superficiales': ['raspones', 'cortadas', 'abrasiones', 'rasguños'],
    'heridas quirúrgicas': ['curación postoperatoria', 'cuidado de suturas', 'prevención de infección quirúrgica'],
    'quemaduras leves': ['quemaduras de primer grado', 'quemadura solar', 'escaldaduras'],
    'quemaduras moderadas': ['quemaduras de segundo grado', 'ampollas por quemadura'],
    'úlceras por presión': ['escaras', 'úlceras de decúbito', 'llagas por presión'],
    'úlceras venosas': ['úlceras en piernas', 'llagas vasculares', 'heridas crónicas'],
    'pie diabético': ['úlceras diabéticas', 'heridas en pie diabético', 'prevención de amputación'],
    'antiséptico': ['desinfección', 'eliminación de gérmenes', 'prevención de infección'],
    
    # ========== DISPOSITIVOS Y MEDICIÓN ==========
    'monitoreo de glucosa': ['medición de azúcar', 'control de diabetes', 'glucometría'],
    'control de diabetes': ['manejo de diabetes', 'regulación de glucosa', 'prevención de complicaciones'],
    'medición de presión arterial': ['control de presión', 'monitoreo hipertensión', 'tensiómetro'],
    'medición de temperatura': ['termometría', 'control de fiebre', 'detección de fiebre'],
    'medición de oxigenación': ['oximetría', 'saturación de oxígeno', 'pulsioximetría'],
    'nebulización': ['terapia respiratoria', 'administración de medicamentos inhalados', 'tratamiento de asma'],
    
    # ========== SALUD SEXUAL Y REPRODUCTIVA ==========
    'disfunción eréctil': ['impotencia', 'problemas de erección', 'salud sexual masculina'],
    'sequedad vaginal': ['lubricación vaginal', 'atrofia vaginal', 'menopausia'],
    'lubricación íntima': ['lubricante sexual', 'comodidad íntima', 'relaciones sexuales'],
    'infecciones vaginales': ['candidiasis vaginal', 'vaginosis', 'hongos vaginales'],
    'prevención de ets': ['protección contra enfermedades de transmisión sexual', 'preservativos', 'sexo seguro'],
    'menopausia': ['climaterio', 'síntomas menopáusicos', 'sofocos', 'cambios hormonales'],
    'síndrome premenstrual': ['spm', 'dolor menstrual', 'molestias premenstruales', 'dismenorrea'],
    'irregularidad menstrual': ['ciclo menstrual irregular', 'amenorrea', 'trastornos menstruales'],
    
    # ========== DESPARASITACIÓN Y CONTROL DE PLAGAS ==========
    'parásitos intestinales': ['desparasitación', 'lombrices', 'oxiuros', 'antiparasitario'],
    'desparasitación': ['eliminación de parásitos', 'tratamiento antiparasitario', 'vermífugo'],
    'pediculosis': ['piojos', 'tratamiento de piojos', 'infestación de piojos'],
    'sarna': ['escabiosis', 'ácaros', 'comezón intensa', 'infestación de ácaros'],
    'repelente de insectos': ['protección contra mosquitos', 'prevención de picaduras', 'repelente de zancudos'],
    'picaduras de insectos': ['mordeduras', 'alivio de picazón por picadura', 'reacción a picadura'],
    
    # ========== HIDRATACIÓN Y NUTRICIÓN ESPECIAL ==========
    'deshidratación': ['rehidratación oral', 'suero oral', 'pérdida de líquidos', 'sales de rehidratación'],
    'rehidratación oral': ['reposición de líquidos', 'sales de rehidratación', 'electrolitos'],
    'nutrición enteral': ['alimentación por sonda', 'suplementación nutricional', 'fórmulas enterales'],
    'malnutrición': ['desnutrición', 'deficiencia nutricional', 'bajo peso'],
    'soporte nutricional': ['nutrición clínica', 'suplementación alimentaria', 'refuerzo nutricional'],
    
    # ========== OTROS ==========
    'inflamación': ['inflamación', 'hinchazón', 'enrojecimiento', 'calor local', 'dolor'],
    'alergia': ['reacción alérgica', 'comezón', 'enrojecimiento', 'hinchazón', 'estornudos'],
    'dolor crónico': ['dolor persistente', 'rigidez', 'limitación de movimiento', 'fatiga'],
    'anemia': ['fatiga', 'debilidad', 'palidez', 'dificultad respiratoria', 'mareo'],
}

def crear_patron_flexible_plural(palabra):
    """
    Crea un patrón regex que acepta la palabra en singular y plural.
    Ejemplos:
    - "hormona" → busca "hormona" o "hormonas"
    - "dolor" → busca "dolor" o "dolores"
    - "infección" → busca "infección" o "infecciones"
    
    NOTA: Maneja correctamente palabras con tildes que pierden el acento en plural
    (ej: "infección" → "infecciones")
    """
    palabra_escaped = re.escape(palabra)
    
    # Palabras que terminan en vocal acentuada + 'n' pierden el acento en plural
    # Ejemplo: infección → infecciones
    if len(palabra) > 2 and palabra[-1] == 'n' and palabra[-2] in 'óí':
        # Crear versión sin acento
        palabra_sin_acento = palabra[:-2] + palabra[-2].replace('ó', 'o').replace('í', 'i') + palabra[-1]
        palabra_sin_acento_escaped = re.escape(palabra_sin_acento)
        return r'\b(' + palabra_escaped + r'|' + palabra_sin_acento_escaped + r'es)\b'
    
    # Si termina en vocal (excepto 'y'), agregar 's' opcional
    elif palabra[-1] in 'aeiouáéíóú':
        return r'\b' + palabra_escaped + r's?\b'
    # Si termina en consonante o 'y', agregar 'es' opcional
    else:
        return r'\b' + palabra_escaped + r'(es)?\b'

def detectar_diagnosticos_en_texto(texto):
    """
    Detecta diagnósticos conocidos en el texto.
    Solo retorna diagnósticos con mínimo 2 síntomas (validados).
    Selectivo con sinónimos: solo si aparecen múltiples veces o en contexto.
    IMPORTANTE: Busca palabras COMPLETAS, no substrings (evita "gota" en "gotas").
    
    🔖 HUELLA: 2025-11-07 regex palabra completa \\b
    """
    if not texto:
        return []
    
    t = texto.lower()
    diagnosticos_detectados = []
    detectados_set = set()
    
    # 1) Búsqueda directa - SIEMPRE detectar si el diagnóstico aparece explícitamente
    # IMPORTANTE: Usar límites de palabra \b para evitar substrings
    # NUEVO: Acepta plurales automáticamente (hormona → hormonas)
    for diagnostico, sintomas in REGLAS_DIAGNOSTICOS.items():
        # Buscar palabra completa con flexibilidad de plurales
        patron = crear_patron_flexible_plural(diagnostico)
        if re.search(patron, t) and diagnostico not in detectados_set:
            # ===== VERIFICAR CONTEXTO NEGATIVO =====
            if detectar_negacion_en_contexto(texto, diagnostico):
                print(f"   ⏭️  Saltando '{diagnostico}' - está en contexto negativo")
                continue  # Saltar si está en contexto negativo
            
            # VALIDACIÓN: mínimo 2 síntomas
            if validar_diagnostico(diagnostico, sintomas):
                diagnosticos_detectados.append({
                    'nombre': diagnostico,
                    'sintomas': sintomas
                })
                detectados_set.add(diagnostico)
    
    # 2) Búsqueda por sinónimos - MUY SELECTIVO (solo si aparecen MÁS DE 3 VECES)
    # Aumentamos umbral para evitar falsos positivos por menciones casuales
    sinonimos_diagnosticos = {
        # Anticonceptivos y preventivos (UMBRAL BAJO para detectarlos)
        'prevención de embarazo': ['anticoncepción', 'anticonceptivo oral', 'control de natalidad'],
        'prevenir el embarazo': ['anticoncepción', 'anticonceptivo oral'],
        'anticonceptivo': ['anticoncepción', 'anticonceptivo oral', 'anticonceptivo hormonal'],
        'píldora': ['anticonceptivo oral'],
        'control natal': ['anticoncepción', 'control de natalidad'],
        'planificación familiar': ['anticoncepción', 'control de natalidad'],
        'anticonceptivo hormonal': ['anticoncepción', 'anticonceptivo hormonal'],
        'etinilestradiol': ['anticonceptivo hormonal', 'anticonceptivo oral'],
        'levonorgestrel': ['anticonceptivo hormonal', 'anticonceptivo oral', 'contracepción de emergencia'],
        'desogestrel': ['anticonceptivo hormonal', 'anticonceptivo oral'],
        'drospirenona': ['anticonceptivo hormonal', 'anticonceptivo oral'],
        
        # Anticoagulantes y antiplaquetarios (UMBRAL BAJO)
        'coágulo': ['prevención de trombosis', 'prevención de coágulos'],
        'coagulación': ['prevención de trombosis', 'prevención de coágulos'],
        'anticoagula': ['prevención de trombosis', 'prevención de coágulos'],
        'antiplaquetari': ['prevención de trombosis', 'prevención de coágulos'],
        'agregación plaquetaria': ['prevención de coágulos', 'prevención de trombosis'],
        'trombosis': ['prevención de trombosis', 'riesgo trombótico'],
        'infarto': ['infarto de miocardio', 'prevención de eventos cardiovasculares'],
        'ataque cardíaco': ['infarto de miocardio', 'prevención de eventos cardiovasculares'],
        'ictus': ['accidente cerebrovascular', 'prevención de eventos cardiovasculares'],
        'derrame': ['accidente cerebrovascular', 'prevención de eventos cardiovasculares'],
        'accidente cerebrovascular': ['accidente cerebrovascular', 'prevención de eventos cardiovasculares'],
        'evento cardiovascular': ['prevención de eventos cardiovasculares', 'riesgo cardiovascular'],
        'arterial periférica': ['enfermedad arterial periférica'],
        'circulación': ['enfermedad arterial periférica'],
        'coronario': ['síndrome coronario agudo', 'prevención de eventos cardiovasculares'],
        'aterotrombótico': ['aterotrombosis', 'prevención de eventos cardiovasculares'],
        'isquémico': ['accidente cerebrovascular', 'accidente isquémico transitorio'],
        
        # Vitaminas y suplementos (UMBRAL BAJO)
        'vitamina': ['suplemento vitamínico', 'deficiencia vitamínica'],
        'vitamina d': ['deficiencia de vitamina d'],
        'vitamina b12': ['deficiencia de vitamina b12'],
        'vitamina c': ['deficiencia de vitamina c'],
        'calcio': ['deficiencia de calcio'],
        'hierro': ['deficiencia de hierro', 'anemia'],
        'ácido fólico': ['deficiencia de ácido fólico'],
        'omega 3': ['omega 3'],
        'probiótico': ['probióticos'],
        'antioxidante': ['antioxidantes'],
        'suplemento': ['suplementación nutricional', 'suplemento vitamínico'],
        
        # Cuidado personal (UMBRAL BAJO)
        'higiene bucal': ['higiene bucal', 'higiene dental'],
        'dientes': ['higiene dental', 'sensibilidad dental'],
        'halitosis': ['mal aliento'],
        'encías': ['gingivitis'],
        'protección solar': ['protección solar'],
        'bloqueador': ['protección solar'],
        'desodorante': ['desodorante'],
        'íntimo': ['higiene íntima'],
        'piojos': ['pediculosis', 'repelente de piojos'],
        
        # Cosméticos (UMBRAL BAJO)
        'arrugas': ['antienvejecimiento'],
        'hidratación': ['hidratación de piel'],
        'piel seca': ['piel seca', 'hidratación de piel'],
        'piel grasa': ['piel grasa'],
        'manchas': ['manchas en la piel'],
        'acné': ['acné'],
        'estrías': ['estrías'],
        'celulitis': ['celulitis'],
        'cabello': ['tratamiento capilar'],
        'caída de cabello': ['caída del cabello', 'alopecia'],
        'caspa': ['caspa'],
        'uñas': ['fortalecimiento de uñas'],
        
        # Bebés (UMBRAL BAJO)
        'pañal': ['dermatitis del pañal'],
        'cordón umbilical': ['cuidado del cordón umbilical'],
        'cólico': ['cólico infantil'],
        'dentición': ['dentición'],
        'bebé': ['cólico infantil', 'dermatitis del pañal'],
        'lactante': ['reflujo en bebés', 'cólico infantil'],
        
        # Curación (UMBRAL BAJO)
        'herida': ['desinfección de heridas', 'curación de heridas'],
        'quemadura': ['quemaduras leves', 'quemaduras moderadas'],
        'antiséptico': ['antiséptico', 'desinfección de heridas'],
        'cicatrización': ['curación de heridas'],
        'úlcera': ['úlceras por presión', 'úlceras venosas'],
        'pie diabético': ['pie diabético'],
        
        # Salud sexual (UMBRAL BAJO)
        'disfunción eréctil': ['disfunción eréctil'],
        'impotencia': ['disfunción eréctil'],
        'sequedad vaginal': ['sequedad vaginal', 'lubricación íntima'],
        'lubricante': ['lubricación íntima'],
        'candidiasis': ['infecciones vaginales'],
        'menopausia': ['menopausia'],
        'menstrual': ['síndrome premenstrual', 'irregularidad menstrual'],
        
        # Desparasitación (UMBRAL BAJO)
        'parásitos': ['parásitos intestinales', 'desparasitación'],
        'lombrices': ['parásitos intestinales'],
        'desparasitante': ['desparasitación'],
        'sarna': ['sarna'],
        'repelente': ['repelente de insectos'],
        'picadura': ['picaduras de insectos'],
        
        # Hidratación (UMBRAL BAJO)
        'deshidratación': ['deshidratación', 'rehidratación oral'],
        'suero oral': ['rehidratación oral'],
        'sales de rehidratación': ['rehidratación oral'],
        
        # Enfermedades comunes
        'tos': ['bronquitis', 'gripe', 'resfriado', 'asma', 'epoc'],
        'respiratoria': ['bronquitis', 'neumonía', 'asma', 'epoc'],
        'dificultad respiratoria': ['asma', 'epoc', 'bronquitis'],
        'congestión': ['sinusitis', 'rinitis', 'resfriado'],
        'garganta': ['faringitis', 'amigdalitis', 'resfriado', 'laringitis'],
        'diarrea': ['gastroenteritis', 'colitis', 'síndrome de colon irritable'],
        'vómito': ['gastroenteritis', 'gastritis', 'pancreatitis'],
        'abdominal': ['gastritis', 'úlcera péptica', 'gastroenteritis', 'hepatitis', 'pancreatitis'],
        'infección': ['infección bacterial', 'infección viral', 'infección fúngica', 'infección parasitaria', 'sepsis'],
        'bacteria': ['infección bacterial', 'sepsis'],
        'virus': ['infección viral', 'gripe', 'resfriado', 'herpes'],
        'hongo': ['infección fúngica'],
        'articulación': ['artritis', 'artrosis', 'bursitis'],
        'dolor articular': ['artritis', 'artrosis'],
        'dolor neuropático': ['neuropatía'],
        'neuropatía': ['neuropatía'],
    }
    
    for patron, diagnosticos_sugeridos in sinonimos_diagnosticos.items():
        # Buscar palabra completa con flexibilidad de plurales
        # Usar función que acepta singular y plural automáticamente
        patron_regex = crear_patron_flexible_plural(patron)
        matches = re.finditer(patron_regex, t)
        cuenta = len(list(matches))
        
        # UMBRAL ESPECIAL PARA PRODUCTOS DE FARMACIA: Solo 1 vez es suficiente
        # Categorías con umbral bajo (productos específicos)
        categorias_umbral_bajo = [
            # Anticonceptivos
            'anticoncepción', 'anticonceptivo oral', 'anticonceptivo hormonal', 'control de natalidad', 'contracepción de emergencia',
            # Vitaminas y suplementos
            'suplemento vitamínico', 'deficiencia vitamínica', 'deficiencia de vitamina d', 'deficiencia de vitamina b12',
            'deficiencia de vitamina c', 'deficiencia de calcio', 'deficiencia de hierro', 'deficiencia de ácido fólico',
            'suplementación nutricional', 'fortalecimiento inmunológico', 'refuerzo energético', 'omega 3', 'probióticos', 'antioxidantes',
            # Cuidado personal
            'higiene bucal', 'higiene dental', 'mal aliento', 'sensibilidad dental', 'blanqueamiento dental', 'gingivitis',
            'higiene íntima', 'limpieza facial', 'desodorante', 'protección solar', 'repelente de piojos',
            # Cosméticos
            'antienvejecimiento', 'hidratación de piel', 'piel seca', 'piel grasa', 'manchas en la piel', 'cicatrices',
            'estrías', 'celulitis', 'ojeras', 'rosácea', 'tratamiento capilar', 'caída del cabello', 'caspa',
            'cabello graso', 'cabello seco', 'fortalecimiento de uñas', 'hongos en uñas',
            # Bebés
            'dermatitis del pañal', 'cuidado del cordón umbilical', 'cólico infantil', 'dentición', 'costra láctea',
            'reflujo en bebés', 'congestión nasal en bebés', 'fiebre infantil',
            # Curación
            'desinfección de heridas', 'curación de heridas', 'heridas superficiales', 'heridas quirúrgicas',
            'quemaduras leves', 'quemaduras moderadas', 'úlceras por presión', 'úlceras venosas', 'pie diabético', 'antiséptico',
            # Salud sexual
            'disfunción eréctil', 'sequedad vaginal', 'lubricación íntima', 'infecciones vaginales', 'prevención de ets',
            'menopausia', 'síndrome premenstrual', 'irregularidad menstrual',
            # Desparasitación
            'parásitos intestinales', 'desparasitación', 'pediculosis', 'sarna', 'repelente de insectos', 'picaduras de insectos',
            # Hidratación
            'deshidratación', 'rehidratación oral', 'nutrición enteral', 'malnutrición', 'soporte nutricional',
            # Dispositivos
            'monitoreo de glucosa', 'control de diabetes', 'medición de presión arterial', 'medición de temperatura',
            'medición de oxigenación', 'nebulización'
        ]
        
        # Verificar si alguno de los diagnósticos sugeridos está en categorías de umbral bajo
        umbral_necesario = 1 if any(d in categorias_umbral_bajo for d in diagnosticos_sugeridos) else 3
        
        if cuenta > umbral_necesario:
            for diag in diagnosticos_sugeridos:
                if diag in REGLAS_DIAGNOSTICOS and diag not in detectados_set:
                    sintomas = REGLAS_DIAGNOSTICOS[diag]
                    if validar_diagnostico(diag, sintomas):
                        diagnosticos_detectados.append({
                            'nombre': diag,
                            'sintomas': sintomas
                        })
                        detectados_set.add(diag)
    
    return diagnosticos_detectados

def extraer_sugeridos_de_texto_avanzado(texto):
    """
    Extrae síntomas sugeridos del texto con heurística ampliada.
    Selectivo: Solo detecta si hay contexto suficiente.
    IMPORTANTE: Busca palabras COMPLETAS, no substrings.
    
    🔖 HUELLA: 2025-11-07 regex palabra completa \\b - sin substrings
    """
    if not texto:
        return []

    t = texto.lower()
    sugeridos = set()

    # 1) Detectar diagnósticos DIRECTOS y añadir síntomas asociados
    # SOLO si el diagnóstico aparece explícitamente en el texto (palabra completa)
    for enfermedad, sintomas in REGLAS_DIAGNOSTICOS.items():
        patron = r'\b' + re.escape(enfermedad) + r'\b'
        if re.search(patron, t):
            for s in sintomas:
                sugeridos.add(s)

    # 2) Búsqueda de síntomas por palabras clave - MÁS SELECTIVO
    # Solo agregar si la palabra clave REALMENTE está en el texto
    sintomas_keywords = {
        'dificultad respiratoria': ['dificultad para respirar','dificultad respiratoria','disnea'],
        'sibilancias': ['sibilancias','wheezing','wheeze'],
        'tos': ['tos','cough','coughing'],
        'tos productiva': ['tos productiva','productive cough'],
        'opresión torácica': ['opresión torácica','tightness in chest','presión en el pecho'],
        'congestión nasal': ['congestión nasal','nasal congestion','congestión'],
        'estornudos': ['estornud','sneez'],
        'rinorrea': ['rinorrea','secreción nasal','runny nose'],
        'prurito ocular': ['prurito ocular','itchy eyes'],
        'dolor de garganta': ['dolor de garganta','sore throat','irritación de garganta'],
        'inflamación': ['inflamación'],
        'fiebre': ['fiebre','fever','temperatura elevada'],
        'náusea': ['náusea','nausea'],
        'vómito': ['vómito','vomit'],
        'diarrea': ['diarrea','diarrhea'],
        'estreñimiento': ['estreñimiento','constipation'],
        'mareo': ['mareo','dizziness','vértigo'],
        'dolor de cabeza': ['dolor de cabeza','headache','cefalea'],
        'fatiga': ['fatiga','fatigue','cansancio'],
        'erupción': ['erupción','rash'],
        'comezón': ['comezón','picazón','itching','prurito'],
        'enrojecimiento': ['enrojecimiento','redness','red'],
        'hinchazón': ['hinchazón','swelling','edema'],
        'ardor': ['ardor','burning','quemazón'],
        'irritación': ['irritación','irritant'],
    }
    
    for sintoma_principal, keywords in sintomas_keywords.items():
        # SELECTIVO: Contar coincidencias con palabras completas
        # SOLO agregar si encuentra AL MENOS UNA keyword específica (no genérica)
        coincidencias = 0
        for kw in keywords:
            patron_kw = r'\b' + re.escape(kw) + r'\b'
            if re.search(patron_kw, t):
                coincidencias += 1
                break  # Con encontrar UNA es suficiente
        
        if coincidencias > 0:
            sugeridos.add(sintoma_principal)

    # 3) Patrones específicos de indicaciones - SOLO si están explícitamente en el texto
    patrones_indicaciones = [
        ('infecciones causadas por bacterias', ['infección bacterial', 'inflamación']),
        ('infecciones de oído', ['infección de oído']),
        ('infecciones de garganta', ['infección de garganta']),
        ('infecciones de piel', ['infección de piel']),
        ('quemaduras', ['quemazón', 'quemadura']),
        ('picaduras', ['picaduras de insectos']),
        ('úlceras', ['úlceras']),
    ]
    
    for patron, sintomas_asociados in patrones_indicaciones:
        # Solo si el patrón aparece explícitamente (palabra completa)
        patron_regex = r'\b' + re.escape(patron) + r'\b'
        if re.search(patron_regex, t):
            for s in sintomas_asociados:
                sugeridos.add(s)

    # 4) Palabras clave muy específicas - SOLO si están muy claras en contexto
    patrones_especificos = [
        ('alergia', ['reacción alérgica', 'comezón']),
        ('urticaria', ['urticaria']),
        ('herpes', ['herpes']),
    ]
    
    for patron, sintomas_asociados in patrones_especificos:
        patron_regex = r'\b' + re.escape(patron) + r'\b'
        if re.search(patron_regex, t):
            for s in sintomas_asociados:
                sugeridos.add(s)

    # ===== FILTRAR SÍNTOMAS RECHAZADOS =====
    sugeridos = {s for s in sugeridos if normalizar(s) not in INDICACIONES_RECHAZADAS}
    
    # ===== FILTRAR EFECTOS SECUNDARIOS =====
    efectos_sec = detectar_efectos_secundarios_en_texto(texto)
    sugeridos = {s for s in sugeridos if normalizar(s) not in efectos_sec}

    return sorted(sugeridos)


# ---------------------- Rutas ----------------------
@app.route('/sugerir-sintomas/pendientes')
def listar_pendientes():
    db = get_db()
    cur = db.execute("""
        SELECT m.id, m.nombre, m.componente_activo_id
        FROM medicamentos m
        LEFT JOIN medicamento_sintoma ms ON m.id = ms.medicamento_id
        WHERE m.componente_activo_id IS NOT NULL
          AND ms.sintoma_id IS NULL
        ORDER BY m.nombre
        LIMIT 200
    """)
    meds = cur.fetchall()
    db.close()
    return render_template('select_medicamento.html', meds=meds)


@app.route('/sugerir-sintomas/ver/<int:med_id>')
def ver_sugerir_med(med_id):
    db = get_db()
    med = db.execute('SELECT id, nombre, componente_activo_id FROM medicamentos WHERE id = ?', (med_id,)).fetchone()
    if not med:
        db.close()
        return 'Medicamento no encontrado', 404

    # preferimos buscar por el nombre del componente activo si existe
    termino_busqueda = med['nombre']
    if med['componente_activo_id']:
        comp = db.execute('SELECT nombre FROM medicamentos WHERE id = ?', (med['componente_activo_id'],)).fetchone()
        if comp and comp['nombre']:
            termino_busqueda = comp['nombre']

    termino_limpio = normalizar_termino_para_busqueda(termino_busqueda, modo='completo')

    # ===== NUEVO: Verificar si usuario quiere skipear scraping =====
    skip_scraping = request.args.get('skip_scraping', '0') == '1'
    
    if skip_scraping:
        # Saltear scraping, mostrar directo búsqueda manual
        texto = f"No se encontró texto en las fuentes automáticas para '{termino_busqueda}'."
        fuente = 'Búsqueda manual'
    else:
        # Hacer scraping normal
        texto, fuente = obtener_texto_indicaciones_preferido(termino_limpio)
        if not texto:
            termino_activo = normalizar_termino_para_busqueda(termino_busqueda, modo='activo')
            texto, fuente = obtener_texto_indicaciones_preferido(termino_activo)

        if not texto:
            texto = f"No se encontró texto en las fuentes automáticas para '{termino_busqueda}'." 

    # ===== FLUJO MEJORADO CON LAS 3 CRÍTICAS =====
    
    # 1) Extraer indicaciones del medicamento
    indicaciones_med = extraer_indicaciones_medicamento(texto)
    
    # 2) Detectar diagnósticos (ya validados con mínimo 2 síntomas)
    diagnosticos_detectados_raw = detectar_diagnosticos_en_texto(texto)
    
    # 3) Preparar diagnósticos para mostrar
    diagnosticos_detectados = []
    sintomas_derivados = set()
    
    for d_raw in diagnosticos_detectados_raw:
        d_nombre = d_raw['nombre']
        d_sintomas = d_raw['sintomas']
        
        d_bd = db.execute('SELECT id FROM diagnosticos WHERE lower(descripcion) = ?', 
                         (d_nombre.lower(),)).fetchone()
        d_id = d_bd['id'] if d_bd else None
        
        diagnosticos_detectados.append({
            'nombre': d_nombre,
            'id': d_id,
            'sintomas': d_sintomas
        })
        
        for sintoma in d_sintomas:
            sintomas_derivados.add(normalizar(sintoma))

    # 4) Obtener síntomas de BD
    sintomas_db = db.execute('SELECT id, nombre FROM sintomas').fetchall()
    
    # 5) Detectar síntomas directos
    sintomas_directos = set()
    for s in sintomas_db:
        # Búsqueda de palabra COMPLETA con flexibilidad de plurales
        # Ejemplo: "hormona" encuentra "hormona" o "hormonas"
        patron = crear_patron_flexible_plural(s['nombre'].lower())
        if re.search(patron, texto.lower()):
            sintomas_directos.add(normalizar(s['nombre']))

    # 6) Extraer con heurística
    sugestiones_heuristica = extraer_sugeridos_de_texto_avanzado(texto)
    for s in sugestiones_heuristica:
        sintomas_directos.add(normalizar(s))

    # 7) Unir y filtrar
    todos_sugeridos = list(sintomas_derivados.union(sintomas_directos))
    todos_sugeridos.sort()
    
    diagnosticos_normalizados = set(normalizar(d['nombre']) for d in diagnosticos_detectados)
    todos_sugeridos = [s for s in todos_sugeridos if s not in diagnosticos_normalizados]

    # 8) MEJORA 2: Normalizar síntomas (eliminar duplicados)
    todos_sugeridos = normalizar_sintomas_lista(todos_sugeridos)
    
    # 8b) Filtrar síntomas rechazados
    todos_sugeridos = [s for s in todos_sugeridos if normalizar(s) not in INDICACIONES_RECHAZADAS]
    
    # 8c) Filtrar efectos secundarios (síntomas que son adversos, no a tratar)
    efectos_sec = detectar_efectos_secundarios_en_texto(texto)
    todos_sugeridos = [s for s in todos_sugeridos if normalizar(s) not in efectos_sec]

    # 9) Preparar lista final
    sugestiones_db = []
    for s_norm in todos_sugeridos:
        # Normalizar antes de buscar en BD
        s_norm_busqueda = normalizar(s_norm)
        encontrado = next((x for x in sintomas_db if normalizar(x['nombre']) == s_norm_busqueda), None)
        
        if encontrado:
            sugestiones_db.append({
                'label': encontrado['nombre'],
                'id': encontrado['id']
            })
        else:
            sugestiones_db.append({
                'label': s_norm,
                'id': None
            })

    # Obtener todos los medicamentos para el selector
    todos_meds = db.execute('''
        SELECT DISTINCT m.id, m.nombre
        FROM medicamentos m
        LEFT JOIN precios p ON p.medicamento_id = m.id
        WHERE m.componente_activo_id IS NOT NULL 
        AND m.id NOT IN (SELECT medicamento_id FROM medicamento_sintoma)
        ORDER BY 
            CASE WHEN p.precio > 0 THEN 0 ELSE 1 END,
            m.nombre
    ''').fetchall()
    
    db.close()
    return render_template(
        'poblacion_medicamentos.html',
        meds=todos_meds,
        med=med,
        termino=termino_limpio,
        texto='',              # ← VACÍO para no revivir texto anterior
        fuente=fuente,
        sugestiones=[],        # ← VACÍO para no revivir síntomas anteriores
        diagnosticos=[]        # ← VACÍO para no revivir diagnósticos anteriores
    )


@app.route('/sugerir-sintomas/datos-medicamento/<int:med_id>')
def datos_medicamento_ajax(med_id):
    """Devuelve datos del medicamento en JSON con separación visual por precio"""
    db = get_db()
    med = db.execute('SELECT id, nombre, componente_activo_id FROM medicamentos WHERE id = ?', (med_id,)).fetchone()
    if not med:
        db.close()
        return jsonify({'error': 'Medicamento no encontrado'}), 404

    termino_busqueda = med['nombre']
    if med['componente_activo_id']:
        comp = db.execute('SELECT nombre FROM medicamentos WHERE id = ?', (med['componente_activo_id'],)).fetchone()
        if comp and comp['nombre']:
            termino_busqueda = comp['nombre']
    termino_limpio = normalizar_termino_para_busqueda(termino_busqueda, modo='completo')

    # Medicamentos con precio (> 0)
    meds_con_precio = db.execute('''
        SELECT DISTINCT m.id, m.nombre
        FROM medicamentos m
        JOIN precios p ON p.medicamento_id = m.id
        WHERE m.componente_activo_id IS NOT NULL 
          AND p.precio > 0
          AND m.id NOT IN (SELECT medicamento_id FROM medicamento_sintoma)
        ORDER BY m.nombre
    ''').fetchall()

    # Medicamentos sin precio (p.price IS NULL o <= 0)
    meds_sin_precio = db.execute('''
        SELECT DISTINCT m.id, m.nombre
        FROM medicamentos m
        LEFT JOIN precios p ON p.medicamento_id = m.id
        WHERE m.componente_activo_id IS NOT NULL 
          AND (p.precio IS NULL OR p.precio <= 0)
          AND m.id NOT IN (SELECT medicamento_id FROM medicamento_sintoma)
        ORDER BY m.nombre
    ''').fetchall()

    db.close()
    return jsonify({
        'success': True,
        'med': {
            'id': med['id'],
            'nombre': med['nombre']
        },
        'termino': termino_limpio,
        'meds_con_precio': [{'id': m['id'], 'nombre': m['nombre']} for m in meds_con_precio],
        'meds_sin_precio': [{'id': m['id'], 'nombre': m['nombre']} for m in meds_sin_precio]
    })



@app.route('/sugerir-sintomas/procesar-texto/<int:med_id>', methods=['POST'])
def procesar_texto_pegado(med_id):
    """
    Recibe texto pegado manualmente, detecta diagnósticos y síntomas,
    retorna JSON para actualizar la página.
    """
    import json
    data = request.get_json()
    texto = data.get('texto', '')
    
    if not texto or len(texto) < 20:
        return json.dumps({'error': 'Texto muy corto'}), 400
    
    # Detectar diagnósticos con el texto pegado
    diagnosticos_detectados_raw = detectar_diagnosticos_en_texto(texto)
    
    # Preparar diagnósticos
    db = get_db()
    diagnosticos_resultado = []
    sintomas_derivados = set()
    
    for d_raw in diagnosticos_detectados_raw:
        d_nombre = d_raw['nombre']
        d_sintomas = d_raw['sintomas']
        
        d_bd = db.execute('SELECT id FROM diagnosticos WHERE lower(descripcion) = ?', 
                         (d_nombre.lower(),)).fetchone()
        d_id = d_bd['id'] if d_bd else None
        
        diagnosticos_resultado.append({
            'nombre': d_nombre,
            'id': d_id,
            'sintomas': d_sintomas,
            'nuevo': not d_id
        })
        
        for sintoma in d_sintomas:
            sintomas_derivados.add(normalizar(sintoma))
    
    # Detectar síntomas
    sintomas_db = db.execute('SELECT id, nombre FROM sintomas').fetchall()
    
    sintomas_directos = set()
    for s in sintomas_db:
        # Búsqueda de palabra COMPLETA con flexibilidad de plurales
        patron = crear_patron_flexible_plural(s['nombre'].lower())
        if re.search(patron, texto.lower()):
            sintomas_directos.add(normalizar(s['nombre']))
    
    # Extraer con heurística
    sugestiones_heuristica = extraer_sugeridos_de_texto_avanzado(texto)
    for s in sugestiones_heuristica:
        sintomas_directos.add(normalizar(s))
    
    # Unir y filtrar
    todos_sugeridos = list(sintomas_derivados.union(sintomas_directos))
    todos_sugeridos.sort()
    
    diagnosticos_normalizados = set(normalizar(d['nombre']) for d in diagnosticos_resultado)
    todos_sugeridos = [s for s in todos_sugeridos if s not in diagnosticos_normalizados]
    
    # Normalizar síntomas
    todos_sugeridos = normalizar_sintomas_lista(todos_sugeridos)
    
    # ===== FILTRAR SÍNTOMAS RECHAZADOS =====
    todos_sugeridos = [s for s in todos_sugeridos if normalizar(s) not in INDICACIONES_RECHAZADAS]
    
    # ===== FILTRAR EFECTOS SECUNDARIOS =====
    efectos_sec = detectar_efectos_secundarios_en_texto(texto)
    todos_sugeridos = [s for s in todos_sugeridos if normalizar(s) not in efectos_sec]
    
    # Preparar síntomas finales
    sintomas_resultado = []
    for s_norm in todos_sugeridos:
        s_norm_busqueda = normalizar(s_norm)
        encontrado = next((x for x in sintomas_db if normalizar(x['nombre']) == s_norm_busqueda), None)
        
        if encontrado:
            sintomas_resultado.append({
                'label': encontrado['nombre'],
                'id': encontrado['id'],
                'nuevo': False
            })
        else:
            sintomas_resultado.append({
                'label': s_norm,
                'id': None,
                'nuevo': True
            })
    
    db.close()
    
    return json.dumps({
        'diagnosticos': diagnosticos_resultado,
        'sintomas': sintomas_resultado,
        'success': True
    })

@app.route('/sugerir-sintomas/guardar/<int:med_id>', methods=['POST'])
def guardar_seleccion(med_id):
    db = get_db()
    
    # ===== PROCESAR DIAGNÓSTICOS =====
    diagnosticos_items = request.form.getlist('diagnostico')
    for dit in diagnosticos_items:
        if not dit:
            continue
        
        if dit.startswith('dx:'):
            diag_id = int(dit.split(':',1)[1])
        elif dit.startswith('new:'):
            diag_nombre = dit.split(':',1)[1]
            # Verificar si ya existe ANTES de insertar
            existente = db.execute('SELECT id FROM diagnosticos WHERE lower(descripcion) = ?', (diag_nombre.lower(),)).fetchone()
            if existente:
                diag_id = existente['id']
            else:
                cur = db.execute('INSERT INTO diagnosticos (descripcion) VALUES (?)', (diag_nombre,))
                diag_id = cur.lastrowid
        else:
            continue
        
        db.execute('INSERT OR IGNORE INTO diagnostico_medicamento (diagnostico_id, medicamento_id) VALUES (?, ?)', 
                  (diag_id, med_id))
        
        # Obtener síntomas del diagnóstico
        diag_nombre_norm = None
        for d_nombre, d_sintomas in REGLAS_DIAGNOSTICOS.items():
            d_bd = db.execute('SELECT descripcion FROM diagnosticos WHERE id = ?', (diag_id,)).fetchone()
            if d_bd:
                if d_nombre.lower() == d_bd['descripcion'].lower():
                    diag_nombre_norm = d_nombre
                    break
        
        if not diag_nombre_norm:
            d_bd = db.execute('SELECT descripcion FROM diagnosticos WHERE id = ?', (diag_id,)).fetchone()
            if d_bd:
                diag_nombre_norm = d_bd['descripcion']
        
        # Crear relaciones diagnóstico-síntoma
        if diag_nombre_norm and diag_nombre_norm in REGLAS_DIAGNOSTICOS:
            sintomas_del_diag = REGLAS_DIAGNOSTICOS[diag_nombre_norm]
            for s_nombre in sintomas_del_diag:
                # Usar INSERT OR IGNORE para evitar UNIQUE constraint
                db.execute('INSERT OR IGNORE INTO sintomas (nombre, descripcion_lower) VALUES (?, ?)', 
                          (s_nombre, s_nombre.lower()))
                # Recuperar el ID (sea nuevo o existente)
                s_bd = db.execute('SELECT id FROM sintomas WHERE lower(nombre) = ?', (s_nombre.lower(),)).fetchone()
                if s_bd:
                    s_id = s_bd['id']
                    db.execute('INSERT OR IGNORE INTO diagnostico_sintoma (diagnostico_id, sintoma_id) VALUES (?, ?)', 
                              (diag_id, s_id))

    # ===== PROCESAR SÍNTOMAS =====
    items = request.form.getlist('sintoma')
    libre = request.form.get('sintoma')
    if libre and libre.strip():
        items.append(libre.strip())
    
    print(f"\n🔍 DEBUGG - Procesando síntomas para medicamento {med_id}:")
    print(f"   Items recibidos: {items}")

    for it in items:
        if not it:
            continue
        
        print(f"\n   Procesando: {it}")
        
        if it.startswith('id:'):
            sid = int(it.split(':',1)[1])
            print(f"   → Síntoma existente, ID: {sid}")
        elif it.startswith('new:'):
            label = it.split(':',1)[1]
            # Usar INSERT OR IGNORE para evitar UNIQUE constraint
            db.execute('INSERT OR IGNORE INTO sintomas (nombre, descripcion_lower) VALUES (?, ?)', (label, label.lower()))
            # Recuperar el ID (sea nuevo o existente)
            resultado = db.execute('SELECT id FROM sintomas WHERE lower(nombre) = ?', (label.lower(),)).fetchone()
            if resultado:
                sid = resultado['id']
                print(f"   → Síntoma '{label}', ID: {sid}")
            else:
                print(f"   ⚠️ Error: No se pudo obtener ID para '{label}'")
                continue
        else:
            label = it.strip()
            if not label:
                continue
            # Usar INSERT OR IGNORE para evitar UNIQUE constraint
            db.execute('INSERT OR IGNORE INTO sintomas (nombre, descripcion_lower) VALUES (?, ?)', (label, label.lower()))
            # Recuperar el ID
            resultado = db.execute('SELECT id FROM sintomas WHERE lower(nombre) = ?', (label.lower(),)).fetchone()
            if resultado:
                sid = resultado['id']
                print(f"   → Síntoma '{label}', ID: {sid}")
            else:
                print(f"   ⚠️ Error: No se pudo obtener ID para '{label}'")
                continue
        
        # Insertar relación medicamento-síntoma
        print(f"   → Insertando relación: med={med_id}, sintoma={sid}")
        db.execute('INSERT OR IGNORE INTO medicamento_sintoma (medicamento_id, sintoma_id) VALUES (?, ?)', (med_id, sid))
    
    print(f"\n✅ Finalizando guardado...")

    db.commit()
    
    # ===== VERIFICAR QUÉ SE GUARDÓ =====
    print(f"\n🔍 VERIFICACIÓN FINAL - Síntomas guardados para medicamento {med_id}:")
    guardados = db.execute(
        'SELECT s.id, s.nombre FROM sintomas s INNER JOIN medicamento_sintoma ms ON s.id = ms.sintoma_id WHERE ms.medicamento_id = ?',
        (med_id,)
    ).fetchall()
    
    print(f"   Total guardados: {len(guardados)}")
    for s in guardados:
        print(f"   ✅ ID {s[0]}: {s[1]}")
    
    db.close()
    return redirect('/sugerir-sintomas/ver/' + str(med_id))


# ---------------------- RUN ----------------------
if __name__ == '__main__':
    print('Iniciando micro-servicio de sugerencia de síntomas...')
    print('Asegúrate de tener medicamentos.db en la misma carpeta.')
    app.run(debug=True, host='0.0.0.0', port=5001)