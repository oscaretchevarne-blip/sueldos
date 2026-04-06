"""
database.py - Esquema de base de datos para el Sistema de Liquidación de Sueldos.
Usa SQLite3 para persistencia local.
"""
import sqlite3
import os
import shutil
from datetime import datetime
from utils import get_logger

logger = get_logger("database")

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sueldos.db")

# Versión actual del esquema — incrementar cada vez que se agregue una migración
SCHEMA_VERSION = 1


def get_connection():
    """Obtiene conexión a la base de datos con WAL mode y timeout robusto."""
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def _get_schema_version(conn):
    """Obtiene la versión actual del esquema de la DB."""
    try:
        row = conn.execute("SELECT valor FROM config WHERE clave = 'schema_version'").fetchone()
        return int(row[0]) if row else 0
    except sqlite3.OperationalError:
        return 0


def _set_schema_version(conn, version):
    """Guarda la versión del esquema en la DB."""
    conn.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('schema_version', ?)", (str(version),))


def _run_one_time_data_migrations(cursor):
    """
    Ejecuta migraciones de datos que solo deben correr una vez.
    Controlado por schema_version para no repetirse en cada inicio.
    """
    conn = cursor.connection
    current_version = _get_schema_version(conn)

    if current_version < 1:
        # v1: Población de códigos contables para empleados específicos
        _data_migrations_v1 = [
            ("UPDATE empleados SET codigo_contable = '1.1.070.10.005', seccion_debito_externo = 'COMERCIALIZACION' "
             "WHERE apellido_nombre LIKE '%MARIETTA%MARCELO%' AND (codigo_contable IS NULL OR codigo_contable = '')"),
            ("UPDATE empleados SET codigo_contable = '1.1.070.10.006', seccion_debito_externo = 'FABRICA' "
             "WHERE apellido_nombre LIKE '%ASAD%HORACIO%' AND (codigo_contable IS NULL OR codigo_contable = '')"),
            ("UPDATE empleados SET codigo_contable = '1.1.070.10.007', seccion_debito_externo = '' "
             "WHERE apellido_nombre LIKE '%FERNANDEZ%IRENE%' AND (codigo_contable IS NULL OR codigo_contable = '')"),
            ("UPDATE empleados SET codigo_contable = '1.1.070.10.008', seccion_debito_externo = '' "
             "WHERE apellido_nombre LIKE '%ZAPPALA%DELIA%' AND (codigo_contable IS NULL OR codigo_contable = '')"),
        ]
        for sql in _data_migrations_v1:
            cursor.execute(sql)
        _set_schema_version(conn, 1)
        logger.info("Migración de datos v1 completada (códigos contables iniciales)")


