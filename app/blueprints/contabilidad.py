from flask import Blueprint, jsonify, request, session, render_template
from decimal import Decimal
import re
from datetime import date as _date, datetime as _dt, timedelta as _td

bp = Blueprint('contabilidad', __name__)

_tablas_listas = False


# ── Tablas ────────────────────────────────────────────────────

def _asegurar_tablas(conn):
    global _tablas_listas
    if _tablas_listas:
        return

    conn.execute("""
        CREATE TABLE IF NOT EXISTS cuentas_puc (
            id                SERIAL PRIMARY KEY,
            codigo            VARCHAR(10) UNIQUE NOT NULL,
            nombre            VARCHAR(255) NOT NULL,
            nivel             SMALLINT NOT NULL,
            codigo_padre      VARCHAR(10),
            naturaleza        VARCHAR(10) NOT NULL DEFAULT 'debito',
            acepta_movimiento BOOLEAN DEFAULT FALSE,
            maneja_terceros   BOOLEAN DEFAULT FALSE,
            maneja_documentos BOOLEAN DEFAULT FALSE,
            creada_por_negocio_id INTEGER,
            revisada          BOOLEAN DEFAULT FALSE,
            activo            BOOLEAN DEFAULT TRUE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_puc_codigo ON cuentas_puc(codigo)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_puc_padre  ON cuentas_puc(codigo_padre)")
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS tipos_documento_negocio (
            id           SERIAL PRIMARY KEY,
            negocio_id   INTEGER NOT NULL,
            codigo       VARCHAR(20) NOT NULL,
            nombre       VARCHAR(100) NOT NULL,
            activo       BOOLEAN DEFAULT TRUE,
            created_at   TIMESTAMP DEFAULT NOW(),
            UNIQUE(negocio_id, codigo)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tipodoc_neg ON tipos_documento_negocio(negocio_id)")
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS modulo_variables_contables (
            id          SERIAL PRIMARY KEY,
            modulo      VARCHAR(50) NOT NULL,
            codigo      VARCHAR(50) NOT NULL,
            descripcion VARCHAR(150) NOT NULL,
            activo      BOOLEAN DEFAULT TRUE,
            orden       INTEGER DEFAULT 0,
            UNIQUE(modulo, codigo)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_modvar_mod ON modulo_variables_contables(modulo)")
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS parametros_contables_negocio (
            id                  SERIAL PRIMARY KEY,
            negocio_id          INTEGER NOT NULL,
            tipo_doc_id         INTEGER NOT NULL REFERENCES tipos_documento_negocio(id) ON DELETE CASCADE,
            descripcion_asiento VARCHAR(255),
            activo              BOOLEAN DEFAULT TRUE,
            UNIQUE(negocio_id, tipo_doc_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_paramcont_neg ON parametros_contables_negocio(negocio_id)")
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS parametros_lineas_contables (
            id            SERIAL PRIMARY KEY,
            parametro_id  INTEGER NOT NULL REFERENCES parametros_contables_negocio(id) ON DELETE CASCADE,
            cuenta_puc_id INTEGER NOT NULL REFERENCES cuentas_puc(id),
            tipo_mov      CHAR(1) NOT NULL CHECK (tipo_mov IN ('D','C')),
            origen        CHAR(1) NOT NULL DEFAULT 'M' CHECK (origen IN ('M','F','C','H')),
            valor_fijo    NUMERIC(14,2),
            formula       VARCHAR(100),
            variable_id   INTEGER REFERENCES modulo_variables_contables(id),
            orden         INTEGER DEFAULT 0,
            activo        BOOLEAN DEFAULT TRUE
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_paramlin_par ON parametros_lineas_contables(parametro_id)")
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS comprobantes_contables (
            id                 SERIAL PRIMARY KEY,
            negocio_id         INTEGER NOT NULL,
            numero_comprobante VARCHAR(50),
            tipo               VARCHAR(30),
            fecha              DATE NOT NULL DEFAULT CURRENT_DATE,
            descripcion        VARCHAR(255),
            total_debitos      NUMERIC(12,2) DEFAULT 0,
            total_creditos     NUMERIC(12,2) DEFAULT 0,
            registrado_por     INTEGER,
            notas              TEXT,
            origen_tipo        VARCHAR(50),
            origen_id          VARCHAR(100),
            created_at         TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_comp_neg ON comprobantes_contables(negocio_id)")
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS movimientos_contables (
            id             SERIAL PRIMARY KEY,
            negocio_id     INTEGER NOT NULL,
            comprobante_id INTEGER REFERENCES comprobantes_contables(id),
            cuenta_id      INTEGER REFERENCES cuentas_puc(id),
            cuenta         VARCHAR(20),
            concepto       VARCHAR(255),
            tipo           VARCHAR(10),
            monto          NUMERIC(14,2),
            registrado_por INTEGER,
            created_at     TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_movcont_comp ON movimientos_contables(comprobante_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_movcont_neg  ON movimientos_contables(negocio_id)")
    conn.commit()

    # grupos_inventario: categoría → cuentas contables (14x inventario + 6x costo ventas + 41x ingresos)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS grupos_inventario (
            id             SERIAL PRIMARY KEY,
            negocio_id     INTEGER NOT NULL,
            nombre         VARCHAR(100) NOT NULL,
            cuenta_inve_id INTEGER REFERENCES cuentas_puc(id),
            cuenta_cos_id  INTEGER REFERENCES cuentas_puc(id),
            cuenta_ingre_id INTEGER REFERENCES cuentas_puc(id),
            UNIQUE(negocio_id, nombre)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_grpinv_neg ON grupos_inventario(negocio_id)")
    conn.commit()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS programaciones_contables (
            id                SERIAL PRIMARY KEY,
            negocio_id        INTEGER NOT NULL,
            tipo_doc_id       INTEGER NOT NULL REFERENCES tipos_documento_negocio(id) ON DELETE CASCADE,
            descripcion       VARCHAR(255),
            frecuencia        VARCHAR(20) NOT NULL DEFAULT 'mensual',
            dia_semana        SMALLINT,
            dia_mes           SMALLINT DEFAULT 1,
            hora              TIME NOT NULL DEFAULT '08:00',
            variables_h       JSONB DEFAULT '{}',
            activo            BOOLEAN DEFAULT TRUE,
            ultimo_ejecutado  TIMESTAMP,
            proximo_ejecutado TIMESTAMP,
            ultimo_resultado  VARCHAR(150),
            created_at        TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prog_neg ON programaciones_contables(negocio_id)")
    conn.commit()

    # config_contabilidad_negocio: global switches for automated accounting settings
    conn.execute("""
        CREATE TABLE IF NOT EXISTS config_contabilidad_negocio (
            negocio_id                INTEGER PRIMARY KEY,
            contab_entradas_categoria BOOLEAN NOT NULL DEFAULT FALSE,
            contab_costos_categoria   BOOLEAN NOT NULL DEFAULT FALSE,
            contab_produccion         BOOLEAN NOT NULL DEFAULT FALSE
        )
    """)
    conn.commit()

    # Columnas nuevas en tipos_documento_negocio y otras tablas
    for sql in [
        "ALTER TABLE tipos_documento_negocio ADD COLUMN IF NOT EXISTS consecutivo    INTEGER DEFAULT 0",
        "ALTER TABLE tipos_documento_negocio ADD COLUMN IF NOT EXISTS numero_inicio  INTEGER DEFAULT 1",
        "ALTER TABLE tipos_documento_negocio ADD COLUMN IF NOT EXISTS predeterminado BOOLEAN DEFAULT FALSE",
        "ALTER TABLE tipos_documento_negocio ADD COLUMN IF NOT EXISTS mueve_inventario BOOLEAN DEFAULT FALSE",
        "ALTER TABLE tipos_documento_negocio ADD COLUMN IF NOT EXISTS tipo_movimiento VARCHAR(20) DEFAULT NULL",
        "ALTER TABLE tipos_documento_negocio ADD COLUMN IF NOT EXISTS es_interno BOOLEAN DEFAULT TRUE",
        "UPDATE tipos_documento_negocio SET es_interno = FALSE WHERE codigo IN ('FACTURA', 'REMISION')",
        # numero_documento en comprobantes_contables para cruce con inventario
        "ALTER TABLE comprobantes_contables  ADD COLUMN IF NOT EXISTS numero_documento INTEGER",
        "ALTER TABLE comprobantes_contables  ADD COLUMN IF NOT EXISTS origen_tipo   VARCHAR(50)",
        "ALTER TABLE comprobantes_contables  ADD COLUMN IF NOT EXISTS origen_id     VARCHAR(100)",
        # tipo_documento y numero_documento en movimientos_inventario
        "ALTER TABLE movimientos_inventario  ADD COLUMN IF NOT EXISTS tipo_documento   VARCHAR(50)",
        "ALTER TABLE movimientos_inventario  ADD COLUMN IF NOT EXISTS numero_documento INTEGER",
        # cuenta_ingre_id en grupos_inventario
        "ALTER TABLE grupos_inventario       ADD COLUMN IF NOT EXISTS cuenta_ingre_id INTEGER REFERENCES cuentas_puc(id)",
        # cuenta_ajuste_favor_id y cuenta_ajuste_contra_id en grupos_inventario
        "ALTER TABLE grupos_inventario       ADD COLUMN IF NOT EXISTS cuenta_ajuste_favor_id INTEGER REFERENCES cuentas_puc(id)",
        "ALTER TABLE grupos_inventario       ADD COLUMN IF NOT EXISTS cuenta_ajuste_contra_id INTEGER REFERENCES cuentas_puc(id)",
        # producto_id en movimientos_contables
        "ALTER TABLE movimientos_contables   ADD COLUMN IF NOT EXISTS producto_id INTEGER REFERENCES productos(id) ON DELETE SET NULL",
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass

    _seed_puc(conn)
    _seed_puc_subcuentas(conn)
    conn.execute("""
        UPDATE cuentas_puc
        SET acepta_movimiento = FALSE
        WHERE codigo IN (
            SELECT DISTINCT codigo_padre FROM cuentas_puc WHERE codigo_padre IS NOT NULL
        )
    """)
    conn.commit()

    # Sembrar método de pago 'credito' en metodos_pago_catalogo si no existe
    exists_credito = conn.execute("SELECT 1 FROM metodos_pago_catalogo WHERE codigo='credito'").fetchone()
    if not exists_credito:
        conn.execute("""
            INSERT INTO metodos_pago_catalogo (nombre, codigo, icono, activo, orden)
            VALUES ('Crédito / Cuenta por cobrar o pagar', 'credito', '', TRUE, 9)
        """)
        conn.commit()

    # Crear tabla de asignación de cuentas por método de pago
    conn.execute("""
        CREATE TABLE IF NOT EXISTS parametros_metodos_pago_negocio (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL REFERENCES terceros(id),
            metodo_codigo VARCHAR(50) NOT NULL,
            cuenta_recaudo_id INTEGER REFERENCES cuentas_puc(id),
            cuenta_pago_id INTEGER REFERENCES cuentas_puc(id),
            created_at TIMESTAMP DEFAULT NOW(),
            UNIQUE(negocio_id, metodo_codigo)
        )
    """)
    conn.commit()

    # Crear tabla de saldos por documento
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saldo_por_documentos (
            id SERIAL PRIMARY KEY,
            negocio_id INTEGER NOT NULL REFERENCES terceros(id),
            cuenta_id INTEGER NOT NULL REFERENCES cuentas_puc(id),
            tercero_id INTEGER NOT NULL REFERENCES terceros(id),
            tipo_documento VARCHAR(50) NOT NULL,
            numero_documento VARCHAR(50) NOT NULL,
            monto_original NUMERIC(15,2) NOT NULL,
            saldo NUMERIC(15,2) NOT NULL,
            usuario_id INTEGER REFERENCES usuarios(id),
            fecha_hora TIMESTAMP NOT NULL DEFAULT NOW(),
            created_at TIMESTAMP DEFAULT NOW(),
            updated_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_saldo_doc_unico ON saldo_por_documentos(negocio_id, tercero_id, cuenta_id, tipo_documento, numero_documento)")
    conn.commit()

    # Alteraciones de columnas
    for sql in [
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS metodo_pago VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE parametros_lineas_contables ADD COLUMN IF NOT EXISTS cuenta_dinamica VARCHAR(50) DEFAULT NULL",
        "ALTER TABLE movimientos_inventario ADD COLUMN IF NOT EXISTS tipo_documento_id INTEGER REFERENCES tipos_documento_negocio(id)",
        "ALTER TABLE comprobantes_contables  ADD COLUMN IF NOT EXISTS tipo_documento_id INTEGER REFERENCES tipos_documento_negocio(id)",
        "ALTER TABLE saldo_por_documentos    ADD COLUMN IF NOT EXISTS tipo_documento_id INTEGER REFERENCES tipos_documento_negocio(id)"
    ]:
        try:
            conn.execute(sql)
            conn.commit()
        except Exception:
            try: conn.rollback()
            except Exception: pass

    # Migrar datos históricos para tipo_documento_id si hay registros vacíos
    try:
        conn.execute("""
            UPDATE movimientos_inventario m
            SET tipo_documento_id = t.id
            FROM tipos_documento_negocio t
            WHERE m.tipo_documento_id IS NULL 
              AND t.negocio_id = m.negocio_id 
              AND UPPER(t.codigo) = UPPER(m.tipo_documento)
        """)
        conn.execute("""
            UPDATE comprobantes_contables c
            SET tipo_documento_id = t.id
            FROM tipos_documento_negocio t
            WHERE c.tipo_documento_id IS NULL 
              AND t.negocio_id = c.negocio_id 
              AND UPPER(t.codigo) = UPPER(c.tipo)
        """)
        conn.execute("""
            UPDATE saldo_por_documentos s
            SET tipo_documento_id = t.id
            FROM tipos_documento_negocio t
            WHERE s.tipo_documento_id IS NULL 
              AND t.negocio_id = s.negocio_id 
              AND UPPER(t.codigo) = UPPER(s.tipo_documento)
        """)
        conn.commit()
    except Exception as e:
        print(f"Error en migración de datos tipo_documento_id: {e}")
        try: conn.rollback()
        except: pass

    # Recreación del índice único de saldos por documento
    try:
        conn.execute("DROP INDEX IF EXISTS idx_saldo_doc_unico")
        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS idx_saldo_doc_unico 
            ON saldo_por_documentos(negocio_id, tercero_id, cuenta_id, tipo_documento_id, numero_documento)
        """)
        conn.commit()
    except Exception as e:
        print(f"Error recreando índice idx_saldo_doc_unico: {e}")
        try: conn.rollback()
        except: pass

    _seed_variables(conn)
    _tablas_listas = True


# ── Seeds ─────────────────────────────────────────────────────

def _seed_variables(conn):
    conn.execute("DELETE FROM modulo_variables_contables WHERE modulo IN ('tienda','restaurante')")
    variables = [
        ('ventas_pos',        'subtotal_venta',        'Subtotal venta POS (sin IVA)',              1),
        ('ventas_pos',        'iva_venta',              'IVA venta POS',                            2),
        ('ventas_pos',        'total_venta',            'Total venta POS (con IVA)',                 3),
        ('ventas_domicilio',  'subtotal_venta',        'Subtotal venta domicilio (sin IVA)',          1),
        ('ventas_domicilio',  'iva_venta',              'IVA venta domicilio',                       2),
        ('ventas_domicilio',  'total_venta',            'Total venta domicilio (con IVA)',            3),
        ('compras_inventario','subtotal_compra',        'Subtotal entrada inventario (sin IVA)',      1),
        ('compras_inventario','iva_compra',             'IVA entrada inventario',                    2),
        ('compras_inventario','total_compra',           'Total entrada inventario (con IVA)',         3),
        ('ventas_restaurante','subtotal_venta',        'Subtotal cobrado en mesa (sin IVA)',          1),
        ('ventas_restaurante','iva_venta',              'IVA cobrado en mesa',                       2),
        ('ventas_restaurante','total_venta',            'Total cobrado en mesa (con IVA)',            3),
        ('produccion',        'costo_total',            'Costo total de producción',                 1),
        ('produccion',        'costo_unitario',         'Costo unitario del producto fabricado',     2),
        ('produccion',        'cantidad_producida',     'Cantidad producida',                        3),
    ]
    for modulo, codigo, descripcion, orden in variables:
        conn.execute("""
            INSERT INTO modulo_variables_contables (modulo, codigo, descripcion, orden, activo)
            VALUES (%s, %s, %s, %s, TRUE)
            ON CONFLICT (modulo, codigo) DO UPDATE
                SET descripcion = EXCLUDED.descripcion, orden = EXCLUDED.orden
        """, (modulo, codigo, descripcion, orden))
    conn.commit()


