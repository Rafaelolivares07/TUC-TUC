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

    # ========== ÓSEO/NUTRICIONAL ==========
    'osteoporosis': ['debilidad ósea', 'dolor óseo', 'fracturas frecuentes', 'pérdida de altura'],
    'raquitismo': ['debilidad ósea', 'deformidades óseas', 'dolor óseo', 'crecimiento deficiente'],
    'osteomalacia': ['dolor óseo', 'debilidad muscular', 'fracturas', 'dolor de espalda'],
    'deficiencia de vitamina d': ['debilidad muscular', 'dolor óseo', 'fatiga', 'depresión'],
    'deficiencia de vitamina c': ['fatiga', 'debilidad', 'encías sangrantes', 'anemia'],
    'deficiencia de vitamina b12': ['fatiga', 'debilidad', 'hormigueo', 'anemia'],
    'deficiencia de calcio': ['debilidad ósea', 'calambres musculares', 'hormigueo', 'fatiga'],
    'deficiencia de hierro': ['fatiga', 'debilidad', 'palidez', 'anemia'],

    # ========== INFECCIONES OFTÁLMICAS ==========
    'conjuntivitis': ['ojos rojos', 'secreción ocular', 'lagrimeo', 'picazón en los ojos', 'sensibilidad a la luz'],
    'conjuntivitis bacteriana': ['ojos rojos', 'secreción ocular', 'lagrimeo', 'picazón en los ojos'],
    'queratitis': ['dolor ocular', 'visión borrosa', 'ojos rojos', 'sensibilidad a la luz', 'lagrimeo'],
    'blefaritis': ['párpados inflamados', 'enrojecimiento de párpados', 'comezón en párpados', 'costras en pestañas'],

    # ========== INFECCIONES SISTÉMICAS GRAVES ==========
    'septicemia': ['fiebre alta', 'escalofríos', 'presión arterial baja', 'confusión', 'taquicardia'],
    'meningitis': ['fiebre alta', 'dolor de cabeza severo', 'rigidez de cuello', 'náusea', 'vómito', 'confusión'],
    'peritonitis': ['dolor abdominal severo', 'fiebre', 'náusea', 'vómito', 'distensión abdominal'],
    'infección urinaria': ['dolor al orinar', 'orina turbia', 'orina con sangre', 'urgencia urinaria', 'fiebre'],
    'infecciones urinarias complicadas': ['dolor al orinar', 'fiebre alta', 'dolor lumbar', 'orina turbia'],

    # ========== INFECCIONES RESPIRATORIAS ESPECÍFICAS ==========
    'fibrosis quística': ['tos crónica', 'mucosidad espesa', 'dificultad respiratoria', 'infecciones pulmonares recurrentes'],
    'infección por pseudomonas': ['fiebre', 'tos productiva', 'dificultad respiratoria', 'mucosidad verde'],
    'infecciones pulmonares crónicas': ['tos persistente', 'mucosidad', 'dificultad respiratoria', 'fiebre recurrente'],

    # ========== OTROS ==========
    'diabetes': ['sed excesiva', 'orina frecuente', 'hambre extrema', 'fatiga'],
    'anemia': ['fatiga', 'debilidad', 'palidez', 'dificultad respiratoria'],
    'alergia': ['reacción alérgica', 'comezón', 'enrojecimiento', 'estornudos'],
    'hipoparatiroidismo': ['calambres musculares', 'hormigueo', 'espasmos', 'fatiga'],
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

    # Detectar patrones de prevención/tratamiento para suplementos
    patrones_prevencion = [
        r'prevenir\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'prevención\s+de\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'prevención\s+del\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'tratar\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'tratamiento\s+de\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'tratamiento\s+del\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'usado\s+para\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'usada\s+para\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'indicado\s+para\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
        r'indicada\s+para\s+([a-záéíóúñ\s]+?)(?:\.|,|;|y\s)',
    ]

    for patron in patrones_prevencion:
        matches = re.finditer(patron, t, re.IGNORECASE)
        for match in matches:
            enfermedad_mencionada = match.group(1).strip().lower()
            # Buscar si esta enfermedad está en REGLAS_DIAGNOSTICOS
            for enfermedad, sintomas in REGLAS_DIAGNOSTICOS.items():
                if enfermedad in enfermedad_mencionada or enfermedad_mencionada in enfermedad:
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
        'debilidad muscular': ['debilidad muscular', 'músculos débiles'],
        'dolor óseo': ['dolor óseo', 'dolor de huesos'],
        'debilidad ósea': ['debilidad ósea', 'huesos débiles'],
        'fracturas frecuentes': ['fracturas frecuentes', 'fracturas'],
        'calambres musculares': ['calambres musculares', 'calambres'],
        'hormigueo': ['hormigueo', 'entumecimiento'],
        'encías sangrantes': ['encías sangrantes', 'sangrado de encías'],
        'palidez': ['palidez', 'piel pálida'],
        'anemia': ['anemia', 'bajo nivel de hierro'],
        'depresión': ['depresión', 'tristeza persistente'],
        'espasmos': ['espasmos', 'contracciones involuntarias'],
        'deformidades óseas': ['deformidades óseas', 'huesos deformados'],
        'crecimiento deficiente': ['crecimiento deficiente', 'crecimiento lento'],
        'pérdida de altura': ['pérdida de altura', 'reducción de estatura'],
        'dolor de espalda': ['dolor de espalda', 'lumbalgia'],

        # Síntomas oftálmicos
        'ojos rojos': ['ojos rojos', 'enrojecimiento ocular', 'conjuntiva roja'],
        'secreción ocular': ['secreción ocular', 'legañas', 'pus en los ojos'],
        'lagrimeo': ['lagrimeo', 'ojos llorosos', 'lágrimas excesivas'],
        'picazón en los ojos': ['picazón en los ojos', 'ojos que pican', 'comezón ocular'],
        'dolor ocular': ['dolor ocular', 'dolor en los ojos', 'dolor de ojos'],
        'visión borrosa': ['visión borrosa', 'vista borrosa', 'visión nublada'],
        'sensibilidad a la luz': ['sensibilidad a la luz', 'fotofobia', 'molestia con luz'],
        'párpados inflamados': ['párpados inflamados', 'párpados hinchados', 'inflamación de párpados'],
        'enrojecimiento de párpados': ['enrojecimiento de párpados', 'párpados rojos'],
        'comezón en párpados': ['comezón en párpados', 'párpados que pican'],
        'costras en pestañas': ['costras en pestañas', 'pestañas con costras'],

        # Síntomas sistémicos graves
        'fiebre alta': ['fiebre alta', 'fiebre elevada', 'temperatura muy alta'],
        'escalofríos': ['escalofríos', 'temblores', 'tiritona'],
        'presión arterial baja': ['presión arterial baja', 'hipotensión', 'presión baja'],
        'confusión': ['confusión', 'desorientación', 'alteración mental'],
        'taquicardia': ['taquicardia', 'ritmo cardíaco acelerado', 'palpitaciones'],
        'rigidez de cuello': ['rigidez de cuello', 'cuello rígido', 'rigidez nucal'],
        'distensión abdominal': ['distensión abdominal', 'abdomen distendido', 'hinchazón abdominal'],

        # Síntomas urinarios
        'dolor al orinar': ['dolor al orinar', 'ardor al orinar', 'micción dolorosa'],
        'orina turbia': ['orina turbia', 'orina opaca', 'orina con aspecto turbio'],
        'orina con sangre': ['orina con sangre', 'hematuria', 'sangre en orina'],
        'urgencia urinaria': ['urgencia urinaria', 'necesidad urgente de orinar', 'urgencia miccional'],
        'dolor lumbar': ['dolor lumbar', 'dolor de espalda baja', 'dolor en los riñones'],

        # Síntomas respiratorios específicos
        'tos crónica': ['tos crónica', 'tos persistente', 'tos de larga duración'],
        'tos productiva': ['tos productiva', 'tos con flema', 'tos con expectoración'],
        'mucosidad espesa': ['mucosidad espesa', 'flema espesa', 'moco espeso'],
        'mucosidad verde': ['mucosidad verde', 'flema verde', 'esputo verde'],
        'infecciones pulmonares recurrentes': ['infecciones pulmonares recurrentes', 'infecciones de pulmón repetidas'],
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
