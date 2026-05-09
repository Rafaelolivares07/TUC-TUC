import json
import os

from anthropic import Anthropic
from flask import Blueprint, jsonify, request

from ..db import get_db_connection

bp = Blueprint('pautas', __name__)

_tablas_listas = False


def _crear_tablas(conn):
    global _tablas_listas
    if _tablas_listas:
        return
    sqls = [
        """CREATE TABLE IF NOT EXISTS pautas (
            id SERIAL PRIMARY KEY,
            tienda_id INTEGER NOT NULL,
            mensaje_base TEXT,
            hook TEXT,
            producto_ids JSONB DEFAULT '[]',
            plataformas JSONB DEFAULT '[]',
            variantes JSONB DEFAULT '{}',
            scheduled_at TIMESTAMP,
            hora VARCHAR(20) DEFAULT 'recomendado',
            status VARCHAR(20) DEFAULT 'borrador',
            presupuesto NUMERIC(12,2),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS pauta_publicaciones (
            id SERIAL PRIMARY KEY,
            pauta_id INTEGER REFERENCES pautas(id) ON DELETE CASCADE,
            plataforma VARCHAR(30),
            contenido_adaptado JSONB DEFAULT '{}',
            external_id VARCHAR(255),
            posted_at TIMESTAMP,
            metrics_json JSONB DEFAULT '{}',
            created_at TIMESTAMP DEFAULT NOW()
        )""",
        """CREATE TABLE IF NOT EXISTS atribucion (
            id SERIAL PRIMARY KEY,
            pedido_id INTEGER,
            pauta_id INTEGER REFERENCES pautas(id) ON DELETE SET NULL,
            plataforma VARCHAR(30),
            fuente VARCHAR(50),
            created_at TIMESTAMP DEFAULT NOW()
        )""",
    ]
    for sql in sqls:
        conn.execute(sql)
    conn.commit()
    _tablas_listas = True


def _get_tienda_id(slug):
    conn = get_db_connection()
    _crear_tablas(conn)
    row = conn.execute("SELECT id FROM tiendas WHERE slug = %s", (slug,)).fetchone()
    conn.close()
    return row['id'] if row else None


@bp.route('/api/tienda/<slug>/pauta', methods=['POST'])
def crear_pauta(slug):
    tienda_id = _get_tienda_id(slug)
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Tienda no encontrada'})
    data = request.json or {}
    conn = get_db_connection()
    try:
        row = conn.execute("""
            INSERT INTO pautas (tienda_id, mensaje_base, producto_ids, plataformas, variantes, hora, scheduled_at, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
        """, (
            tienda_id,
            data.get('mensaje_base', ''),
            json.dumps(data.get('producto_ids', [])),
            json.dumps(data.get('plataformas', [])),
            json.dumps(data.get('variantes', {})),
            data.get('hora', 'recomendado'),
            data.get('scheduled_at'),
            'programada' if data.get('scheduled_at') else 'activa',
        )).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'pauta_id': row['id']})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pauta/borrador', methods=['POST'])
def guardar_borrador(slug):
    tienda_id = _get_tienda_id(slug)
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Tienda no encontrada'})
    data = request.json or {}
    conn = get_db_connection()
    try:
        row = conn.execute("""
            INSERT INTO pautas (tienda_id, mensaje_base, producto_ids, plataformas, status)
            VALUES (%s, %s, %s, %s, 'borrador') RETURNING id
        """, (
            tienda_id,
            data.get('mensaje_base', ''),
            json.dumps(data.get('producto_ids', [])),
            json.dumps(data.get('plataformas', [])),
        )).fetchone()
        conn.commit()
        return jsonify({'ok': True, 'pauta_id': row['id']})
    except Exception as e:
        conn.rollback()
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pauta/generar', methods=['POST'])
def generar_variantes(slug):
    tienda_id = _get_tienda_id(slug)
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Tienda no encontrada'})
    data = request.json or {}
    mensaje_base = data.get('mensaje_base', '').strip()
    plataformas = data.get('plataformas', ['instagram', 'tiktok', 'marketplace', 'whatsapp'])
    tono = data.get('tono', 'vendedor')
    if not mensaje_base:
        return jsonify({'ok': False, 'error': 'mensaje_base requerido'})

    tonos = {
        'vendedor': 'persuasivo, orientado a conversión, destaca beneficios y valor',
        'casual': 'amigable, cercano, como un amigo recomendando',
        'urgente': 'genera urgencia, escasez o tiempo limitado',
    }
    desc_tono = tonos.get(tono, tonos['vendedor'])

    prompt = f"""Adapta este mensaje de marketing para múltiples plataformas.
Tono: {desc_tono}
Mensaje base: {mensaje_base}
Plataformas requeridas: {', '.join(plataformas)}

Responde SOLO con JSON válido, sin texto adicional:
{{
  "instagram": {{"copy": "...", "hashtags": ["tag1","tag2"], "formato": "reel"}},
  "tiktok": {{"copy": "...", "hook": "primera línea que engancha en 3 segs", "formato": "vertical"}},
  "marketplace": {{"titulo": "...", "descripcion": "..."}},
  "whatsapp": {{"copy": "...", "cta": "texto del botón"}}
}}
Solo incluye las plataformas solicitadas."""

    try:
        client = Anthropic(api_key=os.environ.get('ANTHROPIC_API_KEY'))
        msg = client.messages.create(
            model='claude-haiku-4-5-20251001',
            max_tokens=1024,
            messages=[{'role': 'user', 'content': prompt}]
        )
        texto = msg.content[0].text.strip()
        if texto.startswith('```'):
            texto = texto.split('```')[1]
            if texto.startswith('json'):
                texto = texto[4:]
        variantes = json.loads(texto)
        return jsonify({'ok': True, 'variantes': variantes})
    except json.JSONDecodeError:
        return jsonify({'ok': False, 'error': 'Error parseando respuesta IA'})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})