def _seed_puc(conn):
    cnt = conn.execute("SELECT COUNT(*) FROM cuentas_puc").fetchone()[0]
    if cnt > 0:
        return
    D, C = 'debito', 'credito'
    cuentas = [
        ('1','Activo',1,None,D,False,False,False),
        ('11','Disponible',2,'1',D,False,False,False),
        ('1105','Caja',3,'11',D,True,False,False),
        ('1110','Depósitos en establecimientos bancarios',3,'11',D,True,False,False),
        ('1115','Remesas en tránsito',3,'11',D,True,False,False),
        ('1120','Cuentas de ahorro',3,'11',D,True,False,False),
        ('12','Inversiones',2,'1',D,False,False,False),
        ('1205','Acciones',3,'12',D,True,False,False),
        ('13','Deudores',2,'1',D,False,False,False),
        ('1305','Clientes',3,'13',D,True,True,True),
        ('1320','Deudores varios',3,'13',D,True,True,False),
        ('1350','Retención en la fuente',3,'13',D,True,False,False),
        ('1355','Anticipo de impuestos y contribuciones',3,'13',D,True,False,False),
        ('14','Inventarios',2,'1',D,False,False,False),
        ('1405','Materias primas',3,'14',D,True,False,False),
        ('1410','Productos en proceso',3,'14',D,True,False,False),
        ('1420','Productos terminados',3,'14',D,True,False,False),
        ('1425','Mercancías no fabricadas por la empresa',3,'14',D,True,False,False),
        ('1428','Materiales, repuestos y accesorios',3,'14',D,True,False,False),
        ('1430','Envases y empaques',3,'14',D,True,False,False),
        ('1435','Inventarios en tránsito',3,'14',D,True,False,False),
        ('1499','Provisiones',3,'14',C,True,False,False),
        ('15','Propiedades, planta y equipo',2,'1',D,False,False,False),
        ('1504','Terrenos',3,'15',D,True,False,False),
        ('1508','Construcciones y edificaciones',3,'15',D,True,False,False),
        ('1512','Maquinaria y equipo',3,'15',D,True,False,False),
        ('1516','Equipo de oficina',3,'15',D,True,False,False),
        ('1520','Equipo de computación y comunicación',3,'15',D,True,False,False),
        ('1528','Equipo de hoteles y restaurantes',3,'15',D,True,False,False),
        ('1532','Equipo de transporte',3,'15',D,True,False,False),
        ('1572','Depreciación acumulada',3,'15',C,True,False,False),
        ('16','Intangibles',2,'1',D,False,False,False),
        ('1605','Crédito mercantil',3,'16',D,True,False,False),
        ('1635','Licencias',3,'16',D,True,False,False),
        ('1660','Amortización acumulada',3,'16',C,True,False,False),
        ('17','Diferidos',2,'1',D,False,False,False),
        ('1705','Gastos pagados por anticipado',3,'17',D,True,False,False),
        ('1710','Cargos diferidos',3,'17',D,True,False,False),
        ('1775','Impuesto al valor agregado descontable',3,'17',D,True,False,False),
        ('18','Otros activos',2,'1',D,False,False,False),
        ('1895','Otros',3,'18',D,True,False,False),
        ('19','Valorizaciones',2,'1',D,False,False,False),
        ('1905','Activos fijos',3,'19',D,True,False,False),
        ('2','Pasivo',1,None,C,False,False,False),
        ('21','Obligaciones financieras',2,'2',C,False,False,False),
        ('2105','Bancos nacionales',3,'21',C,True,True,True),
        ('2135','Otras entidades financieras',3,'21',C,True,True,True),
        ('22','Proveedores',2,'2',C,False,False,False),
        ('2205','Nacionales',3,'22',C,True,True,True),
        ('2210','Del exterior',3,'22',C,True,True,True),
        ('23','Cuentas por pagar',2,'2',C,False,False,False),
        ('2305','Costos y gastos por pagar',3,'23',C,True,True,False),
        ('2345','Acreedores varios',3,'23',C,True,True,False),
        ('2370','Retención en la fuente',3,'23',C,True,False,False),
        ('2375','Impuesto a las ventas retenido',3,'23',C,True,False,False),
        ('24','Impuestos, gravámenes y tasas',2,'2',C,False,False,False),
        ('2404','Impuesto sobre las ventas por pagar (IVA)',3,'24',C,True,False,False),
        ('2408','Impuesto de industria y comercio',3,'24',C,True,False,False),
        ('2420','Impuesto sobre la renta y complementarios',3,'24',C,True,False,False),
        ('25','Obligaciones laborales',2,'2',C,False,False,False),
        ('2505','Salarios por pagar',3,'25',C,True,True,False),
        ('2510','Cesantías consolidadas',3,'25',C,True,True,False),
        ('2525','Vacaciones consolidadas',3,'25',C,True,True,False),
        ('26','Pasivos estimados y provisiones',2,'2',C,False,False,False),
        ('2605','Para costos y gastos',3,'26',C,True,False,False),
        ('27','Diferidos',2,'2',C,False,False,False),
        ('2705','Ingresos recibidos por anticipado',3,'27',C,True,False,False),
        ('28','Otros pasivos',2,'2',C,False,False,False),
        ('2805','Anticipos y avances recibidos',3,'28',C,True,True,False),
        ('3','Patrimonio',1,None,C,False,False,False),
        ('31','Capital social',2,'3',C,False,False,False),
        ('3105','Capital suscrito y pagado',3,'31',C,True,False,False),
        ('3110','Aportes sociales',3,'31',C,True,False,False),
        ('3115','Capital de personas naturales',3,'31',C,True,False,False),
        ('33','Reservas',2,'3',C,False,False,False),
        ('3305','Reserva legal',3,'33',C,True,False,False),
        ('36','Resultados del ejercicio',2,'3',C,False,False,False),
        ('3605','Utilidad del ejercicio',3,'36',C,True,False,False),
        ('3610','Pérdida del ejercicio',3,'36',D,True,False,False),
        ('37','Resultados de ejercicios anteriores',2,'3',C,False,False,False),
        ('3705','Utilidades acumuladas',3,'37',C,True,False,False),
        ('3710','Pérdidas acumuladas',3,'37',D,True,False,False),
        ('4','Ingresos',1,None,C,False,False,False),
        ('41','Operacionales',2,'4',C,False,False,False),
        ('4135','Comercio al por mayor y al por menor',3,'41',C,True,False,False),
        ('4140','Hoteles y restaurantes',3,'41',C,True,False,False),
        ('4175','Otras actividades de servicios',3,'41',C,True,False,False),
        ('42','No operacionales',2,'4',C,False,False,False),
        ('4205','Financieros',3,'42',C,True,False,False),
        ('4275','Diversas',3,'42',C,True,False,False),
        ('4295','Otras',3,'42',C,True,False,False),
        ('5','Gastos',1,None,D,False,False,False),
        ('51','Operacionales de administración',2,'5',D,False,False,False),
        ('5105','Gastos de personal',3,'51',D,True,False,False),
        ('5110','Honorarios',3,'51',D,True,True,False),
        ('5120','Arrendamientos',3,'51',D,True,True,False),
        ('5135','Servicios',3,'51',D,True,False,False),
        ('5145','Mantenimiento y reparaciones',3,'51',D,True,False,False),
        ('5160','Depreciaciones',3,'51',D,True,False,False),
        ('5175','Diversos',3,'51',D,True,False,False),
        ('52','Operacionales de ventas',2,'5',D,False,False,False),
        ('5205','Gastos de personal',3,'52',D,True,False,False),
        ('5235','Servicios',3,'52',D,True,False,False),
        ('5275','Publicidad, propaganda y promoción',3,'52',D,True,False,False),
        ('5280','Comisiones',3,'52',D,True,True,False),
        ('5290','Diversos',3,'52',D,True,False,False),
        ('53','No operacionales',2,'5',D,False,False,False),
        ('5305','Financieros',3,'53',D,True,False,False),
        ('5315','Gastos extraordinarios',3,'53',D,True,False,False),
        ('5320','Gastos diversos',3,'53',D,True,False,False),
        ('6','Costos de ventas',1,None,D,False,False,False),
        ('61','Costos de ventas y de prestación de servicios',2,'6',D,False,False,False),
        ('6105','Industria manufacturera',3,'61',D,True,False,False),
        ('6110','Empresas de servicios',3,'61',D,True,False,False),
        ('6115','Empresas de comercio',3,'61',D,True,False,False),
        ('6140','Entidades hoteleras',3,'61',D,True,False,False),
        ('6145','Otras entidades',3,'61',D,True,False,False),
        ('7','Costos de producción y operación',1,None,D,False,False,False),
        ('71','Materia prima',2,'7',D,False,False,False),
        ('7105','Materia prima',3,'71',D,True,False,False),
        ('72','Mano de obra directa',2,'7',D,False,False,False),
        ('7205','Sueldos y salarios',3,'72',D,True,False,False),
        ('73','Costos indirectos',2,'7',D,False,False,False),
        ('7305','Materiales indirectos',3,'73',D,True,False,False),
        ('7395','Otros',3,'73',D,True,False,False),
    ]
    for row in cuentas:
        try:
            conn.execute("""
                INSERT INTO cuentas_puc
                    (codigo, nombre, nivel, codigo_padre, naturaleza,
                     acepta_movimiento, maneja_terceros, maneja_documentos)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (codigo) DO NOTHING
            """, row)
        except Exception:
            conn.rollback()
    conn.commit()


def _seed_puc_subcuentas(conn):
    cnt = conn.execute("SELECT COUNT(*) FROM cuentas_puc WHERE nivel = 4").fetchone()[0]
    if cnt > 0:
        return
    D, C = 'debito', 'credito'
    sub = [
        ('110505','Caja general',4,'1105',D,True,False,False),
        ('110510','Cajas menores',4,'1105',D,True,False,False),
        ('111005','Depósitos en cuenta corriente MN',4,'1110',D,True,False,False),
        ('112005','Cuentas de ahorro MN',4,'1120',D,True,False,False),
        ('130505','Clientes nacionales',4,'1305',D,True,True,True),
        ('140505','Materias primas',4,'1405',D,True,False,False),
        ('141005','Productos en proceso',4,'1410',D,True,False,False),
        ('142005','Productos terminados',4,'1420',D,True,False,False),
        ('142505','Mercancías en existencia',4,'1425',D,True,False,False),
        ('220505','Proveedores nacionales',4,'2205',C,True,True,True),
        ('240405','IVA por pagar',4,'2404',C,True,False,False),
        ('410505','Ingresos comercio al por mayor',4,'4135',C,True,False,False),
        ('411505','Ingresos hoteles y restaurantes',4,'4140',C,True,False,False),
        ('611505','Costo de ventas comercio',4,'6115',D,True,False,False),
        ('614005','Costo de ventas restaurantes',4,'6140',D,True,False,False),
    ]
    for row in sub:
        try:
            conn.execute("""
                INSERT INTO cuentas_puc
                    (codigo, nombre, nivel, codigo_padre, naturaleza,
                     acepta_movimiento, maneja_terceros, maneja_documentos)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (codigo) DO NOTHING
            """, row)
        except Exception:
            conn.rollback()
    conn.commit()


# ── Scheduler: Tipo 4 ────────────────────────────────────────

def _calcular_proximo(frecuencia, dia_semana, dia_mes, hora_val, desde=None):
    base = desde or _dt.now()
    if hasattr(hora_val, 'hour'):
        h, m = hora_val.hour, hora_val.minute
    else:
        partes = str(hora_val)[:5].split(':')
        h, m = int(partes[0]), int(partes[1]) if len(partes) > 1 else 0
    if frecuencia == 'diario':
        p = base.replace(hour=h, minute=m, second=0, microsecond=0)
        if p <= base:
            p += _td(days=1)
    elif frecuencia == 'semanal':
        dias = (int(dia_semana or 0) - base.weekday()) % 7
        p = (base + _td(days=dias)).replace(hour=h, minute=m, second=0, microsecond=0)
        if p <= base:
            p += _td(weeks=1)
    else:  # mensual
        dia = int(dia_mes or 1)
        try:
            p = base.replace(day=dia, hour=h, minute=m, second=0, microsecond=0)
        except ValueError:
            p = base.replace(day=28, hour=h, minute=m, second=0, microsecond=0)
        if p <= base:
            mes, ano = base.month + 1, base.year
            if mes > 12:
                mes, ano = 1, ano + 1
            try:
                p = p.replace(year=ano, month=mes)
            except ValueError:
                p = p.replace(year=ano, month=mes, day=28)
    return p


def ejecutar_programaciones_job(app):
    with app.app_context():
        from app.db import get_db_connection
        try:
            conn = get_db_connection()
            _asegurar_tablas(conn)
            ahora = _dt.now()
            progs = conn.execute("""
                SELECT p.*, t.codigo AS tipo_codigo
                FROM programaciones_contables p
                JOIN tipos_documento_negocio t ON t.id = p.tipo_doc_id
                WHERE p.activo = TRUE
                  AND (p.proximo_ejecutado IS NULL OR p.proximo_ejecutado <= %s)
            """, (ahora,)).fetchall()
            for p in progs:
                resultado = 'ok'
                try:
                    comp_id = _ejecutar_asiento_automatico(
                        conn, p['negocio_id'], p['tipo_codigo'],
                        dict(p['variables_h'] or {}),
                        descripcion_override=p['descripcion']
                    )
                    conn.commit()
                    resultado = f'ok comp={comp_id}' if comp_id else 'sin_parametrizacion'
                except Exception as e:
                    try: conn.rollback()
                    except Exception: pass
                    resultado = f'error: {str(e)[:80]}'
                proximo = _calcular_proximo(p['frecuencia'], p['dia_semana'], p['dia_mes'], p['hora'])
                conn.execute(
                    "UPDATE programaciones_contables "
                    "SET ultimo_ejecutado=%s, proximo_ejecutado=%s, ultimo_resultado=%s WHERE id=%s",
                    (ahora, proximo, resultado, p['id'])
                )
                conn.commit()
            conn.close()
        except Exception:
            try: conn.close()
            except Exception: pass


def obtener_siguiente_consecutivo(conn, negocio_id, tipo_doc_identificador):
    """
    Función centralizada para resolver el consecutivo de un documento.
    Soporta búsqueda por ID (entero) o por Nombre/Código (cadena fallback).
    """
    if isinstance(tipo_doc_identificador, int) or (isinstance(tipo_doc_identificador, str) and tipo_doc_identificador.isdigit()):
        td = conn.execute("""
            SELECT id, consecutivo, numero_inicio, es_interno
            FROM tipos_documento_negocio
            WHERE negocio_id = %s AND id = %s
        """, (negocio_id, int(tipo_doc_identificador))).fetchone()
    else:
        td = conn.execute("""
            SELECT id, consecutivo, numero_inicio, es_interno
            FROM tipos_documento_negocio
            WHERE negocio_id = %s AND (UPPER(nombre) = %s OR UPPER(codigo) = %s)
        """, (negocio_id, str(tipo_doc_identificador).upper(), str(tipo_doc_identificador).upper())).fetchone()
    
    if not td:
        return None, True
        
    es_interno = td['es_interno'] if td['es_interno'] is not None else True
    
    if es_interno:
        num = max((td['consecutivo'] or 0) + 1, (td['numero_inicio'] or 1))
        conn.execute("""
            UPDATE tipos_documento_negocio
            SET consecutivo = %s
            WHERE id = %s
        """, (num, td['id']))
        return str(num), True
    else:
        return None, False


def _verificar_periodo_cerrado(conn, negocio_id, fecha):
    """
    Verifica si el periodo correspondiente a 'fecha' (formato YYYY-MM-DD, date o datetime)
    está cerrado para el negocio. Lanza un Exception si lo está.
    """
    if not fecha:
        return
    # Convertir fecha a string YYYY-MM
    if hasattr(fecha, 'strftime'):
        periodo = fecha.strftime('%Y-%m')
    else:
        # Asumiendo string YYYY-MM-DD o similar
        parts = str(fecha).split('-')
        if len(parts) >= 2:
            periodo = f"{parts[0]}-{parts[1]}"
        else:
            return
            
    res = conn.execute("""
        SELECT 1 FROM cierres_periodos 
        WHERE negocio_id = %s AND periodo = %s
    """, (negocio_id, periodo)).fetchone()
    if res:
        raise Exception(f"El periodo contable {periodo} esta cerrado y no admite modificaciones.")


# ── Motor contable ────────────────────────────────────────────

