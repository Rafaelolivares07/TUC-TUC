import os
import subprocess
import tempfile
from flask import Blueprint, request, Response, stream_with_context

bp = Blueprint('backup', __name__)

_TOKEN = 'TucTucBackup_2026'


@bp.route('/api/backup/tuctuc')
def backup_tuctuc():
    if request.args.get('token') != _TOKEN:
        return 'Acceso denegado', 403

    db_url = os.environ.get('DATABASE_URL', '')
    # DATABASE_URL formato: postgresql://user:pass@host:port/dbname
    # Extraer componentes para pg_dump
    try:
        from urllib.parse import urlparse
        p = urlparse(db_url)
        env = os.environ.copy()
        env['PGPASSWORD'] = p.password or ''
        cmd = [
            'pg_dump',
            '-h', p.hostname or 'localhost',
            '-p', str(p.port or 5432),
            '-U', p.username or 'postgres',
            p.path.lstrip('/'),  # nombre de la BD
        ]
    except Exception as e:
        return f'Error parseando DATABASE_URL: {e}', 500

    try:
        result = subprocess.run(
            cmd, env=env,
            capture_output=True
        )
        if result.returncode != 0:
            return f'Error pg_dump: {result.stderr.decode("utf-8", errors="replace")}', 500
        sql_data = result.stdout
    except Exception as e:
        return f'Error ejecutando pg_dump: {e}', 500

    from datetime import datetime
    filename = f'backup_tuctuc_{datetime.now().strftime("%Y-%m-%d_%H-%M")}.sql'

    return Response(
        sql_data,
        mimetype='application/octet-stream',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"',
            'Content-Length': str(len(sql_data)),
            'Cache-Control': 'no-cache, must-revalidate',
        }
    )
