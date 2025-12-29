# -*- coding: utf-8 -*-
"""
Funciones auxiliares para procesamiento de texto y sugerencia de síntomas
Migrado desde sugerir_sintomas_flask.py
"""

import re

# =====================================================================
# REGLAS DE DIAGNÓSTICOS
# =====================================================================

REGLAS_DIAGNOSTICOS = {
    # ========== RESPIRATORIO ==========
    'bronquitis': ['tos', 'mucosidad', 'dificultad respiratoria', 'producción de flema', 'sibilancias'],
    'neumonía': ['fiebre', 'dolor en el pecho', 'dificultad respiratoria', 'tos productiva', 'escalofríos'],
    'asma': ['dificultad respiratoria', 'sibilancias', 'tos nocturna', 'opresión torácica'],
    'rinitis': ['congestión nasal', 'estornudos', 'rinorrea', 'picazón nasal'],
    'sinusitis': ['congestión nasal', 'dolor facial', 'mucosidad nasal espesa', 'presión sinusal'],
    'faringitis': ['dolor de garganta', 'dificultad al tragar', 'inflamación de garganta'],
    'amigdalitis': ['dolor de garganta', 'amígdalas inflamadas', 'dificultad al tragar', 'fiebre'],
    'resfriado': ['congestión nasal', 'estornudos', 'tos leve', 'dolor de garganta', 'rinorrea'],
    'gripe': ['fiebre alta', 'dolor muscular', 'cansancio', 'tos', 'dolor de garganta', 'escalofríos'],

    # ========== DIGESTIVO ==========
    'gastritis': ['dolor abdominal', 'acidez', 'ardor estomacal', 'náusea', 'vómito'],
    'úlcera péptica': ['dolor abdominal', 'acidez', 'dispepsia', 'ardor estomacal'],
    'gastroenteritis': ['diarrea', 'vómito', 'náusea', 'dolor abdominal', 'deshidratación'],
    'diarrea': ['diarrea', 'evacuaciones frecuentes', 'dolor abdominal'],
    'estreñimiento': ['estreñimiento', 'dificultad para defecar', 'dolor abdominal'],
    'colitis': ['diarrea con sangre', 'dolor abdominal', 'cólicos'],

    # ========== CARDIOVASCULAR ==========
    'hipertensión': ['presión arterial elevada', 'dolor de cabeza', 'mareo', 'fatiga'],
    'angina': ['dolor en el pecho', 'opresión torácica', 'dificultad respiratoria'],

    # ========== NEUROLÓGICO ==========
    'migraña': ['dolor de cabeza severo', 'náusea', 'sensibilidad a luz', 'vómito'],
    'cefalea': ['dolor de cabeza', 'tensión', 'mareo'],

    # ========== DERMATOLÓGICO ==========
    'dermatitis': ['enrojecimiento', 'comezón', 'inflamación', 'descamación'],
    'acné': ['pápulas', 'pústulas', 'comedones', 'inflamación'],
    'urticaria': ['rash', 'comezón', 'habones', 'enrojecimiento'],

    # ========== ARTICULAR ==========
    'artritis': ['dolor articular', 'inflamación', 'rigidez matutina', 'hinchazón'],
    'artrosis': ['dolor articular', 'rigidez', 'crujidos', 'limitación de movimiento'],

    # ========== OTROS ==========
    'diabetes': ['sed excesiva', 'orina frecuente', 'hambre extrema', 'fatiga'],
    'anemia': ['fatiga', 'debilidad', 'palidez', 'dificultad respiratoria'],
    'alergia': ['reacción alérgica', 'comezón', 'enrojecimiento', 'estornudos'],
}

# =====================================================================
# FUNCIONES AUXILIARES
# =====================================================================

def normalizar(s):
    """Normaliza texto a lowercase y elimina espacios"""
    if isinstance(s, list):
        return " ".join(str(x) for x in s).strip().lower()
    return str(s).strip().lower()


def detectar_negacion_en_contexto(texto, diagnostico):
    """Detecta si un diagnóstico está mencionado en contexto negativo"""
    negaciones = [
        f'no funciona contra {diagnostico}',
        f'no es efectivo para {diagnostico}',
        f'no se usa para {diagnostico}',
        f'no debe usarse para {diagnostico}',
        f'no trata {diagnostico}',
        f'no cura {diagnostico}',
        f'inefectivo contra {diagnostico}',
        f'no funciona en {diagnostico}',
        f'no sirve para {diagnostico}',
    ]
    texto_lower = texto.lower()
    for negacion in negaciones:
        if negacion in texto_lower:
            return True
    return False


def crear_patron_flexible_plural(palabra):
    """Crea patrón regex que acepta singular y plural"""
    palabra_escaped = re.escape(palabra)
    if len(palabra) > 2 and palabra[-1] == 'n' and palabra[-2] in 'óí':
        palabra_sin_acento = palabra[:-2] + palabra[-2].replace('ó', 'o').replace('í', 'i') + palabra[-1]
        palabra_sin_acento_escaped = re.escape(palabra_sin_acento)
        return r'\b(' + palabra_escaped + r'|' + palabra_sin_acento_escaped + r'es)\b'
    elif palabra[-1] in 'aeiouáéíóú':
        return r'\b' + palabra_escaped + r's?\b'
    else:
        return r'\b' + palabra_escaped + r'(es)?\b'