def init_db():
    """Crea todas las tablas si no existen."""
    conn = get_connection()
    c = conn.cursor()

    # ──────────────────────────────────────────────
    # EMPLEADOS
    # ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS empleados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            apellido_nombre TEXT NOT NULL,
            cuil TEXT,
            tipo TEXT NOT NULL DEFAULT 'JORNAL',  -- MENSUALIZADO / JORNAL / EVENTUAL
            seccion TEXT NOT NULL,
            categoria TEXT,
            fecha_ingreso DATE,
            liquida_mensual INTEGER DEFAULT 0,        -- 0=No, 1=Sí (solo mensualizados)
            liquida_antiguedad_basico INTEGER DEFAULT 0,  -- 0=No, 1=Sí
            estado TEXT NOT NULL DEFAULT 'ACTIVO',    -- ACTIVO / INACTIVO
            diferencia_sueldo REAL DEFAULT 0,
            premio_produccion REAL DEFAULT 0,
            cifra_fija REAL DEFAULT 0,
            seguro REAL DEFAULT 0,
            jubilacion REAL DEFAULT 0,
            obra_social REAL DEFAULT 0,
            fuera_convenio INTEGER DEFAULT 0,         -- 0=No (Bajo Convenio), 1=Sí (Fuera de Convenio)
            sueldo_base REAL DEFAULT 0,               -- Valor manual para fuera de convenio
            hs_fijas REAL DEFAULT 0,                  -- Horas fijas mensuales/quincenales
            condicion TEXT NOT NULL DEFAULT 'PERMANENTE', -- PERMANENTE / EVENTUAL
            anticipos REAL DEFAULT 0,                 -- Monto a descontar (se resetea al cerrar periodo)
            acreditacion_banco REAL DEFAULT 0,        -- Monto ya pagado via banco (se resetea al cerrar periodo)
            otros REAL DEFAULT 0,                     -- Monto libre (puede ser +/-)
            porc_presentismo REAL DEFAULT 15.0,        -- % de presentismo (defecto 15%)
            observaciones TEXT,                       -- Nota libre por empleado
            dias_liquidacion_mensual INTEGER DEFAULT 30, -- Días a liquidar (1-30)
            dias_mensuales_permanente INTEGER DEFAULT 1, -- 1=Sí, 0=No (si No, resetea a 30 al cerrar)
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ──────────────────────────────────────────────
    # CATEGORÍAS Y VALORES DE CONVENIO
    # ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS categorias (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            grupo TEXT DEFAULT 'PRODUCCION',  -- PRODUCCION / MANTENIMIENTO / ADMINISTRATIVAS / OTRA
            estado TEXT NOT NULL DEFAULT 'ACTIVA',  -- ACTIVA / INACTIVA
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS categoria_valores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            categoria_id INTEGER NOT NULL,
            valor_hora REAL DEFAULT 0,
            valor_mensual REAL DEFAULT 0,
            vigencia_mes INTEGER NOT NULL,  -- 1-12
            vigencia_anio INTEGER NOT NULL, -- ej: 2026
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (categoria_id) REFERENCES categorias(id)
        )
    """)

    # ──────────────────────────────────────────────
    # PERÍODOS / QUINCENAS
    # ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS periodos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            quincena INTEGER NOT NULL,  -- 1 o 2
            mes INTEGER NOT NULL,
            anio INTEGER NOT NULL,
            estado TEXT NOT NULL DEFAULT 'ABIERTO',  -- ABIERTO / CERRADO
            fecha_cierre TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(quincena, mes, anio)
        )
    """)

    # ──────────────────────────────────────────────
    # LIQUIDACIONES (cabecera por empleado/período)
    # ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS liquidaciones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            periodo_id INTEGER NOT NULL,
            empleado_id INTEGER NOT NULL,
            tipo_liquidacion TEXT NOT NULL,  -- MENSUALIZADO / JORNAL / EVENTUAL

            -- Horas
            horas_comunes REAL DEFAULT 0,
            horas_extra_50 REAL DEFAULT 0,
            horas_extra_100 REAL DEFAULT 0,

            -- Valores usados (snapshot del momento de liquidación)
            valor_hora_usado REAL DEFAULT 0,
            valor_mensual_usado REAL DEFAULT 0,
            porcentaje_antiguedad REAL DEFAULT 0,

            -- Haberes calculados
            importe_horas_comunes REAL DEFAULT 0,
            importe_basico_mensual REAL DEFAULT 0,
            importe_extra_50 REAL DEFAULT 0,
            importe_extra_100 REAL DEFAULT 0,
            importe_antiguedad_horas REAL DEFAULT 0,
            importe_antiguedad_extras REAL DEFAULT 0,
            importe_antiguedad_basico REAL DEFAULT 0,
            importe_antiguedad_total REAL DEFAULT 0,
            importe_diferencia_sueldo REAL DEFAULT 0,
            importe_premio_produccion REAL DEFAULT 0,
            importe_cifra_fija REAL DEFAULT 0,
            importe_trabajos_varios REAL DEFAULT 0,
            importe_viaticos REAL DEFAULT 0,
            importe_jubilacion REAL DEFAULT 0,
            importe_obra_social REAL DEFAULT 0,
            importe_presentismo REAL DEFAULT 0,
            importe_prop_aguinaldo REAL DEFAULT 0,

            -- Conceptos libres
            concepto_libre_1_nombre TEXT DEFAULT '',
            concepto_libre_1_importe REAL DEFAULT 0,
            concepto_libre_2_nombre TEXT DEFAULT '',
            concepto_libre_2_importe REAL DEFAULT 0,
            importe_anticipos REAL DEFAULT 0,
            importe_otros REAL DEFAULT 0,
            observaciones TEXT,

            -- Vacaciones
            dias_vacaciones REAL DEFAULT 0,
            importe_vacaciones REAL DEFAULT 0,

            -- Remplazo Encargado
            remplazo_encargado REAL DEFAULT 0,
            importe_remplazo_encargado REAL DEFAULT 0,

            -- Totales
            total_haberes REAL DEFAULT 0,
            total_deducciones REAL DEFAULT 0,
            total_neto REAL DEFAULT 0,
            porcentaje_presentismo REAL DEFAULT 15.0,
            importe_acreditacion_banco REAL DEFAULT 0,

            -- Redondeo
            redondeo REAL DEFAULT 0,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (periodo_id) REFERENCES periodos(id),
            FOREIGN KEY (empleado_id) REFERENCES empleados(id),
            UNIQUE(periodo_id, empleado_id)
        )
    """)

    # ── Migraciones (agregar columnas nuevas si no existen) ──
    # Se usa _safe_add_column para evitar errores si la columna ya existe.
    # Cada columna se registra aquí para bases de datos creadas antes de que
    # la columna existiera en el CREATE TABLE inicial.
    def _safe_add_column(table, column, col_type):
        try:
            c.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
            logger.info(f"Migración: columna {table}.{column} agregada")
        except sqlite3.OperationalError:
            pass  # La columna ya existe

    _safe_add_column("empleados", "liquida_presentismo", "INTEGER DEFAULT 1")
    _safe_add_column("liquidaciones", "dias_trabajados", "REAL DEFAULT 0")
    _safe_add_column("empleados", "fuera_convenio", "INTEGER DEFAULT 0")
    _safe_add_column("liquidaciones", "dias_vacaciones", "REAL DEFAULT 0")

    _safe_add_column("liquidaciones", "importe_vacaciones", "REAL DEFAULT 0")
    _safe_add_column("empleados", "sueldo_base", "REAL DEFAULT 0")
    _safe_add_column("empleados", "hs_fijas", "REAL DEFAULT 0")
    _safe_add_column("liquidaciones", "remplazo_encargado", "REAL DEFAULT 0")
    _safe_add_column("empleados", "condicion", "TEXT NOT NULL DEFAULT 'PERMANENTE'")

    # Migración de datos: eventuales que estaban como tipo='EVENTUAL' pasan a condicion='EVENTUAL'
    try:
        c.execute("UPDATE empleados SET condicion = 'EVENTUAL', tipo = 'JORNAL' WHERE tipo = 'EVENTUAL'")
    except sqlite3.OperationalError:
        pass

    _safe_add_column("empleados", "descuento_premio_prod", "REAL DEFAULT 0")
    _safe_add_column("empleados", "cobra_cifra_fija", "INTEGER DEFAULT 0")

    # Columnas adicionales para anticipos, contabilidad, etc.
    columnas_nuevas = [
        ("empleados", "anticipos", "REAL DEFAULT 0"),
        ("empleados", "otros", "REAL DEFAULT 0"),
        ("empleados", "observaciones", "TEXT"),
        ("liquidaciones", "importe_anticipos", "REAL DEFAULT 0"),
        ("liquidaciones", "importe_acreditacion_banco", "REAL DEFAULT 0"),
        ("liquidaciones", "importe_otros", "REAL DEFAULT 0"),
        ("liquidaciones", "porcentaje_presentismo", "REAL DEFAULT 15.0"),
        ("empleados", "porc_presentismo", "REAL DEFAULT 15.0"),
        ("empleados", "acreditacion_banco", "REAL DEFAULT 0"),
        ("empleados", "dias_liquidacion_mensual", "INTEGER DEFAULT 30"),
        ("empleados", "dias_mensuales_permanente", "INTEGER DEFAULT 1"),
        ("liquidaciones", "importe_descuento_premio_prod", "REAL DEFAULT 0"),
        ("liquidaciones", "observaciones", "TEXT"),
        ("empleados", "codigo_contable", "TEXT DEFAULT ''"),
        ("empleados", "seccion_debito_externo", "TEXT DEFAULT ''"),
    ]
    for tab, col, typ in columnas_nuevas:
        _safe_add_column(tab, col, typ)

    # ── Historial de aumentos masivos FC (para retrotraer) ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS historial_aumentos_fc (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            porcentaje REAL NOT NULL,
            seccion TEXT,
            cantidad_empleados INTEGER NOT NULL,
            detalle TEXT NOT NULL,
            revertido INTEGER DEFAULT 0
        )
    """)

    # ── Tabla de cuentas contables del asiento ──
    c.execute("""
        CREATE TABLE IF NOT EXISTS cuentas_asiento (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            clave TEXT UNIQUE NOT NULL,
            codigo TEXT NOT NULL DEFAULT '',
            nombre TEXT NOT NULL DEFAULT '',
            tipo TEXT NOT NULL DEFAULT 'D'
        )
    """)

    # Cargar cuentas por defecto si la tabla está vacía
    n_cuentas = c.execute("SELECT COUNT(*) FROM cuentas_asiento").fetchone()[0]
    if n_cuentas == 0:
        cuentas_default = [
            # clave, codigo, nombre, tipo (D=Debe / H=Haber)
            ('ADMINISTRACION',       '4.4.010.10.101', 'Sueldos Administración',       'D'),
            ('COMERCIALIZACION',     '4.4.020.10.101', 'Sueldos Comercialización',     'D'),
            ('DEPOSITO',             '4.4.040.00.001', 'Sueldos Depósito',              'D'),
            ('FABRICA',              '4.4.050.00.001', 'Sueldos Fábrica',              'D'),
            ('MANTENIMIENTO',        '4.4.050.00.002', 'Sueldos Mantenimiento',         'D'),
            ('MATRICERIA',           '4.4.060.00.001', 'Sueldos Matricería',           'D'),
            ('CONTROL CALIDAD',      '4.4.070.00.001', 'Sueldos Control Calidad',       'D'),
            ('SDO.FUERA SIJIP',      '4.4.010.10.301', 'Sueldos Fuera de SIJIP',        'D'),
            ('SUELDOS_A_PAGAR',      '2.1.030.10.101', 'Sueldos a Pagar',               'H'),
            ('SEGUROS',              '4.6.010.10.103', 'Seguros',                        'H'),
            ('ACRED_FUERA_SIJIP',    '2.1.030.10.201', 'SDO. Fuera SIJIP - Acred.',     'H'),
            # Abreviaciones comunes para mejor matching
            ('ADMINIST.',            '4.4.010.10.101', 'Sueldos Administración',       'D'),
            ('CALIDAD',              '4.4.070.00.001', 'Sueldos Control Calidad',       'D'),
            ('COMERCIALIZ.',         '4.4.020.10.101', 'Sueldos Comercialización',     'D'),
            ('MANTENIM.',            '4.4.050.00.002', 'Sueldos Mantenimiento',         'D'),
        ]
        c.executemany(
            "INSERT OR IGNORE INTO cuentas_asiento (clave, codigo, nombre, tipo) VALUES (?, ?, ?, ?)",
            cuentas_default
        )
        logger.info("Cuentas contables por defecto cargadas")

    # ── Población de códigos contables para empleados específicos ──
    # Solo se ejecuta una vez (migración v1), controlado por schema_version
    _run_one_time_data_migrations(c)

    # ──────────────────────────────────────────────
    # CONFIGURACIÓN (período activo, etc.)
    # ──────────────────────────────────────────────
    c.execute("""
        CREATE TABLE IF NOT EXISTS config (
            clave TEXT PRIMARY KEY,
            valor TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
    logger.info("Base de datos inicializada correctamente")


# ──────────────────────────────────────────────────
# FUNCIONES AUXILIARES - CONFIG (período activo)
# ──────────────────────────────────────────────────
def guardar_periodo_activo(quincena, mes, anio):
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('periodo_q', ?)", (str(quincena),))
    c.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('periodo_m', ?)", (str(mes),))
    c.execute("INSERT OR REPLACE INTO config (clave, valor) VALUES ('periodo_a', ?)", (str(anio),))
    conn.commit()
    conn.close()

def cargar_periodo_activo():
    """Devuelve (quincena, mes, anio) guardados o None si no hay."""
    conn = get_connection()
    try:
        q = conn.execute("SELECT valor FROM config WHERE clave='periodo_q'").fetchone()
        m = conn.execute("SELECT valor FROM config WHERE clave='periodo_m'").fetchone()
        a = conn.execute("SELECT valor FROM config WHERE clave='periodo_a'").fetchone()
        conn.close()
        if q and m and a:
            return int(q[0]), int(m[0]), int(a[0])
        return None
    except Exception:
        conn.close()
        return None


# ──────────────────────────────────────────────────
# FUNCIONES AUXILIARES - CUENTAS ASIENTO CONTABLE
# ──────────────────────────────────────────────────

def get_cuentas_asiento():
    """Devuelve todas las cuentas del asiento contable como lista de dicts."""
    conn = get_connection()
    rows = conn.execute("SELECT * FROM cuentas_asiento ORDER BY tipo, codigo").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_cuenta_por_clave(clave):
    """Devuelve la cuenta por clave (ej: 'FABRICA', 'SUELDOS_A_PAGAR')."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM cuentas_asiento WHERE clave = ?", (clave,)).fetchone()
    conn.close()
    return dict(row) if row else None