def _ejecutar_asiento_automatico(conn, negocio_id, tipo_doc_identificador, variables,
                                  registrado_por=None, fecha=None, descripcion_override=None,
                                  origen_tipo=None, origen_id=None,
                                  metodo_pago=None, tercero_id=None,
                                  tipo_documento_fisico=None, documento_numero_fisico=None):
    """
    Motor parametrizable best-effort.
    Retorna comprobante_id (int) o None si no hay parametrización activa.
    conn: abierta, el llamador hace commit/rollback.
    """
    if isinstance(tipo_doc_identificador, int) or (isinstance(tipo_doc_identificador, str) and tipo_doc_identificador.isdigit()):
        tipo_doc = conn.execute(
            "SELECT id, nombre, consecutivo, numero_inicio, tipo_movimiento, codigo FROM tipos_documento_negocio "
            "WHERE negocio_id=%s AND id=%s",
            (negocio_id, int(tipo_doc_identificador))
        ).fetchone()
    else:
        tipo_doc = conn.execute(
            "SELECT id, nombre, consecutivo, numero_inicio, tipo_movimiento, codigo FROM tipos_documento_negocio "
            "WHERE negocio_id=%s AND (UPPER(nombre)=%s OR UPPER(codigo)=%s)",
            (negocio_id, str(tipo_doc_identificador).upper(), str(tipo_doc_identificador).upper())
        ).fetchone()

    if not tipo_doc:
        return None

    tipo_doc_codigo = tipo_doc['codigo'] or tipo_doc['nombre'].upper().replace(' ', '_')

    param = conn.execute(
        "SELECT id, descripcion_asiento FROM parametros_contables_negocio "
        "WHERE negocio_id=%s AND tipo_doc_id=%s AND activo=TRUE",
        (negocio_id, tipo_doc['id'])
    ).fetchone()
    if not param:
        return None

    lineas_raw = conn.execute("""
        SELECT l.cuenta_puc_id, l.tipo_mov, l.origen,
               l.valor_fijo, l.formula, l.orden,
               c.codigo AS cuenta_codigo, c.nombre AS cuenta_nombre,
               v.codigo AS var_codigo, l.cuenta_dinamica
        FROM parametros_lineas_contables l
        JOIN cuentas_puc c ON c.id = l.cuenta_puc_id
        LEFT JOIN modulo_variables_contables v ON v.id = l.variable_id
        WHERE l.parametro_id = %s AND l.activo = TRUE
        ORDER BY l.orden
    """, (param['id'],)).fetchall()

    # Resolver cuentas dinámicas en líneas de plantilla
    lineas = []
    for l in lineas_raw:
        row = dict(l)
        if row.get('cuenta_dinamica'):
            cuenta_res = None
            if row['cuenta_dinamica'] == 'metodo_pago_pago' and metodo_pago:
                pm = conn.execute(
                    "SELECT cuenta_pago_id FROM parametros_metodos_pago_negocio WHERE negocio_id = %s AND metodo_codigo = %s",
                    (negocio_id, metodo_pago)
                ).fetchone()
                if pm and pm['cuenta_pago_id']:
                    cuenta_res = pm['cuenta_pago_id']
            elif row['cuenta_dinamica'] == 'metodo_pago_recaudo' and metodo_pago:
                pm = conn.execute(
                    "SELECT cuenta_recaudo_id FROM parametros_metodos_pago_negocio WHERE negocio_id = %s AND metodo_codigo = %s",
                    (negocio_id, metodo_pago)
                ).fetchone()
                if pm and pm['cuenta_recaudo_id']:
                    cuenta_res = pm['cuenta_recaudo_id']
            
            if cuenta_res:
                c_puc = conn.execute("SELECT codigo, nombre FROM cuentas_puc WHERE id = %s", (cuenta_res,)).fetchone()
                if c_puc:
                    row['cuenta_puc_id'] = cuenta_res
                    row['cuenta_codigo'] = c_puc['codigo']
                    row['cuenta_nombre'] = c_puc['nombre']
        lineas.append(row)

    # ── NUEVO: Parametrización de ingresos por categoría ──────────────
    categorized_revenue = 0.0
    injected_revenue_movs = []
    
    if tipo_doc.get('tipo_movimiento') == 'venta' and origen_tipo == 'pedido' and origen_id:
        try:
            items_mov = conn.execute("""
                SELECT pi.producto_id, pi.cantidad, pi.precio_unitario, p.categoria, p.nombre AS producto_nombre
                FROM pedido_items pi
                JOIN productos p ON p.id = pi.producto_id
                WHERE pi.pedido_id = %s
            """, (int(origen_id),)).fetchall()
            
            for item in items_mov:
                if item['categoria']:
                    gi = conn.execute("""
                        SELECT gi.cuenta_ingre_id, c.codigo AS cod_ingre, c.nombre AS nom_ingre
                        FROM grupos_inventario gi
                        JOIN cuentas_puc c ON c.id = gi.cuenta_ingre_id
                        WHERE gi.negocio_id = %s AND gi.nombre = %s
                    """, (negocio_id, item['categoria'])).fetchone()
                    
                    if gi and gi['cuenta_ingre_id']:
                        subtotal_item = float(item['cantidad'] or 0) * float(item['precio_unitario'] or 0)
                        if subtotal_item > 0:
                            categorized_revenue += subtotal_item
                            injected_revenue_movs.append({
                                'cuenta_puc_id': gi['cuenta_ingre_id'],
                                'cuenta_codigo': gi['cod_ingre'],
                                'concepto':      f"Venta: {item['producto_nombre']}",
                                'tipo_mov':      'C', # Crédito para ingresos
                                'monto':         subtotal_item
                            })
                            
            if 'subtotal_venta' in variables:
                variables['subtotal_venta'] = max(0.0, float(variables['subtotal_venta']) - categorized_revenue)
        except Exception as e_rev:
            print(f"[cont] Error calculando ingresos por categoria: {e_rev}")

    pos_amounts = {}
    mov_list = []

    for idx, linea in enumerate(lineas, start=1):
        origen = linea['origen']
        monto = 0.0
        if origen == 'F':
            monto = float(linea['valor_fijo'] or 0)
        elif origen == 'H':
            monto = float(variables.get(linea['var_codigo'] or '', 0))
        elif origen == 'C':
            formula = linea['formula'] or '0'
            def _repl(m, _pa=dict(pos_amounts)):
                return str(_pa.get(int(m.group(1)), 0.0))
            formula_eval = re.sub(r'L(\d+)', _repl, formula)
            try:
                monto = float(eval(formula_eval, {"__builtins__": {}}, {}))  # noqa: S307
            except Exception:
                monto = 0.0
        pos_amounts[idx] = monto
        if monto != 0 and origen != 'M':
            mov_list.append({
                'cuenta_puc_id': linea['cuenta_puc_id'],
                'cuenta_codigo': linea['cuenta_codigo'],
                'concepto':      linea['cuenta_nombre'],
                'tipo_mov':      linea['tipo_mov'],
                'monto':         abs(monto),
            })

    # Agregar líneas de ingresos categorizados (si existen)
    mov_list.extend(injected_revenue_movs)

    # Inyección automática de líneas de inventario (14x) por cada producto si contab_entradas_categoria está habilitado
    cfg_contab = conn.execute("SELECT contab_entradas_categoria FROM config_contabilidad_negocio WHERE negocio_id = %s", (negocio_id,)).fetchone()
    if cfg_contab and cfg_contab['contab_entradas_categoria'] and tipo_doc.get('tipo_movimiento') == 'entrada' and tipo_documento_fisico and documento_numero_fisico:
        # Buscar los items reales ingresados para esta entrada en movimientos_inventario
        items_mov = conn.execute("""
            SELECT m.producto_id, m.cantidad, m.valor_unitario, m.valor_total, p.categoria, p.nombre AS producto_nombre
            FROM movimientos_inventario m
            JOIN productos p ON p.id = m.producto_id
            WHERE m.negocio_id = %s AND m.tipo_documento = %s AND m.documento_numero = %s
        """, (negocio_id, tipo_documento_fisico, documento_numero_fisico)).fetchall()
        
        template_cuenta_ids = {m['cuenta_puc_id'] for m in mov_list}
        
        for item in items_mov:
            if item['categoria']:
                gi = conn.execute("""
                    SELECT gi.cuenta_inve_id, c.codigo AS cod_inve, c.nombre AS nom_inve
                    FROM grupos_inventario gi
                    JOIN cuentas_puc c ON c.id = gi.cuenta_inve_id
                    WHERE gi.negocio_id = %s AND gi.nombre = %s
                """, (negocio_id, item['categoria'])).fetchone()
                
                if gi and gi['cuenta_inve_id']:
                    if gi['cuenta_inve_id'] not in template_cuenta_ids:
                        mov_list.append({
                            'cuenta_puc_id': gi['cuenta_inve_id'],
                            'cuenta_codigo': gi['cod_inve'],
                            'concepto':      f"Inv: {item['producto_nombre']}",
                            'tipo_mov':      'D', # Débito en compras/entradas
                            'monto':         float(item['valor_total']),
                        })

    # Inyección automática de líneas de costo de venta (61x debit) y baja de inventario (14x credit) por cada producto si contab_costos_categoria está habilitado
    if tipo_doc.get('tipo_movimiento') == 'venta' and origen_tipo == 'pedido' and origen_id:
        cfg_costos = conn.execute("SELECT contab_costos_categoria FROM config_contabilidad_negocio WHERE negocio_id = %s", (negocio_id,)).fetchone()
        if cfg_costos and cfg_costos['contab_costos_categoria']:
            try:
                # Query the actual inventory movements generated for this sale (ingredients / discounted products)
                items_mov = conn.execute("""
                    SELECT m.producto_id, m.cantidad, m.costo_und, p.categoria, p.nombre AS producto_nombre,
                           m.producto_padre_id, m.tipo, m.motivo, m.valor_unitario
                    FROM movimientos_inventario m
                    JOIN productos p ON p.id = m.producto_id
                    WHERE m.negocio_id = %s AND m.referencia_id = %s AND m.referencia_tipo IN ('pedido', 'pedido_tienda', 'pedido_restaurante')
                """, (negocio_id, int(origen_id))).fetchall()
                
                debitos_costos = {} # Key: (cuenta_puc_id, cuenta_codigo, concepto) -> total_costo
                
                for item in items_mov:
                    # Inyección automática de asientos para ajustes en caliente vinculados a la factura
                    if item['motivo'] == 'ajuste':
                        total_adj = float(item['cantidad'] or 0) * float(item['valor_unitario'] or 0)
                        if total_adj > 0 and item['categoria']:
                            gi_adj = conn.execute("""
                                SELECT gi.cuenta_inve_id, gi.cuenta_ajuste_favor_id,
                                       c_inv.codigo AS cod_inve, c_inv.nombre AS nom_inve,
                                       c_fav.codigo AS cod_fav, c_fav.nombre AS nom_fav
                                FROM grupos_inventario gi
                                LEFT JOIN cuentas_puc c_inv ON c_inv.id = gi.cuenta_inve_id
                                LEFT JOIN cuentas_puc c_fav ON c_fav.id = gi.cuenta_ajuste_favor_id
                                WHERE gi.negocio_id = %s AND gi.nombre = %s
                            """, (negocio_id, item['categoria'])).fetchone()
                            if gi_adj and gi_adj['cuenta_inve_id'] and gi_adj['cuenta_ajuste_favor_id']:
                                # Débito en Inventario (14x)
                                mov_list.append({
                                    'cuenta_puc_id': gi_adj['cuenta_inve_id'],
                                    'cuenta_codigo': gi_adj['cod_inve'],
                                    'concepto':      f"Inv: {item['producto_nombre']}",
                                    'tipo_mov':      'D',
                                    'monto':         total_adj,
                                })
                                # Crédito en Ingreso por Ajuste (41x)
                                mov_list.append({
                                    'cuenta_puc_id': gi_adj['cuenta_ajuste_favor_id'],
                                    'cuenta_codigo': gi_adj['cod_fav'],
                                    'concepto':      f"Ajuste Físico (+): Insumo {item['producto_nombre']}",
                                    'tipo_mov':      'C',
                                    'monto':         total_adj,
                                })
                        continue

                    total_costo = float(item['cantidad'] or 0) * float(item['costo_und'] or 0)
                    if total_costo > 0:
                        # 1. Crédito en inventario (14x) usando la categoría del ingrediente/componente
                        if item['categoria']:
                            gi_ing = conn.execute("""
                                SELECT gi.cuenta_inve_id, c_inv.codigo AS cod_inve, c_inv.nombre AS nom_inve
                                FROM grupos_inventario gi
                                LEFT JOIN cuentas_puc c_inv ON c_inv.id = gi.cuenta_inve_id
                                WHERE gi.negocio_id = %s AND gi.nombre = %s
                            """, (negocio_id, item['categoria'])).fetchone()
                            
                            if gi_ing and gi_ing['cuenta_inve_id']:
                                mov_list.append({
                                    'cuenta_puc_id': gi_ing['cuenta_inve_id'],
                                    'cuenta_codigo': gi_ing['cod_inve'],
                                    'concepto':      f"Baja Inv: {item['producto_nombre']}",
                                    'tipo_mov':      'C',
                                    'monto':         total_costo,
                                })
                        
                        # 2. Débito en costo de venta (61x) acumulado bajo la categoría del producto vendido (sándwich)
                        p_padre_id = item['producto_padre_id']
                        if p_padre_id:
                            padre = conn.execute("SELECT nombre, categoria FROM productos WHERE id = %s", (p_padre_id,)).fetchone()
                            if padre:
                                sold_name = padre['nombre']
                                sold_cat = padre['categoria']
                            else:
                                sold_name = item['producto_nombre']
                                sold_cat = item['categoria']
                        else:
                            sold_name = item['producto_nombre']
                            sold_cat = item['categoria']
                            
                        if sold_cat:
                            gi_sold = conn.execute("""
                                SELECT gi.cuenta_cos_id, c_cos.codigo AS cod_costo, c_cos.nombre AS nom_costo
                                FROM grupos_inventario gi
                                LEFT JOIN cuentas_puc c_cos ON c_cos.id = gi.cuenta_cos_id
                                WHERE gi.negocio_id = %s AND gi.nombre = %s
                            """, (negocio_id, sold_cat)).fetchone()
                            
                            if gi_sold and gi_sold['cuenta_cos_id']:
                                key = (gi_sold['cuenta_cos_id'], gi_sold['cod_costo'], f"Costo Venta: {sold_name}")
                                debitos_costos[key] = debitos_costos.get(key, 0.0) + total_costo
                
                # Agregar los débitos de costo agrupados por producto vendido
                for (cuenta_puc_id, cuenta_codigo, concepto), monto in debitos_costos.items():
                    if monto > 0:
                        mov_list.append({
                            'cuenta_puc_id': cuenta_puc_id,
                            'cuenta_codigo': cuenta_codigo,
                            'concepto':      concepto,
                            'tipo_mov':      'D',
                            'monto':         monto,
                        })
            except Exception as e_costos:
                print(f"[cont] Error calculando costo de ventas/inventarios por categoria: {e_costos}")

    # Inyección automática de contrapartida de método de pago
    if metodo_pago:
        cuenta_metodo = None
        tipo_mov_contra = 'C'
        tipo_mov_negocio = tipo_doc.get('tipo_movimiento')
        
        if tipo_mov_negocio == 'entrada':
            row_metodo = conn.execute(
                "SELECT cuenta_pago_id FROM parametros_metodos_pago_negocio WHERE negocio_id = %s AND metodo_codigo = %s",
                (negocio_id, metodo_pago)
            ).fetchone()
            if row_metodo and row_metodo['cuenta_pago_id']:
                cuenta_metodo = row_metodo['cuenta_pago_id']
                tipo_mov_contra = 'C'
        elif tipo_mov_negocio == 'venta':
            row_metodo = conn.execute(
                "SELECT cuenta_recaudo_id FROM parametros_metodos_pago_negocio WHERE negocio_id = %s AND metodo_codigo = %s",
                (negocio_id, metodo_pago)
            ).fetchone()
            if row_metodo and row_metodo['cuenta_recaudo_id']:
                cuenta_metodo = row_metodo['cuenta_recaudo_id']
                tipo_mov_contra = 'D'
                
        if cuenta_metodo:
            c_puc = conn.execute("SELECT codigo, nombre FROM cuentas_puc WHERE id = %s", (cuenta_metodo,)).fetchone()
            if c_puc:
                monto_contra = float(variables.get('total_compra') or variables.get('total_venta') or 0.0)
                if monto_contra > 0:
                    # Evitar duplicar si ya se parametrizó explícitamente (mejor remover de la lista anterior)
                    mov_list = [m for m in mov_list if m['cuenta_puc_id'] != cuenta_metodo]
                    mov_list.append({
                        'cuenta_puc_id': cuenta_metodo,
                        'cuenta_codigo': c_puc['codigo'],
                        'concepto':      c_puc['nombre'],
                        'tipo_mov':      tipo_mov_contra,
                        'monto':         monto_contra,
                    })

    if not mov_list:
        return None

    total_deb  = sum(m['monto'] for m in mov_list if m['tipo_mov'] == 'D')
    total_cred = sum(m['monto'] for m in mov_list if m['tipo_mov'] == 'C')
    desc       = descripcion_override or param['descripcion_asiento'] or tipo_doc_codigo
    fecha_uso  = fecha or _date.today()
    _verificar_periodo_cerrado(conn, negocio_id, fecha_uso)

    # Consecutivo contable: si ya viene provisto documento_numero_fisico
    # (resuelto por el llamador), lo usamos directamente sin incrementar el consecutivo.
    # De lo contrario (para documentos que se registran directo desde contabilidad/ventas rápidas sin número),
    # generamos e incrementamos el consecutivo secuencial.
    if documento_numero_fisico:
        numero = f"{tipo_doc_codigo}-{documento_numero_fisico}"
        try:
            num_doc = int(documento_numero_fisico)
        except ValueError:
            num_doc = None
    else:
        num_doc = max((tipo_doc['consecutivo'] or 0) + 1, (tipo_doc['numero_inicio'] or 1))
        conn.execute(
            "UPDATE tipos_documento_negocio SET consecutivo=%s WHERE id=%s",
            (num_doc, tipo_doc['id'])
        )
        numero = f"{tipo_doc_codigo}-{num_doc}"

    comp_id = conn.execute("""
        INSERT INTO comprobantes_contables
            (negocio_id, numero_comprobante, numero_documento, tipo, fecha, descripcion,
             total_debitos, total_creditos, registrado_por, notas, origen_tipo, origen_id, tipo_documento_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Generado automáticamente',%s,%s,%s)
        RETURNING id
    """, (negocio_id, numero, num_doc, tipo_doc_codigo, fecha_uso, desc,
          total_deb, total_cred, registrado_por, origen_tipo, origen_id, tipo_doc['id'])).fetchone()['id']

    for m in mov_list:
        # Validación y control de saldos por documento
        c_doc = conn.execute("SELECT maneja_documentos, naturaleza FROM cuentas_puc WHERE id = %s", (m['cuenta_puc_id'],)).fetchone()
        if c_doc and c_doc['maneja_documentos']:
            t_id = tercero_id
            t_doc = tipo_documento_fisico or tipo_doc_codigo
            d_num = documento_numero_fisico or str(num_doc)
            
            if not t_id:
                raise ValueError("Se requiere seleccionar un tercero para registrar movimientos en una cuenta que maneja documentos.")
            
            es_debito = (m['tipo_mov'] == 'D')
            es_naturaleza_debito = (c_doc['naturaleza'] == 'debito')
            es_incremento = (es_debito == es_naturaleza_debito)
            
            if es_incremento:
                # Nacimiento / Aumento
                existente = conn.execute("""
                    SELECT id, saldo FROM saldo_por_documentos
                    WHERE negocio_id = %s AND tercero_id = %s AND cuenta_id = %s
                      AND tipo_documento_id = %s AND numero_documento = %s
                """, (negocio_id, t_id, m['cuenta_puc_id'], tipo_doc['id'], d_num)).fetchone()
                
                if existente:
                    raise ValueError(
                        f"El documento {t_doc} {d_num} ya existe registrado para este tercero en saldos por documento. "
                        f"No se permite duplicar el documento, incrementar su valor original, "
                        f"ni volver a crear uno nuevo con un saldo diferente."
                    )
                
                conn.execute("""
                    INSERT INTO saldo_por_documentos
                    (negocio_id, tercero_id, cuenta_id, tipo_documento, numero_documento,
                     monto_original, saldo, usuario_id, fecha_hora, tipo_documento_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                """, (negocio_id, t_id, m['cuenta_puc_id'], t_doc, d_num,
                      m['monto'], m['monto'], registrado_por, tipo_doc['id']))
            else:
                # Reducción / Abono
                existente = conn.execute("""
                    SELECT id, saldo FROM saldo_por_documentos
                    WHERE negocio_id = %s AND tercero_id = %s AND cuenta_id = %s
                      AND tipo_documento_id = %s AND numero_documento = %s
                """, (negocio_id, t_id, m['cuenta_puc_id'], tipo_doc['id'], d_num)).fetchone()
                
                if not existente:
                    raise ValueError(
                        f"El documento {t_doc} {d_num} no existe en saldos por documento. "
                        f"No se puede abonar a un documento inexistente."
                    )
                
                saldo_actual = float(existente['saldo'])
                monto_abono = float(m['monto'])
                
                if monto_abono > saldo_actual:
                    raise ValueError(
                        f"El abono pretendido de ${monto_abono:.2f} supera el saldo pendiente actual del documento "
                        f"{t_doc} {d_num} (Saldo actual: ${saldo_actual:.2f}). Por favor, ajuste el valor del abono "
                        f"para que sea menor o igual al saldo pendiente."
                    )
                
                nuevo_saldo = saldo_actual - monto_abono
                conn.execute("""
                    UPDATE saldo_por_documentos 
                    SET saldo = %s, updated_at = NOW()
                    WHERE id = %s
                """, (nuevo_saldo, existente['id']))

        conn.execute("""
            INSERT INTO movimientos_contables
                (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, tercero_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (negocio_id, comp_id, m['cuenta_puc_id'], m['cuenta_codigo'],
              m['concepto'], 'debito' if m['tipo_mov'] == 'D' else 'credito',
              m['monto'], registrado_por, tercero_id))

    return comp_id


def _tipo_doc_para_modulo(conn, negocio_id, modulo):
    """Retorna el tipo_doc predeterminado (o el primero) vinculado a un módulo por sus variables H."""
    return conn.execute("""
        SELECT DISTINCT t.id, t.codigo, t.consecutivo, t.numero_inicio
        FROM tipos_documento_negocio t
        JOIN parametros_contables_negocio p ON p.tipo_doc_id = t.id AND p.negocio_id = t.negocio_id
        JOIN parametros_lineas_contables l  ON l.parametro_id = p.id AND l.origen = 'H'
        JOIN modulo_variables_contables v   ON v.id = l.variable_id
        WHERE t.negocio_id = %s AND p.activo = TRUE AND v.modulo = %s
        ORDER BY t.predeterminado DESC, t.id
        LIMIT 1
    """, (negocio_id, modulo)).fetchone()


def _ejecutar_asiento_costo_mov(conn, negocio_id, producto_id, cantidad, costo_und,
                                 registrado_por=None, descripcion=None, producto_padre_id=None,
                                 tercero_id=None, fecha=None):
    """
    Genera asiento COGS para una salida de inventario por venta:
      Débito  cuenta_cos  (6x) — costo de ventas
      Crédito cuenta_inve (14x) — sale del inventario
    Busca la cuenta via grupos_inventario usando productos.categoria.
    Retorna comprobante_id o None si no hay grupo configurado.
    """
    # Verify switch
    cfg = conn.execute("SELECT contab_costos_categoria FROM config_contabilidad_negocio WHERE negocio_id = %s", (negocio_id,)).fetchone()
    if not cfg or not cfg['contab_costos_categoria']:
        return None

    producto = conn.execute(
        "SELECT nombre, categoria FROM productos WHERE id=%s AND negocio_id=%s",
        (producto_id, negocio_id)
    ).fetchone()
    if not producto or not producto['categoria']:
        return None

    # Resolve category for the Cost of Sales account (6x)
    cat_costo = producto['categoria']
    if producto_padre_id:
        padre = conn.execute("SELECT categoria, nombre FROM productos WHERE id=%s AND negocio_id=%s", (producto_padre_id, negocio_id)).fetchone()
        if padre and padre['categoria']:
            cat_costo = padre['categoria']

    # Load inventory account of component's category
    grupo_inve = conn.execute("""
        SELECT gi.cuenta_inve_id, c.codigo AS cod_inve, c.nombre AS nom_inve
        FROM grupos_inventario gi
        JOIN cuentas_puc c ON c.id = gi.cuenta_inve_id
        WHERE gi.negocio_id=%s AND gi.nombre=%s
    """, (negocio_id, producto['categoria'])).fetchone()

    # Load cost account of sold product's category
    grupo_costo = conn.execute("""
        SELECT gi.cuenta_cos_id, c.codigo AS cod_cos, c.nombre AS nom_cos
        FROM grupos_inventario gi
        JOIN cuentas_puc c ON c.id = gi.cuenta_cos_id
        WHERE gi.negocio_id=%s AND gi.nombre=%s
    """, (negocio_id, cat_costo)).fetchone()

    if not grupo_inve or not grupo_costo:
        return None

    monto = float(Decimal(str(cantidad)) * Decimal(str(costo_und)))
    if monto <= 0:
        return None

    fecha_uso = fecha or _date.today()
    _verificar_periodo_cerrado(conn, negocio_id, fecha_uso)
    desc = descripcion or f'Costo venta: {producto["nombre"]}'
    cnt = conn.execute(
        "SELECT COUNT(*) AS n FROM comprobantes_contables WHERE negocio_id=%s AND tipo='COSTO_VENTA'",
        (negocio_id,)
    ).fetchone()['n']
    numero = f"AUTO-COSTO_VENTA-{(cnt or 0) + 1}"

    comp_id = conn.execute("""
        INSERT INTO comprobantes_contables
            (negocio_id, numero_comprobante, tipo, fecha, descripcion,
             total_debitos, total_creditos, registrado_por, notas)
        VALUES (%s,%s,'COSTO_VENTA',%s,%s,%s,%s,%s,'Costo de venta automático')
        RETURNING id
    """, (negocio_id, numero, fecha_uso, desc, monto, monto, registrado_por)).fetchone()['id']

    # Débito costo de ventas (6x) - from sold product category
    conn.execute("""
        INSERT INTO movimientos_contables
            (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, tercero_id)
        VALUES (%s,%s,%s,%s,%s,'debito',%s,%s,%s)
    """, (negocio_id, comp_id, grupo_costo['cuenta_cos_id'], grupo_costo['cod_cos'], grupo_costo['nom_cos'],
          monto, registrado_por, tercero_id))

    # Crédito inventario (14x) - from component/ingredient category
    conn.execute("""
        INSERT INTO movimientos_contables
            (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, tercero_id)
        VALUES (%s,%s,%s,%s,%s,'credito',%s,%s,%s)
    """, (negocio_id, comp_id, grupo_inve['cuenta_inve_id'], grupo_inve['cod_inve'], grupo_inve['nom_inve'],
          monto, registrado_por, tercero_id))

    return comp_id


def _ejecutar_asiento_produccion(conn, negocio_id, producto_terminado_id, costo_total,
                                 componentes, registrado_por=None, descripcion=None,
                                 origen_tipo=None, origen_id=None,
                                 tipo_documento=None, documento_numero=None,
                                 tipo_documento_id=None):
    """
    Asiento de producción — reclasificación dentro del 14x:
      Débito  cuenta_inve del producto terminado  × costo_total
      Crédito cuenta_inve de cada componente       × cant × costo_und
    componentes: lista de dicts {producto_id, cantidad, costo_und}
    Retorna comprobante_id o None si falta algún grupo configurado.
    """
    # Verify switch
    cfg = conn.execute("SELECT contab_produccion FROM config_contabilidad_negocio WHERE negocio_id = %s", (negocio_id,)).fetchone()
    if not cfg or not cfg['contab_produccion']:
        return None
    def _cuenta_inve(prod_id, categ):
        if not categ:
            return None
        return conn.execute(
            "SELECT gi.cuenta_inve_id, pi.codigo AS cod, pi.nombre AS nom "
            "FROM grupos_inventario gi "
            "JOIN cuentas_puc pi ON pi.id = gi.cuenta_inve_id "
            "WHERE gi.negocio_id=%s AND gi.nombre=%s",
            (negocio_id, categ)
        ).fetchone()

    terminado = conn.execute(
        "SELECT nombre, categoria FROM productos WHERE id=%s AND negocio_id=%s",
        (producto_terminado_id, negocio_id)
    ).fetchone()
    if not terminado:
        return None
    grp_term = _cuenta_inve(producto_terminado_id, terminado['categoria'])
    if not grp_term:
        return None

    monto_total = float(Decimal(str(costo_total)))
    if monto_total <= 0:
        return None

    lineas_cred = []
    for c in componentes:
        prod = conn.execute(
            "SELECT nombre, categoria FROM productos WHERE id=%s", (c['producto_id'],)
        ).fetchone()
        if not prod:
            return None
        grp = _cuenta_inve(c['producto_id'], prod['categoria'])
        if not grp:
            return None
        monto_c = float(Decimal(str(c['cantidad'])) * Decimal(str(c['costo_und'])))
        if monto_c > 0:
            lineas_cred.append({
                'cuenta_id': grp['cuenta_inve_id'],
                'cod':       grp['cod'],
                'nom_prod':  prod['nombre'],
                'monto':     monto_c,
            })

    if not lineas_cred:
        return None

    # Resolve tipo_documento_id if missing but tipo_documento string is provided
    if not tipo_documento_id and tipo_documento:
        td_row = conn.execute("""
            SELECT id FROM tipos_documento_negocio
            WHERE negocio_id = %s AND (UPPER(nombre) = %s OR UPPER(codigo) = %s)
            LIMIT 1
        """, (negocio_id, str(tipo_documento).upper(), str(tipo_documento).upper())).fetchone()
        if td_row:
            tipo_documento_id = td_row['id']

    fecha_uso = _date.today()
    _verificar_periodo_cerrado(conn, negocio_id, fecha_uso)
    desc = descripcion or f'Producción: {terminado["nombre"]}'
    if documento_numero:
        numero = documento_numero
    else:
        cnt = conn.execute(
            "SELECT COUNT(*) AS n FROM comprobantes_contables WHERE negocio_id=%s AND tipo='PRODUCCION'",
            (negocio_id,)
        ).fetchone()['n']
        numero = f"AUTO-PRODUCCION-{(cnt or 0) + 1}"
    total_cred = sum(l['monto'] for l in lineas_cred)

    comp_id = conn.execute("""
        INSERT INTO comprobantes_contables
            (negocio_id, numero_comprobante, tipo, fecha, descripcion,
             total_debitos, total_creditos, registrado_por, notas, origen_tipo, origen_id, tipo_documento_id)
        VALUES (%s,%s,'PRODUCCION',%s,%s,%s,%s,%s,'Producción automática',%s,%s,%s)
        RETURNING id
    """, (negocio_id, numero, fecha_uso, desc,
          monto_total, total_cred, registrado_por, origen_tipo, origen_id, tipo_documento_id)).fetchone()['id']

    conn.execute("""
        INSERT INTO movimientos_contables
            (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por)
        VALUES (%s,%s,%s,%s,%s,'debito',%s,%s)
    """, (negocio_id, comp_id, grp_term['cuenta_inve_id'], grp_term['cod'],
          terminado['nombre'], monto_total, registrado_por))

    for l in lineas_cred:
        conn.execute("""
            INSERT INTO movimientos_contables
                (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por)
            VALUES (%s,%s,%s,%s,%s,'credito',%s,%s)
        """, (negocio_id, comp_id, l['cuenta_id'], l['cod'],
              l['nom_prod'], l['monto'], registrado_por))

    return comp_id


# ── UI ────────────────────────────────────────────────────────

_TIPO_TABLA = {
    'restaurante': 'restaurantes',
    'tienda':      'tiendas',
}

@bp.route('/contabilidad/<tipo>/<slug>')
def contabilidad_por_slug(tipo, slug):
    if not session.get('usuario_id'):
        return __import__('flask').redirect('/login')
    tabla = _TIPO_TABLA.get(tipo)
    if not tabla:
        return "Tipo de negocio no soportado", 404
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        row = conn.execute(
            f"SELECT tercero_id, nombre FROM {tabla} WHERE slug=%s", (slug,)
        ).fetchone()
        conn.close()
        if not row or not row['tercero_id']:
            return "Negocio no encontrado", 404
        return render_template('contabilidad_admin.html',
                               negocio_id=row['tercero_id'],
                               negocio_nombre=row['nombre'])
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return f"Error: {e}", 500


@bp.route('/admin/contabilidad/<int:negocio_id>')
def admin_contabilidad(negocio_id):
    if not session.get('usuario_id'):
        return __import__('flask').redirect('/login')
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        negocio = conn.execute(
            "SELECT nombre FROM terceros WHERE id=%s AND tipo_tercero='negocio'",
            (negocio_id,)
        ).fetchone()
        conn.close()
        if not negocio:
            return "Negocio no encontrado", 404
        return render_template('contabilidad_admin.html',
                               negocio_id=negocio_id,
                               negocio_nombre=negocio['nombre'])
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return f"Error: {e}", 500


# ── API: PUC ──────────────────────────────────────────────────

@bp.route('/api/contabilidad/puc')
def api_puc():
    q        = request.args.get('q', '').strip()
    modo     = request.args.get('modo', '')
    solo_mov = request.args.get('solo_movimiento', '')
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        where, params = ["activo = TRUE"], []
        if q:
            if modo == 'codigo':
                where.append("codigo LIKE %s")
                params.append(f'{q}%')
            elif modo == 'nombre':
                where.append("nombre ILIKE %s")
                params.append(f'%{q}%')
            else:
                where.append("(codigo ILIKE %s OR nombre ILIKE %s)")
                params += [f'%{q}%', f'%{q}%']
        
        if solo_mov == '1':
            where.append("acepta_movimiento = TRUE")
            
        rows = conn.execute(
            f"SELECT id, codigo, nombre, nivel, codigo_padre, naturaleza, acepta_movimiento, maneja_terceros, maneja_documentos "
            f"FROM cuentas_puc WHERE {' AND '.join(where)} ORDER BY codigo LIMIT 1500",
            params
        ).fetchall()
        conn.close()
        return jsonify({'ok': True, 'cuentas': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/puc/<int:cuenta_id>', methods=['PATCH'])
def api_puc_editar(cuenta_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        fields = []
        params = []
        if 'nombre' in data:
            fields.append("nombre = %s")
            params.append(data['nombre'].strip())
        if 'naturaleza' in data:
            fields.append("naturaleza = %s")
            params.append(data['naturaleza'])
        if 'acepta_movimiento' in data:
            fields.append("acepta_movimiento = %s")
            params.append(bool(data['acepta_movimiento']))
        if 'maneja_terceros' in data:
            fields.append("maneja_terceros = %s")
            params.append(bool(data['maneja_terceros']))
        if 'maneja_documentos' in data:
            fields.append("maneja_documentos = %s")
            params.append(bool(data['maneja_documentos']))
        if 'activo' in data:
            fields.append("activo = %s")
            params.append(bool(data['activo']))
            
        if not fields:
            conn.close()
            return jsonify({'ok': False, 'error': 'No hay campos para actualizar'}), 400
            
        params.append(cuenta_id)
        conn.execute(f"UPDATE cuentas_puc SET {', '.join(fields)} WHERE id = %s", params)
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/puc/nueva', methods=['POST'])
def api_puc_nueva():
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    codigo  = (data.get('codigo') or '').strip()
    nombre  = (data.get('nombre') or '').strip()
    nivel   = data.get('nivel')
    codigo_padre = (data.get('codigo_padre') or '').strip() or None
    naturaleza   = data.get('naturaleza', 'debito')
    negocio_id   = data.get('negocio_id')
    if not codigo or not nombre or not nivel:
        return jsonify({'ok': False, 'error': 'Código, nombre y nivel son requeridos'}), 400
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        nueva = conn.execute("""
            INSERT INTO cuentas_puc
                (codigo, nombre, nivel, codigo_padre, naturaleza,
                 acepta_movimiento, maneja_terceros, maneja_documentos,
                 creada_por_negocio_id, revisada)
            VALUES (%s,%s,%s,%s,%s,TRUE,FALSE,FALSE,%s,FALSE)
            ON CONFLICT (codigo) DO NOTHING
            RETURNING id, codigo, nombre
        """, (codigo, nombre, int(nivel), codigo_padre, naturaleza, negocio_id)).fetchone()
        conn.commit(); conn.close()
        if not nueva:
            return jsonify({'ok': False, 'error': f'El código {codigo} ya existe'}), 409
        return jsonify({'ok': True, 'cuenta': dict(nueva)})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Tipos de documento ───────────────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/tipos-doc', methods=['GET'])
def api_tipos_doc_get(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT id, codigo, nombre, activo, consecutivo, numero_inicio, predeterminado, mueve_inventario, tipo_movimiento, es_interno "
            "FROM tipos_documento_negocio WHERE negocio_id=%s ORDER BY nombre", (negocio_id,)
        ).fetchall()
        conn.close()
        return jsonify({'ok': True, 'tipos': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/tipos-doc', methods=['POST'])
def api_tipos_doc_post(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data          = request.get_json() or {}
    nombre        = (data.get('nombre') or '').strip()
    numero_inicio = int(data.get('numero_inicio') or 1)
    predeterminado = bool(data.get('predeterminado', False))
    mueve_inventario = bool(data.get('mueve_inventario', False))
    es_interno     = bool(data.get('es_interno', True))
    tipo_movimiento = data.get('tipo_movimiento')
    if tipo_movimiento:
        tipo_movimiento = tipo_movimiento.strip().lower()
        if tipo_movimiento not in ('entrada', 'salida', 'produccion', 'venta', 'ajuste'):
            tipo_movimiento = None
    else:
        tipo_movimiento = None

    if not nombre:
        return jsonify({'ok': False, 'error': 'El nombre es requerido'}), 400
    
    import re
    # Clean the name to form a slug/code under the hood
    codigo = re.sub(r'[^A-Z0-9_]', '', nombre.upper().replace(' ', '_'))
    if not codigo:
        codigo = 'DOC_NEW'

    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        
        # Check conflict on code and append sequence if necessary
        base_codigo = codigo
        counter = 1
        while True:
            exists = conn.execute("SELECT 1 FROM tipos_documento_negocio WHERE negocio_id=%s AND codigo=%s", (negocio_id, codigo)).fetchone()
            if not exists:
                break
            codigo = f"{base_codigo}_{counter}"
            counter += 1

        nuevo = conn.execute("""
            INSERT INTO tipos_documento_negocio (negocio_id, codigo, nombre, numero_inicio, predeterminado, mueve_inventario, tipo_movimiento, es_interno)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (negocio_id, codigo) DO NOTHING
            RETURNING id, codigo, nombre, activo, consecutivo, numero_inicio, predeterminado, mueve_inventario, tipo_movimiento, es_interno
        """, (negocio_id, codigo, nombre, numero_inicio, predeterminado, mueve_inventario, tipo_movimiento, es_interno)).fetchone()
        conn.commit(); conn.close()
        if not nuevo:
            return jsonify({'ok': False, 'error': f'El tipo de documento ya existe'}), 409
        return jsonify({'ok': True, 'tipo': dict(nuevo)})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/tipos-doc/<int:tid>', methods=['PATCH'])
def api_tipos_doc_patch(negocio_id, tid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        if 'activo' in data:
            conn.execute(
                "UPDATE tipos_documento_negocio SET activo=%s WHERE id=%s AND negocio_id=%s",
                (bool(data['activo']), tid, negocio_id))
        if 'codigo' in data:
            nuevo_codigo = (data['codigo'] or '').strip().upper()
            if not nuevo_codigo:
                return jsonify({'ok': False, 'error': 'El código del documento no puede estar vacío'}), 400
            exists = conn.execute(
                "SELECT 1 FROM tipos_documento_negocio WHERE negocio_id=%s AND codigo=%s AND id!=%s",
                (negocio_id, nuevo_codigo, tid)
            ).fetchone()
            if exists:
                return jsonify({'ok': False, 'error': f'El código {nuevo_codigo} ya está en uso'}), 409
            conn.execute(
                "UPDATE tipos_documento_negocio SET codigo=%s WHERE id=%s AND negocio_id=%s",
                (nuevo_codigo, tid, negocio_id))
        if 'nombre' in data:
            conn.execute(
                "UPDATE tipos_documento_negocio SET nombre=%s WHERE id=%s AND negocio_id=%s",
                (data['nombre'].strip(), tid, negocio_id))
        if 'numero_inicio' in data:
            conn.execute(
                "UPDATE tipos_documento_negocio SET numero_inicio=%s WHERE id=%s AND negocio_id=%s",
                (int(data['numero_inicio'] or 1), tid, negocio_id))
        if 'consecutivo' in data:
            conn.execute(
                "UPDATE tipos_documento_negocio SET consecutivo=%s WHERE id=%s AND negocio_id=%s",
                (int(data['consecutivo'] or 0), tid, negocio_id))
        if 'predeterminado' in data:
            conn.execute(
                "UPDATE tipos_documento_negocio SET predeterminado=%s WHERE id=%s AND negocio_id=%s",
                (bool(data['predeterminado']), tid, negocio_id))
        if 'mueve_inventario' in data:
            conn.execute(
                "UPDATE tipos_documento_negocio SET mueve_inventario=%s WHERE id=%s AND negocio_id=%s",
                (bool(data['mueve_inventario']), tid, negocio_id))
        if 'es_interno' in data:
            conn.execute(
                "UPDATE tipos_documento_negocio SET es_interno=%s WHERE id=%s AND negocio_id=%s",
                (bool(data['es_interno']), tid, negocio_id))
        if 'tipo_movimiento' in data:
            tipo_mov = data['tipo_movimiento']
            if tipo_mov:
                tipo_mov = tipo_mov.strip().lower()
                if tipo_mov not in ('entrada', 'salida', 'produccion', 'venta', 'ajuste'):
                    tipo_mov = None
            else:
                tipo_mov = None
            conn.execute(
                "UPDATE tipos_documento_negocio SET tipo_movimiento=%s WHERE id=%s AND negocio_id=%s",
                (tipo_mov, tid, negocio_id))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Previsualizar asiento desde tipo_doc ─────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/tipos-doc/<int:tid>/previsualizar', methods=['GET'])
def api_tipos_doc_previsualizar_get(negocio_id, tid):
    """Retorna las variables H que el usuario debe ingresar para este tipo de documento."""
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        param = conn.execute(
            "SELECT id, descripcion_asiento FROM parametros_contables_negocio "
            "WHERE negocio_id=%s AND tipo_doc_id=%s AND activo=TRUE",
            (negocio_id, tid)
        ).fetchone()
        if not param:
            conn.close()
            return jsonify({'ok': True, 'tiene_parametrizacion': False, 'variables': []})
        hvars = conn.execute("""
            SELECT DISTINCT v.codigo, v.descripcion, v.modulo
            FROM parametros_lineas_contables l
            JOIN modulo_variables_contables v ON v.id = l.variable_id
            WHERE l.parametro_id=%s AND l.origen='H' AND l.activo=TRUE
            ORDER BY v.modulo, v.codigo
        """, (param['id'],)).fetchall()
        conn.close()
        return jsonify({
            'ok': True,
            'tiene_parametrizacion': True,
            'descripcion': param['descripcion_asiento'],
            'variables': [dict(v) for v in hvars],
        })
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/tipos-doc/<int:tid>/previsualizar', methods=['POST'])
def api_tipos_doc_previsualizar_post(negocio_id, tid):
    """Ejecuta el motor contable sin guardar y retorna las líneas calculadas."""
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data      = request.get_json() or {}
    variables = data.get('variables', {})
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        tipo_doc = conn.execute(
            "SELECT id, codigo, nombre FROM tipos_documento_negocio WHERE id=%s AND negocio_id=%s",
            (tid, negocio_id)
        ).fetchone()
        if not tipo_doc:
            conn.close()
            return jsonify({'ok': False, 'error': 'Tipo de documento no encontrado'}), 404
        param = conn.execute(
            "SELECT id, descripcion_asiento FROM parametros_contables_negocio "
            "WHERE negocio_id=%s AND tipo_doc_id=%s AND activo=TRUE",
            (negocio_id, tid)
        ).fetchone()
        if not param:
            conn.close()
            return jsonify({'ok': False, 'error': 'Sin parametrización activa para este tipo de documento'}), 400
        lineas_db = conn.execute("""
            SELECT l.cuenta_puc_id, l.tipo_mov, l.origen,
                   l.valor_fijo, l.formula, l.orden,
                   c.codigo AS cuenta_codigo, c.nombre AS cuenta_nombre,
                   v.codigo AS var_codigo
            FROM parametros_lineas_contables l
            JOIN cuentas_puc c ON c.id = l.cuenta_puc_id
            LEFT JOIN modulo_variables_contables v ON v.id = l.variable_id
            WHERE l.parametro_id = %s AND l.activo = TRUE
            ORDER BY l.orden
        """, (param['id'],)).fetchall()
        conn.close()

        pos_amounts = {}
        mov_list = []
        for idx, linea in enumerate(lineas_db, start=1):
            origen = linea['origen']
            monto = 0.0
            if origen == 'F':
                monto = float(linea['valor_fijo'] or 0)
            elif origen == 'H':
                monto = float(variables.get(linea['var_codigo'] or '', 0))
            elif origen == 'C':
                formula = linea['formula'] or '0'
                def _repl(m, _pa=dict(pos_amounts)):
                    return str(_pa.get(int(m.group(1)), 0.0))
                formula_eval = re.sub(r'L(\d+)', _repl, formula)
                try:
                    monto = float(eval(formula_eval, {"__builtins__": {}}, {}))  # noqa: S307
                except Exception:
                    monto = 0.0
            pos_amounts[idx] = monto
            mov_list.append({
                'cuenta_puc_id': linea['cuenta_puc_id'],
                'cuenta_codigo': linea['cuenta_codigo'],
                'cuenta_nombre': linea['cuenta_nombre'],
                'tipo_mov':      linea['tipo_mov'],
                'monto':         abs(monto),
                'origen':        origen,
            })

        return jsonify({
            'ok':         True,
            'lineas':     mov_list,
            'descripcion': param['descripcion_asiento'] or tipo_doc['codigo'],
            'tipo_codigo': tipo_doc['codigo'],
        })
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Parametrización ──────────────────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/parametros', methods=['GET'])
def api_parametros_get(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        rows = conn.execute("""
            SELECT p.id, p.tipo_doc_id, t.codigo AS tipo_codigo, t.nombre AS tipo_nombre,
                   p.descripcion_asiento, p.activo
            FROM parametros_contables_negocio p
            JOIN tipos_documento_negocio t ON t.id = p.tipo_doc_id
            WHERE p.negocio_id = %s ORDER BY t.codigo
        """, (negocio_id,)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'parametros': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/parametros', methods=['POST'])
def api_parametros_post(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data        = request.get_json() or {}
    tipo_doc_id = data.get('tipo_doc_id')
    descripcion = (data.get('descripcion_asiento') or '').strip() or None
    if not tipo_doc_id:
        return jsonify({'ok': False, 'error': 'tipo_doc_id es requerido'}), 400
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        conn.execute("""
            INSERT INTO parametros_contables_negocio (negocio_id, tipo_doc_id, descripcion_asiento)
            VALUES (%s,%s,%s)
            ON CONFLICT (negocio_id, tipo_doc_id)
            DO UPDATE SET descripcion_asiento=EXCLUDED.descripcion_asiento, activo=TRUE
        """, (negocio_id, tipo_doc_id, descripcion))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/parametros/<int:pid>', methods=['PATCH'])
def api_parametro_patch(negocio_id, pid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        if 'activo' in data:
            conn.execute(
                "UPDATE parametros_contables_negocio SET activo=%s WHERE id=%s AND negocio_id=%s",
                (bool(data['activo']), pid, negocio_id))
        if 'descripcion_asiento' in data:
            conn.execute(
                "UPDATE parametros_contables_negocio SET descripcion_asiento=%s WHERE id=%s AND negocio_id=%s",
                (data['descripcion_asiento'].strip() or None, pid, negocio_id))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Líneas de parametrización ───────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/parametros/<int:pid>/lineas', methods=['GET'])
def api_param_lineas_get(negocio_id, pid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        lineas = conn.execute("""
            SELECT l.id, l.cuenta_puc_id, c.codigo AS cuenta_codigo, c.nombre AS cuenta_nombre,
                   l.tipo_mov, l.origen, l.valor_fijo, l.formula,
                   l.variable_id, v.codigo AS var_codigo, v.descripcion AS variable_desc, v.modulo AS variable_modulo,
                   l.orden, l.activo
            FROM parametros_lineas_contables l
            JOIN cuentas_puc c ON c.id = l.cuenta_puc_id
            LEFT JOIN modulo_variables_contables v ON v.id = l.variable_id
            WHERE l.parametro_id = %s ORDER BY l.orden, l.id
        """, (pid,)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'lineas': [dict(l) for l in lineas]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/parametros/<int:pid>/lineas', methods=['POST'])
def api_param_lineas_post(negocio_id, pid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data          = request.get_json() or {}
    cuenta_puc_id = data.get('cuenta_puc_id')
    tipo_mov      = (data.get('tipo_mov') or '').upper()
    origen        = (data.get('origen') or 'M').upper()
    valor_fijo    = data.get('valor_fijo')
    formula       = (data.get('formula') or '').strip() or None
    variable_id   = data.get('variable_id')
    orden         = int(data.get('orden') or 0)
    if not cuenta_puc_id or tipo_mov not in ('D', 'C'):
        return jsonify({'ok': False, 'error': 'cuenta_puc_id y tipo_mov (D/C) son requeridos'}), 400
    if origen not in ('M', 'F', 'C', 'H'):
        return jsonify({'ok': False, 'error': 'origen debe ser M, F, C o H'}), 400
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        # Validar fuente única para líneas H
        if origen == 'H' and variable_id:
            nueva_var = conn.execute(
                "SELECT modulo FROM modulo_variables_contables WHERE id=%s", (variable_id,)
            ).fetchone()
            if nueva_var:
                conflicto = conn.execute("""
                    SELECT v.modulo FROM parametros_lineas_contables l
                    JOIN modulo_variables_contables v ON v.id = l.variable_id
                    WHERE l.parametro_id=%s AND l.origen='H' AND l.activo=TRUE AND v.modulo!=%s
                    LIMIT 1
                """, (pid, nueva_var['modulo'])).fetchone()
                if conflicto:
                    conn.close()
                    return jsonify({'ok': False,
                                    'error': f"El parámetro ya usa variables de '{conflicto['modulo']}'. "
                                             f"No se puede mezclar con '{nueva_var['modulo']}'."}), 400
        nueva = conn.execute("""
            INSERT INTO parametros_lineas_contables
                (parametro_id, cuenta_puc_id, tipo_mov, origen, valor_fijo, formula, variable_id, orden)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (pid, cuenta_puc_id, tipo_mov, origen, valor_fijo, formula, variable_id, orden)).fetchone()
        conn.commit(); conn.close()
        return jsonify({'ok': True, 'id': nueva[0]})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/parametros/<int:pid>/lineas/<int:lid>', methods=['DELETE'])
