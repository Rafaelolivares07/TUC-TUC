from .db import get_db_connection


CLIENTE_SUFFIXES = ('.tuc-tuc.co',)
EXCLUIR_SUBDOMINIOS = {'www', 'bistro', 'api', 'admin', 'mail', 'rockola'}
HOSTS_PLATAFORMA = {'tuc-tuc.co', 'www.tuc-tuc.co', 'admin.tuc-tuc.co', 'rockola.tuc-tuc.co', 'localhost', '127.0.0.1', '0.0.0.0'}


def normalizar_host(host):
    host = (host or '').split(':')[0].strip().lower().rstrip('.')
    if host.startswith('www.'):
        host = host[4:]
    return host


def normalizar_dominio_publico(valor):
    dominio = (valor or '').strip().lower()
    dominio = dominio.replace('https://', '').replace('http://', '')
    dominio = dominio.split('/')[0].split('?')[0].split('#')[0]
    dominio = dominio.split(':')[0].strip().rstrip('.')
    if dominio.startswith('www.'):
        dominio = dominio[4:]
    return dominio


def slug_subdominio_publico(host):
    host = normalizar_host(host)
    for suffix in CLIENTE_SUFFIXES:
        if host.endswith(suffix):
            sub = host[:-len(suffix)]
            if sub and sub not in EXCLUIR_SUBDOMINIOS and '.' not in sub:
                return sub
            return ''
    return ''


def asegurar_tabla_dominios_negocio(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dominios_negocio (
            id SERIAL PRIMARY KEY,
            tipo_negocio VARCHAR(30) NOT NULL,
            negocio_id INTEGER NOT NULL,
            dominio VARCHAR(255) NOT NULL UNIQUE,
            activo BOOLEAN DEFAULT TRUE,
            verificado BOOLEAN DEFAULT FALSE,
            principal BOOLEAN DEFAULT FALSE,
            estado VARCHAR(30) DEFAULT 'pendiente',
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_dominios_negocio_lookup
        ON dominios_negocio (tipo_negocio, LOWER(dominio))
    """)
    conn.commit()


def _alternativas_host(host):
    host = normalizar_host(host)
    if not host:
        return []
    alternativas = [host]
    if host.startswith('www.'):
        alternativas.append(host[4:])
    else:
        alternativas.append(f'www.{host}')
    return list(dict.fromkeys(alternativas))


def resolver_negocio_por_host(host):
    host = normalizar_host(host)
    slug = slug_subdominio_publico(host)
    if slug:
        return {'slug': slug, 'tipo_negocio': None, 'origen': 'subdominio'}
    if host in HOSTS_PLATAFORMA or '.' not in host:
        return None
    if any(host.endswith(suffix) for suffix in CLIENTE_SUFFIXES):
        return None

    alternativas = _alternativas_host(host)
    if not alternativas:
        return None

    conn = get_db_connection()
    try:
        asegurar_tabla_dominios_negocio(conn)
        row = conn.execute("""
            SELECT d.tipo_negocio, d.negocio_id,
                   COALESCE(t.slug, r.slug) AS slug
            FROM dominios_negocio d
            LEFT JOIN tiendas t
              ON d.tipo_negocio = 'tienda'
             AND t.id = d.negocio_id
             AND t.activo = TRUE
            LEFT JOIN restaurantes r
              ON d.tipo_negocio = 'restaurante'
             AND r.id = d.negocio_id
             AND r.activo = TRUE
            WHERE LOWER(d.dominio) = ANY(%s)
              AND COALESCE(d.activo, TRUE) = TRUE
              AND d.tipo_negocio IN ('tienda', 'restaurante')
              AND COALESCE(t.slug, r.slug) IS NOT NULL
            ORDER BY d.principal DESC, d.verificado DESC, d.id DESC
            LIMIT 1
        """, (alternativas,)).fetchone()
        if not row:
            return None
        return {
            'slug': row['slug'],
            'tipo_negocio': row['tipo_negocio'],
            'negocio_id': row['negocio_id'],
            'origen': 'dominio',
        }
    finally:
        conn.close()


def resolver_slug_por_host(host, tipo_negocio):
    negocio = resolver_negocio_por_host(host)
    if not negocio:
        return ''
    if negocio.get('tipo_negocio') and negocio['tipo_negocio'] != tipo_negocio:
        return ''
    return negocio.get('slug') or ''