def detectar_efectos_secundarios_en_texto(texto):
    """Detecta efectos secundarios mencionados en el texto para filtrarlos"""
    if not texto:
        return set()
    t = texto.lower()
    efectos_secundarios = set()

    patrones_efectos = [
        r'puede causar\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'efectos secundarios\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'reacción adversa\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'no debe\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'evitar\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
        r'contraindicado\s+([a-záéíóúñ\s]+?)(?:\.|,|;)',
    ]

    for patron in patrones_efectos:
        matches = re.finditer(patron, t, re.IGNORECASE)
        for match in matches:
            sintoma_mencionado = match.group(1).strip().lower()
            if sintoma_mencionado and len(sintoma_mencionado) > 2:
                sintoma_norm = normalizar(sintoma_mencionado)
                efectos_secundarios.add(sintoma_norm)

    return efectos_secundarios


def normalizar_sintomas_lista(sintomas_lista):
    """Normaliza lista de síntomas y elimina duplicados por sinónimos"""
    if not sintomas_lista:
        return []

    sintomas_norm = {}
    sinonimos = {
        'dolor': ['dolor general', 'molestia'],
        'debilidad': ['debilitamiento'],
        'comezón': ['picazón', 'picor'],
        'inflamación': ['hinchazón'],
    }

    for s in sintomas_lista:
        s_norm = normalizar(s)
        clave = s_norm

        for principal, lista_sin in sinonimos.items():
            if s_norm == principal or s_norm in [normalizar(x) for x in lista_sin]:
                clave = principal
                break

        if clave not in sintomas_norm:
            sintomas_norm[clave] = s.strip().title() if len(s.strip()) > 0 else s

    return sorted(list(sintomas_norm.values()))


def validar_diagnostico(nombre_diagnostico, sintomas_lista):
    """Valida que un diagnóstico tenga suficientes síntomas"""
    if not sintomas_lista or len(sintomas_lista) < 2:
        return False
    return True


def detectar_diagnosticos_en_texto(texto):
    """Detecta diagnósticos mencionados en el texto"""
    if not texto:
        return []

    t = texto.lower()
    diagnosticos_detectados = []
    detectados_set = set()

    for diagnostico, sintomas in REGLAS_DIAGNOSTICOS.items():
        patron = crear_patron_flexible_plural(diagnostico)
        if re.search(patron, t) and diagnostico not in detectados_set:
            if detectar_negacion_en_contexto(texto, diagnostico):
                continue
            if validar_diagnostico(diagnostico, sintomas):
                diagnosticos_detectados.append({
                    'nombre': diagnostico,
                    'sintomas': sintomas
                })
                detectados_set.add(diagnostico)

    return diagnosticos_detectados


def extraer_sugeridos_de_texto_avanzado(texto):
    """Extrae síntomas sugeridos del texto usando heurísticas"""
    if not texto:
        return []

    t = texto.lower()
    sugeridos = set()

    # Extraer síntomas de diagnósticos detectados
    for enfermedad, sintomas in REGLAS_DIAGNOSTICOS.items():
        patron = r'\b' + re.escape(enfermedad) + r'\b'
        if re.search(patron, t):
            for s in sintomas:
                sugeridos.add(s)

    # Keywords de síntomas comunes
    sintomas_keywords = {
        'fiebre': ['fiebre', 'fever', 'temperatura elevada'],
        'náusea': ['náusea', 'nausea'],
        'vómito': ['vómito', 'vomit'],
        'diarrea': ['diarrea', 'diarrhea'],
        'dolor de cabeza': ['dolor de cabeza', 'headache', 'cefalea'],
        'fatiga': ['fatiga', 'fatigue', 'cansancio'],
        'mareo': ['mareo', 'dizziness', 'vértigo'],
        'tos': ['tos', 'cough'],
        'dolor de garganta': ['dolor de garganta', 'sore throat'],
        'congestión nasal': ['congestión nasal', 'nasal congestion'],
        'estornudos': ['estornud', 'sneez'],
        'comezón': ['comezón', 'picazón', 'itching', 'prurito'],
        'enrojecimiento': ['enrojecimiento', 'redness'],
        'hinchazón': ['hinchazón', 'swelling', 'edema'],
        'dolor muscular': ['dolor muscular', 'malestar muscular'],
    }

    for sintoma_principal, keywords in sintomas_keywords.items():
        for kw in keywords:
            patron_kw = r'\b' + re.escape(kw) + r'\b'
            if re.search(patron_kw, t):
                sugeridos.add(sintoma_principal)
                break

    # Filtrar efectos secundarios
    efectos_sec = detectar_efectos_secundarios_en_texto(texto)
    sugeridos = {s for s in sugeridos if normalizar(s) not in efectos_sec}

    return sorted(sugeridos)


def validar_texto_medicamento(texto, nombre_medicamento):
    """
    Valida si el texto procesado corresponde al medicamento indicado
    Retorna: (coincide: bool, confianza: int)
    """
    if not texto or not nombre_medicamento:
        return False, 0

    texto_lower = texto.lower()
    nombre_lower = nombre_medicamento.lower()

    # Extraer palabras clave del nombre del medicamento (sin dosis)
    nombre_limpio = re.sub(r'\d+\s*(mg|mcg|g|ml|%)', '', nombre_lower)
    nombre_limpio = re.sub(r'[^a-záéíóúñ\s]', ' ', nombre_limpio)
    palabras_medicamento = [p for p in nombre_limpio.split() if len(p) > 3]

    if not palabras_medicamento:
        return True, 50  # No podemos validar, pero dejamos continuar

    # Contar coincidencias
    coincidencias = 0
    for palabra in palabras_medicamento:
        if palabra in texto_lower:
            coincidencias += 1

    # Calcular confianza
    confianza = int((coincidencias / len(palabras_medicamento)) * 100)
    coincide = confianza >= 30  # Umbral: al menos 30% de coincidencia

    return coincide, confianza
