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
    'acceso intravenoso': ['administración de líquidos', 'extracción de muestras', 'hidratación intravenosa', 'suministro de medicamentos'],
    'accidente cerebrovascular': ['derrame cerebral', 'evento cerebrovascular isquémico', 'ictus', 'infarto cerebral'],
    'accidente isquémico transitorio': ['ait', 'isquemia cerebral transitoria', 'mini derrame'],
    'aclarar piel': ['hiperpigmentación', 'manchas oscuras', 'melasma', 'tono irregular'],
    'acné': ['comedones', 'enrojecimiento', 'inflamación', 'pápulas', 'pústulas'],
    'acné cosmético': ['brotes', 'comedones', 'espinillas', 'granos', 'puntos negros'],
    'acumulación de ácido láctico': ['agotamiento muscular', 'dolor muscular', 'fatiga muscular', 'recuperación post-ejercicio'],
    'administración de medicamentos intravenosos': ['infusión de fármacos', 'suministro de medicamentos', 'terapia intravenosa'],
    'after sun': ['enrojecimiento post-solar', 'piel quemada', 'quemaduras solares'],
    'alergia': ['comezón', 'enrojecimiento', 'estornudos', 'hinchazón', 'reacción alérgica'],
    'alergia al látex': ['intolerancia al látex', 'reacción alérgica al látex', 'sensibilidad al látex'],
    'alopecia': ['calvicie', 'debilitamiento del cabello', 'pérdida de cabello'],
    'amigdalitis': ['amígdalas inflamadas', 'dificultad al tragar', 'dolor de garganta', 'fiebre'],
    'anemia': ['debilidad', 'dificultad respiratoria', 'fatiga', 'mareo', 'palidez'],
    'anestesia local': ['adormecimiento local', 'bloqueo de dolor', 'insensibilidad temporal'],
    'angina': ['dificultad respiratoria', 'dolor en el pecho', 'mareo', 'opresión torácica', 'sudoración'],
    'ansiedad': ['inquietud', 'nerviosismo', 'palpitaciones', 'sudoración', 'temblores'],
    'anti-edad': ['arrugas', 'envejecimiento prematuro', 'flacidez', 'líneas de expresión', 'pérdida de firmeza'],
    'antiarrugas': ['arrugas', 'líneas de expresión', 'líneas finas', 'patas de gallo'],
    'antibioticoterapia intravenosa': ['administración de antibióticos', 'terapia antibiótica parenteral'],
    'anticoagulación': ['moretones fáciles', 'riesgo de sangrado', 'sangrado de encías'],
    'anticoncepción': ['control natal', 'método anticonceptivo', 'planificación familiar', 'prevención de embarazo'],
    'anticonceptivo': ['control de natalidad', 'método de barrera', 'prevención de embarazo', 'protección contra embarazo'],
    'anticonceptivo hormonal': ['control hormonal', 'prevención de embarazo', 'regulación menstrual'],
    'anticonceptivo oral': ['control natal', 'prevención de embarazo', 'píldora anticonceptiva'],
    'antienvejecimiento': ['anti-edad', 'líneas de expresión', 'reducción de arrugas', 'rejuvenecimiento'],
    'antiinflamatorio cosmético': ['enrojecimiento', 'inflamación de piel', 'irritación'],
    'antioxidantes': ['antienvejecimiento', 'protección celular', 'radicales libres'],
    'antiséptico': ['desinfección', 'eliminación de gérmenes', 'prevención de infecciones', 'prevención de infección'],
    'antitranspirante': ['exceso de sudor', 'hiperhidrosis', 'sudoración excesiva'],
    'arritmia': ['desmayo', 'dificultad respiratoria', 'dolor en el pecho', 'fatiga', 'latidos irregulares', 'mareo', 'palpitaciones', 'síncope'],
    'artritis': ['dolor articular', 'hinchazón', 'inflamación', 'limitación de movimiento', 'rigidez matutina'],
    'artrosis': ['crujidos', 'deformidad', 'dolor articular', 'limitación de movimiento', 'rigidez'],
    'asma': ['dificultad para respirar', 'dificultad respiratoria', 'opresión torácica', 'sibilancias', 'tos nocturna'],
    'astringente': ['brillo excesivo', 'exceso de sebo', 'piel grasa', 'poros dilatados'],
    'aterosclerosis': ['dificultad respiratoria', 'dolor en el pecho', 'entumecimiento', 'mareo'],
    'aterotrombosis': ['eventos aterotrombóticos', 'prevención aterotrombótica', 'trombosis arterial'],
    'balanitis candidiásica': ['enrojecimiento del glande', 'inflamación del pene', 'picazón en el glande', 'secreción blanquecina'],
    'blanqueamiento dental': ['aclarado dental', 'dientes blancos', 'estética dental'],
    'blefaritis': ['comezón en párpados', 'costras en pestañas', 'enrojecimiento de párpados', 'párpados inflamados'],
    'brillo capilar': ['cabello opaco', 'falta de brillo en cabello'],
    'brillo facial': ['exceso de sebo', 'piel grasa', 'zona t brillante'],
    'bronquitis': ['dificultad respiratoria', 'mucosidad', 'producción de flema', 'sibilancias', 'tos'],
    'bursitis': ['dolor articular', 'hinchazón', 'inflamación', 'limitación de movimiento'],
    'cabello graso': ['cabello oleoso', 'cuero cabelludo graso', 'exceso de grasa capilar', 'seborrea capilar'],
    'cabello seco': ['cabello deshidratado', 'cabello quebradizo', 'cabello áspero', 'falta de brillo', 'falta de hidratación capilar', 'resequedad capilar'],
    'calambres menstruales': ['cólicos abdominales', 'dolor menstrual', 'dolor pélvico'],
    'calenturas': ['ampollas en la boca', 'hormigueo en labios', 'llagas en los labios'],
    'calmar piel': ['enrojecimiento', 'inflamación', 'irritación', 'sensibilidad'],
    'candidiasis cutánea': ['descamación', 'enrojecimiento', 'picazón', 'piel húmeda', 'sarpullido'],
    'candidiasis vulvovaginal': ['ardor vaginal', 'enrojecimiento genital', 'flujo vaginal blanco', 'irritación vaginal', 'picazón vaginal'],
    'caspa': ['dermatitis seborreica', 'descamación del cuero cabelludo', 'escamas', 'picazón del cuero cabelludo', 'picazón en cuero cabelludo'],
    'cataratas': ['dificultad nocturna', 'opacidad del cristalino', 'sensibilidad a luz', 'visión borrosa'],
    'caída de cabello': ['alopecia', 'debilitamiento capilar', 'pérdida de cabello'],
    'caída del cabello': ['alopecia', 'calvicie', 'debilitamiento capilar', 'pérdida de cabello'],
    'cefalea': ['dolor de cabeza', 'fatiga', 'mareo', 'tensión'],
    'celulitis': ['lipodistrofia', 'nódulos de grasa', 'piel de naranja', 'textura irregular en muslos', 'tratamiento de celulitis'],
    'cicatrices': ['cicatrización', 'marcas en piel', 'queloides', 'regeneración cutánea'],
    'cistitis': ['ardor al orinar', 'dolor suprapúbico', 'orina frecuente', 'urgencia urinaria'],
    'citomegalovirus': ['dolor muscular', 'fatiga', 'fiebre', 'inflamación de ganglios'],
    'cmv': ['debilidad', 'dolor muscular', 'fatiga', 'fiebre'],
    'colitis': ['cólicos', 'diarrea con sangre', 'dolor abdominal', 'inflamación intestinal'],
    'colostomía': ['control de olores', 'manejo de drenaje', 'prevención de irritación', 'protección de piel periestoma', 'recolección de efluentes'],
    'condón': ['anticonceptivo de barrera', 'preservativo', 'prevención de embarazo', 'protección sexual'],
    'congestión nasal en bebés': ['higiene nasal', 'mocos en bebé', 'nariz tapada en lactante'],
    'conjuntivitis': ['comezón', 'enrojecimiento ocular', 'lagrimeo', 'ojos rojos', 'picazón en los ojos', 'secreción ocular', 'sensibilidad a la luz', 'sensibilidad a luz'],
    'conjuntivitis bacteriana': ['lagrimeo', 'ojos rojos', 'picazón en los ojos', 'secreción ocular'],
    'contracepción de emergencia': ['anticoncepción postcoital', 'prevención de embarazo no deseado'],
    'control de diabetes': ['manejo de diabetes', 'prevención de complicaciones', 'regulación de glucosa'],
    'control de impurezas': ['exceso de grasa', 'impurezas', 'piel grasa', 'poros obstruidos'],
    'control de natalidad': ['control natal', 'planificación familiar', 'prevención de embarazo'],
    'convulsiones': ['convulsiones', 'espasmos musculares', 'pérdida de conciencia', 'sacudidas involuntarias'],
    'costra láctea': ['dermatitis seborreica infantil', 'escamas en cuero cabelludo de bebé'],
    'coágulos sanguíneos': ['calor en la zona', 'dolor localizado', 'enrojecimiento', 'hinchazón'],
    'crisis epilépticas': ['convulsiones', 'espasmos musculares', 'pérdida de conciencia', 'rigidez muscular'],
    'cuidado de manos': ['manos agrietadas', 'manos secas', 'resequedad en manos'],
    'cuidado de ostomía': ['discreción', 'prevención de irritación', 'protección de piel periestoma', 'recolección de efluentes', 'vaciado controlado'],
    'cuidado de pies': ['callos', 'durezas', 'pies secos', 'talones agrietados'],
    'cuidado del cordón umbilical': ['antisepsia umbilical', 'limpieza del ombligo', 'prevención de onfalitis'],
    'culebrilla': ['ampollas', 'ardor en la piel', 'dolor intenso', 'erupción cutánea'],
    'curación de heridas': ['cicatrización', 'cierre de heridas', 'regeneración de tejido'],
    'cólico infantil': ['cólicos del lactante', 'dolor abdominal en bebé', 'gases en bebé'],
    'cólicos abdominales': ['dolor intermitente', 'dolor tipo cólico', 'espasmos abdominales'],
    'daño al nervio óptico': ['puntos ciegos', 'pérdida de visión', 'visión borrosa'],
    'daño nervioso': ['debilidad muscular', 'dolor nervioso', 'entumecimiento', 'hormigueo'],
    'daño por radicales libres': ['deterioro de tejidos', 'envejecimiento prematuro', 'fatiga'],
    'debilitamiento del sistema inmunitario': ['debilidad', 'fatiga', 'infecciones frecuentes', 'recuperación lenta'],
    'deficiencia de calcio': ['calambres musculares', 'debilidad ósea', 'deficiencia de calcio', 'fatiga', 'hormigueo', 'osteopenia', 'suplementación de calcio'],
    'deficiencia de hierro': ['anemia', 'anemia ferropénica', 'debilidad', 'deficiencia de hierro', 'fatiga', 'palidez', 'suplementación de hierro'],
    'deficiencia de vitamina b12': ['anemia', 'anemia perniciosa', 'debilidad', 'deficiencia de b12', 'fatiga', 'hormigueo', 'suplementación b12'],
    'deficiencia de vitamina b6': ['anemia', 'confusión', 'debilidad', 'depresión', 'fatiga', 'hormigueo', 'sistema inmunitario debilitado'],
    'deficiencia de vitamina c': ['anemia', 'debilidad', 'deficiencia de vitamina c', 'encías sangrantes', 'escorbuto', 'fatiga', 'suplementación vitamina c'],
    'deficiencia de vitamina d': ['debilidad muscular', 'deficiencia de vitamina d', 'depresión', 'dolor óseo', 'fatiga', 'insuficiencia de vitamina d', 'suplementación de vitamina d'],
    'deficiencia de vitamina e': ['debilidad', 'debilidad muscular', 'deterioro del sistema inmunitario', 'hormigueo', 'infecciones recurrentes', 'problemas de visión'],
    'deficiencia de ácido fólico': ['anemia megaloblástica', 'deficiencia de folato', 'suplementación ácido fólico'],
    'deficiencia nutricional': ['debilidad', 'fatiga', 'palidez', 'pérdida de peso', 'sistema inmunitario debilitado'],
    'deficiencia vitamínica': ['carencia nutricional', 'déficit vitamínico', 'falta de vitaminas', 'suplementación vitamínica'],
    'deficiencias vitamínicas': ['debilidad', 'deterioro del sistema inmunitario', 'fatiga', 'hormigueo'],
    'dentición': ['dolor de encías en bebé', 'molestias por dentición', 'salida de dientes'],
    'depresión': ['falta de motivación', 'fatiga', 'insomnio', 'pérdida de apetito', 'tristeza persistente'],
    'dermatitis': ['comezón', 'descamación', 'enrojecimiento', 'inflamación', 'irritación'],
    'dermatitis del pañal': ['irritación por pañal', 'pañalitis', 'rozadura de pañal', 'sarpullido de pañal'],
    'deshidratación': ['pérdida de líquidos', 'rehidratación oral', 'sales de rehidratación', 'suero oral'],
    'desinfección': ['antiséptico', 'eliminación de bacterias', 'higiene'],
    'desinfección de heridas': ['antisepsia', 'limpieza de heridas', 'prevención de infección'],
    'desodorante': ['antitranspirante', 'control de olor corporal', 'mal olor axilar', 'olor corporal', 'protección contra sudor', 'sudoración'],
    'desparasitación': ['eliminación de parásitos', 'tratamiento antiparasitario', 'vermífugo'],
    'despigmentante': ['hiperpigmentación', 'manchas oscuras', 'melasma', 'pecas'],
    'diabetes': ['fatiga', 'hambre extrema', 'orina frecuente', 'pérdida de peso', 'sed excesiva', 'visión borrosa'],
    'diarrea': ['deshidratación', 'diarrea', 'dolor abdominal', 'evacuaciones frecuentes'],
    'digestión lenta': ['digestión difícil', 'malestar digestivo', 'pesadez estomacal', 'sensación de llenura'],
    'disfunción eréctil': ['impotencia', 'problemas de erección', 'salud sexual masculina'],
    'dismenorrea': ['cólicos menstruales', 'dolor abdominal', 'dolor menstrual', 'náusea durante menstruación'],
    'dispepsia': ['dolor abdominal superior', 'eructos', 'malestar estomacal', 'náusea', 'sensación de llenura'],
    'dispepsia funcional': ['digestión lenta', 'indigestión', 'malestar estomacal', 'pesadez estomacal'],
    'distensión abdominal': ['abdomen distendido', 'gases', 'hinchazón abdominal', 'sensación de llenura'],
    'dolor abdominal': ['cólicos', 'dolor de estómago', 'dolor en el abdomen', 'malestar abdominal'],
    'dolor crónico': ['dolor persistente', 'fatiga', 'limitación de movimiento', 'rigidez'],
    'dolor muscular post-ejercicio': ['dolor muscular', 'fatiga muscular', 'malestar muscular', 'recuperación muscular'],
    'dolor preoperatorio': ['ansiedad preoperatoria', 'dolor antes de procedimiento', 'molestia anticipada'],
    'eczema': ['ampollas', 'comezón intensa', 'descamación', 'enrojecimiento', 'inflamación'],
    'elasticidad': ['falta de tonicidad', 'piel flácida', 'pérdida de elasticidad'],
    'embolia pulmonar': ['dificultad respiratoria', 'dolor en el pecho', 'mareo', 'taquicardia', 'tos con sangre'],
    'enfermedad arterial periférica': ['claudicación intermitente', 'dolor en piernas al caminar', 'problemas de circulación en piernas'],
    'enfermedades de transmisión sexual': ['enfermedades venéreas', 'ets', 'infecciones de transmisión sexual', 'its'],
    'entrenamiento intenso': ['dolor muscular post-ejercicio', 'fatiga muscular', 'recuperación deportiva'],
    'epilepsia': ['confusión', 'convulsiones', 'crisis epilépticas', 'espasmos musculares', 'pérdida de conciencia'],
    'episodios maníacos': ['euforia', 'hiperactividad', 'impulsividad', 'insomnio'],
    'epoc': ['cansancio', 'dificultad respiratoria', 'producción de flema', 'sibilancias', 'tos crónica'],
    'equilibrio de ph': ['desequilibrio cutáneo', 'irritación', 'piel sensible'],
    'esguince': ['dolor', 'hematoma', 'inestabilidad', 'inflamación', 'limitación de movimiento'],
    'espasmos intestinales': ['cólicos', 'dolor abdominal tipo cólico', 'dolor intermitente'],
    'estreñimiento': ['dificultad para defecar', 'distensión abdominal', 'dolor abdominal', 'estreñimiento'],
    'estrés oxidativo': ['debilidad', 'deterioro celular', 'envejecimiento prematuro', 'fatiga'],
    'estrías': ['atenuación de estrías', 'estrías blancas', 'estrías rojas', 'marcas de estiramiento', 'prevención de estrías'],
    'exfoliación': ['células muertas', 'piel opaca', 'poros obstruidos', 'textura irregular'],
    'extracción de muestras sanguíneas': ['análisis de sangre', 'laboratorio clínico', 'toma de muestras de sangre'],
    'faringitis': ['dificultad al tragar', 'dolor de garganta', 'enrojecimiento', 'garganta irritada', 'inflamación de garganta'],
    'fatiga muscular': ['agotamiento muscular', 'cansancio muscular', 'dolor muscular', 'recuperación muscular'],
    'fibrilación auricular': ['falta de aire', 'fatiga', 'latidos irregulares', 'mareo', 'palpitaciones irregulares'],
    'fibrosis quística': ['dificultad respiratoria', 'infecciones pulmonares recurrentes', 'mucosidad espesa', 'tos crónica'],
    'fiebre infantil': ['antipirético pediátrico', 'temperatura elevada en niños'],
    'firmeza': ['falta de firmeza', 'piel colgante', 'piel flácida', 'pérdida de elasticidad'],
    'fortalecimiento capilar': ['cabello débil', 'cabello quebradizo', 'puntas abiertas'],
    'fortalecimiento de uñas': ['crecimiento de uñas', 'uñas débiles', 'uñas quebradizas'],
    'fortalecimiento inmunológico': ['estimulación inmunológica', 'mejora de defensas', 'refuerzo inmune'],
    'fractura': ['deformidad', 'dolor severo', 'hematoma', 'imposibilidad de movimiento', 'inflamación'],
    'gastritis': ['acidez', 'ardor estomacal', 'dolor abdominal', 'náusea', 'vómito'],
    'gastroenteritis': ['deshidratación', 'diarrea', 'dolor abdominal', 'náusea', 'vómito'],
    'gingivitis': ['enfermedad periodontal', 'inflamación de encías', 'sangrado de encías'],
    'glaucoma': ['dolor ocular', 'halos alrededor de luces', 'halos visuales', 'presión ocular elevada', 'pérdida de visión periférica', 'visión borrosa', 'visión periférica reducida'],
    'gota': ['articulación metatarsofalángica', 'ataque agudo de gota', 'crisis gotosa', 'depositos de urato', 'primer dedo del pie', 'tofáceos', 'ácido úrico'],
    'gripe': ['cansancio', 'dolor de garganta', 'dolor muscular', 'escalofríos', 'fiebre alta', 'tos'],
    'hemangioma': ['lesión cutánea roja', 'mancha roja en la piel', 'tumor vascular benigno'],
    'hemangiomas infantiles': ['mancha roja en la piel', 'marca de nacimiento', 'protuberancia roja', 'tumor vascular'],
    'hemangiomas superficiales': ['lesión cutánea', 'mancha roja en la piel', 'protuberancia roja'],
    'hepatitis': ['dolor abdominal superior', 'fatiga', 'ictericia', 'náusea', 'orina oscura'],
    'heridas quirúrgicas': ['cuidado de suturas', 'curación postoperatoria', 'prevención de infección quirúrgica'],
    'heridas superficiales': ['abrasiones', 'cortadas', 'rasguños', 'raspones'],
    'herpes': ['ampollas', 'ardor', 'comezón', 'dolor', 'inflamación local'],
    'herpes genital': ['ampollas genitales', 'ardor al orinar', 'dolor genital', 'lesiones genitales', 'picazón genital'],
    'herpes labial': ['ampollas en la boca', 'ardor bucal', 'hormigueo en labios', 'llagas en los labios'],
    'herpes simple': ['ampollas', 'ardor en la piel', 'dolor localizado', 'lesiones cutáneas', 'picazón'],
    'herpes zóster': ['ampollas', 'ardor en la piel', 'dolor intenso', 'erupción cutánea', 'picazón'],
    'hidratación corporal': ['descamación en cuerpo', 'piel seca en cuerpo', 'resequedad corporal'],
    'hidratación de piel': ['descamación', 'hidratación cutánea', 'humectación', 'piel seca', 'piel áspera', 'resequedad', 'suavidad de piel', 'tirantez'],
    'hidratación intravenosa': ['administración de líquidos', 'hidratación parenteral', 'reposición de líquidos'],
    'hidratación profunda': ['piel agrietada', 'piel muy seca', 'resequedad severa'],
    'higiene bucal': ['cuidado de dientes', 'limpieza dental', 'prevención de caries', 'salud bucal'],
    'higiene dental': ['cuidado dental', 'enjuague bucal', 'hilo dental', 'limpieza dental'],
    'higiene personal': ['aseo', 'cuidado personal', 'limpieza'],
    'higiene íntima': ['cuidado íntimo', 'higiene genital', 'limpieza vaginal', 'pH balanceado'],
    'hipertensión': ['dificultad respiratoria', 'dolor de cabeza', 'fatiga', 'mareo', 'presión arterial elevada'],
    'hipertensión ocular': ['dolor ocular leve', 'presión ocular elevada', 'sin síntomas aparentes'],
    'hipertiroidismo': ['intolerancia al calor', 'nerviosismo', 'palpitaciones', 'pérdida de peso', 'tremor'],
    'hipoparatiroidismo': ['calambres musculares', 'espasmos', 'fatiga', 'hormigueo'],
    'hipotiroidismo': ['aumento de peso', 'depresión', 'fatiga', 'intolerancia al frío', 'piel seca'],
    'hongos en uñas': ['infección fúngica de uñas', 'onicomicosis', 'uñas amarillas'],
    'hongos vaginales': ['ardor vaginal', 'flujo vaginal blanco', 'irritación vaginal', 'picazón vaginal'],
    'humectación': ['deshidratación cutánea', 'falta de humedad', 'piel seca', 'resequedad'],
    'ileostomía': ['control de olores', 'manejo de drenaje', 'prevención de fugas', 'protección de piel periestoma', 'recolección de efluentes'],
    'incontinencia': ['nicturia', 'pérdida involuntaria de orina', 'urgencia urinaria'],
    'incontinencia fecal': ['control de fugas', 'discreción', 'protección de piel', 'recolección de efluentes'],
    'infarto de miocardio': ['ataque cardíaco', 'dolor torácico', 'evento cardiovascular', 'infarto al corazón'],
    'infecciones por hongos': ['descamación', 'enrojecimiento', 'irritación', 'mal olor', 'picazón'],
    'infecciones pulmonares crónicas': ['dificultad respiratoria', 'fiebre recurrente', 'mucosidad', 'tos persistente'],
    'infecciones recurrentes': ['fatiga', 'infecciones frecuentes', 'sistema inmunitario debilitado'],
    'infecciones superficiales de la piel': ['descamación', 'enrojecimiento', 'irritación cutánea', 'picazón'],
    'infecciones urinarias complicadas': ['dolor al orinar', 'dolor lumbar', 'fiebre alta', 'orina turbia'],
    'infecciones vaginales': ['candidiasis vaginal', 'hongos vaginales', 'vaginosis'],
    'infección bacterial': ['dolor', 'enrojecimiento', 'fiebre', 'inflamación', 'pus'],
    'infección bacteriana de piel': ['calor local', 'dolor', 'enrojecimiento', 'inflamación', 'pus'],
    'infección fúngica': ['comezón', 'descamación', 'enrojecimiento', 'maceramiento', 'olor característico'],
    'infección fúngica general': ['comezón', 'descamación', 'enrojecimiento', 'inflamación'],
    'infección parasitaria': ['comezón', 'debilitamiento', 'diarrea', 'dolor abdominal'],
    'infección por pseudomonas': ['dificultad respiratoria', 'fiebre', 'mucosidad verde', 'tos productiva'],
    'infección urinaria': ['ardor al orinar', 'dolor abdominal bajo', 'dolor al orinar', 'fiebre', 'orina con sangre', 'orina frecuente', 'orina turbia', 'turbidez', 'urgencia urinaria'],
    'infección vaginal por hongos': ['ardor vaginal', 'flujo vaginal', 'molestias al orinar', 'picazón vaginal'],
    'infección viral': ['cansancio', 'congestión nasal', 'dolor muscular', 'fiebre', 'tos'],
    'inflamación': ['calor local', 'dolor', 'enrojecimiento', 'hinchazón', 'inflamación'],
    'inflamación del glande': ['dolor en el pene', 'enrojecimiento del glande', 'irritación genital', 'picazón genital'],
    'insomnio': ['cansancio diurno', 'dificultad para dormir', 'insomnio', 'sueño no reparador'],
    'insuficiencia cardíaca': ['arritmia', 'cansancio', 'dificultad respiratoria', 'hinchazón de pies'],
    'insuficiencia enzimática digestiva': ['deficiencia de enzimas', 'digestión lenta', 'mala digestión', 'pesadez estomacal'],
    'intestino irritable': ['diarrea', 'distensión abdominal', 'dolor abdominal', 'estreñimiento', 'gases'],
    'irregularidad menstrual': ['amenorrea', 'ciclo menstrual irregular', 'trastornos menstruales'],
    'labios secos': ['descamación de labios', 'labios agrietados', 'resequedad labial'],
    'laringitis': ['dificultad al hablar', 'dolor de garganta', 'pérdida de voz', 'ronquera', 'tos seca'],
    'lesión muscular menor': ['dolor muscular', 'inflamación muscular', 'recuperación muscular', 'tensión muscular'],
    'limpieza antiséptica': ['desinfección', 'eliminación de gérmenes', 'higiene'],
    'limpieza de heridas': ['antiséptico para heridas', 'cuidado de lesiones', 'desinfección de heridas'],
    'limpieza de piel': ['impurezas', 'limpieza facial', 'residuos', 'suciedad'],
    'limpieza facial': ['cuidado de rostro', 'eliminación de impurezas', 'higiene facial', 'limpieza de piel', 'purificación de piel'],
    'lubricación íntima': ['comodidad íntima', 'lubricante sexual', 'relaciones sexuales'],
    'luminosidad': ['falta de brillo', 'falta de luminosidad', 'piel opaca', 'tono apagado'],
    'mal aliento': ['aliento desagradable', 'halitosis', 'higiene bucal'],
    'mala digestión': ['digestión lenta', 'dispepsia', 'indigestión', 'malestar digestivo', 'pesadez estomacal'],
    'malnutrición': ['bajo peso', 'deficiencia nutricional', 'desnutrición'],
    'manchas en la piel': ['aclarado de piel', 'decoloración', 'hiperpigmentación', 'manchas oscuras', 'manchas solares', 'melasma', 'uniformidad del tono'],
    'manchas superficiales': ['decoloración superficial', 'hiperpigmentación leve', 'manchas leves'],
    'manejo de estoma': ['control de olores', 'discreción', 'prevención de fugas', 'protección de piel', 'recolección de efluentes'],
    'matificante': ['brillo excesivo', 'exceso de sebo', 'piel grasa'],
    'medición de oxigenación': ['oximetría', 'pulsioximetría', 'saturación de oxígeno'],
    'medición de presión arterial': ['control de presión', 'monitoreo hipertensión', 'tensiómetro'],
    'medición de temperatura': ['control de fiebre', 'detección de fiebre', 'termometría'],
    'meningitis': ['confusión', 'dolor de cabeza severo', 'fiebre alta', 'náusea', 'rigidez de cuello', 'vómito'],
    'menopausia': ['cambios hormonales', 'climaterio', 'sofocos', 'síntomas menopáusicos'],
    'migraña': ['dolor de cabeza severo', 'náusea', 'sensibilidad a luz', 'visión borrosa', 'vómito'],
    'monitoreo de glucosa': ['control de diabetes', 'glucometría', 'medición de azúcar'],
    'método de barrera': ['anticonceptivo de barrera', 'barrera anticonceptiva', 'protección física'],
    'nebulización': ['administración de medicamentos inhalados', 'terapia respiratoria', 'tratamiento de asma'],
    'nefritis': ['dolor en flanco', 'fatiga', 'fiebre', 'hinchazón', 'orina anormal'],
    'neumonía': ['dificultad respiratoria', 'dolor en el pecho', 'escalofríos', 'fiebre', 'tos productiva'],
    'neuralgia posherpética': ['ardor persistente', 'dolor crónico', 'dolor nervioso', 'sensibilidad en la piel'],
    'neuropatía': ['debilidad muscular', 'dolor neuropático', 'entumecimiento', 'hormigueo'],
    'neuropatía periférica': ['debilidad muscular', 'dolor nervioso', 'entumecimiento', 'hormigueo', 'sensación de ardor'],
    'nutrición capilar': ['cabello dañado', 'cabello maltratado', 'falta de nutrientes'],
    'nutrición de piel': ['falta de nutrientes', 'piel maltratada', 'piel seca'],
    'nutrición enteral': ['alimentación por sonda', 'fórmulas enterales', 'suplementación nutricional'],
    'obesidad': ['aumento de peso', 'dificultad para perder peso', 'dificultad respiratoria', 'dolor articular', 'exceso de peso', 'sobrepeso'],
    'ojeras': ['bolsas bajo ojos', 'círculos oscuros', 'hinchazón periocular'],
    'omega 3': ['salud cardiovascular', 'suplementación omega 3', 'ácidos grasos esenciales'],
    'osteomalacia': ['debilidad muscular', 'dolor de espalda', 'dolor óseo', 'fracturas'],
    'osteoporosis': ['debilidad ósea', 'dolor óseo', 'fracturas frecuentes', 'fragilidad ósea', 'pérdida de altura'],
    'ostomía permanente': ['adaptación a dispositivo', 'manejo postquirúrgico', 'protección de piel periestoma', 'recolección de efluentes'],
    'pancreatitis': ['dolor abdominal severo', 'dolor en espalda', 'fiebre', 'náusea', 'vómito'],
    'parkinson': ['inestabilidad', 'lentitud de movimiento', 'rigidez muscular', 'temblores'],
    'parásitos intestinales': ['antiparasitario', 'desparasitación', 'lombrices', 'oxiuros'],
    'pediculosis': ['infestación de piojos', 'piojos', 'tratamiento de piojos'],
    'peritonitis': ['distensión abdominal', 'dolor abdominal severo', 'fiebre', 'náusea', 'vómito'],
    'pesadez estomacal': ['digestión lenta', 'estómago pesado', 'malestar después de comer', 'sensación de llenura'],
    'picaduras de insectos': ['alivio de picazón por picadura', 'mordeduras', 'reacción a picadura'],
    'pie de atleta': ['descamación de pies', 'enrojecimiento de pies', 'grietas en la piel de pies', 'mal olor en pies', 'picazón entre los dedos'],
    'pie diabético': ['heridas en pie diabético', 'prevención de amputación', 'úlceras diabéticas'],
    'piel grasa': ['control de brillo', 'control de sebo', 'exceso de grasa', 'piel oleosa', 'producción de grasa', 'seborrea'],
    'piel mixta': ['combinación de tipos de piel', 'piel mixta a grasa', 'zona T grasa'],
    'piel seca': ['aspereza', 'comezón por sequedad', 'descamación', 'deshidratación de piel', 'resequedad', 'sequedad cutánea', 'tirantez', 'xerosis'],
    'piel sensible': ['enrojecimiento', 'intolerancia', 'irritación', 'sensibilidad'],
    'pitiriasis versicolor': ['cambios de color en la piel', 'descamación leve', 'manchas claras u oscuras en la piel', 'picazón leve'],
    'planificación familiar': ['anticonceptivo', 'control natal', 'prevención de embarazo'],
    'poliisopreno': ['alternativa sintética', 'material sin látex', 'para sensibilidad al látex'],
    'poros dilatados': ['poros abiertos', 'poros visibles', 'textura irregular'],
    'poros obstruidos': ['comedones', 'poros dilatados', 'puntos negros', 'taponamiento de poros'],
    'preservativo': ['anticonceptivo de barrera', 'condón', 'protección sexual'],
    'presión intraocular elevada': ['dolor ocular', 'presión en los ojos', 'visión borrosa'],
    'prevención cardiovascular': ['prevención de eventos cardiovasculares', 'protección cardíaca'],
    'prevención de acné': ['control de brotes', 'prevención de granitos', 'prevención de imperfecciones'],
    'prevención de acv': ['confusión', 'debilidad', 'dolor de cabeza', 'mareo'],
    'prevención de ataques cerebrales': ['confusión', 'debilidad', 'dolor de cabeza', 'mareo'],
    'prevención de coágulos': ['agregación plaquetaria', 'prevención de trombosis', 'riesgo de coagulación'],
    'prevención de embarazo': ['anticonceptivo', 'control natal', 'planificación familiar', 'protección contra embarazo'],
    'prevención de ets': ['preservativos', 'protección contra enfermedades de transmisión sexual', 'protección contra enfermedades venéreas', 'protección contra ets', 'sexo seguro'],
    'prevención de eventos cardiovasculares': ['prevención de ictus', 'prevención de infarto', 'protección cardiovascular'],
    'prevención de infarto': ['dolor en el pecho', 'falta de aire', 'fatiga', 'mareo'],
    'prevención de its': ['protección contra enfermedades de transmisión sexual', 'protección contra its', 'sexo seguro'],
    'prevención de osteoporosis': ['fortalecimiento óseo', 'prevención de fracturas'],
    'prevención de stroke': ['confusión', 'debilidad', 'dolor de cabeza', 'mareo'],
    'prevención de trombosis': ['anticoagulación preventiva', 'prevención de coágulos'],
    'probióticos': ['equilibrio intestinal', 'flora intestinal', 'salud digestiva'],
    'procedimiento dental': ['anestesia dental', 'bloqueo dental', 'procedimiento odontológico'],
    'procedimiento oftálmico': ['anestesia ocular', 'anestesia oftálmica', 'procedimiento de ojo'],
    'procedimiento quirúrgico': ['anestesia local necesaria', 'anestesia requerida', 'cirugía menor'],
    'procedimiento urológico': ['anestesia uretral', 'cateterismo', 'sondaje'],
    'prostatitis': ['dificultad para orinar', 'dolor al orinar', 'dolor pélvico', 'fiebre'],
    'protección antioxidante': ['prevención de envejecimiento', 'protección celular'],
    'protección contra embarazo': ['anticonceptivo', 'método anticonceptivo', 'prevención de embarazo'],
    'protección contra enfermedades de transmisión sexual': ['prevención de ets', 'prevención de its', 'sexo seguro'],
    'protección de la piel': ['barrera protectora', 'cuidado de piel', 'protección contra resequedad'],
    'protección labial': ['labios agrietados', 'labios secos', 'resequedad labial'],
    'protección sexual': ['barrera de protección', 'prevención de ets', 'prevención de its', 'sexo seguro'],
    'protección solar': ['bloqueador solar', 'daño solar', 'fotoenvejecimiento', 'prevención de quemaduras solares', 'protección contra rayos solares', 'protección uv', 'quemaduras solares', 'rayos uv'],
    'protector solar labial': ['cuidado labial solar', 'protección contra rayos uv en labios'],
    'prótesis valvulares': ['dificultad respiratoria', 'fatiga', 'palpitaciones'],
    'psoriasis': ['comezón', 'descamación plateada', 'dolor', 'enrojecimiento', 'placas gruesas'],
    'quemaduras leves': ['escaldaduras', 'quemadura solar', 'quemaduras de primer grado'],
    'quemaduras moderadas': ['ampollas por quemadura', 'quemaduras de segundo grado'],
    'queratitis': ['dolor ocular', 'lagrimeo', 'ojos rojos', 'sensibilidad a la luz', 'visión borrosa'],
    'quimioterapia': ['administración de quimioterapia', 'infusión de citostáticos', 'tratamiento oncológico'],
    'radiancia': ['falta de brillo', 'piel opaca', 'tono apagado'],
    'raquitismo': ['crecimiento deficiente', 'debilidad ósea', 'deformidades óseas', 'dolor óseo'],
    'reafirmante corporal': ['flacidez corporal', 'pérdida de firmeza en cuerpo'],
    'recuperación deportiva': ['descanso muscular', 'recuperación muscular', 'regeneración muscular', 'restauración de energía'],
    'reflujo en bebés': ['reflujo gastroesofágico', 'regurgitación', 'vómitos en lactante'],
    'reflujo gastroesofágico': ['acidez', 'ardor estomacal', 'regurgitación', 'tos crónica'],
    'reflujo gástrico': ['acidez', 'ardor estomacal', 'dificultad al tragar', 'dolor en el pecho', 'regurgitación'],
    'refuerzo energético': ['combatir fatiga', 'energía', 'vigor', 'vitalidad'],
    'rehidratación oral': ['electrolitos', 'reposición de líquidos', 'sales de rehidratación'],
    'rejuvenecimiento': ['envejecimiento de piel', 'piel madura', 'signos de edad'],
    'renovación celular': ['células muertas', 'piel opaca', 'textura irregular'],
    'reparación capilar': ['cabello dañado', 'cabello quebradizo', 'puntas abiertas'],
    'reparación de piel': ['cicatrices', 'daño solar', 'piel dañada', 'piel maltratada'],
    'repelente de insectos': ['prevención de picaduras', 'protección contra mosquitos', 'repelente de zancudos'],
    'repelente de piojos': ['pediculosis', 'prevención de piojos', 'tratamiento antipiojos'],
    'resequedad': ['descamación', 'falta de hidratación', 'piel seca', 'tirantez'],
    'resfriado': ['congestión nasal', 'dolor de garganta', 'estornudos', 'rinorrea', 'tos leve'],
    'riesgo cardiovascular': ['eventos cardiovasculares', 'prevención cardiovascular', 'protección cardíaca'],
    'rinitis': ['congestión nasal', 'estornudos', 'obstrucción nasal', 'picazón nasal', 'rinorrea'],
    'rosácea': ['enrojecimiento facial', 'rubor facial', 'vasos sanguíneos visibles'],
    'sarna': ['comezón intensa', 'escabiosis', 'infestación de ácaros', 'ácaros'],
    'sensibilidad al látex': ['alergia al látex', 'irritación por látex', 'reacción al látex'],
    'sensibilidad dental': ['dientes sensibles', 'dolor dental al frío', 'hipersensibilidad dental'],
    'sepsis': ['confusión', 'dolor muscular', 'fiebre alta', 'hipotensión', 'taquicardia'],
    'septicemia': ['confusión', 'escalofríos', 'fiebre alta', 'presión arterial baja', 'taquicardia'],
    'sequedad vaginal': ['atrofia vaginal', 'lubricación vaginal', 'menopausia'],
    'sii': ['cólicos', 'diarrea', 'distensión abdominal', 'dolor abdominal', 'estreñimiento'],
    'sin látex': ['alternativa al látex', 'libre de látex', 'para alergia al látex'],
    'sinusitis': ['cefalea sinusal', 'congestión nasal', 'dolor facial', 'mucosidad nasal espesa', 'presión sinusal'],
    'sobrecarga muscular': ['descanso muscular', 'dolor muscular', 'fatiga muscular', 'recuperación muscular'],
    'sobrepeso': ['aumento de peso', 'exceso de peso', 'obesidad'],
    'soporte nutricional': ['nutrición clínica', 'refuerzo nutricional', 'suplementación alimentaria'],
    'suavidad corporal': ['piel áspera en cuerpo', 'textura rugosa'],
    'suavizar la piel': ['aspereza', 'piel rugosa', 'piel áspera', 'textura irregular'],
    'suplementación nutricional': ['complemento alimenticio', 'multivitamínico', 'refuerzo nutricional'],
    'suplemento vitamínico': ['prevención de deficiencias', 'suplementación nutricional'],
    'síndrome coronario agudo': ['angina inestable', 'dolor torácico agudo', 'evento coronario'],
    'síndrome de colon irritable': ['diarrea', 'distensión abdominal', 'dolor abdominal', 'estreñimiento', 'gases'],
    'síndrome de intestino irritable': ['cambios en evacuaciones', 'cólicos', 'diarrea', 'distensión abdominal', 'dolor abdominal', 'estreñimiento', 'gases'],
    'síndrome premenstrual': ['cambios de ánimo', 'cólicos', 'dismenorrea', 'dolor menstrual', 'fatiga', 'hinchazón', 'irritabilidad', 'molestias premenstruales', 'spm'],
    'síntomas menstruales': ['calambres abdominales', 'cambios de ánimo', 'cólicos menstruales', 'dolor menstrual', 'fatiga durante menstruación'],
    'tendinitis': ['debilidad muscular', 'dolor en tendón', 'inflamación', 'limitación de movimiento'],
    'terapia intravenosa prolongada': ['acceso venoso prolongado', 'terapia parenteral', 'tratamiento a largo plazo'],
    'tinea corporis': ['descamación', 'enrojecimiento', 'manchas circulares en la piel', 'picazón'],
    'tinea cruris': ['enrojecimiento en la ingle', 'irritación genital', 'picazón en la ingle'],
    'tinea pedis': ['descamación de pies', 'enrojecimiento de pies', 'picazón entre los dedos', 'piel agrietada en pies'],
    'tiña': ['bordes elevados', 'descamación', 'enrojecimiento', 'manchas circulares en la piel', 'picazón'],
    'tiña de las manos': ['descamación en manos', 'enrojecimiento de manos', 'grietas en manos', 'picazón en manos'],
    'tiña del cuerpo': ['descamación', 'enrojecimiento', 'manchas circulares en la piel', 'picazón'],
    'tiña inguinal': ['descamación en área genital', 'enrojecimiento en la ingle', 'picazón en la ingle', 'sarpullido en la ingle'],
    'tonificar': ['falta de tono', 'piel flácida', 'pérdida de firmeza'],
    'transfusión de sangre': ['administración de hemoderivados', 'reposición de sangre', 'transfusión sanguínea'],
    'trastorno bipolar': ['cambios de ánimo', 'depresión', 'episodios maníacos', 'irritabilidad'],
    'trastorno funcional intestinal': ['diarrea', 'distensión abdominal', 'dolor abdominal', 'estreñimiento'],
    'trastorno por atracón': ['ansiedad por comida', 'comer en exceso', 'pérdida de control al comer'],
    'trastornos de la alimentación': ['ansiedad por comida', 'comer en exceso', 'pérdida de apetito', 'pérdida de peso'],
    'trastornos de motilidad intestinal': ['diarrea', 'distensión', 'dolor abdominal', 'estreñimiento'],
    'trastornos del control de impulsos': ['ansiedad', 'comportamiento compulsivo', 'impulsividad', 'irritabilidad'],
    'trastornos nerviosos periféricos': ['debilidad', 'entumecimiento', 'hormigueo', 'sensación de alfileres y agujas'],
    'tratamiento capilar': ['cuidado del cabello', 'fortalecimiento capilar', 'salud del cabello'],
    'trombosis': ['calor local', 'dolor', 'enrojecimiento', 'hinchazón', 'inflamación'],
    'trombosis venosa profunda': ['calor en la zona afectada', 'dolor en piernas', 'enrojecimiento en piernas', 'hinchazón de piernas'],
    'tuberculosis': ['debilidad general', 'dolor torácico', 'escalofríos', 'expectoración con sangre', 'fatiga extrema', 'fiebre nocturna', 'infección por Mycobacterium tuberculosis', 'pérdida de peso inexplicable', 'sudoración nocturna', 'tos persistente'],
    'tvp': ['dolor en piernas', 'enrojecimiento en piernas', 'hinchazón de piernas'],
    'unificar tono': ['decoloración', 'manchas', 'pigmentación desigual', 'tono irregular'],
    'urostomía': ['control de olores', 'manejo de drenaje urinario', 'protección de piel periestoma', 'recolección de orina'],
    'urticaria': ['comezón', 'enrojecimiento', 'habones', 'hinchazón', 'rash'],
    'vacunación': ['inmunización', 'prevención de infecciones', 'protección inmunológica'],
    'venopunción': ['canalización intravenosa', 'inserción de aguja', 'punción venosa'],
    'verrugas': ['crecimientos en piel', 'rugosidad', 'verruga plantar'],
    'válvulas cardíacas artificiales': ['dificultad respiratoria', 'fatiga', 'mareo', 'palpitaciones'],
    'úlcera péptica': ['acidez', 'ardor estomacal', 'dispepsia', 'dolor abdominal', 'sangrado digestivo'],
    'úlceras por presión': ['escaras', 'llagas por presión', 'úlceras de decúbito'],
    'úlceras venosas': ['heridas crónicas', 'llagas vasculares', 'úlceras en piernas'],
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

        # Síntomas neurológicos / epilepsia
        'convulsiones': ['convulsiones', 'convulsión', 'ataque epiléptico', 'ataques'],
        'crisis epilépticas': ['crisis epilépticas', 'crisis epiléptica', 'epilepsia'],
        'pérdida de conciencia': ['pérdida de conciencia', 'desmayo', 'pérdida del conocimiento'],
        'espasmos musculares': ['espasmos musculares', 'espasmo', 'contracciones musculares'],
        'rigidez muscular': ['rigidez muscular', 'músculos rígidos', 'tensión muscular'],
        'sacudidas involuntarias': ['sacudidas involuntarias', 'movimientos involuntarios', 'sacudidas'],

        # Síntomas psiquiátricos / trastorno bipolar
        'cambios de ánimo': ['cambios de ánimo', 'cambios de humor', 'inestabilidad emocional'],
        'episodios maníacos': ['episodios maníacos', 'manía', 'episodio maníaco'],
        'euforia': ['euforia', 'exceso de energía', 'hiperactividad emocional'],
        'hiperactividad': ['hiperactividad', 'exceso de actividad', 'inquietud extrema'],
        'irritabilidad': ['irritabilidad', 'irritación', 'mal humor'],

        # Síntomas de trastornos alimentarios
        'comer en exceso': ['comer en exceso', 'atracón', 'comer compulsivamente'],
        'pérdida de control al comer': ['pérdida de control al comer', 'comer sin control'],
        'ansiedad por comida': ['ansiedad por comida', 'ansiedad alimentaria'],
        'pérdida de apetito': ['pérdida de apetito', 'falta de apetito', 'inapetencia', 'anorexia'],
        'exceso de peso': ['exceso de peso', 'sobrepeso'],
        'aumento de peso': ['aumento de peso', 'subida de peso', 'incremento de peso'],
        'dificultad para perder peso': ['dificultad para perder peso', 'no logra bajar de peso'],
        'impulsividad': ['impulsividad', 'actuar sin pensar', 'falta de control'],
        'comportamiento compulsivo': ['comportamiento compulsivo', 'compulsión', 'conducta compulsiva'],

        # Síntomas de infecciones virales por herpes
        'dolor intenso': ['dolor intenso', 'dolor fuerte', 'dolor agudo'],
        'erupción cutánea': ['erupción cutánea', 'erupción', 'brote en la piel', 'sarpullido'],
        'ampollas': ['ampollas', 'vesículas', 'burbujas en la piel'],
        'ardor en la piel': ['ardor en la piel', 'quemazón en la piel', 'sensación de quemadura'],
        'lesiones genitales': ['lesiones genitales', 'llagas genitales', 'úlceras genitales'],
        'ampollas genitales': ['ampollas genitales', 'vesículas genitales'],
        'dolor genital': ['dolor genital', 'molestia genital'],
        'picazón genital': ['picazón genital', 'comezón genital', 'prurito genital'],
        'llagas en los labios': ['llagas en los labios', 'úlceras labiales', 'heridas en labios'],
        'ampollas en la boca': ['ampollas en la boca', 'vesículas bucales', 'ampollas labiales'],
        'ardor bucal': ['ardor bucal', 'quemazón en la boca', 'ardor en labios'],
        'hormigueo en labios': ['hormigueo en labios', 'cosquilleo en labios'],
        'lesiones cutáneas': ['lesiones cutáneas', 'llagas en la piel', 'úlceras cutáneas'],
        'dolor localizado': ['dolor localizado', 'dolor en zona específica'],
        'dolor crónico': ['dolor crónico', 'dolor persistente', 'dolor de larga duración'],
        'dolor nervioso': ['dolor nervioso', 'dolor neuropático', 'neuralgia'],
        'ardor persistente': ['ardor persistente', 'quemazón continua'],
        'sensibilidad en la piel': ['sensibilidad en la piel', 'piel sensible', 'hipersensibilidad cutánea'],
        'inflamación de ganglios': ['inflamación de ganglios', 'ganglios inflamados', 'adenopatía'],
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