def guardar_cuenta_asiento(clave, codigo, nombre, tipo):
    """Crea o actualiza una cuenta del asiento contable."""
    conn = get_connection()
    conn.execute("""
        INSERT INTO cuentas_asiento (clave, codigo, nombre, tipo)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(clave) DO UPDATE SET codigo=excluded.codigo, nombre=excluded.nombre, tipo=excluded.tipo
    """, (clave, codigo, nombre, tipo))
    conn.commit()
    conn.close()


# ──────────────────────────────────────────────────
# FUNCIONES AUXILIARES - EMPLEADOS
# ──────────────────────────────────────────────────

def get_empleados(estado=None, seccion=None, categoria=None, busqueda=None, fuera_convenio=None, condicion=None):
    """Obtiene lista de empleados con filtros opcionales."""
    conn = get_connection()
    query = "SELECT * FROM empleados WHERE 1=1"
    params = []

    if estado:
        query += " AND estado = ?"
        params.append(estado)
    if seccion:
        query += " AND seccion = ?"
        params.append(seccion)
    if categoria:
        query += " AND categoria = ?"
        params.append(categoria)
    if fuera_convenio is not None:
        query += " AND fuera_convenio = ?"
        params.append(fuera_convenio)
    if condicion:
        query += " AND condicion = ?"
        params.append(condicion)
    if busqueda:
        query += " AND apellido_nombre LIKE ?"
        params.append(f"%{busqueda}%")

    query += " ORDER BY apellido_nombre"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_empleado(emp_id):
    """Obtiene un empleado por ID."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM empleados WHERE id = ?", (emp_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def crear_empleado(data):
    """Crea un nuevo empleado. Retorna el ID creado."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO empleados (apellido_nombre, cuil, tipo, seccion, categoria,
            fecha_ingreso, liquida_mensual, liquida_antiguedad_basico, liquida_presentismo,
             estado, diferencia_sueldo, premio_produccion, cifra_fija, seguro, jubilacion, obra_social,
             fuera_convenio, sueldo_base, hs_fijas, condicion, anticipos, acreditacion_banco, otros, porc_presentismo, 
             dias_liquidacion_mensual, dias_mensuales_permanente, descuento_premio_prod, cobra_cifra_fija, observaciones)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        data.get('apellido_nombre', ''),
        data.get('cuil', ''),
        data.get('tipo', 'JORNAL'),
        data.get('seccion', ''),
        data.get('categoria', ''),
        data.get('fecha_ingreso'),
        data.get('liquida_mensual', 0),
        data.get('liquida_antiguedad_basico', 0),
        data.get('liquida_presentismo', 1),
        data.get('estado', 'ACTIVO'),
        data.get('diferencia_sueldo', 0),
        data.get('premio_produccion', 0),
        data.get('cifra_fija', 0),
        data.get('seguro', 0),
        data.get('jubilacion', 0),
        data.get('obra_social', 0),
        data.get('fuera_convenio', 0),
        data.get('sueldo_base', 0),
        data.get('hs_fijas', 0),
        data.get('condicion', 'PERMANENTE'),
        data.get('anticipos', 0),
        data.get('acreditacion_banco', 0),
        data.get('otros', 0),
        data.get('porc_presentismo', 15.0),
        data.get('dias_liquidacion_mensual', 30),
        data.get('dias_mensuales_permanente', 1),
        data.get('descuento_premio_prod', 0),
        data.get('cobra_cifra_fija', 0),
        data.get('observaciones', ''),
    ))
    emp_id = c.lastrowid
    conn.commit()
    conn.close()
    return emp_id