def api_param_linea_delete(negocio_id, pid, lid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        conn.execute("DELETE FROM parametros_lineas_contables WHERE id=%s AND parametro_id=%s", (lid, pid))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Comprobantes ─────────────────────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/comprobantes', methods=['GET'])
def api_comprobantes_get(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        fecha_desde = request.args.get('desde')
        fecha_hasta = request.args.get('hasta')
        tipo_f      = request.args.get('tipo', '')
        where = ["c.negocio_id = %s"]; params = [negocio_id]
        if fecha_desde: where.append("c.fecha >= %s"); params.append(fecha_desde)
        if fecha_hasta: where.append("c.fecha <= %s"); params.append(fecha_hasta)
        if tipo_f:      where.append("c.tipo = %s");  params.append(tipo_f.upper())
        rows = conn.execute(f"""
            SELECT c.id, c.numero_comprobante, c.tipo, c.fecha,
                   c.descripcion, c.total_debitos, c.total_creditos, c.notas, c.created_at,
                   (SELECT COUNT(*) FROM movimientos_contables m WHERE m.comprobante_id = c.id) AS num_lineas
            FROM comprobantes_contables c
            WHERE {' AND '.join(where)}
            ORDER BY c.fecha DESC, c.id DESC LIMIT 200
        """, params).fetchall()
        conn.close()
        return jsonify({'ok': True, 'comprobantes': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/comprobante', methods=['POST'])
def api_comprobante_post(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data        = request.get_json() or {}
    tipo_comp   = (data.get('tipo') or '').strip()
    fecha       = data.get('fecha') or None
    descripcion = (data.get('descripcion') or '').strip() or None
    notas       = (data.get('notas') or '').strip() or None
    lineas      = data.get('lineas', [])
    tipo_doc_id = data.get('tipo_doc_id')          # Type-3: parametrized manual
    if not lineas:
        return jsonify({'ok': False, 'error': 'Debe agregar al menos una línea'}), 400
    total_deb  = sum(float(l.get('debito') or 0) for l in lineas)
    total_cred = sum(float(l.get('credito') or 0) for l in lineas)
    from ..db import get_db_connection
    uid = session['usuario_id']
    try:
        conn = get_db_connection()
        _verificar_periodo_cerrado(conn, negocio_id, fecha)
        _asegurar_tablas(conn)
        num_doc      = None
        numero_comp  = None
        if tipo_doc_id:
            td = conn.execute(
                "SELECT id, codigo, consecutivo, numero_inicio FROM tipos_documento_negocio "
                "WHERE id=%s AND negocio_id=%s",
                (tipo_doc_id, negocio_id)
            ).fetchone()
            if td:
                tipo_comp = td['codigo']
                num_doc   = max((td['consecutivo'] or 0) + 1, (td['numero_inicio'] or 1))
                conn.execute(
                    "UPDATE tipos_documento_negocio SET consecutivo=%s WHERE id=%s",
                    (num_doc, td['id'])
                )
                numero_comp = f"{td['codigo']}-{num_doc}"
        if not tipo_comp:
            conn.close()
            return jsonify({'ok': False, 'error': 'Tipo de comprobante requerido'}), 400
        comp_id = conn.execute("""
            INSERT INTO comprobantes_contables
                (negocio_id, numero_comprobante, numero_documento, tipo, fecha, descripcion,
                 total_debitos, total_creditos, registrado_por, notas)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id
        """, (negocio_id, numero_comp, num_doc, tipo_comp, fecha, descripcion,
              total_deb, total_cred, uid, notas)).fetchone()['id']
        for l in lineas:
            debito  = float(l.get('debito')  or 0)
            credito = float(l.get('credito') or 0)
            monto   = debito if debito > 0 else credito
            tipo_m  = 'debito' if debito > 0 else 'credito'
            tercero_l_id = l.get('tercero_id') or None
            conn.execute("""
                INSERT INTO movimientos_contables
                    (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por, tercero_id)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """, (negocio_id, comp_id, l.get('cuenta_id'), l.get('cuenta_codigo',''),
                  (l.get('concepto') or '').strip() or None, tipo_m, monto, uid, tercero_l_id))
        conn.commit(); conn.close()
        return jsonify({'ok': True, 'comprobante_id': comp_id})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/comprobante/<int:comp_id>/lineas', methods=['GET'])
def api_comprobante_lineas(negocio_id, comp_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        lineas = conn.execute("""
            SELECT m.id, m.tipo, m.cuenta, m.concepto, m.monto, m.cuenta_id,
                   p.codigo AS cuenta_codigo, p.nombre AS cuenta_nombre
            FROM movimientos_contables m
            LEFT JOIN cuentas_puc p ON p.id = m.cuenta_id
            WHERE m.comprobante_id=%s AND m.negocio_id=%s ORDER BY m.id
        """, (comp_id, negocio_id)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'lineas': [dict(l) for l in lineas]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Variables de módulos ─────────────────────────────────

@bp.route('/api/contabilidad/variables-modulos', methods=['GET'])
def api_variables_get():
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        rows = conn.execute(
            "SELECT * FROM modulo_variables_contables ORDER BY modulo, orden, id"
        ).fetchall()
        conn.close()
        return jsonify({'ok': True, 'variables': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Grupos de inventario ─────────────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/grupos-inventario', methods=['GET'])
def api_grupos_get(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        # Categorías reales de productos + su grupo si ya está configurado
        rows = conn.execute("""
            SELECT p.categoria AS nombre,
                   g.id,
                   g.cuenta_inve_id, pi.codigo AS cod_inve, pi.nombre AS nom_inve,
                   g.cuenta_cos_id,  pc.codigo AS cod_cos,  pc.nombre AS nom_cos,
                   g.cuenta_ingre_id, pg.codigo AS cod_ingre, pg.nombre AS nom_ingre,
                   g.cuenta_ajuste_favor_id, pf.codigo AS cod_ajuste_favor, pf.nombre AS nom_ajuste_favor,
                   g.cuenta_ajuste_contra_id, pa.codigo AS cod_ajuste_contra, pa.nombre AS nom_ajuste_contra
            FROM (
                SELECT DISTINCT categoria FROM productos
                WHERE negocio_id = %s AND categoria IS NOT NULL AND categoria <> ''
            ) p
            LEFT JOIN grupos_inventario g
                ON g.negocio_id = %s AND g.nombre = p.categoria
            LEFT JOIN cuentas_puc pi ON pi.id = g.cuenta_inve_id
            LEFT JOIN cuentas_puc pc ON pc.id = g.cuenta_cos_id
            LEFT JOIN cuentas_puc pg ON pg.id = g.cuenta_ingre_id
            LEFT JOIN cuentas_puc pf ON pf.id = g.cuenta_ajuste_favor_id
            LEFT JOIN cuentas_puc pa ON pa.id = g.cuenta_ajuste_contra_id
            ORDER BY p.categoria
        """, (negocio_id, negocio_id)).fetchall()
        conn.close()
        return jsonify({'ok': True, 'grupos': [dict(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/grupos-inventario', methods=['POST'])
def api_grupos_post(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data            = request.get_json() or {}
    nombre          = (data.get('nombre') or '').strip()
    cuenta_inve_id  = data.get('cuenta_inve_id')
    cuenta_cos_id   = data.get('cuenta_cos_id')
    cuenta_ingre_id = data.get('cuenta_ingre_id')
    cuenta_ajuste_favor_id = data.get('cuenta_ajuste_favor_id')
    cuenta_ajuste_contra_id = data.get('cuenta_ajuste_contra_id')
    if not nombre:
        return jsonify({'ok': False, 'error': 'Nombre del grupo es requerido'}), 400
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        row = conn.execute("""
            INSERT INTO grupos_inventario (negocio_id, nombre, cuenta_inve_id, cuenta_cos_id, cuenta_ingre_id, cuenta_ajuste_favor_id, cuenta_ajuste_contra_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (negocio_id, nombre) DO UPDATE
                SET cuenta_inve_id=EXCLUDED.cuenta_inve_id, 
                    cuenta_cos_id=EXCLUDED.cuenta_cos_id, 
                    cuenta_ingre_id=EXCLUDED.cuenta_ingre_id,
                    cuenta_ajuste_favor_id=EXCLUDED.cuenta_ajuste_favor_id,
                    cuenta_ajuste_contra_id=EXCLUDED.cuenta_ajuste_contra_id
            RETURNING id
        """, (negocio_id, nombre, cuenta_inve_id, cuenta_cos_id, cuenta_ingre_id, cuenta_ajuste_favor_id, cuenta_ajuste_contra_id)).fetchone()
        conn.commit(); conn.close()
        return jsonify({'ok': True, 'id': row['id']})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/grupos-inventario/<int:gid>', methods=['PATCH', 'DELETE'])
def api_grupo_item(negocio_id, gid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        if request.method == 'DELETE':
            conn.execute("DELETE FROM grupos_inventario WHERE id=%s AND negocio_id=%s", (gid, negocio_id))
        else:
            data = request.get_json() or {}
            if 'cuenta_inve_id' in data:
                conn.execute("UPDATE grupos_inventario SET cuenta_inve_id=%s WHERE id=%s AND negocio_id=%s",
                             (data['cuenta_inve_id'], gid, negocio_id))
            if 'cuenta_cos_id' in data:
                conn.execute("UPDATE grupos_inventario SET cuenta_cos_id=%s WHERE id=%s AND negocio_id=%s",
                             (data['cuenta_cos_id'], gid, negocio_id))
            if 'cuenta_ingre_id' in data:
                conn.execute("UPDATE grupos_inventario SET cuenta_ingre_id=%s WHERE id=%s AND negocio_id=%s",
                             (data['cuenta_ingre_id'], gid, negocio_id))
            if 'cuenta_ajuste_favor_id' in data:
                conn.execute("UPDATE grupos_inventario SET cuenta_ajuste_favor_id=%s WHERE id=%s AND negocio_id=%s",
                             (data['cuenta_ajuste_favor_id'], gid, negocio_id))
            if 'cuenta_ajuste_contra_id' in data:
                conn.execute("UPDATE grupos_inventario SET cuenta_ajuste_contra_id=%s WHERE id=%s AND negocio_id=%s",
                             (data['cuenta_ajuste_contra_id'], gid, negocio_id))
            if 'nombre' in data:
                conn.execute("UPDATE grupos_inventario SET nombre=%s WHERE id=%s AND negocio_id=%s",
                             (data['nombre'].strip(), gid, negocio_id))
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── Programaciones contables (Tipo 4) ─────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/programaciones', methods=['GET'])
def api_programaciones_list(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        rows = conn.execute("""
            SELECT p.id, p.tipo_doc_id, t.codigo AS tipo_doc_codigo, t.nombre AS tipo_doc_nombre,
                   p.descripcion, p.frecuencia, p.dia_semana, p.dia_mes,
                   p.hora::text AS hora, p.variables_h, p.activo,
                   p.ultimo_ejecutado, p.proximo_ejecutado, p.ultimo_resultado
            FROM programaciones_contables p
            JOIN tipos_documento_negocio t ON t.id = p.tipo_doc_id
            WHERE p.negocio_id = %s
            ORDER BY p.id
        """, (negocio_id,)).fetchall()
        conn.close()
        def _row(r):
            d = dict(r)
            for k in ('ultimo_ejecutado', 'proximo_ejecutado'):
                if d[k]:
                    d[k] = d[k].isoformat()
            if d['variables_h'] is None:
                d['variables_h'] = {}
            return d
        return jsonify({'ok': True, 'programaciones': [_row(r) for r in rows]})
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/programaciones', methods=['POST'])
def api_programaciones_create(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    import json as _json
    data = request.get_json() or {}
    tipo_doc_id  = data.get('tipo_doc_id')
    descripcion  = (data.get('descripcion') or '').strip() or None
    frecuencia   = data.get('frecuencia', 'mensual')
    dia_semana   = data.get('dia_semana')
    dia_mes      = data.get('dia_mes', 1)
    hora_str     = data.get('hora', '08:00')
    variables_h  = data.get('variables_h', {})
    if not tipo_doc_id:
        return jsonify({'ok': False, 'error': 'tipo_doc_id requerido'}), 400
    from ..db import get_db_connection
    import datetime as _datetime
    try:
        hora_val = _datetime.time.fromisoformat(hora_str)
    except Exception:
        hora_val = _datetime.time(8, 0)
    proximo = _calcular_proximo(frecuencia, dia_semana, dia_mes, hora_val)
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        row = conn.execute("""
            INSERT INTO programaciones_contables
                (negocio_id, tipo_doc_id, descripcion, frecuencia, dia_semana, dia_mes,
                 hora, variables_h, activo, proximo_ejecutado)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,TRUE,%s)
            RETURNING id
        """, (negocio_id, tipo_doc_id, descripcion, frecuencia, dia_semana, dia_mes,
              hora_str, _json.dumps(variables_h), proximo)).fetchone()
        conn.commit(); conn.close()
        return jsonify({'ok': True, 'id': row['id'], 'proximo_ejecutado': proximo.isoformat()})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/programaciones/<int:pid>', methods=['PATCH', 'DELETE'])
def api_programaciones_item(negocio_id, pid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    import json as _json
    try:
        conn = get_db_connection()
        if request.method == 'DELETE':
            conn.execute("DELETE FROM programaciones_contables WHERE id=%s AND negocio_id=%s",
                         (pid, negocio_id))
        else:
            data = request.get_json() or {}
            sets, vals = [], []
            for campo in ('descripcion', 'frecuencia', 'dia_semana', 'dia_mes', 'hora', 'activo'):
                if campo in data:
                    sets.append(f"{campo}=%s"); vals.append(data[campo])
            if 'variables_h' in data:
                sets.append("variables_h=%s"); vals.append(_json.dumps(data['variables_h']))
            if sets:
                vals += [pid, negocio_id]
                conn.execute(f"UPDATE programaciones_contables SET {','.join(sets)} "
                             f"WHERE id=%s AND negocio_id=%s", vals)
        conn.commit(); conn.close()
        return jsonify({'ok': True})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/programaciones/<int:pid>/ejecutar', methods=['POST'])
def api_programaciones_ejecutar(negocio_id, pid):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        prog = conn.execute("""
            SELECT p.*, t.codigo AS tipo_doc_codigo
            FROM programaciones_contables p
            JOIN tipos_documento_negocio t ON t.id = p.tipo_doc_id
            WHERE p.id=%s AND p.negocio_id=%s
        """, (pid, negocio_id)).fetchone()
        if not prog:
            conn.close()
            return jsonify({'ok': False, 'error': 'Programación no encontrada'}), 404
        variables_h = prog['variables_h'] or {}
        resultado = _ejecutar_asiento_automatico(
            conn, negocio_id, prog['tipo_doc_codigo'], variables_h,
            registrado_por=session.get('usuario_id'),
            descripcion_override=prog['descripcion']
        )
        ahora = _dt.now()
        proximo = _calcular_proximo(prog['frecuencia'], prog['dia_semana'], prog['dia_mes'],
                                    prog['hora'], desde=ahora)
        conn.execute("""
            UPDATE programaciones_contables
            SET ultimo_ejecutado=%s, proximo_ejecutado=%s, ultimo_resultado=%s
            WHERE id=%s
        """, (ahora, proximo, str(resultado.get('mensaje', ''))[:150], pid))
        conn.commit(); conn.close()
        return jsonify({'ok': True, 'resultado': resultado,
                        'proximo_ejecutado': proximo.isoformat()})
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


@bp.route('/api/contabilidad/<int:negocio_id>/config', methods=['GET', 'POST'])
def api_contabilidad_config(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        
        # Ensure row exists
        row = conn.execute("SELECT contab_entradas_categoria, contab_costos_categoria, contab_produccion FROM config_contabilidad_negocio WHERE negocio_id = %s", (negocio_id,)).fetchone()
        if not row:
            conn.execute("INSERT INTO config_contabilidad_negocio (negocio_id, contab_entradas_categoria, contab_costos_categoria, contab_produccion) VALUES (%s, FALSE, FALSE, FALSE) ON CONFLICT (negocio_id) DO NOTHING", (negocio_id,))
            conn.commit()
            row = {'contab_entradas_categoria': False, 'contab_costos_categoria': False, 'contab_produccion': False}
        
        if request.method == 'POST':
            data = request.get_json() or {}
            contab_entradas_categoria = bool(data.get('contab_entradas_categoria'))
            contab_costos_categoria = bool(data.get('contab_costos_categoria'))
            contab_produccion = bool(data.get('contab_produccion'))
            
            conn.execute("""
                UPDATE config_contabilidad_negocio
                SET contab_entradas_categoria = %s,
                    contab_costos_categoria = %s,
                    contab_produccion = %s
                WHERE negocio_id = %s
            """, (contab_entradas_categoria, contab_costos_categoria, contab_produccion, negocio_id))
            conn.commit()
            return jsonify({'ok': True})
            
        return jsonify({'ok': True, 'config': dict(row)})
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/contabilidad/<int:negocio_id>/config-metodos', methods=['GET', 'POST'])
def api_contabilidad_config_metodos(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    from ..db import get_db_connection
    conn = get_db_connection()
    try:
        _asegurar_tablas(conn)
        
        if request.method == 'POST':
            data = request.get_json() or {}
            metodo_codigo = (data.get('metodo_codigo') or '').strip()
            cuenta_recaudo_id = data.get('cuenta_recaudo_id')
            cuenta_pago_id = data.get('cuenta_pago_id')
            
            if not metodo_codigo:
                return jsonify({'ok': False, 'error': 'Código de método requerido'}), 400
                
            recaudo_id = int(cuenta_recaudo_id) if cuenta_recaudo_id else None
            pago_id = int(cuenta_pago_id) if cuenta_pago_id else None
            
            conn.execute("""
                INSERT INTO parametros_metodos_pago_negocio 
                (negocio_id, metodo_codigo, cuenta_recaudo_id, cuenta_pago_id)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (negocio_id, metodo_codigo) 
                DO UPDATE SET 
                    cuenta_recaudo_id = EXCLUDED.cuenta_recaudo_id,
                    cuenta_pago_id = EXCLUDED.cuenta_pago_id
            """, (negocio_id, metodo_codigo, recaudo_id, pago_id))
            conn.commit()
            return jsonify({'ok': True})
            
        # GET: list active payment methods
        cfg = conn.execute("SELECT metodos_pago FROM config_negocio WHERE tercero_id = %s", (negocio_id,)).fetchone()
        activos = []
        if cfg and cfg['metodos_pago']:
            activos = cfg['metodos_pago']
            if isinstance(activos, str):
                import json
                try: activos = json.loads(activos)
                except Exception: activos = []
        
        if not isinstance(activos, list):
            activos = []
            
        if 'credito' not in activos:
            activos.append('credito')
            
        catalogo = []
        if activos:
            placeholders = ', '.join(['%s'] * len(activos))
            catalogo = conn.execute(f"""
                SELECT nombre, codigo 
                FROM metodos_pago_catalogo 
                WHERE codigo IN ({placeholders}) AND activo = TRUE
                ORDER BY orden, nombre
            """, tuple(activos)).fetchall()
        
        mappings = conn.execute("""
            SELECT pm.metodo_codigo, 
                   pm.cuenta_recaudo_id, cr.codigo AS recaudo_codigo, cr.nombre AS recaudo_nombre,
                   pm.cuenta_pago_id, cp.codigo AS pago_codigo, cp.nombre AS pago_nombre
            FROM parametros_metodos_pago_negocio pm
            LEFT JOIN cuentas_puc cr ON cr.id = pm.cuenta_recaudo_id
            LEFT JOIN cuentas_puc cp ON cp.id = pm.cuenta_pago_id
            WHERE pm.negocio_id = %s
        """, (negocio_id,)).fetchall()
        
        mapping_dict = {m['metodo_codigo']: dict(m) for m in mappings}
        
        result = []
        for c in catalogo:
            m = mapping_dict.get(c['codigo'], {})
            result.append({
                'codigo': c['codigo'],
                'nombre': c['nombre'],
                'cuenta_recaudo_id': m.get('cuenta_recaudo_id'),
                'recaudo_codigo': m.get('recaudo_codigo'),
                'recaudo_nombre': m.get('recaudo_nombre'),
                'cuenta_pago_id': m.get('cuenta_pago_id'),
                'pago_codigo': m.get('pago_codigo'),
                'pago_nombre': m.get('pago_nombre'),
            })
            
        return jsonify({'ok': True, 'metodos': result})
    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


@bp.route('/api/contabilidad/<int:negocio_id>/reporte-movimientos')
def api_reporte_movimientos(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403

    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    cuenta_id = request.args.get('cuenta_id')
    tercero_id = request.args.get('tercero_id')
    agrupar = request.args.get('agrupar', 'sin_agrupar') # 'sin_agrupar', 'cuenta', 'tercero'

    if not desde or not hasta:
        return jsonify({'ok': False, 'error': 'Fechas desde y hasta son requeridas'}), 400

    try:
        cuenta_id = int(cuenta_id) if cuenta_id else None
        tercero_id = int(tercero_id) if tercero_id else None
    except ValueError:
        return jsonify({'ok': False, 'error': 'IDs invalidos'}), 400

    from ..db import get_db_connection
    conn = get_db_connection()
    try:
        where_anterior = ["c.negocio_id = %s", "c.fecha < %s"]
        params_anterior = [negocio_id, desde]

        where_periodo = ["c.negocio_id = %s", "c.fecha >= %s", "c.fecha <= %s"]
        params_periodo = [negocio_id, desde, hasta]

        if cuenta_id:
            where_anterior.append("m.cuenta_id = %s")
            params_anterior.append(cuenta_id)
            where_periodo.append("m.cuenta_id = %s")
            params_periodo.append(cuenta_id)

        if tercero_id:
            where_anterior.append("m.tercero_id = %s")
            params_anterior.append(tercero_id)
            where_periodo.append("m.tercero_id = %s")
            params_periodo.append(tercero_id)

        if cuenta_id and tercero_id:
            agrupar = 'sin_agrupar'

        blocks = []

        if agrupar == 'sin_agrupar':
            sa_row = conn.execute(f"""
                SELECT 
                    COALESCE(SUM(CASE WHEN m.tipo IN ('debito', 'D') THEN m.monto ELSE 0 END), 0) AS total_debitos,
                    COALESCE(SUM(CASE WHEN m.tipo IN ('credito', 'C') THEN m.monto ELSE 0 END), 0) AS total_credits
                FROM movimientos_contables m
                JOIN comprobantes_contables c ON c.id = m.comprobante_id
                WHERE {" AND ".join(where_anterior)}
            """, params_anterior).fetchone()

            saldo_anterior = float(sa_row['total_debitos'] - sa_row['total_credits'])

            movs = conn.execute(f"""
                SELECT 
                    m.id,
                    c.fecha,
                    c.numero_comprobante,
                    COALESCE(tdn.nombre, c.tipo) AS tipo_comprobante,
                    m.cuenta_id,
                    p.codigo AS cuenta_codigo,
                    p.nombre AS cuenta_nombre,
                    m.tercero_id,
                    t.nombre AS tercero_nombre,
                    m.concepto,
                    m.tipo AS tipo_mov,
                    m.monto
                FROM movimientos_contables m
                JOIN comprobantes_contables c ON c.id = m.comprobante_id
                LEFT JOIN tipos_documento_negocio tdn ON tdn.id = c.tipo_documento_id
                LEFT JOIN cuentas_puc p ON p.id = m.cuenta_id
                LEFT JOIN terceros t ON t.id = m.tercero_id
                WHERE {" AND ".join(where_periodo)}
                ORDER BY c.fecha, c.numero_comprobante, m.id
            """, params_periodo).fetchall()

            lineas = []
            saldo_acc = saldo_anterior
            total_deb = 0.0
            total_cred = 0.0

            for r in movs:
                monto = float(r['monto'])
                es_deb = r['tipo_mov'] in ('debito', 'D')
                if es_deb:
                    deb_val = monto
                    cred_val = 0.0
                    saldo_acc += deb_val
                    total_deb += deb_val
                else:
                    deb_val = 0.0
                    cred_val = monto
                    saldo_acc -= cred_val
                    total_cred += cred_val

                lineas.append({
                    'id': r['id'],
                    'fecha': r['fecha'].strftime('%Y-%m-%d') if r['fecha'] else '',
                    'numero_comprobante': r['numero_comprobante'],
                    'tipo_comprobante': r['tipo_comprobante'],
                    'cuenta_id': r['cuenta_id'],
                    'cuenta_codigo': r['cuenta_codigo'],
                    'cuenta_nombre': r['cuenta_nombre'],
                    'tercero_id': r['tercero_id'],
                    'tercero_nombre': r['tercero_nombre'] or 'Tercero Ocasional',
                    'concepto': r['concepto'],
                    'debito': deb_val,
                    'credito': cred_val,
                    'saldo': saldo_acc
                })

            blocks.append({
                'title': 'Movimientos Contables - Consulta Cronológica',
                'saldo_anterior': saldo_anterior,
                'lineas': lineas,
                'total_debitos': total_deb,
                'total_creditos': total_cred,
                'saldo_final': saldo_anterior + total_deb - total_cred
            })

        elif agrupar == 'cuenta':
            sa_rows = conn.execute(f"""
                SELECT 
                    m.cuenta_id,
                    p.codigo AS cuenta_codigo,
                    p.nombre AS cuenta_nombre,
                    COALESCE(SUM(CASE WHEN m.tipo IN ('debito', 'D') THEN m.monto ELSE 0 END), 0) AS total_debitos,
                    COALESCE(SUM(CASE WHEN m.tipo IN ('credito', 'C') THEN m.monto ELSE 0 END), 0) AS total_credits
                FROM movimientos_contables m
                JOIN comprobantes_contables c ON c.id = m.comprobante_id
                JOIN cuentas_puc p ON p.id = m.cuenta_id
                WHERE {" AND ".join(where_anterior)}
                GROUP BY m.cuenta_id, p.codigo, p.nombre
            """, params_anterior).fetchall()

            saldos_ant_map = {}
            cuenta_meta = {}
            for r in sa_rows:
                cid = r['cuenta_id']
                saldos_ant_map[cid] = float(r['total_debitos'] - r['total_credits'])
                cuenta_meta[cid] = {'codigo': r['cuenta_codigo'], 'nombre': r['cuenta_nombre']}

            movs = conn.execute(f"""
                SELECT 
                    m.id,
                    c.fecha,
                    c.numero_comprobante,
                    COALESCE(tdn.nombre, c.tipo) AS tipo_comprobante,
                    m.cuenta_id,
                    p.codigo AS cuenta_codigo,
                    p.nombre AS cuenta_nombre,
                    m.tercero_id,
                    t.nombre AS tercero_nombre,
                    m.concepto,
                    m.tipo AS tipo_mov,
                    m.monto
                FROM movimientos_contables m
                JOIN comprobantes_contables c ON c.id = m.comprobante_id
                LEFT JOIN tipos_documento_negocio tdn ON tdn.id = c.tipo_documento_id
                JOIN cuentas_puc p ON p.id = m.cuenta_id
                LEFT JOIN terceros t ON t.id = m.tercero_id
                WHERE {" AND ".join(where_periodo)}
                ORDER BY p.codigo, c.fecha, c.numero_comprobante, m.id
            """, params_periodo).fetchall()

            movs_por_cuenta = {}
            for r in movs:
                cid = r['cuenta_id']
                if cid not in movs_por_cuenta:
                    movs_por_cuenta[cid] = []
                movs_por_cuenta[cid].append(r)
                if cid not in cuenta_meta:
                    cuenta_meta[cid] = {'codigo': r['cuenta_codigo'], 'nombre': r['cuenta_nombre']}

            todos_cuenta_ids = set(saldos_ant_map.keys()) | set(movs_por_cuenta.keys())
            for cid in sorted(todos_cuenta_ids, key=lambda x: cuenta_meta[x]['codigo']):
                meta = cuenta_meta[cid]
                saldo_ant = saldos_ant_map.get(cid, 0.0)
                m_list = movs_por_cuenta.get(cid, [])

                if saldo_ant == 0.0 and not m_list:
                    continue

                lineas = []
                saldo_acc = saldo_ant
                total_deb = 0.0
                total_cred = 0.0

                for r in m_list:
                    monto = float(r['monto'])
                    es_deb = r['tipo_mov'] in ('debito', 'D')
                    if es_deb:
                        deb_val = monto
                        cred_val = 0.0
                        saldo_acc += deb_val
                        total_deb += deb_val
                    else:
                        deb_val = 0.0
                        cred_val = monto
                        saldo_acc -= cred_val
                        total_cred += cred_val

                    lineas.append({
                        'id': r['id'],
                        'fecha': r['fecha'].strftime('%Y-%m-%d') if r['fecha'] else '',
                        'numero_comprobante': r['numero_comprobante'],
                        'tipo_comprobante': r['tipo_comprobante'],
                        'tercero_id': r['tercero_id'],
                        'tercero_nombre': r['tercero_nombre'] or 'Tercero Ocasional',
                        'concepto': r['concepto'],
                        'debito': deb_val,
                        'credito': cred_val,
                        'saldo': saldo_acc
                    })

                blocks.append({
                    'title': f"{meta['codigo']} - {meta['nombre']}",
                    'cuenta_id': cid,
                    'cuenta_codigo': meta['codigo'],
                    'cuenta_nombre': meta['nombre'],
                    'saldo_anterior': saldo_ant,
                    'lineas': lineas,
                    'total_debitos': total_deb,
                    'total_creditos': total_cred,
                    'saldo_final': saldo_ant + total_deb - total_cred
                })

        elif agrupar == 'tercero':
            sa_rows = conn.execute(f"""
                SELECT 
                    m.tercero_id,
                    t.nombre AS tercero_nombre,
                    COALESCE(SUM(CASE WHEN m.tipo IN ('debito', 'D') THEN m.monto ELSE 0 END), 0) AS total_debitos,
                    COALESCE(SUM(CASE WHEN m.tipo IN ('credito', 'C') THEN m.monto ELSE 0 END), 0) AS total_credits
                FROM movimientos_contables m
                JOIN comprobantes_contables c ON c.id = m.comprobante_id
                LEFT JOIN terceros t ON t.id = m.tercero_id
                WHERE {" AND ".join(where_anterior)}
                GROUP BY m.tercero_id, t.nombre
            """, params_anterior).fetchall()

            saldos_ant_map = {}
            tercero_meta = {}
            for r in sa_rows:
                tid = r['tercero_id']
                saldos_ant_map[tid] = float(r['total_debitos'] - r['total_credits'])
                tercero_meta[tid] = r['tercero_nombre'] or 'Tercero Ocasional'

            movs = conn.execute(f"""
                SELECT 
                    m.id,
                    c.fecha,
                    c.numero_comprobante,
                    COALESCE(tdn.nombre, c.tipo) AS tipo_comprobante,
                    m.cuenta_id,
                    p.codigo AS cuenta_codigo,
                    p.nombre AS cuenta_nombre,
                    m.tercero_id,
                    t.nombre AS tercero_nombre,
                    m.concepto,
                    m.tipo AS tipo_mov,
                    m.monto
                FROM movimientos_contables m
                JOIN comprobantes_contables c ON c.id = m.comprobante_id
                LEFT JOIN tipos_documento_negocio tdn ON tdn.id = c.tipo_documento_id
                LEFT JOIN cuentas_puc p ON p.id = m.cuenta_id
                LEFT JOIN terceros t ON t.id = m.tercero_id
                WHERE {" AND ".join(where_periodo)}
                ORDER BY COALESCE(t.nombre, 'Tercero Ocasional'), c.fecha, c.numero_comprobante, m.id
            """, params_periodo).fetchall()

            movs_por_tercero = {}
            for r in movs:
                tid = r['tercero_id']
                if tid not in movs_por_tercero:
                    movs_por_tercero[tid] = []
                movs_por_tercero[tid].append(r)
                if tid not in tercero_meta:
                    tercero_meta[tid] = r['tercero_nombre'] or 'Tercero Ocasional'

            todos_tercero_ids = set(saldos_ant_map.keys()) | set(movs_por_tercero.keys())
            sorted_tids = sorted(todos_tercero_ids, key=lambda x: tercero_meta.get(x, 'Tercero Ocasional'))

            for tid in sorted_tids:
                name = tercero_meta.get(tid, 'Tercero Ocasional')
                saldo_ant = saldos_ant_map.get(tid, 0.0)
                m_list = movs_por_tercero.get(tid, [])

                if saldo_ant == 0.0 and not m_list:
                    continue

                lineas = []
                saldo_acc = saldo_ant
                total_deb = 0.0
                total_cred = 0.0

                for r in m_list:
                    monto = float(r['monto'])
                    es_deb = r['tipo_mov'] in ('debito', 'D')
                    if es_deb:
                        deb_val = monto
                        cred_val = 0.0
                        saldo_acc += deb_val
                        total_deb += deb_val
                    else:
                        deb_val = 0.0
                        cred_val = monto
                        saldo_acc -= cred_val
                        total_cred += cred_val

                    lineas.append({
                        'id': r['id'],
                        'fecha': r['fecha'].strftime('%Y-%m-%d') if r['fecha'] else '',
                        'numero_comprobante': r['numero_comprobante'],
                        'tipo_comprobante': r['tipo_comprobante'],
                        'cuenta_id': r['cuenta_id'],
                        'cuenta_codigo': r['cuenta_codigo'],
                        'cuenta_nombre': r['cuenta_nombre'],
                        'concepto': r['concepto'],
                        'debito': deb_val,
                        'credito': cred_val,
                        'saldo': saldo_acc
                    })

                blocks.append({
                    'title': f"Tercero: {name}",
                    'tercero_id': tid,
                    'tercero_nombre': name,
                    'saldo_anterior': saldo_ant,
                    'lineas': lineas,
                    'total_debitos': total_deb,
                    'total_creditos': total_cred,
                    'saldo_final': saldo_ant + total_deb - total_cred
                })

        return jsonify({'ok': True, 'blocks': blocks})

    except Exception as e:
        try: conn.rollback()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
    finally:
        conn.close()


# ── API: Balance de Comprobación ──────────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/balance-comprobacion', methods=['GET'])
def api_balance_comprobacion(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    
    # Si no se proveen fechas, usar el mes actual
    if not desde or not hasta:
        today = _date.today()
        desde = today.strftime('%Y-%m-01')
        import calendar
        last_day = calendar.monthrange(today.year, today.month)[1]
        hasta = today.strftime(f'%Y-%m-{last_day:02d}')
        
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        
        # 1. Obtener todas las cuentas del PUC para mapear nombres y jerarquías
        puc_rows = conn.execute("""
            SELECT id, codigo, nombre, nivel, naturaleza, codigo_padre
            FROM cuentas_puc
            WHERE creada_por_negocio_id IS NULL OR creada_por_negocio_id = %s
        """, (negocio_id,)).fetchall()
        puc_map = {r['codigo']: dict(r) for r in puc_rows}
        
        # 2. Consultar saldos y movimientos acumulados para cuentas con movimiento
        mov_rows = conn.execute("""
            SELECT 
                c.id as cuenta_id, 
                c.codigo, 
                c.nombre, 
                c.naturaleza,
                COALESCE(SUM(CASE WHEN cc.fecha < %s AND m.tipo IN ('debito', 'D') THEN m.monto ELSE 0 END), 0) AS deb_ant,
                COALESCE(SUM(CASE WHEN cc.fecha < %s AND m.tipo IN ('credito', 'C') THEN m.monto ELSE 0 END), 0) AS cred_ant,
                COALESCE(SUM(CASE WHEN cc.fecha >= %s AND cc.fecha <= %s AND m.tipo IN ('debito', 'D') THEN m.monto ELSE 0 END), 0) AS deb_per,
                COALESCE(SUM(CASE WHEN cc.fecha >= %s AND cc.fecha <= %s AND m.tipo IN ('credito', 'C') THEN m.monto ELSE 0 END), 0) AS cred_per
            FROM cuentas_puc c
            LEFT JOIN movimientos_contables m ON m.cuenta_id = c.id AND m.negocio_id = %s
            LEFT JOIN comprobantes_contables cc ON m.comprobante_id = cc.id
            WHERE c.acepta_movimiento = TRUE
            GROUP BY c.id, c.codigo, c.nombre, c.naturaleza
        """, (desde, desde, desde, hasta, desde, hasta, negocio_id)).fetchall()
        
        # 3. Inicializar el árbol de resultados con las cuentas de nivel 1 y 2
        result_map = {}
        for code, r in puc_map.items():
            if r['nivel'] in (1, 2):
                result_map[code] = {
                    'id': r['id'],
                    'codigo': r['codigo'],
                    'nombre': r['nombre'],
                    'nivel': r['nivel'],
                    'naturaleza': r['naturaleza'],
                    'deb_ant': 0.0,
                    'cred_ant': 0.0,
                    'deb_per': 0.0,
                    'cred_per': 0.0,
                }
                
        # 4. Procesar cuentas con movimientos y acumular hacia arriba
        for r in mov_rows:
            deb_ant = float(r['deb_ant'])
            cred_ant = float(r['cred_ant'])
            deb_per = float(r['deb_per'])
            cred_per = float(r['cred_per'])
            
            # Si no hay movimientos ni saldo, no la agregamos
            if deb_ant == 0.0 and cred_ant == 0.0 and deb_per == 0.0 and cred_per == 0.0:
                continue
                
            code = r['codigo']
            result_map[code] = {
                'id': r['cuenta_id'],
                'codigo': r['codigo'],
                'nombre': r['nombre'],
                'nivel': puc_map.get(code, {}).get('nivel', 4),
                'naturaleza': r['naturaleza'],
                'deb_ant': deb_ant,
                'cred_ant': cred_ant,
                'deb_per': deb_per,
                'cred_per': cred_per,
            }
            
            # Acumular hacia arriba en los padres
            curr_code = code
            while curr_code:
                parent_info = puc_map.get(curr_code)
                if not parent_info:
                    break
                parent_code = parent_info['codigo_padre']
                if not parent_code:
                    break
                
                # Si el padre no está en result_map, agregarlo
                if parent_code not in result_map:
                    p_info = puc_map.get(parent_code)
                    if p_info:
                        result_map[parent_code] = {
                            'id': p_info['id'],
                            'codigo': p_info['codigo'],
                            'nombre': p_info['nombre'],
                            'nivel': p_info['nivel'],
                            'naturaleza': p_info['naturaleza'],
                            'deb_ant': 0.0,
                            'cred_ant': 0.0,
                            'deb_per': 0.0,
                            'cred_per': 0.0,
                        }
                
                if parent_code in result_map:
                    result_map[parent_code]['deb_ant'] += deb_ant
                    result_map[parent_code]['cred_ant'] += cred_ant
                    result_map[parent_code]['deb_per'] += deb_per
                    result_map[parent_code]['cred_per'] += cred_per
                
                curr_code = parent_code
                
        # 5. Formatear y calcular saldos finales para la respuesta
        cuentas_list = []
        for code, r in result_map.items():
            nat = r['naturaleza']
            deb_ant = r['deb_ant']
            cred_ant = r['cred_ant']
            deb_per = r['deb_per']
            cred_per = r['cred_per']
            
            if nat == 'debito':
                saldo_anterior = deb_ant - cred_ant
                saldo_final = saldo_anterior + deb_per - cred_per
            else:
                saldo_anterior = cred_ant - deb_ant
                saldo_final = saldo_anterior + cred_per - deb_per
                
            cuentas_list.append({
                'id': r['id'],
                'codigo': r['codigo'],
                'nombre': r['nombre'],
                'nivel': r['nivel'],
                'naturaleza': nat,
                'saldo_anterior': saldo_anterior,
                'debito': deb_per,
                'credito': cred_per,
                'saldo_final': saldo_final
            })
            
        # Ordenar por código contable
        cuentas_list.sort(key=lambda x: x['codigo'])
        
        # Verificar si el periodo correspondiente a "hasta" está cerrado
        target_period = hasta[:7]
        closed_row = conn.execute("""
            SELECT 1 FROM cierres_periodos WHERE negocio_id = %s AND periodo = %s
        """, (negocio_id, target_period)).fetchone()
        
        # Listar todos los periodos cerrados para mostrar en UI
        cierres_rows = conn.execute("""
            SELECT periodo FROM cierres_periodos WHERE negocio_id = %s ORDER BY periodo DESC
        """, (negocio_id,)).fetchall()
        periodos_cerrados = [c['periodo'] for c in cierres_rows]
        
        conn.close()
        return jsonify({
            'ok': True,
            'cuentas': cuentas_list,
            'periodo_cerrado': bool(closed_row),
            'periodos_cerrados': periodos_cerrados
        })
        
    except Exception as e:
        try: conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500


# ── API: Ejecutar Cierre de Periodo ───────────────────────────

@bp.route('/api/contabilidad/<int:negocio_id>/cierre-periodo', methods=['POST'])
def api_cierre_periodo(negocio_id):
    if not session.get('usuario_id'):
        return jsonify({'ok': False, 'error': 'No autorizado'}), 403
    data = request.get_json() or {}
    periodo = data.get('periodo')
    if not periodo or not re.match(r'^\d{4}-\d{2}$', periodo):
        return jsonify({'ok': False, 'error': 'Periodo inválido o no especificado'}), 400
        
    from ..db import get_db_connection
    try:
        conn = get_db_connection()
        _asegurar_tablas(conn)
        
        # 1. Validar que el periodo no esté ya cerrado
        already_closed = conn.execute("""
            SELECT 1 FROM cierres_periodos WHERE negocio_id = %s AND periodo = %s
        """, (negocio_id, periodo)).fetchone()
        if already_closed:
            conn.close()
            return jsonify({'ok': False, 'error': f"El periodo {periodo} ya se encuentra cerrado."}), 400
            
        # 2. Validar orden cronológico de los cierres
        earliest_row = conn.execute("""
            SELECT MIN(fecha) as first_date FROM comprobantes_contables WHERE negocio_id = %s
        """, (negocio_id,)).fetchone()
        
        if earliest_row and earliest_row['first_date']:
            first_date = earliest_row['first_date']
            target_yr, target_mo = map(int, periodo.split('-'))
            curr_yr = first_date.year
            curr_mo = first_date.month
            
            months_to_check = []
            while (curr_yr < target_yr) or (curr_yr == target_yr and curr_mo < target_mo):
                months_to_check.append(f"{curr_yr:04d}-{curr_mo:02d}")
                if curr_mo == 12:
                    curr_mo = 1
                    curr_yr += 1
                else:
                    curr_mo += 1
                    
            if months_to_check:
                placeholders = ', '.join(['%s'] * len(months_to_check))
                closed_rows = conn.execute(f"""
                    SELECT periodo FROM cierres_periodos
                    WHERE negocio_id = %s AND periodo IN ({placeholders})
                """, [negocio_id] + months_to_check).fetchall()
                closed_set = {r['periodo'] for r in closed_rows}
                missing = [m for m in months_to_check if m not in closed_set]
                if missing:
                    conn.close()
                    return jsonify({
                        'ok': False,
                        'error': f"No se puede cerrar {periodo} sin haber cerrado los periodos anteriores: {', '.join(missing)}"
                    }), 400
                    
        # 3. Buscar o crear el tipo de documento para cierres
        td = conn.execute("""
            SELECT id, codigo, consecutivo, numero_inicio FROM tipos_documento_negocio
            WHERE negocio_id = %s AND tipo_movimiento = 'cierre' LIMIT 1
        """, (negocio_id,)).fetchone()
        
        if not td:
            td = conn.execute("""
                INSERT INTO tipos_documento_negocio 
                    (negocio_id, codigo, nombre, consecutivo, numero_inicio, tipo_movimiento, es_interno)
                VALUES (%s, 'CI', 'Cierre Contable', 0, 1, 'cierre', TRUE)
                RETURNING id, codigo, consecutivo, numero_inicio
            """, (negocio_id,)).fetchone()
            
        # 4. Obtener la cuenta de resultados parametrizada
        param = conn.execute("""
            SELECT id FROM parametros_contables_negocio
            WHERE negocio_id = %s AND tipo_doc_id = %s LIMIT 1
        """, (negocio_id, td['id'])).fetchone()
        
        if not param:
            param = conn.execute("""
                INSERT INTO parametros_contables_negocio (negocio_id, tipo_doc_id, descripcion_asiento)
                VALUES (%s, %s, 'Asiento de cierre contable') RETURNING id
            """, (negocio_id, td['id'])).fetchone()
            
        linea_dest = conn.execute("""
            SELECT l.cuenta_puc_id, c.codigo as cuenta_codigo 
            FROM parametros_lineas_contables l
            JOIN modulo_variables_contables v ON v.id = l.variable_id
            JOIN cuentas_puc c ON c.id = l.cuenta_puc_id
            WHERE l.parametro_id = %s AND v.modulo = 'CIERRE' AND v.codigo = 'RESULTADO_PERIODO'
            LIMIT 1
        """, (param['id'],)).fetchone()
        
        if not linea_dest:
            conn.close()
            return jsonify({
                'ok': False,
                'error': "Debes configurar la cuenta de patrimonio para la variable 'RESULTADO_PERIODO' en la pestaña de Parametrización para el documento de cierre (CI)."
            }), 400
            
        # 5. Calcular saldos finales de las cuentas 4, 5, 6 y 7
        import calendar
        yr, mo = map(int, periodo.split('-'))
        last_day = calendar.monthrange(yr, mo)[1]
        fecha_fin = f"{periodo}-{last_day:02d}"
        
        saldos_rows = conn.execute("""
            SELECT 
                c.id as cuenta_id, 
                c.codigo, 
                c.naturaleza,
                COALESCE(SUM(CASE WHEN m.tipo IN ('debito', 'D') THEN m.monto ELSE 0 END), 0) AS deb_total,
                COALESCE(SUM(CASE WHEN m.tipo IN ('credito', 'C') THEN m.monto ELSE 0 END), 0) AS cred_total
            FROM cuentas_puc c
            JOIN movimientos_contables m ON m.cuenta_id = c.id AND m.negocio_id = %s
            JOIN comprobantes_contables cc ON m.comprobante_id = cc.id
            WHERE (c.codigo LIKE '4%' OR c.codigo LIKE '5%' OR c.codigo LIKE '6%' OR c.codigo LIKE '7%')
              AND cc.fecha <= %s
            GROUP BY c.id, c.codigo, c.naturaleza
        """, (negocio_id, fecha_fin)).fetchall()
        
        # 6. Generar líneas de cierre para cuentas con saldo
        lineas_cierre = []
        total_debitos_cierre = 0.0
        total_creditos_cierre = 0.0
        
        for r in saldos_rows:
            deb = float(r['deb_total'])
            cred = float(r['cred_total'])
            
            if r['naturaleza'] == 'debito':
                balance = deb - cred
            else:
                balance = cred - deb
                
            if balance == 0.0:
                continue
                
            # Si tiene saldo débito, se acredita. Si tiene saldo crédito, se debita
            if r['naturaleza'] == 'debito':
                tipo_mov_cierre = 'credito'
                total_creditos_cierre += balance
            else:
                tipo_mov_cierre = 'debito'
                total_debitos_cierre += balance
                
            lineas_cierre.append({
                'cuenta_id': r['cuenta_id'],
                'cuenta_codigo': r['codigo'],
                'tipo': tipo_mov_cierre,
                'monto': balance
            })
            
        if not lineas_cierre:
            conn.close()
            return jsonify({'ok': False, 'error': f"No existen saldos para cerrar en el periodo {periodo}."}), 400
            
        # 7. Agregar línea balanceadora a la cuenta de resultados
        diff = total_creditos_cierre - total_debitos_cierre
        if diff > 0:
            # Requiere un débito para balancear
            lineas_cierre.append({
                'cuenta_id': linea_dest['cuenta_puc_id'],
                'cuenta_codigo': linea_dest['cuenta_codigo'],
                'tipo': 'debito',
                'monto': diff
            })
            total_debitos_cierre += diff
        elif diff < 0:
            # Requiere un crédito para balancear
            lineas_cierre.append({
                'cuenta_id': linea_dest['cuenta_puc_id'],
                'cuenta_codigo': linea_dest['cuenta_codigo'],
                'tipo': 'credito',
                'monto': -diff
            })
            total_creditos_cierre += -diff
            
        # 8. Guardar comprobante y movimientos contables
        num_doc = max((td['consecutivo'] or 0) + 1, (td['numero_inicio'] or 1))
        numero = f"{td['codigo']}-{num_doc}"
        
        conn.execute("""
            UPDATE tipos_documento_negocio SET consecutivo=%s WHERE id=%s
        """, (num_doc, td['id']))
        
        comp_id = conn.execute("""
            INSERT INTO comprobantes_contables
                (negocio_id, numero_comprobante, numero_documento, tipo, fecha, descripcion,
                 total_debitos, total_creditos, registrado_por, notas, origen_tipo, origen_id, tipo_documento_id)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'Cierre de periodo contable',%s,%s,%s)
            RETURNING id
        """, (negocio_id, numero, num_doc, td['codigo'], fecha_fin, f"Cierre contable resultados periodo {periodo}",
              total_debitos_cierre, total_creditos_cierre, session['usuario_id'], 'cierre', periodo, td['id'])).fetchone()['id']
              
        for l in lineas_cierre:
            conn.execute("""
                INSERT INTO movimientos_contables
                    (negocio_id, comprobante_id, cuenta_id, cuenta, concepto, tipo, monto, registrado_por)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
            """, (negocio_id, comp_id, l['cuenta_id'], l['cuenta_codigo'],
                  f"Cierre de periodo {periodo}", l['tipo'], l['monto'], session['usuario_id']))
                  
        # Registrar en la tabla cierres_periodos
        conn.execute("""
            INSERT INTO cierres_periodos (negocio_id, periodo, comprobante_id)
            VALUES (%s, %s, %s)
        """, (negocio_id, periodo, comp_id))
        
        conn.commit()
        conn.close()
        return jsonify({'ok': True, 'comprobante_id': comp_id, 'periodo': periodo})
        
    except Exception as e:
        try: conn.rollback(); conn.close()
        except Exception: pass
        return jsonify({'ok': False, 'error': str(e)}), 500
