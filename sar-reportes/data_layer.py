"""
data_layer.py — Abstracción de fuente de datos local / remoto

Uso:
    from data_layer import DataLayer

    # Local
    dl = DataLayer(fuente='local', ruta_bd=r'C:\\...\\BASEDATOSEMPRESAS')

    # Remoto (vía Admin Agent + cola PostgreSQL en AWS)
    dl = DataLayer(fuente='remoto', base_url='https://admin.tuc-tuc.co', cliente_id='pilar')

    filas = dl.leer(tablas=[
        {'tabla': 'PRODUCTOS',     'campos': ['CODIGO','NOMBRE'], 'filtros': {}},
        {'tabla': 'PROD_FACT1',    'campos': ['COD_PRO','FECHAHORA','CANTIDAD'],
         'filtros': {'EMPRESA': 'MG', 'FECHAHORA': {'desde': '2026-01-01', 'hasta': '2026-05-12'}}},
    ])
    # retorna {'PRODUCTOS': [...], 'PROD_FACT1': [...]}
"""

import os, sys, time, json
sys.path.insert(0, os.path.dirname(__file__))
from agente import leer_tabla_filtrada

POLL_INTERVALO  = 2    # segundos entre checks de respuesta
TIMEOUT_REMOTO  = 60   # segundos máximo esperando respuesta del agente


class DataLayer:

    def __init__(self, fuente, ruta_bd=None, base_url=None, cliente_id=None, aws_session=None):
        """
        fuente: 'local' | 'remoto'
        ruta_bd: ruta a la carpeta con los .DBF (modo local)
        base_url: URL del servidor AWS (modo remoto)
        cliente_id: id del cliente/agente (modo remoto)
        aws_session: requests.Session ya autenticada contra AWS (modo remoto)
        """
        self.fuente      = fuente
        self.ruta_bd     = ruta_bd
        self.base_url    = (base_url or '').rstrip('/')
        self.cliente_id  = cliente_id
        self.aws_session = aws_session

    def leer(self, tablas):
        """
        tablas: list de {tabla, campos, filtros}
        retorna: dict {NOMBRE_TABLA: [filas...]}
        """
        if self.fuente == 'local':
            return self._leer_local(tablas)
        elif self.fuente == 'remoto':
            return self._leer_remoto(tablas)
        else:
            raise ValueError(f'fuente desconocida: {self.fuente!r}')

    # ── Local ─────────────────────────────────────────────────────────────────

    def _leer_local(self, tablas):
        resultado = {}
        for t in tablas:
            nombre  = t['tabla'].upper()
            campos  = t.get('campos', [])
            filtros = t.get('filtros', {})
            resultado[nombre] = leer_tabla_filtrada(self.ruta_bd, nombre, campos, filtros)
        return resultado

    # ── Remoto ────────────────────────────────────────────────────────────────

    def _leer_remoto(self, tablas):
        s = self.aws_session  # requests.Session ya autenticada

        # Encolar consulta
        r = s.post(
            f'{self.base_url}/api/admin-agent/consultar',
            json={'cliente_id': self.cliente_id,
                  'tipo': 'multi_tabla',
                  'parametros': {'tablas': tablas}},
            timeout=15
        )
        data = r.json()
        if not data.get('ok'):
            raise RuntimeError(f'Error encolando consulta: {data.get("error")}')
        consulta_id = data['consulta_id']

        # Esperar respuesta
        t0 = time.time()
        while True:
            if time.time() - t0 > TIMEOUT_REMOTO:
                raise TimeoutError('El agente no respondió a tiempo')
            time.sleep(POLL_INTERVALO)
            r = s.get(
                f'{self.base_url}/api/admin-agent/resultado/{consulta_id}',
                timeout=15
            )
            data = r.json()
            if data.get('estado') == 'lista':
                return data['respuesta']
            if data.get('estado') == 'error':
                raise RuntimeError(f'Error en agente: {data.get("error")}')
            # pendiente/procesando → seguir esperando


def leer_ruta_bd():
    """Lee la ruta de BD desde ruta.dbf (solo para uso local en esta máquina)."""
    import dbf
    ruta_file = r'C:\S.A.R\RutaBaseDatos\ruta.dbf'
    t = dbf.Table(ruta_file, ignore_memos=True)
    t.open(dbf.READ_ONLY)
    ruta = None
    for r in t:
        ruta = r['RUTA'].strip()
        break
    t.close()
    if not ruta:
        raise RuntimeError('ruta.dbf vacío')
    return os.path.dirname(ruta)