def actualizar_empleado(emp_id, data):
    """Actualiza un empleado existente."""
    conn = get_connection()
    fields = []
    values = []
    for key in ['apellido_nombre', 'cuil', 'tipo', 'seccion', 'categoria',
                'fecha_ingreso', 'liquida_mensual', 'liquida_antiguedad_basico',
                'liquida_presentismo', 'estado', 'diferencia_sueldo',
                'premio_produccion', 'cifra_fija', 'seguro', 'jubilacion', 'obra_social',
                'fuera_convenio', 'sueldo_base', 'hs_fijas', 'condicion',
                'anticipos', 'acreditacion_banco', 'otros', 'porc_presentismo', 
                'dias_liquidacion_mensual', 'dias_mensuales_permanente', 'descuento_premio_prod', 
                'cobra_cifra_fija', 'observaciones']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    
    if not fields:
        conn.close()
        return

    query = f"UPDATE empleados SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id = ?"
    values.append(emp_id)
    conn.execute(query, values)
    conn.commit()
    conn.close()


def aplicar_aumento_masivo_fc(porcentaje, seccion=None):
    """
    Aplica un aumento porcentual a:
    - sueldo_base y diferencia_sueldo para empleados FUERA DE CONVENIO
    - diferencia_sueldo para empleados BAJO CONVENIO que tengan dif > 0
    Guarda snapshot previo para poder retrotraer.
    """
    import json
    logger.info(f"Iniciando aumento masivo FC: {porcentaje}% - Sección: {seccion or 'Todas'}")
    conn = get_connection()
    c = conn.cursor()

    # Obtener TODOS los empleados afectados ANTES del cambio (snapshot)
    # FC: se les toca sueldo_base + diferencia_sueldo
    # Bajo Convenio con dif > 0: solo diferencia_sueldo
    q_select = """
        SELECT id, apellido_nombre, sueldo_base, diferencia_sueldo, fuera_convenio
        FROM empleados
        WHERE estado = 'ACTIVO'
          AND (fuera_convenio = 1 OR (fuera_convenio = 0 AND diferencia_sueldo > 0))
    """
    params_sel = []
    if seccion:
        q_select += " AND seccion = ?"
        params_sel.append(seccion)

    empleados_antes = c.execute(q_select, params_sel).fetchall()

    # Guardar detalle como JSON
    detalle = json.dumps([
        {"id": e["id"], "nombre": e["apellido_nombre"],
         "sueldo_base": e["sueldo_base"], "diferencia_sueldo": e["diferencia_sueldo"],
         "fuera_convenio": e["fuera_convenio"]}
        for e in empleados_antes
    ])

    # Registrar en historial
    c.execute("""
        INSERT INTO historial_aumentos_fc (porcentaje, seccion, cantidad_empleados, detalle)
        VALUES (?, ?, ?, ?)
    """, [porcentaje, seccion, len(empleados_antes), detalle])

    factor = 1 + (porcentaje / 100.0)

    # 1) Fuera de Convenio: sueldo_base + diferencia_sueldo
    q_fc = """
        UPDATE empleados
        SET sueldo_base = sueldo_base * ?,
            diferencia_sueldo = diferencia_sueldo * ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE fuera_convenio = 1 AND estado = 'ACTIVO'
    """
    p_fc = [factor, factor]
    if seccion:
        q_fc += " AND seccion = ?"
        p_fc.append(seccion)
    c.execute(q_fc, p_fc)

    # 2) Bajo Convenio con diferencia_sueldo > 0: solo diferencia_sueldo
    q_bc = """
        UPDATE empleados
        SET diferencia_sueldo = diferencia_sueldo * ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE fuera_convenio = 0 AND diferencia_sueldo > 0 AND estado = 'ACTIVO'
    """
    p_bc = [factor]
    if seccion:
        q_bc += " AND seccion = ?"
        p_bc.append(seccion)
    c.execute(q_bc, p_bc)

    conn.commit()
    conn.close()
    logger.info(f"Aumento masivo FC aplicado: {porcentaje}% a {len(empleados_antes)} empleados")


