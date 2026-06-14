import secrets

from flask import request, session


def init_tablas_visitas_publicas(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS visitantes_publicos (
            id SERIAL PRIMARY KEY,
            tipo_negocio VARCHAR(30) NOT NULL,
            negocio_id INTEGER NOT NULL,
            visitante_token VARCHAR(90) NOT NULL,
            usuario_id INTEGER,
            primer_path TEXT,
            ultimo_path TEXT,
            user_agent TEXT,
            ip_primera VARCHAR(80),
            ip_ultima VARCHAR(80),
            visitas INTEGER DEFAULT 1,
            first_seen TIMESTAMP DEFAULT NOW(),
            last_seen TIMESTAMP DEFAULT NOW(),
            UNIQUE(tipo_negocio, negocio_id, visitante_token)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS visitas_publicas (
            id SERIAL PRIMARY KEY,
            tipo_negocio VARCHAR(30) NOT NULL,
            negocio_id INTEGER NOT NULL,
            visitante_id INTEGER REFERENCES visitantes_publicos(id) ON DELETE SET NULL,
            usuario_id INTEGER,
            recurso_tipo VARCHAR(50) NOT NULL DEFAULT 'portada',
            recurso_id INTEGER,
            titulo TEXT,
            detalle TEXT,
            path TEXT,
            referrer TEXT,
            ip VARCHAR(80),
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visitantes_publicos_negocio
        ON visitantes_publicos(tipo_negocio, negocio_id, last_seen DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visitas_publicas_negocio
        ON visitas_publicas(tipo_negocio, negocio_id, created_at DESC)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_visitas_publicas_recurso
        ON visitas_publicas(tipo_negocio, negocio_id, recurso_tipo, recurso_id)
    """)
    conn.commit()


def ip_cliente():
    reenviada = (request.headers.get('X-Forwarded-For') or '').split(',')[0].strip()
    return reenviada or request.remote_addr or ''


def registrar_visita_publica(
    conn,
    tipo_negocio,
    negocio_id,
    recurso_tipo='portada',
    recurso_id=None,
    titulo=None,
    detalle=None,
):
    init_tablas_visitas_publicas(conn)
    cookie_name = f'tt_visitante_{tipo_negocio}_{negocio_id}'
    token = request.cookies.get(cookie_name) or secrets.token_urlsafe(24)
    usuario_id = session.get('usuario_id') or session.get('chat_tercero_id')
    path = request.full_path.rstrip('?') or request.path
    referrer = request.referrer or ''
    user_agent = (request.headers.get('User-Agent') or '')[:1000]
    ip = ip_cliente()[:80]
    try:
        existente = conn.execute("""
            SELECT id
            FROM visitantes_publicos
            WHERE tipo_negocio = %s AND negocio_id = %s AND visitante_token = %s
        """, (tipo_negocio, negocio_id, token)).fetchone()
        es_nuevo = not bool(existente)
        if existente:
            visitante_id = existente['id']
            conn.execute("""
                UPDATE visitantes_publicos
                SET usuario_id = COALESCE(%s, usuario_id),
                    ultimo_path = %s,
                    user_agent = %s,
                    ip_ultima = %s,
                    visitas = COALESCE(visitas, 0) + 1,
                    last_seen = NOW()
                WHERE id = %s
            """, (usuario_id, path, user_agent, ip, visitante_id))
        else:
            row = conn.execute("""
                INSERT INTO visitantes_publicos
                    (tipo_negocio, negocio_id, visitante_token, usuario_id, primer_path,
                     ultimo_path, user_agent, ip_primera, ip_ultima)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                RETURNING id
            """, (tipo_negocio, negocio_id, token, usuario_id, path, path, user_agent, ip, ip)).fetchone()
            visitante_id = row['id']
        conn.execute("""
            INSERT INTO visitas_publicas
                (tipo_negocio, negocio_id, visitante_id, usuario_id, recurso_tipo, recurso_id,
                 titulo, detalle, path, referrer, ip, user_agent)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            tipo_negocio, negocio_id, visitante_id, usuario_id, recurso_tipo, recurso_id,
            titulo, detalle, path, referrer, ip, user_agent,
        ))
        conn.commit()
        return {'cookie_name': cookie_name, 'token': token, 'nuevo': es_nuevo}
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"[visitas publicas] {tipo_negocio}/{negocio_id}: {e}")
        return {'cookie_name': cookie_name, 'token': token, 'nuevo': False}


def respuesta_con_visitante(response, visita):
    if visita and visita.get('cookie_name') and visita.get('token'):
        response.set_cookie(
            visita['cookie_name'],
            visita['token'],
            max_age=60 * 60 * 24 * 365 * 2,
            httponly=True,
            samesite='Lax',
            secure=request.is_secure,
        )
    return response


def listar_visitas_publicas(conn, tipo_negocio, negocio_id, limite_visitantes=80, limite_visitas=160):
    init_tablas_visitas_publicas(conn)
    visitantes = conn.execute("""
        SELECT v.id, v.visitante_token, v.usuario_id, v.primer_path, v.ultimo_path,
               v.ip_primera, v.ip_ultima, v.visitas, v.first_seen, v.last_seen,
               v.user_agent, t.nombre AS usuario_nombre, t.telefono AS usuario_telefono
        FROM visitantes_publicos v
        LEFT JOIN terceros t ON t.id = v.usuario_id
        WHERE v.tipo_negocio = %s AND v.negocio_id = %s
        ORDER BY v.last_seen DESC
        LIMIT %s
    """, (tipo_negocio, negocio_id, limite_visitantes)).fetchall()
    visitas = conn.execute("""
        SELECT vi.id, vi.visitante_id, vi.usuario_id, vi.recurso_tipo AS tipo,
               vi.recurso_id, vi.titulo, vi.detalle, vi.path, vi.referrer, vi.ip,
               vi.user_agent, vi.created_at, t.nombre AS usuario_nombre,
               vp.visitante_token
        FROM visitas_publicas vi
        LEFT JOIN terceros t ON t.id = vi.usuario_id
        LEFT JOIN visitantes_publicos vp ON vp.id = vi.visitante_id
        WHERE vi.tipo_negocio = %s AND vi.negocio_id = %s
        ORDER BY vi.created_at DESC
        LIMIT %s
    """, (tipo_negocio, negocio_id, limite_visitas)).fetchall()
    visitantes_out = []
    for v in visitantes:
        item = dict(v)
        item['id'] = f"g-{v['id']}"
        item['first_seen'] = str(v['first_seen']) if v['first_seen'] else ''
        item['last_seen'] = str(v['last_seen']) if v['last_seen'] else ''
        visitantes_out.append(item)
    visitas_out = []
    for v in visitas:
        item = dict(v)
        item['id'] = f"g-{v['id']}"
        item['visitante_id'] = f"g-{v['visitante_id']}" if v['visitante_id'] else None
        item['created_at'] = str(v['created_at']) if v['created_at'] else ''
        visitas_out.append(item)
    return visitantes_out, visitas_out