@bp.route('/api/tienda/<slug>/pauta/kpis')
def kpis_pauta(slug):
    tienda_id = _get_tienda_id(slug)
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Tienda no encontrada'})
    conn = get_db_connection()
    try:
        row = conn.execute("""
            SELECT COUNT(*) as pedidos, COALESCE(SUM(p.total), 0) as ventas
            FROM atribucion a
            JOIN pedidos p ON p.id = a.pedido_id
            WHERE a.pauta_id IN (SELECT id FROM pautas WHERE tienda_id = %s)
              AND a.created_at >= NOW() - INTERVAL '7 days'
        """, (tienda_id,)).fetchone()
        return jsonify({
            'ok': True,
            'clics': 0,
            'ctr': None,
            'pedidos': row['pedidos'] if row else 0,
            'ventas': float(row['ventas']) if row else 0,
            'roas': None,
        })
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pauta/atribucion')
def atribucion_pauta(slug):
    tienda_id = _get_tienda_id(slug)
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Tienda no encontrada'})
    dias = int(request.args.get('dias', 30))
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT a.plataforma, a.fuente, p.total, p.estado, t.nombre as cliente
            FROM atribucion a
            JOIN pedidos p ON p.id = a.pedido_id
            JOIN terceros t ON t.id = p.tercero_id
            WHERE a.pauta_id IN (SELECT id FROM pautas WHERE tienda_id = %s)
              AND a.created_at >= NOW() - INTERVAL '%s days'
            ORDER BY a.created_at DESC LIMIT 20
        """ , (tienda_id, dias)).fetchall()
        ventas = []
        mix = {}
        for row in rows:
            plataforma = row['plataforma']
            ventas.append({
                'plataforma': plataforma,
                'fuente': row['fuente'],
                'fuente_display': (row['fuente'] or '').replace('_', ' ').title(),
                'total': float(row['total'] or 0),
                'estado': row['estado'] or '—',
                'cliente': row['cliente'] or '—',
                'producto': '—',
            })
            mix[plataforma] = mix.get(plataforma, 0) + 1
        return jsonify({'ok': True, 'ventas': ventas, 'mix': mix})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        conn.close()


@bp.route('/api/tienda/<slug>/pauta/calendario')
def calendario_pauta(slug):
    tienda_id = _get_tienda_id(slug)
    if not tienda_id:
        return jsonify({'ok': False, 'error': 'Tienda no encontrada'})
    conn = get_db_connection()
    try:
        rows = conn.execute("""
            SELECT id, mensaje_base, hook, plataformas, scheduled_at, status
            FROM pautas
            WHERE tienda_id = %s
              AND (scheduled_at >= NOW() - INTERVAL '7 days' OR status = 'activa')
            ORDER BY scheduled_at ASC NULLS LAST LIMIT 20
        """, (tienda_id,)).fetchall()
        pautas = []
        for row in rows:
            scheduled_at = row['scheduled_at']
            hora = scheduled_at.strftime('%a %d %H:%M') if scheduled_at else 'En vivo'
            plataformas = row['plataformas']
            if isinstance(plataformas, str):
                plataformas = json.loads(plataformas or '[]')
            pautas.append({
                'id': row['id'],
                'mensaje_base': (row['mensaje_base'] or '')[:60],
                'hook': row['hook'],
                'plataformas': plataformas,
                'hora': hora,
                'status': row['status'],
            })
        return jsonify({'ok': True, 'pautas': pautas})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})
    finally:
        conn.close()