def get_ultimo_aumento_fc(mes=None, anio=None):
    """Obtiene el último aumento masivo FC no revertido del período indicado.
    Si no se pasan mes/anio, busca cualquier aumento no revertido (legacy)."""
    conn = get_connection()
    if mes and anio:
        # Solo buscar aumentos aplicados dentro del mes/año del período activo
        row = conn.execute("""
            SELECT * FROM historial_aumentos_fc
            WHERE revertido = 0
              AND CAST(strftime('%%m', fecha) AS INTEGER) = ?
              AND CAST(strftime('%%Y', fecha) AS INTEGER) = ?
            ORDER BY id DESC LIMIT 1
        """, (mes, anio)).fetchone()
    else:
        row = conn.execute("""
            SELECT * FROM historial_aumentos_fc
            WHERE revertido = 0
            ORDER BY id DESC LIMIT 1
        """).fetchone()
    conn.close()
    return dict(row) if row else None


def retrotraer_aumento_fc(aumento_id):
    """
    Retrotrrae el aumento indicado restaurando los valores originales
    de sueldo_base y diferencia_sueldo desde el snapshot guardado.
    """
    import json
    logger.info(f"Retrotraendo aumento FC ID={aumento_id}")
    conn = get_connection()
    c = conn.cursor()

    row = c.execute("SELECT * FROM historial_aumentos_fc WHERE id = ? AND revertido = 0", [aumento_id]).fetchone()
    if not row:
        conn.close()
        return 0

    detalle = json.loads(row["detalle"])
    count = 0
    for emp in detalle:
        c.execute("""
            UPDATE empleados
            SET sueldo_base = ?, diferencia_sueldo = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, [emp["sueldo_base"], emp["diferencia_sueldo"], emp["id"]])
        count += 1

    c.execute("UPDATE historial_aumentos_fc SET revertido = 1 WHERE id = ?", [aumento_id])
    conn.commit()
    conn.close()
    return count

def eliminar_empleados_inactivos():
    """
    Elimina permanentemente los empleados con estado 'INACTIVO'
    y todas sus liquidaciones asociadas (para cumplir integridad referencial).
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Obtener IDs de inactivos
        inactivos = conn.execute("SELECT id FROM empleados WHERE estado = 'INACTIVO'").fetchall()
        ids = [row['id'] for row in inactivos]
        
        if not ids:
            return 0
        
        # 2. Borrar liquidaciones de esos empleados
        placeholders = ', '.join(['?'] * len(ids))
        c.execute(f"DELETE FROM liquidaciones WHERE empleado_id IN ({placeholders})", ids)
        
        # 3. Borrar empleados
        c.execute(f"DELETE FROM empleados WHERE id IN ({placeholders})", ids)
        
        num_borrados = len(ids)
        conn.commit()
        return num_borrados
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def eliminar_empleado(emp_id):
    """
    Elimina permanentemente un empleado específico y todas sus liquidaciones.
    """
    conn = get_connection()
    c = conn.cursor()
    try:
        # 1. Borrar liquidaciones del empleado
        c.execute("DELETE FROM liquidaciones WHERE empleado_id = ?", (emp_id,))
        
        # 2. Borrar el empleado
        c.execute("DELETE FROM empleados WHERE id = ?", (emp_id,))
        
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


def get_secciones():
    """Obtiene lista de secciones únicas."""
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT seccion FROM empleados ORDER BY seccion").fetchall()
    conn.close()
    return [r['seccion'] for r in rows]


def get_categorias_empleados():
    """Obtiene lista de categorías únicas usadas por empleados."""
    conn = get_connection()
    rows = conn.execute("SELECT DISTINCT categoria FROM empleados WHERE categoria IS NOT NULL ORDER BY categoria").fetchall()
    conn.close()
    return [r['categoria'] for r in rows]


# ──────────────────────────────────────────────────
# FUNCIONES AUXILIARES - CATEGORÍAS
# ──────────────────────────────────────────────────

def get_categorias(estado=None):
    """Obtiene todas las categorías."""
    conn = get_connection()
    query = "SELECT * FROM categorias WHERE 1=1"
    params = []
    if estado:
        query += " AND estado = ?"
        params.append(estado)
    query += " ORDER BY grupo, nombre"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def crear_categoria(nombre, grupo='PRODUCCION'):
    """Crea una categoría nueva. Retorna el ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO categorias (nombre, grupo) VALUES (?, ?)", (nombre, grupo))
    cat_id = c.lastrowid
    conn.commit()
    conn.close()
    return cat_id


def get_categoria_por_nombre(nombre):
    """Busca una categoría por nombre."""
    conn = get_connection()
    row = conn.execute("SELECT * FROM categorias WHERE nombre = ?", (nombre,)).fetchone()
    conn.close()
    return dict(row) if row else None


def crear_valor_categoria(categoria_id, valor_hora, valor_mensual, mes, anio):
    """Agrega o actualiza un valor de categoría para un período específico (upsert)."""
    conn = get_connection()
    c = conn.cursor()
    # Verificar si ya existe un valor para esta categoría/mes/año
    existing = c.execute("""
        SELECT id FROM categoria_valores
        WHERE categoria_id = ? AND vigencia_mes = ? AND vigencia_anio = ?
        ORDER BY id DESC LIMIT 1
    """, (categoria_id, mes, anio)).fetchone()
    if existing:
        c.execute("""
            UPDATE categoria_valores
            SET valor_hora = ?, valor_mensual = ?, created_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (valor_hora, valor_mensual, existing[0]))
    else:
        c.execute("""
            INSERT INTO categoria_valores (categoria_id, valor_hora, valor_mensual, vigencia_mes, vigencia_anio)
            VALUES (?, ?, ?, ?, ?)
        """, (categoria_id, valor_hora, valor_mensual, mes, anio))
    conn.commit()
    conn.close()


def get_valor_categoria(categoria_nombre, mes, anio):
    """
    Obtiene el valor vigente de una categoría para un período dado.
    Si no hay valor para ese período, toma el último registrado.
    """
    conn = get_connection()
    # Primero buscar valor exacto para el período
    row = conn.execute("""
        SELECT cv.* FROM categoria_valores cv
        JOIN categorias c ON cv.categoria_id = c.id
        WHERE c.nombre = ? AND cv.vigencia_mes = ? AND cv.vigencia_anio = ?
        ORDER BY cv.id DESC LIMIT 1
    """, (categoria_nombre, mes, anio)).fetchone()

    if not row:
        # Tomar el último valor registrado
        row = conn.execute("""
            SELECT cv.* FROM categoria_valores cv
            JOIN categorias c ON cv.categoria_id = c.id
            WHERE c.nombre = ?
            ORDER BY cv.vigencia_anio DESC, cv.vigencia_mes DESC, cv.id DESC
            LIMIT 1
        """, (categoria_nombre,)).fetchone()

    conn.close()
    return dict(row) if row else None


def get_valores_categoria(categoria_id):
    """Obtiene todos los valores históricos de una categoría."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT * FROM categoria_valores
        WHERE categoria_id = ?
        ORDER BY vigencia_anio DESC, vigencia_mes DESC
    """, (categoria_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def actualizar_categoria(cat_id, data):
    """Actualiza una categoría."""
    conn = get_connection()
    fields = []
    values = []
    for key in ['nombre', 'grupo', 'estado']:
        if key in data:
            fields.append(f"{key} = ?")
            values.append(data[key])
    if fields:
        values.append(cat_id)
        conn.execute(f"UPDATE categorias SET {', '.join(fields)} WHERE id = ?", values)
        conn.commit()
    conn.close()


def empleados_con_categoria(cat_nombre):
    """Cuenta cuántos empleados están asignados a una categoría."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM empleados WHERE categoria = ? AND estado = 'ACTIVO'",
        (cat_nombre,)
    ).fetchone()
    conn.close()
    return row['cnt'] if row else 0


# ──────────────────────────────────────────────────
# FUNCIONES AUXILIARES - PERÍODOS
# ──────────────────────────────────────────────────

def get_periodo(quincena, mes, anio):
    """Obtiene un período o None si no existe."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM periodos WHERE quincena = ? AND mes = ? AND anio = ?",
        (quincena, mes, anio)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def crear_periodo(quincena, mes, anio):
    """Crea un nuevo período. Retorna el ID."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("INSERT INTO periodos (quincena, mes, anio) VALUES (?, ?, ?)",
              (quincena, mes, anio))
    periodo_id = c.lastrowid
    conn.commit()
    conn.close()
    return periodo_id


def cerrar_periodo(periodo_id):
    """Cierra un período (irreversible). Usa transacción para garantizar atomicidad."""
    conn = get_connection()
    try:
        conn.execute("""
            UPDATE periodos SET estado = 'CERRADO', fecha_cierre = CURRENT_TIMESTAMP
            WHERE id = ? AND estado = 'ABIERTO'
        """, (periodo_id,))

        # RESETEAR ANTICIPOS Y ACREDITACION BANCO A 0 AL CERRAR (Administración de Personal)
        conn.execute("UPDATE empleados SET anticipos = 0, acreditacion_banco = 0, descuento_premio_prod = 0")

        # Resetear días de liquidación mensual si no son permanentes
        conn.execute("UPDATE empleados SET dias_liquidacion_mensual = 30 WHERE dias_mensuales_permanente = 0")

        # Marcar aumentos FC no revertidos como consumidos (revertido=2)
        # para que no bloqueen aumentos en el siguiente período
        conn.execute("UPDATE historial_aumentos_fc SET revertido = 2 WHERE revertido = 0")

        conn.commit()
        logger.info(f"Período ID={periodo_id} cerrado exitosamente")
    except Exception as e:
        conn.rollback()
        logger.error(f"Error cerrando período ID={periodo_id}: {e}")
        raise
    finally:
        conn.close()


def respaldar_db(periodo_tag=""):
    """Crea una copia de seguridad de la base de datos con validación de integridad."""
    backup_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "BACKUPS_CIERRE")
    if not os.path.exists(backup_dir):
        os.makedirs(backup_dir)

    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    tag = f"_{periodo_tag.replace('/', '-')}" if periodo_tag else ""
    backup_filename = f"sueldos_respaldo_{timestamp}{tag}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    # Forzar checkpoint de WAL antes de copiar para asegurar datos completos
    try:
        conn = get_connection()
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        conn.close()
    except sqlite3.OperationalError as e:
        logger.warning(f"No se pudo hacer checkpoint WAL antes del backup: {e}")

    shutil.copy2(DB_PATH, backup_path)

    # Validar integridad del backup
    try:
        conn_backup = sqlite3.connect(backup_path)
        result = conn_backup.execute("PRAGMA integrity_check").fetchone()
        conn_backup.close()
        if result[0] != 'ok':
            logger.error(f"Backup CORRUPTO detectado: {backup_path} - {result[0]}")
            raise RuntimeError(f"El backup falló la verificación de integridad: {result[0]}")
        logger.info(f"Backup creado y verificado: {backup_path}")
    except sqlite3.Error as e:
        logger.error(f"Error verificando integridad del backup: {e}")
        raise

    return backup_path


def get_periodos(estado=None):
    """Obtiene todos los períodos."""
    conn = get_connection()
    query = "SELECT * FROM periodos WHERE 1=1"
    params = []
    if estado:
        query += " AND estado = ?"
        params.append(estado)
    query += " ORDER BY anio DESC, mes DESC, quincena DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ──────────────────────────────────────────────────
# FUNCIONES AUXILIARES - LIQUIDACIONES
# ──────────────────────────────────────────────────

def get_liquidacion(periodo_id, empleado_id):
    """Obtiene la liquidación de un empleado en un período."""
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM liquidaciones WHERE periodo_id = ? AND empleado_id = ?",
        (periodo_id, empleado_id)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_liquidaciones_periodo(periodo_id):
    """Obtiene todas las liquidaciones de un período."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT l.*, e.apellido_nombre, e.cuil, e.seccion, e.categoria
        FROM liquidaciones l
        JOIN empleados e ON l.empleado_id = e.id
        WHERE l.periodo_id = ?
        ORDER BY e.apellido_nombre
    """, (periodo_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def guardar_liquidacion(data):
    """Guarda o actualiza una liquidación."""
    conn = get_connection()
    c = conn.cursor()

    # Filtrar claves internas (las que empiezan con _) para evitar errores en la DB
    data_clean = {k: v for k, v in data.items() if not k.startswith('_')}

    # Verificar si ya existe
    existing = conn.execute(
        "SELECT id FROM liquidaciones WHERE periodo_id = ? AND empleado_id = ?",
        (data_clean['periodo_id'], data_clean['empleado_id'])
    ).fetchone()

    if existing:
        # Actualizar
        fields = []
        values = []
        for key, val in data_clean.items():
            if key not in ('periodo_id', 'empleado_id', 'id'):
                fields.append(f"{key} = ?")
                values.append(val)
        fields.append("updated_at = CURRENT_TIMESTAMP")
        values.append(existing['id'])
        conn.execute(f"UPDATE liquidaciones SET {', '.join(fields)} WHERE id = ?", values)
    else:
        # Insertar
        cols = ', '.join(data_clean.keys())
        placeholders = ', '.join(['?'] * len(data_clean))
        c.execute(f"INSERT INTO liquidaciones ({cols}) VALUES ({placeholders})",
                  list(data_clean.values()))

    conn.commit()
    conn.close()


def eliminar_liquidacion(periodo_id, empleado_id):
    """Elimina una liquidación específica."""
    conn = get_connection()
    conn.execute("DELETE FROM liquidaciones WHERE periodo_id = ? AND empleado_id = ?", (periodo_id, empleado_id))
    conn.commit()
    conn.close()


def eliminar_liquidaciones_multiples(periodo_id, empleado_ids):
    """Elimina múltiples liquidaciones de un período."""
    if not empleado_ids:
        return
    conn = get_connection()
    placeholders = ', '.join(['?'] * len(empleado_ids))
    query = f"DELETE FROM liquidaciones WHERE periodo_id = ? AND empleado_id IN ({placeholders})"
    conn.execute(query, [periodo_id] + list(empleado_ids))
    conn.commit()
    conn.close()


def get_historial_empleado(empleado_id):
    """Obtiene el historial de liquidaciones de un empleado."""
    conn = get_connection()
    rows = conn.execute("""
        SELECT l.*, p.quincena, p.mes, p.anio, p.estado as periodo_estado
        FROM liquidaciones l
        JOIN periodos p ON l.periodo_id = p.id
        WHERE l.empleado_id = ?
        ORDER BY p.anio DESC, p.mes DESC, p.quincena DESC
    """, (empleado_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]


# Inicializar BD al importar
init_db()

# ──────────────────────────────────────────────
# NOVEDADES IMPORTADAS
# ──────────────────────────────────────────────

def guardar_novedad_importada(novedad):
    """Guarda o actualiza una novedad importada de Excel."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("""
        INSERT INTO novedades_importadas (
            periodo_id, empleado_id, horas_comunes, horas_extra_50, horas_extra_100,
            dias_trabajados, dias_vacaciones, trabajos_varios, viaticos,
            remplazo_encargado, prop_aguinaldo, concepto_libre_1_nombre,
            concepto_libre_1_importe, concepto_libre_2_nombre, concepto_libre_2_importe
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(periodo_id, empleado_id) DO UPDATE SET
            horas_comunes=excluded.horas_comunes,
            horas_extra_50=excluded.horas_extra_50,
            horas_extra_100=excluded.horas_extra_100,
            dias_trabajados=excluded.dias_trabajados,
            dias_vacaciones=excluded.dias_vacaciones,
            trabajos_varios=excluded.trabajos_varios,
            viaticos=excluded.viaticos,
            remplazo_encargado=excluded.remplazo_encargado,
            prop_aguinaldo=excluded.prop_aguinaldo,
            concepto_libre_1_nombre=excluded.concepto_libre_1_nombre,
            concepto_libre_1_importe=excluded.concepto_libre_1_importe,
            concepto_libre_2_nombre=excluded.concepto_libre_2_nombre,
            concepto_libre_2_importe=excluded.concepto_libre_2_importe,
            created_at=CURRENT_TIMESTAMP
    """, (
        novedad['periodo_id'], novedad['empleado_id'], novedad.get('horas_comunes', 0),
        novedad.get('horas_extra_50', 0), novedad.get('horas_extra_100', 0),
        novedad.get('dias_trabajados', 0), novedad.get('dias_vacaciones', 0),
        novedad.get('trabajos_varios', 0), novedad.get('viaticos', 0),
        novedad.get('remplazo_encargado', 0), novedad.get('prop_aguinaldo', 0),
        novedad.get('concepto_libre_1_nombre', ''), novedad.get('concepto_libre_1_importe', 0),
        novedad.get('concepto_libre_2_nombre', ''), novedad.get('concepto_libre_2_importe', 0)
    ))
    conn.commit()
    conn.close()

def get_novedades_importadas(periodo_id):
    """Obtiene todas las novedades guardadas para un periodo."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM novedades_importadas WHERE periodo_id = ?", (periodo_id,))
    rows = [dict(r) for r in c.fetchall()]
    conn.close()
    return {r['empleado_id']: r for r in rows}

def eliminar_novedades_importadas(periodo_id):
    """Elimina todas las novedades de un periodo."""
    conn = get_connection()
    c = conn.cursor()
    c.execute("DELETE FROM novedades_importadas WHERE periodo_id = ?", (periodo_id,))
    conn.commit()
    conn.close()
