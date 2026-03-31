"""
app.py - Aplicación principal de Liquidación de Sueldos.
Interfaz Streamlit con tres módulos: Administración, Liquidación e Informes.
"""
import streamlit as st
import pandas as pd
import os
import io
from datetime import date, datetime

import database as db
import import_data
import calculator
import reports


def _fmt_ar(n, decimales=2):
    """Formato argentino: punto para miles, coma para decimales."""
    if n is None:
        return '0,00' if decimales == 2 else '0'
    fmt_us = f"{abs(n):,.{decimales}f}"
    fmt_ar = fmt_us.replace(',', '@').replace('.', ',').replace('@', '.')
    if n < 0:
        return f"-{fmt_ar}"
    return fmt_ar


def _fmt_df(df):
    """Aplica formato argentino a todas las columnas numéricas de un DataFrame."""
    df_fmt = df.copy()
    for col in df_fmt.columns:
        if df_fmt[col].dtype.kind in 'if':  # integer or float
            df_fmt[col] = df_fmt[col].apply(lambda x: _fmt_ar(x))
    return df_fmt


# ════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════
st.set_page_config(
    page_title="Liquidación de Sueldos",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ════════════════════════════════════════════════════
# AUTENTICACION
# ════════════════════════════════════════════════════
USUARIOS = {
    "etcheoscar": "oscar2026",
}

def login():
    """Pantalla de login elegante."""
    st.markdown("""
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        .stApp {
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%) !important;
        }
        .login-card {
            background: rgba(30, 41, 59, 0.85);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(99, 102, 241, 0.3);
            border-radius: 20px;
            padding: 48px 40px;
            max-width: 420px;
            margin: 0 auto;
            box-shadow: 0 25px 60px rgba(0, 0, 0, 0.5), 0 0 40px rgba(99, 102, 241, 0.1);
        }
        .login-icon {
            font-size: 56px;
            text-align: center;
            margin-bottom: 8px;
        }
        .login-title {
            font-family: 'Inter', sans-serif;
            font-weight: 700;
            font-size: 28px;
            text-align: center;
            color: #f1f5f9;
            margin-bottom: 4px;
        }
        .login-subtitle {
            font-family: 'Inter', sans-serif;
            font-weight: 400;
            font-size: 14px;
            text-align: center;
            color: #94a3b8;
            margin-bottom: 32px;
        }
        .login-footer {
            font-family: 'Inter', sans-serif;
            font-size: 12px;
            text-align: center;
            color: #475569;
            margin-top: 24px;
        }
        /* Mobile responsive */
        @media (max-width: 768px) {
            .login-card {
                padding: 32px 20px;
                margin: 0 8px;
                border-radius: 16px;
            }
            .login-icon { font-size: 44px; }
            .login-title { font-size: 22px; }
            .login-subtitle { font-size: 13px; margin-bottom: 20px; }
        }
    </style>
    """, unsafe_allow_html=True)

    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown('<div class="login-card">', unsafe_allow_html=True)
        st.markdown('<div class="login-icon">💰</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-title">Liquidacion de Sueldos</div>', unsafe_allow_html=True)
        st.markdown('<div class="login-subtitle">Ingrese sus credenciales para acceder al sistema</div>', unsafe_allow_html=True)

        usuario = st.text_input("👤 Usuario", key="login_user", placeholder="Ingrese su usuario")
        clave = st.text_input("🔒 Contrasena", type="password", key="login_pass", placeholder="Ingrese su contrasena")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔓  INGRESAR AL SISTEMA", use_container_width=True, type="primary"):
            if usuario in USUARIOS and USUARIOS[usuario] == clave:
                st.session_state["autenticado"] = True
                st.session_state["usuario"] = usuario
                st.rerun()
            else:
                st.error("❌ Usuario o contrasena incorrectos.")

        st.markdown('<div class="login-footer">Sistema protegido · Acceso autorizado unicamente</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    st.stop()

if not st.session_state.get("autenticado", False):
    login()
else:
    # Limpiar cualquier residuo visual del login
    st.markdown("""<style>.login-card{display:none !important;}</style>""", unsafe_allow_html=True)

# Mostrar mensajes de éxito pendientes (por rerun)
if 'mensaje_exito' in st.session_state:
    st.success(st.session_state.mensaje_exito)
    del st.session_state.mensaje_exito

# Cargar fuentes y CSS premium
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    :root {
        --primary: #6366f1; /* Indigo */
        --secondary: #ec4899; /* Pink */
        --success: #10b981; /* Emerald */
        --warning: #f59e0b; /* Amber */
        --danger: #ef4444; /* Red */
        --bg-dark: #0f172a;
        --glass: rgba(30, 41, 59, 0.7);
        --glass-border: rgba(255, 255, 255, 0.1);
    }

    /* Global reset and header fix */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }
    .main, .stApp {
        background: radial-gradient(circle at top right, #1e1b4b, #0f172a) !important;
        font-family: 'Inter', sans-serif !important;
        color: #f1f5f9 !important;
    }

    .main .block-container { padding-top: 1rem; }

    /* Glassmorphism containers */
    div.stExpander, div[data-testid="stForm"], .stTabs [data-baseweb="tab-panel"] {
        background: var(--glass) !important;
        backdrop-filter: blur(12px) !important;
        border: 1px solid var(--glass-border) !important;
        border-radius: 12px !important;
        padding: 1.5rem !important;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3) !important;
    }

    /* Metrics and text */
    div[data-testid="stMetricValue"] { 
        font-weight: 700; 
        color: var(--primary);
        letter-spacing: -0.025em;
    }
    h1, h2, h3 { 
        color: #fff !important; 
        font-weight: 700 !important;
        letter-spacing: -0.025em;
    }

    /* Tabs styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background: transparent !important;
        padding: 10px 0;
    }
    .stTabs [data-baseweb="tab"] {
        background: rgba(255, 255, 255, 0.05) !important;
        border-radius: 10px !important;
        padding: 8px 24px !important;
        color: #94a3b8 !important;
        border: 1px solid transparent !important;
        transition: all 0.3s ease;
    }
    .stTabs [aria-selected="true"] {
        background: var(--primary) !important;
        color: white !important;
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.4);
    }

    /* Buttons */
    /* Buttons Styling */
    .stButton > button, div[data-testid="stDownloadButton"] > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        background-color: #334155 !important; /* Slate background for secondary buttons */
        color: #ffffff !important;
        border: 1px solid rgba(255,255,255,0.2) !important;
        transition: all 0.2s ease !important;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        padding: 0.6rem 1.2rem !important;
    }
    
    .stButton > button:hover, div[data-testid="stDownloadButton"] > button:hover {
        transform: translateY(-2px);
        background-color: #475569 !important;
        border-color: #6366f1 !important;
        color: #ffffff !important;
        box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    }
    
    /* Primary buttons (Indigo) */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #6366f1, #4f46e5) !important;
        border: none !important;
        color: #ffffff !important;
    }
    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #818cf8, #6366f1) !important;
        box-shadow: 0 0 20px rgba(99, 102, 241, 0.4) !important;
    }

    /* Checkboxes: HIGH CONTRAST FIX */
    div[data-testid="stCheckbox"] {
        background: rgba(255, 255, 255, 0.05);
        padding: 5px 12px;
        border-radius: 8px;
        border: 1px solid var(--glass-border);
        transition: all 0.2s ease;
    }
    div[data-testid="stCheckbox"]:hover {
        background: rgba(255, 255, 255, 0.1);
        border-color: #ffffff;
    }
    /* The checkbox box itself */
    div[data-testid="stCheckbox"] span[data-baseweb="checkbox"] {
        background-color: #1e293b !important; /* Deep dark background */
        border: 2px solid #6366f1 !important; /* Indigo border */
        width: 22px !important;
        height: 22px !important;
        border-radius: 4px !important;
    }
    /* Active state */
    div[data-testid="stCheckbox"] [aria-checked="true"] div {
        background-color: #6366f1 !important;
    }

    /* High Contrast Text Fixes */
    .stMarkdown, p, span, label {
        color: #f8fafc !important; /* Extremely light gray/white */
    }

    /* SPECIFIC FIX FOR CHECKBOX LABELS */
    div[data-testid="stCheckbox"] label p {
        color: #ffffff !important;
        font-weight: 600 !important;
        font-size: 1.05rem !important;
    }

    /* Inputs labels and values */
    .stNumberInput label, .stTextInput label, .stSelectbox label, .stDateInput label, .stRadio label {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    
    /* Radio options specifically */
    div[data-testid="stRadio"] label p {
        color: #ffffff !important;
        font-weight: 500 !important;
    }

    /* Input fields themselves */
    .stNumberInput input, .stTextInput input, .stSelectbox [data-baseweb="select"], .stDateInput input {
        color: #ffffff !important;
        background-color: #1e293b !important; /* Solid dark background for inputs */
        border: 1px solid var(--glass-border) !important;
    }

    /* SPECIFIC FIX FOR DISABLED FIELDS (Make them readable) */
    input:disabled, [data-disabled="true"] {
        -webkit-text-fill-color: #ffffff !important; /* Force white even when disabled */
        color: #ffffff !important;
        background-color: #334155 !important; /* Slightly lighter but still dark background for disabled */
        opacity: 1 !important;
    }
    
    /* Selectbox specifically */
    div[data-baseweb="select"] > div {
        color: #ffffff !important;
        background-color: #1e293b !important;
    }

    /* Sidebar cleanup */
    section[data-testid="stSidebar"] {
        background-color: #0f172a !important;
        border-right: 1px solid var(--glass-border);
    }
    section[data-testid="stSidebar"] .stMarkdown p {
        color: #f1f5f9 !important;
    }

    /* Notifications (Info, Warning, Error) */
    div[data-testid="stNotification"] {
        background-color: rgba(30, 41, 59, 0.8) !important;
        backdrop-filter: blur(10px);
        border: 1px solid rgba(255,255,255,0.1) !important;
        color: #ffffff !important;
    }
    div[data-testid="stNotification"] p {
        color: #ffffff !important;
    }

    /* ═══ MOBILE RESPONSIVE ═══ */
    @media (max-width: 768px) {
        /* Container principal - menos padding */
        .main .block-container {
            padding: 0.3rem 0.5rem !important;
            max-width: 100% !important;
        }

        /* Sidebar mas angosta en movil */
        section[data-testid="stSidebar"] {
            min-width: 240px !important;
            max-width: 280px !important;
        }
        section[data-testid="stSidebar"] .block-container {
            padding: 0.5rem !important;
        }

        /* Columnas: forzar stack vertical en movil */
        div[data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
            gap: 4px !important;
        }
        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"] {
            flex: 1 1 100% !important;
            min-width: 100% !important;
            width: 100% !important;
        }

        /* Tabs: scroll horizontal, no wrap */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            flex-wrap: nowrap !important;
            gap: 4px !important;
            padding: 4px 0 !important;
            -webkit-overflow-scrolling: touch;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 12px !important;
            padding: 6px 10px !important;
            white-space: nowrap !important;
            flex-shrink: 0 !important;
        }

        /* Glassmorphism containers: menos padding */
        div.stExpander, div[data-testid="stForm"], .stTabs [data-baseweb="tab-panel"] {
            padding: 0.6rem !important;
            border-radius: 8px !important;
        }

        /* Botones touch-friendly */
        .stButton > button, div[data-testid="stDownloadButton"] > button {
            min-height: 44px !important;
            font-size: 13px !important;
            padding: 0.4rem 0.8rem !important;
            width: 100% !important;
            letter-spacing: 0 !important;
            text-transform: none !important;
        }

        /* Inputs mas grandes para touch */
        .stTextInput input, .stNumberInput input,
        div[data-baseweb="select"] {
            min-height: 44px !important;
            font-size: 16px !important;
        }

        /* Tablas: scroll horizontal y texto mas chico */
        .stDataFrame, div[data-testid="stDataFrame"] {
            overflow-x: auto !important;
            max-width: 100% !important;
        }
        .stDataFrame table {
            font-size: 11px !important;
        }

        /* Metricas compactas */
        div[data-testid="stMetric"] {
            padding: 6px !important;
        }
        div[data-testid="stMetric"] label {
            font-size: 10px !important;
        }
        div[data-testid="stMetric"] div[data-testid="stMetricValue"] {
            font-size: 16px !important;
        }

        /* Titulos mas chicos */
        h1 { font-size: 1.3rem !important; }
        h2 { font-size: 1.1rem !important; }
        h3 { font-size: 1rem !important; }

        /* Expanders mas compactos */
        details[data-testid="stExpander"] summary {
            font-size: 13px !important;
            padding: 8px !important;
        }

        /* Checkboxes */
        div[data-testid="stCheckbox"] {
            padding: 4px 8px !important;
        }

        /* Selectbox labels */
        .stSelectbox label, .stTextInput label, .stNumberInput label {
            font-size: 12px !important;
        }

        /* Ocultar elementos decorativos pesados en movil */
        .stDeployButton { display: none !important; }
    }
</style>
""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════
# ESTADO DE SESIÓN
# ════════════════════════════════════════════════════
if 'periodo_quincena' not in st.session_state:
    _guardado = db.cargar_periodo_activo()
    if _guardado:
        st.session_state.periodo_quincena, st.session_state.periodo_mes, st.session_state.periodo_anio = _guardado
    else:
        st.session_state.periodo_quincena = 2
        st.session_state.periodo_mes = 2
        st.session_state.periodo_anio = 2026


# ════════════════════════════════════════════════════
# BARRA LATERAL: BÚSQUEDA Y PERÍODO
# ════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## 💰 Liquidación de Sueldos")
    col_user, col_logout = st.columns([3, 1])
    with col_user:
        st.caption(f"👤 {st.session_state.get('usuario', '')}")
    with col_logout:
        if st.button("🚪", help="Cerrar sesion", key="btn_logout"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    st.markdown("---")

    # ── Selección de período ──
    st.markdown("### 📅 Período activo")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.periodo_quincena = st.selectbox(
            "Quincena", [1, 2], index=st.session_state.periodo_quincena - 1, key="sel_q"
        )
    with col2:
        st.session_state.periodo_mes = st.selectbox(
            "Mes", list(range(1, 13)), index=st.session_state.periodo_mes - 1, key="sel_m"
        )
    with col3:
        st.session_state.periodo_anio = st.number_input(
            "Año", min_value=2020, max_value=2050, value=st.session_state.periodo_anio, key="sel_a"
        )

    q = st.session_state.periodo_quincena
    m = st.session_state.periodo_mes
    a = st.session_state.periodo_anio
    periodo_str = f"{q:02d}/{m:02d}/{str(a)[2:]}"

    # Persistir período activo en DB
    db.guardar_periodo_activo(q, m, a)

    # Verificar estado del período
    periodo_actual = db.get_periodo(q, m, a)
    if periodo_actual and periodo_actual['estado'] == 'CERRADO':
        st.warning(f"⚠️ Período {periodo_str} CERRADO")
    else:
        st.success(f"✅ Período {periodo_str} ABIERTO")

    st.markdown("---")

    # ── Búsqueda de personal ──
    st.markdown("### 🔍 Búsqueda de personal")
    busqueda = st.text_input("Apellido / Nombre", placeholder="Escribí para buscar...", key="busqueda_global")

    secciones_lista = db.get_secciones()
    filtro_seccion = st.selectbox("Sección", ["Todas"] + secciones_lista, key="filtro_sec")

    cats_lista = db.get_categorias_empleados()
    filtro_cat = st.selectbox("Categoría", ["Todas"] + cats_lista, key="filtro_cat")

    if busqueda or filtro_seccion != "Todas" or filtro_cat != "Todas":
        resultados = db.get_empleados(
            busqueda=busqueda if busqueda else None,
            seccion=filtro_seccion if filtro_seccion != "Todas" else None,
            categoria=filtro_cat if filtro_cat != "Todas" else None
        )
        if resultados:
            st.markdown(f"**{len(resultados)} resultados**")
            for emp in resultados[:15]:
                if st.button(f"👤 {emp['apellido_nombre']}", key=f"bus_{emp['id']}"):
                    st.session_state.ver_empleado = emp['id']
                    st.session_state.tab_activo = "empleado_detalle"
        else:
            st.info("Sin resultados")


# ════════════════════════════════════════════════════
# CONTENIDO PRINCIPAL - TABS
# ════════════════════════════════════════════════════
tab_admin, tab_liq, tab_informes = st.tabs([
    "📂 Administración",
    "📝 Liquidación",
    "📈 Informes"
])


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB A — ADMINISTRACIÓN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_admin:
    sub_a1, sub_a2 = st.tabs(["👥 Gestión de Empleados", "📋 Categorías y Convenio"])

    # ── A1: GESTIÓN DE EMPLEADOS ──
    with sub_a1:
        st.markdown("# 👥 Gestión de Empleados")

        # Importación
        with st.expander("📂 Importar desde Excel", expanded=False):
            archivo = st.file_uploader("Subir archivo Excel (.xlsx / .xls)", type=["xlsx", "xls"], key="upload_excel")
            if archivo:
                if st.button("🚀 Importar personal", key="btn_importar"):
                    # Guardar temporalmente
                    tmp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "temp_import.xlsx")
                    with open(tmp_path, 'wb') as f:
                        f.write(archivo.read())
                    importados, errores = import_data.importar_personal_excel(tmp_path)
                    os.remove(tmp_path)

                    st.success(f"✅ Se importaron {importados} empleados correctamente.")

                    if errores:
                        st.warning(f"⚠️ {len(errores)} empleados con CUIL con error o faltante:")
                        df_err = pd.DataFrame(errores)
                        st.dataframe(df_err, use_container_width=True)

        # Lista de empleados
        empleados = db.get_empleados()
        if empleados:
            # 1. Filtros rápidos (para afectar tanto a la lista como al dropdown de edición)
            col_f1, col_f2, col_f3, col_f4 = st.columns(4)
            with col_f1:
                f_estado = st.selectbox("Filtrar Estado", ["Todos", "ACTIVO", "INACTIVO"], key="f_estado")
            with col_f2:
                f_cond = st.selectbox("Filtrar Condición", ["Todos", "PERMANENTE", "EVENTUAL"], key="f_cond")
            with col_f3:
                f_tipo = st.selectbox("Filtrar Tipo", ["Todos", "MENSUALIZADO", "JORNAL"], key="f_tipo")
            with col_f4:
                f_sec = st.selectbox("Filtrar Sección", ["Todas"] + db.get_secciones(), key="f_sec_admin")

            # Aplicar filtros
            emp_filtrados = empleados
            if f_estado != "Todos":
                emp_filtrados = [e for e in emp_filtrados if e['estado'] == f_estado]
            if f_cond != "Todos":
                emp_filtrados = [e for e in emp_filtrados if e.get('condicion', 'PERMANENTE') == f_cond]
            if f_tipo != "Todos":
                emp_filtrados = [e for e in emp_filtrados if e['tipo'] == f_tipo]
            if f_sec != "Todas":
                emp_filtrados = [e for e in emp_filtrados if e['seccion'] == f_sec]

            st.markdown("---")
            st.markdown("### ✏️ Editar / Crear Empleado")
            
            accion = st.radio("Acción", ["Editar empleado existente", "Crear nuevo empleado"], horizontal=True, key=f"rad_acc_{emp_id if 'emp_id' in locals() else 'global'}")

            if accion == "Editar empleado existente":
                if 'sel_emp_key_cnt' not in st.session_state:
                    st.session_state.sel_emp_key_cnt = 0
                    
                opciones_nombres = ["--- Seleccione un empleado ---"] + [f"{e['id']} - {e['apellido_nombre']}" for e in emp_filtrados]
                opciones_dict = {f"{e['id']} - {e['apellido_nombre']}": e['id'] for e in emp_filtrados}
                
                col_sel, col_limpiar = st.columns([5, 1])
                with col_sel:
                    sel = st.selectbox("Seleccionar empleado", opciones_nombres, key=f"sel_emp_edit_{st.session_state.sel_emp_key_cnt}")
                with col_limpiar:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("🗑️", key="btn_limpiar_sel_emp", help="Limpiar selección"):
                        st.session_state.sel_emp_key_cnt += 1
                        st.rerun()

                if 'msg_edit_emp' in st.session_state:
                    st.success(st.session_state.msg_edit_emp)
                    del st.session_state.msg_edit_emp
                
                if sel and sel != "--- Seleccione un empleado ---":
                    emp_id = opciones_dict[sel]
                    emp = db.get_empleado(emp_id)
                    if emp:
                        # Control de desbloqueo (fuera del form para disparar rerun)
                        desbloqueado = st.checkbox("🔓 Habilitar edición de datos básicos (Nombre, Ingreso, etc.)", 
                                                   key=f"unlock_{emp_id}")
                        
                        if not desbloqueado:
                            st.info("💡 Marcá el cuadro de arriba para habilitar la edición de este empleado.")
                        
                        with st.form("form_editar_emp"):
                            # ... todos los inputs se mantienen igual ...
                            col1, col2 = st.columns(2)
                            with col1:
                                nombre = st.text_input("Apellido y Nombre", value=emp['apellido_nombre'], disabled=not desbloqueado, key=f"emp_nom_{emp_id}")
                                cuil = st.text_input("CUIL", value=emp.get('cuil', ''), disabled=not desbloqueado, key=f"emp_cuil_{emp_id}")
                                
                                c_tp1, c_tp2 = st.columns(2)
                                with c_tp1:
                                    condicion = st.selectbox("Condición", ["PERMANENTE", "EVENTUAL"],
                                                        index=["PERMANENTE", "EVENTUAL"].index(emp.get('condicion', 'PERMANENTE')),
                                                        disabled=not desbloqueado, key=f"emp_cond_{emp_id}")
                                with c_tp2:
                                    tipo = st.selectbox("Tipo", ["JORNAL", "MENSUALIZADO"],
                                                        index=0 if emp['tipo'] == 'JORNAL' else 1,
                                                        disabled=not desbloqueado, key=f"emp_tipo_{emp_id}")
                                
                                seccion = st.text_input("Sección", value=emp.get('seccion', ''), disabled=not desbloqueado, key=f"emp_sec_{emp_id}")
                                cats_conv = [c['nombre'] for c in db.get_categorias()]
                                cat_idx = 0
                                if emp.get('categoria') in cats_conv:
                                    cat_idx = cats_conv.index(emp['categoria'])
                                
                                convenio = st.radio("Convenio", ["Bajo Convenio", "Fuera de Convenio"], 
                                                    index=0 if not emp.get('fuera_convenio') else 1, horizontal=True,
                                                    key=f"emp_conv_{emp_id}")
                                fuera_conv = 1 if convenio == "Fuera de Convenio" else 0

                                c_cat1, c_cat2 = st.columns([1, 1])
                                with c_cat1:
                                    categoria = st.selectbox("Categoría", cats_conv, index=cat_idx, key=f"emp_cat_{emp_id}")
                                with c_cat2:
                                    val_cat_db = db.get_valor_categoria(categoria, datetime.now().month, datetime.now().year)
                                    db_val = 0.0
                                    if val_cat_db:
                                        db_val = val_cat_db['valor_hora'] if tipo in ["JORNAL", "EVENTUAL"] else val_cat_db['valor_mensual']
                                    
                                    label_val = "Valor Hora" if tipo in ["JORNAL", "EVENTUAL"] else "Sueldo Básico"
                                    
                                    # Determinar valor a mostrar: si es fuera de convenio prioritizar el manual del legajo
                                    val_manual = float(emp.get('sueldo_base', 0))
                                    val_to_show = val_manual if (fuera_conv and val_manual > 0) else db_val
                                    
                                    # Siempre permitir edición para evitar confusión del usuario
                                    sueldo_base = st.number_input(label_val, value=val_to_show, key=f"emp_sb_edit_{emp_id}")

                                    estado = st.selectbox("Estado", ["ACTIVO", "INACTIVO"],
                                                        index=0 if emp['estado'] == 'ACTIVO' else 1, disabled=not desbloqueado, key=f"emp_est_{emp_id}")
                                    
                                    if not fuera_conv and val_manual > 0 and val_manual != db_val:
                                        st.caption(f"ℹ️ Monto manual guardado: ${_fmt_ar(val_manual)} (Seleccioná 'Fuera de Convenio' para usarlo)")

                            with col2:
                                fi = emp.get('fecha_ingreso')
                                if fi and isinstance(fi, str):
                                    try:
                                        fi = datetime.strptime(fi, '%Y-%m-%d').date()
                                    except:
                                        try:
                                            fi = datetime.strptime(fi, '%d/%m/%Y').date()
                                        except:
                                            fi = date.today()
                                elif not fi:
                                    fi = date.today()
                                fi_str = fi.strftime('%d/%m/%Y') if isinstance(fi, date) else ''
                                fecha_ing_str = st.text_input("Fecha de ingreso (DD/MM/AAAA)", value=fi_str, disabled=not desbloqueado, key=f"emp_fi_{emp_id}")
                                try:
                                    fecha_ing = datetime.strptime(fecha_ing_str, '%d/%m/%Y').date()
                                except:
                                    fecha_ing = fi
                                liq_mensual = st.checkbox("¿Liquida mensual?", value=bool(emp.get('liquida_mensual', 0)), disabled=not desbloqueado, key=f"emp_lm_{emp_id}")
                                liq_ant_bas = st.checkbox("¿Liquida antigüedad sobre básico?",
                                                        value=bool(emp.get('liquida_antiguedad_basico', 0)), disabled=not desbloqueado, key=f"emp_lab_{emp_id}")
                                liq_present = st.checkbox("¿Liquida presentismo?",
                                                        value=bool(emp.get('liquida_presentismo', 1)), disabled=not desbloqueado, key=f"emp_lp_{emp_id}")
                                pct_pres = st.number_input("Porcentaje Presentismo (%)", value=float(emp.get('porc_presentismo', 15.0)), step=0.01, format="%.2f", disabled=not desbloqueado, key=f"emp_pp_pct_{emp_id}")
                                
                                if liq_mensual:
                                    c_dms1, c_dms2 = st.columns(2)
                                    with c_dms1:
                                        dias_liq_mensual = st.selectbox("Días a liquidar", list(range(1, 31)), 
                                                                    index=emp.get('dias_liquidacion_mensual', 30)-1, 
                                                                    key=f"emp_dlm_{emp_id}")
                                    with c_dms2:
                                        # Por defecto SI si es 30, sino segun DB
                                        def_perm = True if dias_liq_mensual == 30 else bool(emp.get('dias_mensuales_permanente', 1))
                                        dias_perm = st.checkbox("¿Permanente?", value=def_perm, key=f"emp_dms_p_{emp_id}")
                                else:
                                    dias_liq_mensual = 30
                                    dias_perm = 1

                                st.markdown("---")
                                c_add_row1, c_add_row2 = st.columns(2)
                                with c_add_row1:
                                    anticipos = st.number_input("Anticipos", value=float(emp.get('anticipos', 0)), key=f"emp_ant_{emp_id}")
                                with c_add_row2:
                                    acred_banco = st.number_input("Acreditación Banco", value=float(emp.get('acreditacion_banco', 0)), key=f"emp_ab_{emp_id}")
                                otros = st.number_input("Otros (+ Haber / - Descuento)", value=float(emp.get('otros', 0)), key=f"emp_otr_{emp_id}")
                                observaciones = st.text_area("Observaciones", value=emp.get('observaciones', ''), key=f"emp_obs_{emp_id}", height=80)

                                dif_sueldo = st.number_input("Diferencia de sueldo", value=float(emp.get('diferencia_sueldo', 0)), key=f"emp_ds_{emp_id}")
                                premio = st.number_input("Premio producción", value=float(emp.get('premio_produccion', 0)), key=f"emp_pp_{emp_id}")
                                desc_premio = st.number_input("DESC.PREM.PROD.", value=float(emp.get('descuento_premio_prod', 0)), key=f"emp_dpp_{emp_id}")
                                cifra_fija = st.number_input("Cifra Fija", value=float(emp.get('cifra_fija', 0)), key=f"emp_cf_{emp_id}")
                                cobra_cifra_fija = st.checkbox("¿Cobra Cifra Fija?", value=bool(emp.get('cobra_cifra_fija', 0)), key=f"emp_ccf_{emp_id}")
                                jubilacion = st.number_input("Jubilación", value=float(emp.get('jubilacion', 0)), key=f"emp_jub_{emp_id}")
                                obra_social = st.number_input("Obra Social", value=float(emp.get('obra_social', 0)), key=f"emp_os_{emp_id}")
                                seguro = st.number_input("Seguro", value=float(emp.get('seguro', 0)), key=f"emp_seg_{emp_id}")
                                hs_fijas = st.number_input("HS Fijas por periodo", value=float(emp.get('hs_fijas', 0)), key=f"emp_hf_{emp_id}")
                                st.markdown("**Contabilidad:**")
                                codigo_contable = st.text_input("Código Contable (subcuenta individual)", value=emp.get('codigo_contable', '') or '', key=f"emp_cc_{emp_id}", help="Ej: 1.1.070.10.006 (para empleados Fuera de SIJIP)")
                                seccion_debito_ext = st.text_input("Sección Débito ext. (asiento)", value=emp.get('seccion_debito_externo', '') or '', key=f"emp_sde_{emp_id}", help="Ej: FABRICA — sección donde se debita la acred. banco de este empleado")

                            st.markdown("---")
                            confirmar_guardado = st.checkbox("⚠️ Confirmo que deseo aplicar estos cambios permanentemente", value=False, disabled=not desbloqueado, key=f"emp_conf_{emp_id}")

                            submitted = st.form_submit_button("💾 Guardar cambios", disabled=not desbloqueado)
                            
                            if submitted:
                                if not confirmar_guardado:
                                    st.error("❌ Debes marcar la casilla de confirmación para poder guardar.")
                                else:
                                    db.actualizar_empleado(emp_id, {
                                        'apellido_nombre': nombre,
                                        'cuil': cuil,
                                        'tipo': tipo,
                                        'seccion': seccion,
                                        'categoria': categoria,
                                        'fecha_ingreso': fecha_ing.strftime('%Y-%m-%d'),
                                        'liquida_mensual': 1 if liq_mensual else 0,
                                        'liquida_antiguedad_basico': 1 if liq_ant_bas else 0,
                                        'liquida_presentismo': 1 if liq_present else 0,
                                        'estado': estado,
                                        'diferencia_sueldo': dif_sueldo,
                                        'premio_produccion': premio,
                                        'descuento_premio_prod': desc_premio,
                                        'cifra_fija': cifra_fija,
                                        'cobra_cifra_fija': 1 if cobra_cifra_fija else 0,
                                        'jubilacion': jubilacion,
                                        'obra_social': obra_social,
                                        'seguro': seguro,
                                        'fuera_convenio': fuera_conv,
                                        'sueldo_base': sueldo_base,
                                        'hs_fijas': hs_fijas,
                                        'condicion': condicion,
                                        'anticipos': anticipos,
                                        'acreditacion_banco': acred_banco,
                                        'otros': otros,
                                        'porc_presentismo': pct_pres,
                                        'dias_liquidacion_mensual': dias_liq_mensual,
                                        'dias_mensuales_permanente': 1 if dias_perm else 0,
                                        'observaciones': observaciones,
                                        'codigo_contable': codigo_contable,
                                        'seccion_debito_externo': seccion_debito_ext,
                                    })
                                    st.session_state.sel_emp_key_cnt += 1
                                    st.rerun()

                        # Zona de Peligro: Eliminar Empleado
                        for _ in range(3): st.write("") # Espacio
                        with st.expander("⚠️ ZONA DE PELIGRO: Eliminar Empleado"):
                            st.error(f"Esta acción eliminará PERMANENTEMENTE a **{emp['apellido_nombre']}** y TODO su historial de liquidaciones.")
                            conf_borrar = st.checkbox(f"Confirmo que deseo eliminar a {emp['apellido_nombre']} definitivamente", key=f"del_conf_{emp_id}")
                            if st.button("🗑️ Eliminar Empleado Permanentemente", type="secondary", disabled=not conf_borrar, key=f"btn_del_{emp_id}", use_container_width=True):
                                db.eliminar_empleado(emp_id)
                                st.session_state.mensaje_exito = f"✅ El empleado {emp['apellido_nombre']} ha sido eliminado de la nómina."
                                st.session_state.sel_emp_key_cnt += 1
                                st.rerun()

            else:
                if 'msg_crear_emp' in st.session_state:
                    st.success(st.session_state.msg_crear_emp)
                    del st.session_state.msg_crear_emp

                # Crear nuevo
                with st.form("form_crear_emp", clear_on_submit=True):
                    col1, col2 = st.columns(2)
                    with col1:
                        nombre = st.text_input("Apellido y Nombre", key="new_emp_nom")
                        cuil = st.text_input("CUIL", key="new_emp_cuil")
                        
                        c_ntp1, c_ntp2 = st.columns(2)
                        with c_ntp1:
                            condicion = st.selectbox("Condición", ["PERMANENTE", "EVENTUAL"], key="new_emp_cond")
                        with c_ntp2:
                            tipo = st.selectbox("Tipo", ["JORNAL", "MENSUALIZADO"], key="new_emp_tipo")
                        
                        seccion = st.text_input("Sección", key="new_emp_sec")
                        cats_conv = [c['nombre'] for c in db.get_categorias()]
                        convenio = st.radio("Convenio", ["Bajo Convenio", "Fuera de Convenio"], horizontal=True, key="new_emp_conv")
                        fuera_conv = 1 if convenio == "Fuera de Convenio" else 0

                        c_cat1, c_cat2 = st.columns([1, 1])
                        with c_cat1:
                            categoria = st.selectbox("Categoría", cats_conv if cats_conv else ["Sin categorías"], key="new_emp_cat")
                        with c_cat2:
                            val_cat_db = db.get_valor_categoria(categoria, datetime.now().month, datetime.now().year)
                            db_val = 0.0
                            if val_cat_db:
                                db_val = val_cat_db['valor_hora'] if tipo in ["JORNAL", "EVENTUAL"] else val_cat_db['valor_mensual']
                            
                            label_val = "Valor Hora" if tipo in ["JORNAL", "EVENTUAL"] else "Sueldo Básico"
                            
                            # Siempre permitir edición en creación para evitar confusión
                            sueldo_base = st.number_input(label_val, value=db_val, key="new_emp_sb")
                            estado = st.selectbox("Estado", ["ACTIVO", "INACTIVO"], key="new_emp_est")
                    with col2:
                        fecha_ing_str_new = st.text_input("Fecha de ingreso (DD/MM/AAAA)", value=date.today().strftime('%d/%m/%Y'), key="new_emp_fi")
                        try:
                            fecha_ing = datetime.strptime(fecha_ing_str_new, '%d/%m/%Y').date()
                        except:
                            fecha_ing = date.today()
                        liq_mensual = st.checkbox("¿Liquida mensual?", key="new_emp_lm")
                        liq_ant_bas = st.checkbox("¿Liquida antigüedad sobre básico?", key="new_emp_lab")
                        liq_present = st.checkbox("¿Liquida presentismo?", value=True, key="new_emp_lp")
                        pct_pres = st.number_input("Porcentaje Presentismo (%)", value=15.0, step=0.01, format="%.2f", key="new_emp_pp_pct")
                        dif_sueldo = st.number_input("Diferencia de sueldo", value=0.0, key="new_emp_ds")
                        premio = st.number_input("Premio producción", value=0.0, key="new_emp_pp")
                        desc_premio = st.number_input("DESC.PREM.PROD.", value=0.0, key="new_emp_dpp")
                        cifra_fija = st.number_input("Cifra Fija", value=0.0, key="new_emp_cf")
                        cobra_cifra_fija_new = st.checkbox("¿Cobra Cifra Fija?", value=False, key="new_emp_ccf")
                        
                        st.markdown("---")
                        c_nadd_row1, c_nadd_row2 = st.columns(2)
                        with c_nadd_row1:
                            anticipos = st.number_input("Anticipos", value=0.0, key="new_emp_ant")
                        with c_nadd_row2:
                            acred_banco = st.number_input("Acreditación Banco", value=0.0, key="new_emp_ab")
                        otros = st.number_input("Otros (+/-)", value=0.0, key="new_emp_otr")
                        
                        if liq_mensual:
                            c_ndms1, c_ndms2 = st.columns(2)
                            with c_ndms1:
                                dias_liq_mensual = st.selectbox("Días a liquidar", list(range(1, 31)), index=29, key="new_emp_dlm")
                            with c_ndms2:
                                dias_perm = st.checkbox("¿Permanente?", value=True, key="new_emp_dms_p")
                        else:
                            dias_liq_mensual = 30
                            dias_perm = 1

                        observaciones = st.text_area("Observaciones", key="new_emp_obs", height=80)

                        jubilacion = st.number_input("Jubilación", value=0.0, key="new_emp_jub")
                        obra_social = st.number_input("Obra Social", value=0.0, key="new_emp_os")
                        seguro = st.number_input("Seguro", value=0.0, key="new_emp_seg")
                        hs_fijas = st.number_input("HS Fijas por periodo", value=0.0, key="new_emp_hf")

                    if st.form_submit_button("➕ Crear empleado"):
                        if nombre:
                            db.crear_empleado({
                                'apellido_nombre': nombre,
                                'cuil': cuil,
                                'tipo': tipo,
                                'seccion': seccion,
                                'categoria': categoria,
                                'fecha_ingreso': fecha_ing.strftime('%Y-%m-%d'),
                                'liquida_mensual': 1 if liq_mensual else 0,
                                'liquida_antiguedad_basico': 1 if liq_ant_bas else 0,
                                'liquida_presentismo': 1 if liq_present else 0,
                                'estado': estado,
                                'diferencia_sueldo': dif_sueldo,
                                'premio_produccion': premio,
                                'descuento_premio_prod': desc_premio,
                                'cobra_cifra_fija': 1 if cobra_cifra_fija_new else 0,
                                'cifra_fija': cifra_fija,
                                'jubilacion': jubilacion,
                                'obra_social': obra_social,
                                'seguro': seguro,
                                'fuera_convenio': fuera_conv,
                                'sueldo_base': sueldo_base,
                                'hs_fijas': hs_fijas,
                                'condicion': condicion,
                                'anticipos': anticipos,
                                'acreditacion_banco': acred_banco,
                                'otros': otros,
                                'porc_presentismo': pct_pres,
                                'dias_liquidacion_mensual': dias_liq_mensual,
                                'dias_mensuales_permanente': 1 if dias_perm else 0,
                                'observaciones': observaciones
                            })
                            st.session_state.msg_crear_emp = f"✅ Empleado {nombre} creado correctamente"
                            st.rerun()
                        else:
                            st.error("El nombre es obligatorio")

            # Preparar DataFrame para las tablas
            df_emp = pd.DataFrame(emp_filtrados)
            if not df_emp.empty and 'fecha_ingreso' in df_emp.columns:
                def _fmt_date(d):
                    if not d: return ''
                    for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                        try:
                            return datetime.strptime(d, fmt).strftime('%d/%m/%Y')
                        except ValueError:
                            continue
                    return d
                df_emp['fecha_ingreso'] = df_emp['fecha_ingreso'].apply(_fmt_date)

            # Agregar columnas de valor básico/hora y flags SI/NO
            if not df_emp.empty:
                def _fmt_basico(v):
                    """Formato argentino: punto miles, coma decimales."""
                    if v == 0: return '-'
                    txt = f"{v:,.2f}"
                    txt = txt.replace(',', 'X').replace('.', ',').replace('X', '.')
                    return f"${txt}"

                valores_basico = []
                valores_basico_num = []
                for _, row in df_emp.iterrows():
                    cat_nombre = row.get('categoria', '')
                    tipo = row.get('tipo', '')
                    fuera = row.get('fuera_convenio', 0)
                    val = 0.0
                    if fuera and row.get('sueldo_base', 0) > 0:
                        val = float(row['sueldo_base'])
                    elif cat_nombre:
                        cat_val = db.get_valor_categoria(cat_nombre, m, a)
                        if cat_val:
                            if tipo == 'MENSUALIZADO':
                                val = float(cat_val.get('valor_mensual', 0))
                            else:
                                val = float(cat_val.get('valor_hora', 0))
                    valores_basico.append(_fmt_basico(val))
                    valores_basico_num.append(val)
                df_emp['basico_hora'] = valores_basico
                df_emp['basico_hora_num'] = valores_basico_num
                df_emp['liq_basico'] = df_emp.get('liquida_mensual', pd.Series([0]*len(df_emp))).apply(lambda x: 'SI' if x else 'NO')
                df_emp['ant_basico'] = df_emp.get('liquida_antiguedad_basico', pd.Series([0]*len(df_emp))).apply(lambda x: 'SI' if x else 'NO')
                df_emp['liq_present'] = df_emp.get('liquida_presentismo', pd.Series([1]*len(df_emp))).apply(lambda x: 'SI' if x else 'NO')
                df_emp['conv'] = df_emp.get('fuera_convenio', pd.Series([0]*len(df_emp))).apply(lambda x: 'FC' if x else 'BC')

            cols_mostrar = ['id', 'apellido_nombre', 'cuil', 'tipo', 'condicion', 'seccion', 'categoria', 'conv', 'basico_hora',
                            'diferencia_sueldo', 'premio_produccion', 'cifra_fija', 'seguro', 'hs_fijas',
                            'jubilacion', 'obra_social', 'porc_presentismo', 'anticipos', 'otros',
                            'liq_basico', 'ant_basico', 'liq_present', 'fecha_ingreso', 'estado', 'observaciones']
            cols_existentes = [c for c in cols_mostrar if c in df_emp.columns]

            # Botones para elegir condición
            _col_cfg = {
                'id': st.column_config.NumberColumn('ID', width=50),
                'apellido_nombre': st.column_config.TextColumn('Apellido y Nombre', width=170),
                'cuil': st.column_config.TextColumn('CUIL', width=105),
                'tipo': st.column_config.TextColumn('Tipo', width=85),
                'condicion': st.column_config.TextColumn('Condición', width=85),
                'seccion': st.column_config.TextColumn('Sección', width=85),
                'categoria': st.column_config.TextColumn('Categoría', width=120),
                'conv': st.column_config.TextColumn('Conv.', width=40),
                'basico_hora': st.column_config.TextColumn('Básico/Hora', width=90),
                'diferencia_sueldo': st.column_config.NumberColumn('Dif. Sueldo', format="$%.2f", width=90),
                'premio_produccion': st.column_config.NumberColumn('Premio Prod.', format="$%.2f", width=90),
                'cifra_fija': st.column_config.NumberColumn('Cifra Fija', format="$%.2f", width=85),
                'seguro': st.column_config.NumberColumn('Seguro', format="$%.2f", width=80),
                'hs_fijas': st.column_config.NumberColumn('Hs. Fijas', format="%.1f", width=65),
                'jubilacion': st.column_config.NumberColumn('Jubilación', format="$%.2f", width=80),
                'obra_social': st.column_config.NumberColumn('Obra Social', format="$%.2f", width=80),
                'porc_presentismo': st.column_config.NumberColumn('% Present.', format="%.1f%%", width=70),
                'anticipos': st.column_config.NumberColumn('Anticipos', format="$%.2f", width=85),
                'otros': st.column_config.NumberColumn('Otros', format="$%.2f", width=80),
                'liq_basico': st.column_config.TextColumn('Liq.Básico', width=65),
                'ant_basico': st.column_config.TextColumn('Ant.s/Básico', width=70),
                'liq_present': st.column_config.TextColumn('Presentismo', width=70),
                'fecha_ingreso': st.column_config.TextColumn('F. Ingreso', width=80),
                'estado': st.column_config.TextColumn('Estado', width=65),
                'observaciones': st.column_config.TextColumn('Observaciones', width=120),
            }
            df_perm = df_emp[df_emp.get('condicion', 'PERMANENTE') == 'PERMANENTE']
            df_event = df_emp[df_emp.get('condicion', 'PERMANENTE') == 'EVENTUAL']

            if 'vista_personal' not in st.session_state:
                st.session_state.vista_personal = None

            btn_c1, btn_c2 = st.columns(2)
            with btn_c1:
                if st.button(f"🏠 Permanentes ({len(df_perm)})", use_container_width=True, type="primary" if st.session_state.vista_personal == 'perm' else "secondary"):
                    st.session_state.vista_personal = 'perm' if st.session_state.vista_personal != 'perm' else None
                    st.rerun()
            with btn_c2:
                if st.button(f"📋 Eventuales ({len(df_event)})", use_container_width=True, type="primary" if st.session_state.vista_personal == 'event' else "secondary"):
                    st.session_state.vista_personal = 'event' if st.session_state.vista_personal != 'event' else None
                    st.rerun()

            def _descargar_listado(df_vista, label_tipo):
                """Genera botones de descarga PDF y Excel para un listado de empleados."""
                c_dl1, c_dl2 = st.columns(2)
                with c_dl1:
                    try:
                        pdf_data = reports.generar_listado_empleados_pdf(df_vista[cols_existentes])
                        st.download_button(
                            f"📄 Descargar {label_tipo} PDF",
                            data=pdf_data,
                            file_name=f"{label_tipo}_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                            mime="application/pdf",
                            key=f"dl_pdf_{label_tipo}"
                        )
                    except Exception as ex:
                        st.error(f"Error generando PDF: {ex}")
                with c_dl2:
                    buf = io.BytesIO()
                    cols_xl = [c if c != 'basico_hora' else 'basico_hora_num' for c in cols_existentes]
                    cols_xl_ok = [c for c in cols_xl if c in df_vista.columns]
                    df_xl = df_vista[cols_xl_ok].copy()
                    df_xl = df_xl.rename(columns={'basico_hora_num': 'basico_hora'})
                    # Columnas monetarias para formatear en Excel
                    cols_money = ['basico_hora', 'diferencia_sueldo', 'premio_produccion', 'cifra_fija',
                                  'seguro', 'jubilacion', 'obra_social', 'anticipos', 'otros']
                    with pd.ExcelWriter(buf, engine='xlsxwriter') as writer:
                        df_xl.to_excel(writer, index=False, sheet_name=label_tipo)
                        workbook = writer.book
                        worksheet = writer.sheets[label_tipo]
                        # Formato pesos argentino: $1.234,56 (numerico, operable con formulas)
                        money_fmt = workbook.add_format({'num_format': '$#,##0.00', 'align': 'right'})
                        for cm in cols_money:
                            if cm in df_xl.columns:
                                ci = list(df_xl.columns).index(cm)
                                for ri in range(1, len(df_xl) + 1):
                                    val = df_xl.iloc[ri - 1][cm]
                                    try:
                                        worksheet.write_number(ri, ci, round(float(val or 0), 2), money_fmt)
                                    except (ValueError, TypeError):
                                        pass
                    st.download_button(
                        f"📊 Descargar {label_tipo} Excel",
                        data=buf.getvalue(),
                        file_name=f"{label_tipo}_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_xl_{label_tipo}"
                    )

            if st.session_state.vista_personal == 'perm':
                st.markdown(f"**{len(df_perm)} permanentes**")
                if not df_perm.empty:
                    st.dataframe(
                        _fmt_df(df_perm[cols_existentes]),
                        use_container_width=True,
                        hide_index=True,
                        column_config=_col_cfg
                    )
                    _descargar_listado(df_perm, "Permanentes")
                else:
                    st.info("No hay empleados permanentes con estos filtros.")
            elif st.session_state.vista_personal == 'event':
                st.markdown(f"**{len(df_event)} eventuales**")
                if not df_event.empty:
                    st.dataframe(
                        _fmt_df(df_event[cols_existentes]),
                        use_container_width=True,
                        hide_index=True,
                        column_config=_col_cfg
                    )
                    _descargar_listado(df_event, "Eventuales")
                else:
                    st.info("No hay empleados eventuales con estos filtros.")

            # Limpieza de inactivos
            with st.expander("🧹 Limpieza de Base de Datos"):
                st.warning("Esta acción eliminará PERMANENTEMENTE a todos los empleados marcados como 'INACTIVO' y sus liquidaciones históricas.")
                conf_limpieza = st.checkbox("Confirmo que deseo borrar permanentemente a los inactivos", key="conf_limp_db")
                if st.button("🗑️ Limpiar Base de Datos (Borrar Inactivos)", disabled=not conf_limpieza, type="secondary", use_container_width=True):
                    num = db.eliminar_empleados_inactivos()
                    st.session_state.mensaje_exito = f"✅ Se han eliminado {num} empleados inactivos y su historial."
                    st.rerun()
            
            # Aumentos Masivos Fuera de Convenio
            with st.expander("📈 Aumentos Masivos (Fuera de Convenio + Diferencia de Sueldo)"):
                st.info("Esta herramienta aplica un aumento porcentual a:\n"
                        "- **Fuera de Convenio:** Sueldo Básico + Diferencia de Sueldo\n"
                        "- **Bajo Convenio con Dif. Sueldo > 0:** solo Diferencia de Sueldo")

                col_inc1, col_inc2 = st.columns(2)
                with col_inc1:
                    pct_inc = st.number_input("Porcentaje de aumento (%)", min_value=0.0, step=0.5, value=0.0, key="pct_inc_val")
                with col_inc2:
                    sec_inc = st.selectbox("Sector (opcional)", ["Todos"] + db.get_secciones(), key="sec_inc_sel")

                sector_filter = None if sec_inc == "Todos" else sec_inc

                # Previsualización: FC + Bajo Convenio con dif > 0
                emps_fc = db.get_empleados(estado='ACTIVO', fuera_convenio=1, seccion=sector_filter)
                emps_bc_dif = [e for e in db.get_empleados(estado='ACTIVO', fuera_convenio=0, seccion=sector_filter) if float(e.get('diferencia_sueldo', 0) or 0) > 0]

                total_afectados = len(emps_fc) + len(emps_bc_dif)
                if total_afectados > 0:
                    factor = 1 + (pct_inc / 100.0)

                    if emps_fc:
                        st.markdown(f"**Fuera de Convenio:** {len(emps_fc)} empleados (Básico + Dif. Sueldo)")
                        preview_fc = []
                        for ef in emps_fc:
                            preview_fc.append({
                                'Nombre': ef['apellido_nombre'],
                                'Básico Actual': ef['sueldo_base'],
                                'Nvo. Básico': ef['sueldo_base'] * factor,
                                'Dif. Actual': ef['diferencia_sueldo'],
                                'Nva. Dif.': ef['diferencia_sueldo'] * factor
                            })
                        st.dataframe(_fmt_df(pd.DataFrame(preview_fc)), use_container_width=True, hide_index=True)

                    if emps_bc_dif:
                        st.markdown(f"**Bajo Convenio con Dif. Sueldo:** {len(emps_bc_dif)} empleados (solo Dif. Sueldo)")
                        preview_bc = []
                        for eb in emps_bc_dif:
                            preview_bc.append({
                                'Nombre': eb['apellido_nombre'],
                                'Dif. Actual': eb['diferencia_sueldo'],
                                'Nva. Dif.': eb['diferencia_sueldo'] * factor
                            })
                        st.dataframe(_fmt_df(pd.DataFrame(preview_bc)), use_container_width=True, hide_index=True)

                    st.markdown(f"**Total empleados afectados: {total_afectados}**")

                    # Verificar si ya hay un aumento pendiente sin revertir
                    ultimo_aumento = db.get_ultimo_aumento_fc()
                    ya_aplicado = ultimo_aumento and not ultimo_aumento.get('revertido', 0)

                    if ya_aplicado:
                        st.success(f"✅ Ya hay un aumento vigente del **{ultimo_aumento['porcentaje']}%** aplicado el {ultimo_aumento['fecha'][:16]}. "
                                   f"Si querés aplicar otro, primero retrotraé el anterior.")
                    else:
                        st.warning("⚠️ Al presionar el botón se modificarán permanentemente los valores en la base de datos.")
                        confirmar = st.checkbox("Confirmo que deseo aplicar este aumento", key="conf_aumento_masivo")
                        if confirmar:
                            if st.button("🚀 Aplicar Aumento Masivo", type="primary", use_container_width=True):
                                if pct_inc <= 0:
                                    st.error("El porcentaje debe ser mayor a cero.")
                                else:
                                    db.aplicar_aumento_masivo_fc(pct_inc, sector_filter)
                                    st.session_state.mensaje_exito = f"✅ Aumento del {pct_inc}% aplicado exitosamente a {total_afectados} empleados. Los valores ya están actualizados en cada legajo."
                                    st.rerun()
                else:
                    st.info("No hay empleados afectados para el sector seleccionado.")

                # --- Retrotraer último aumento ---
                st.divider()
                ultimo = db.get_ultimo_aumento_fc()
                if ultimo:
                    st.markdown(f"**Último aumento aplicado:** {ultimo['porcentaje']}% — "
                                f"{ultimo['cantidad_empleados']} empleados — "
                                f"{ultimo['fecha'][:16].replace('T',' ')}"
                                f"{' — Sector: ' + ultimo['seccion'] if ultimo['seccion'] else ''}")
                    import json
                    detalle_prev = json.loads(ultimo['detalle'])
                    factor_prev = 1 + (ultimo['porcentaje'] / 100.0)
                    preview_retro = []
                    for ep in detalle_prev:
                        preview_retro.append({
                            'Nombre': ep['nombre'],
                            'Básico Actual': ep['sueldo_base'] * factor_prev,
                            'Básico Original': ep['sueldo_base'],
                            'Dif. Actual': ep['diferencia_sueldo'] * factor_prev,
                            'Dif. Original': ep['diferencia_sueldo']
                        })
                    with st.expander("👁️ Ver detalle de valores a restaurar"):
                        st.dataframe(_fmt_df(pd.DataFrame(preview_retro)), use_container_width=True, hide_index=True)

                    conf_retro = st.checkbox("Confirmo que deseo retrotraer este aumento", key="conf_retro_fc")
                    if st.button("↩️ Retrotraer Último Aumento", type="secondary", use_container_width=True, disabled=not conf_retro):
                        n = db.retrotraer_aumento_fc(ultimo['id'])
                        st.success(f"✅ Se restauraron los valores originales de {n} empleados.")
                        st.rerun()
                else:
                    st.caption("No hay aumentos recientes para retrotraer.")

            # Exportar listado de personal
            st.markdown("#### ⬇️ Exportar Personal")
            c_e1, c_e2 = st.columns(2)
            with c_e1:
                try:
                    pdf_per = reports.generar_listado_empleados_pdf(df_emp[cols_existentes])
                    st.download_button(
                        "📄 Descargar Personal PDF",
                        data=pdf_per,
                        file_name=f"Personal_{datetime.now().strftime('%Y-%m-%d')}.pdf",
                        mime="application/pdf"
                    )
                except Exception as ex:
                    st.error(f"Error generando PDF: {ex}")
            with c_e2:
                buffer = io.BytesIO()
                cols_excel = [c if c != 'basico_hora' else 'basico_hora_num' for c in cols_existentes]
                cols_excel_exist = [c for c in cols_excel if c in df_emp.columns]
                df_excel = df_emp[cols_excel_exist].copy()
                df_excel = df_excel.rename(columns={'basico_hora_num': 'basico_hora'})
                cols_money_all = ['basico_hora', 'diferencia_sueldo', 'premio_produccion', 'cifra_fija',
                                  'seguro', 'jubilacion', 'obra_social', 'anticipos', 'otros']
                with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                    df_excel.to_excel(writer, index=False, sheet_name='Personal')
                    workbook = writer.book
                    worksheet = writer.sheets['Personal']
                    money_fmt = workbook.add_format({'num_format': '$#,##0.00', 'align': 'right'})
                    for cm in cols_money_all:
                        if cm in df_excel.columns:
                            ci = list(df_excel.columns).index(cm)
                            for ri in range(1, len(df_excel) + 1):
                                try:
                                    worksheet.write_number(ri, ci, round(float(df_excel.iloc[ri - 1][cm] or 0), 2), money_fmt)
                                except (ValueError, TypeError):
                                    pass
                st.download_button(
                    "📊 Descargar Personal Excel",
                    data=buffer.getvalue(),
                    file_name=f"Personal_{datetime.now().strftime('%Y-%m-%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
        else:
            st.info("No hay empleados cargados. Importá el archivo Excel desde el panel de arriba.")

    # ── A2: CATEGORÍAS Y CONVENIO ──
    with sub_a2:
        st.markdown("## 📋 Categorías y Convenio")
        st.info(f"📅 Período activo: **{periodo_str}** — Mes de referencia: **{m}/{a}**")

        # ── Panel de carga de nuevo convenio ──
        with st.expander("📥 Cargar Nuevo Convenio (Archivo Excel)", expanded=True):
            st.markdown("""
            Subí el archivo **Excel o PDF** con los valores del nuevo convenio.  
            - Si el archivo contiene **varios meses**, el sistema usará automáticamente el del **mes del período activo**.  
            - Si **no subís archivo**, el período continuará con los valores ya cargados del mes anterior.
            """)

            uploaded_conv = st.file_uploader(
                "Seleccionar archivo Excel o PDF del convenio",
                type=['xlsx', 'xls', 'pdf'],
                key="uploader_convenio"
            )

            if uploaded_conv:
                try:
                    es_pdf = uploaded_conv.name.lower().endswith('.pdf')

                    if es_pdf:
                        # ── Parsear PDF con pdfplumber ──
                        st.info("📄 Archivo PDF detectado. Extrayendo tablas...")
                        pdf_bytes = uploaded_conv.read()
                        # Guardar copia para debug
                        try:
                            with open(os.path.join("data", "ultimo_convenio.pdf"), "wb") as _f:
                                _f.write(pdf_bytes)
                        except:
                            pass
                        df_conv = import_data.extraer_tabla_convenio_pdf(pdf_bytes)
                        if df_conv is None or df_conv.empty:
                            st.error("⚠️ No se pudieron extraer tablas del PDF. Verificá que el archivo contenga tablas con datos de convenio.")
                            df_conv = None
                        else:
                            st.success(f"✅ PDF cargado: **{uploaded_conv.name}** — {len(df_conv)} filas extraídas")
                            # Mostrar solo filas del mes activo como preview
                            if 'Mes' in df_conv.columns:
                                df_preview = df_conv[df_conv['Mes'] == m]
                                if df_preview.empty:
                                    df_preview = df_conv.head(20)
                                st.dataframe(df_preview, use_container_width=True, hide_index=True)
                            else:
                                st.dataframe(df_conv.head(20), use_container_width=True)
                            # Para PDFs: si no hay columna Mes, pedir al usuario el mes a asignar
                            if 'Mes' in df_conv.columns and df_conv['Mes'].notna().any():
                                pass  # Ya tiene mes
                            else:
                                st.warning("⚠️ El PDF no tiene columna de Mes. Se asignará el mes del período activo.")
                                df_conv['Mes'] = m
                                df_conv['Anio'] = a
                            # Normalizar nombres de columna al mismo formato que Excel
                            df_conv = df_conv.rename(columns={
                                'Categoria': 'Categoria', 'ValorHora': 'ValorHora', 'ValorMensual': 'ValorMensual'
                            })
                    else:
                        # ── Parsear Excel ──
                        df_conv = pd.read_excel(uploaded_conv, sheet_name=0)
                        st.success(f"✅ Archivo cargado: **{uploaded_conv.name}** — {len(df_conv)} filas")
                        st.dataframe(df_conv.head(10), use_container_width=True)

                    # Detectar columna de mes y año
                    col_mes = next((c for c in df_conv.columns if 'mes' in str(c).lower() or 'month' in str(c).lower()), None)
                    col_anio = next((c for c in df_conv.columns if 'año' in str(c).lower() or 'anio' in str(c).lower() or 'year' in str(c).lower()), None)
                    col_cat = next((c for c in df_conv.columns if 'categ' in str(c).lower() or 'nombre' in str(c).lower() or 'descripcion' in str(c).lower()), None)
                    col_vh = next((c for c in df_conv.columns if 'hora' in str(c).lower()), None)
                    col_vm = next((c for c in df_conv.columns if 'mensual' in str(c).lower() or 'sueldo' in str(c).lower()), None)

                    if col_mes and col_cat and (col_vh or col_vm):
                        meses_en_archivo = sorted(df_conv[col_mes].dropna().unique().tolist())
                        st.info(f"📆 Meses detectados en el archivo: **{meses_en_archivo}**")

                        # Filtrar por mes del período activo
                        if col_anio:
                            df_mes_activo = df_conv[(df_conv[col_mes] == m) & (df_conv[col_anio] == a)]
                        else:
                            df_mes_activo = df_conv[df_conv[col_mes] == m]

                        if df_mes_activo.empty:
                            st.warning(f"⚠️ El archivo no contiene datos para el mes **{m}/{a}**. Verificá el archivo.")
                        else:
                            st.success(f"✅ Se usarán los valores del mes **{m}/{a}** ({len(df_mes_activo)} categorías)")

                            # Calcular variación respecto al mes anterior
                            mes_ant = m - 1 if m > 1 else 12
                            anio_ant = a if m > 1 else a - 1
                            if col_anio:
                                df_mes_ant = df_conv[(df_conv[col_mes] == mes_ant) & (df_conv[col_anio] == anio_ant)]
                            else:
                                df_mes_ant = df_conv[df_conv[col_mes] == mes_ant]

                            pct_variacion = None
                            if not df_mes_ant.empty and (col_vh or col_vm):
                                col_val = col_vm if col_vm else col_vh
                                val_nuevo = pd.to_numeric(df_mes_activo[col_val], errors='coerce').mean()
                                val_ant = pd.to_numeric(df_mes_ant[col_val], errors='coerce').mean()
                                if val_ant and val_ant > 0:
                                    pct_variacion = round((val_nuevo / val_ant - 1) * 100, 2)

                            if pct_variacion is not None:
                                st.metric("📈 Variación detectada (mes a mes)", f"+{pct_variacion}%")
                            else:
                                # Calcular desde DB si no hay mes anterior en el archivo
                                vals_db_ant = []
                                for cat in db.get_categorias():
                                    v = db.get_valor_categoria(cat['nombre'], mes_ant, anio_ant)
                                    if v:
                                        n_ant = v.get('valor_mensual', 0) or v.get('valor_hora', 0)
                                        if n_ant > 0:
                                            vals_db_ant.append(n_ant)
                                if vals_db_ant:
                                    st.info(f"📊 No hay mes anterior en el archivo. Se calculará variación contra DB del período {mes_ant}/{anio_ant}.")

                            st.markdown("---")
                            st.warning("⚠️ Al confirmar, se actualizarán los valores de convenio para el mes activo.")
                            
                            conf_conv = st.checkbox("✅ Confirmo que deseo cargar estos valores de convenio", key="conf_cargar_conv")
                            
                            if conf_conv:
                                if st.button("💾 Cargar Convenio", type="primary", use_container_width=True, key="btn_cargar_conv"):
                                    # Guardar valores a DB
                                    filas_guardadas = 0
                                    for _, fila in df_mes_activo.iterrows():
                                        nombre_cat = str(fila[col_cat]).strip()
                                        nombre_conv = import_data.mapear_categoria_excel_a_convenio(nombre_cat) or nombre_cat
                                        cat_obj = db.get_categoria_por_nombre(nombre_conv)
                                        if not cat_obj:
                                            # Crear categoría si no existe
                                            cat_id = db.crear_categoria(nombre_conv, 'PRODUCCION')
                                        else:
                                            cat_id = cat_obj['id']
                                        vh = float(fila[col_vh]) if col_vh and pd.notna(fila.get(col_vh)) else 0.0
                                        vm = float(fila[col_vm]) if col_vm and pd.notna(fila.get(col_vm)) else 0.0
                                        db.crear_valor_categoria(cat_id, vh, vm, m, a)
                                        filas_guardadas += 1
                                    
                                    st.success(f"✅ Se cargaron {filas_guardadas} categorías para {m}/{a}")

                                    # Calcular variación real para preguntar aumento
                                    porc_real, _ = import_data.aplicar_aumento_fuera_convenio.__wrapped__(m, a) if hasattr(import_data.aplicar_aumento_fuera_convenio, '__wrapped__') else (pct_variacion, 0)
                                    porc_real = pct_variacion  # usar el calculado del archivo

                                    if porc_real and porc_real > 0:
                                        st.session_state['pct_aumento_pendiente'] = porc_real
                                        st.session_state['pct_aumento_mes'] = m
                                        st.session_state['pct_aumento_anio'] = a
                                    
                                    st.rerun()
                    else:
                        st.warning("⚠️ No se pudieron detectar las columnas del archivo. Asegurate de que tenga columnas tipo: Mes, Categoría, Valor Hora / Valor Mensual.")

                except Exception as ex:
                    st.error(f"Error leyendo el archivo: {ex}")

            else:
                st.info("💡 Si no subís archivo, el período usará los valores de convenio ya cargados (del período anterior).")

        # ── Pregunta de aumento a Fuera de Convenio + Dif. Sueldo ──
        if 'pct_aumento_pendiente' in st.session_state:
            pct = st.session_state['pct_aumento_pendiente']
            emps_fc = db.get_empleados(estado='ACTIVO', fuera_convenio=1)
            emps_bc_dif = [e for e in db.get_empleados(estado='ACTIVO', fuera_convenio=0) if float(e.get('diferencia_sueldo', 0) or 0) > 0]
            n_fc = len(emps_fc)
            n_bc = len(emps_bc_dif)
            n_total = n_fc + n_bc

            st.markdown("---")
            st.markdown(f"### 📈 Aplicar aumento del convenio (+{pct:.2f}%)")
            st.info(f"El nuevo convenio implica un aumento del **+{pct:.2f}%**.\n"
                    f"- **{n_fc}** empleados Fuera de Convenio (Básico + Dif. Sueldo)\n"
                    f"- **{n_bc}** empleados Bajo Convenio con Dif. Sueldo (solo Dif. Sueldo)")

            col_si, col_no = st.columns(2)
            with col_si:
                if st.button(f"✅ SÍ — Aplicar +{pct:.2f}% a {n_total} empleados", type="primary", use_container_width=True, key="btn_si_aumento_fc"):
                    db.aplicar_aumento_masivo_fc(pct, None)
                    del st.session_state['pct_aumento_pendiente']
                    st.session_state.mensaje_exito = f"✅ Aumento del {pct:.2f}% aplicado a {n_total} empleados ({n_fc} FC + {n_bc} Bajo Convenio con Dif.)."
                    st.rerun()
            with col_no:
                if st.button("❌ NO — No aplicar aumento", use_container_width=True, key="btn_no_aumento_fc"):
                    del st.session_state['pct_aumento_pendiente']
                    st.rerun()

        # ── Tabla de categorías ──
        st.markdown("---")
        st.markdown("### 📋 Tabla de Categorías Actuales")
        categorias = db.get_categorias()
        if categorias:
            for cat in categorias:
                valores = db.get_valores_categoria(cat['id'])
                with st.expander(f"📋 {cat['nombre']} ({cat['grupo']}) — {cat['estado']}", expanded=False):
                    emps_asignados = db.empleados_con_categoria(cat['nombre'])
                    if emps_asignados > 0:
                        st.info(f"👥 {emps_asignados} empleados asignados a esta categoría")

                    if valores:
                        df_val = pd.DataFrame(valores)
                        df_val = df_val[['vigencia_mes', 'vigencia_anio', 'valor_hora', 'valor_mensual']]
                        df_val.columns = ['Mes', 'Año', 'Valor Hora', 'Valor Mensual']
                        st.dataframe(df_val, use_container_width=True, hide_index=True)

                    # Agregar nuevo valor manualmente
                    with st.form(f"form_val_{cat['id']}"):
                        st.markdown("**Agregar valor manualmente**")
                        c1, c2, c3, c4 = st.columns(4)
                        with c1:
                            nuevo_mes = st.number_input("Mes", 1, 12, value=m, key=f"cat_nvm_{cat['id']}")
                        with c2:
                            nuevo_anio = st.number_input("Año", 2020, 2050, value=a, key=f"cat_nva_{cat['id']}")
                        with c3:
                            nuevo_vh = st.number_input("Valor Hora", value=0.0, key=f"cat_nvh_{cat['id']}")
                        with c4:
                            nuevo_vm = st.number_input("Valor Mensual", value=0.0, key=f"cat_nvm2_{cat['id']}")

                        if st.form_submit_button("➕ Agregar valor"):
                            db.crear_valor_categoria(cat['id'], nuevo_vh, nuevo_vm, nuevo_mes, nuevo_anio)
                            st.success("Valor agregado")
                            st.rerun()

                    col_a, col_b = st.columns(2)
                    with col_a:
                        if cat['estado'] == 'ACTIVA':
                            if st.button(f"🚫 Dar de baja", key=f"cat_baja_{cat['id']}"):
                                db.actualizar_categoria(cat['id'], {'estado': 'INACTIVA'})
                                st.rerun()
                        else:
                            if st.button(f"✅ Reactivar", key=f"cat_act_{cat['id']}"):
                                db.actualizar_categoria(cat['id'], {'estado': 'ACTIVA'})
                                st.rerun()

            # Crear nueva categoría
            st.markdown("---")
            st.markdown("### ➕ Crear categoría nueva")
            with st.form("form_nueva_cat"):
                c1, c2 = st.columns(2)
                with c1:
                    nuevo_nombre = st.text_input("Nombre de la categoría", key="new_cat_nom")
                with c2:
                    nuevo_grupo = st.selectbox("Grupo", ["PRODUCCION", "MANTENIMIENTO", "ADMINISTRATIVAS", "OTRA"], key="new_cat_grupo")
                if st.form_submit_button("Crear categoría"):
                    if nuevo_nombre:
                        db.crear_categoria(nuevo_nombre, nuevo_grupo)
                        st.success(f"Categoría '{nuevo_nombre}' creada")
                        st.rerun()

        else:
            st.info("No hay categorías cargadas. Subí un archivo de convenio para cargarlas.")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB B — LIQUIDACIÓN
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_liq:
    st.markdown(f"## 📋 Liquidación — Período {periodo_str}")

    q = st.session_state.periodo_quincena
    m = st.session_state.periodo_mes
    a = st.session_state.periodo_anio

    # Verificar/crear período
    periodo = db.get_periodo(q, m, a)
    if not periodo:
        if st.button("📌 Crear período", key="btn_crear_periodo"):
            pid = db.crear_periodo(q, m, a)
            st.success(f"Período {periodo_str} creado")
            st.rerun()
        st.stop()

    periodo_id = periodo['id']
    es_cerrado = periodo['estado'] == 'CERRADO'

    # CARGAR NOVEDADES PERSISTIDAS si no están en la sesión
    if 'novedades_importadas' not in st.session_state or st.session_state.get('prev_periodo_id') != periodo_id:
        st.session_state.novedades_importadas = db.get_novedades_importadas(periodo_id)
        st.session_state.prev_periodo_id = periodo_id

    if es_cerrado:
        st.error("🔒 Este período está CERRADO. No se pueden hacer modificaciones.")

    # Obtener empleados activos
    empleados_activos = db.get_empleados(estado='ACTIVO')
    if not empleados_activos:
        st.info("No hay empleados activos. Importá el personal desde el Módulo A.")
        st.stop()

    # Selector de empleado
    if 'liq_emp_key_cnt' not in st.session_state:
        st.session_state.liq_emp_key_cnt = 0

    if 'msg_liq' in st.session_state:
        st.success(st.session_state.msg_liq)
        del st.session_state.msg_liq
    if 'msg_liq_warn' in st.session_state:
        st.warning(st.session_state.msg_liq_warn)
        del st.session_state.msg_liq_warn

    opciones_nombres = ["--- Seleccione un empleado ---"] + [f"{e['apellido_nombre']} ({e['seccion']})" for e in empleados_activos]
    opciones_emp = {f"{e['apellido_nombre']} ({e['seccion']})": e for e in empleados_activos}
    
    # 📥 Herramientas de Liquidación Masiva
    if not es_cerrado:
        with st.expander("🛠️ Herramientas de Liquidación Masiva", expanded=False):
            t1, t2, t3 = st.tabs(["📂 Importar Novedades", "🚀 Ejecución Masiva", "🗑️ Limpieza/Borrado"])
            
            with t1:
                c_i1, c_i2 = st.columns(2)
                with c_i1:
                    st.markdown("##### 1. Descargar Plantilla")
                    df_template = pd.DataFrame(columns=[
                        'CUIL', 'DIAS VACACIONES', 'HS EXTRAS 50%', 'HS EXTRAS 100%', 
                        'TRABAJOS VARIOS', 'VIATICOS', 'HS REMPLAZO ENCARGADO', 
                        'OTRO CONCEPTO NOMBRE', 'OTRO CONCEPTO IMPORTE'
                    ])
                    if empleados_activos:
                        # Usar el primer empleado como ejemplo
                        e = empleados_activos[0]
                        df_template.loc[0] = [e['cuil'], 0, 0, 0, 0, 0, 0, '', 0]

                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_template.to_excel(writer, index=False, sheet_name='Novedades')
                    
                    st.download_button(
                        "📄 Descargar Plantilla Excel",
                        data=buffer.getvalue(),
                        file_name="Plantilla_Novedades_Liquidacion.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key="btn_template_nov"
                    )
                
                with c_i2:
                   with st.expander("📥 Importar Novedades desde Excel"):
                    st.info("Podés subir varios archivos. Los nombres se compararán con la base de datos automáticamente (insensible a acentos/formato).")
                    
                    # Generar una clave para el uploader basada en un contador en session_state para poder resetearlo
                    if 'uploader_key' not in st.session_state:
                        st.session_state.uploader_key = 0
                        
                    col_up, col_reset = st.columns([3, 1])
                    with col_up:
                        uploaded_files = st.file_uploader(
                            "Subir Excel(s) de Novedades", 
                            type=['xlsx', 'xls'], 
                            accept_multiple_files=True, 
                            key=f"uploader_novs_{st.session_state.uploader_key}"
                        )
                    with col_reset:
                        st.write(" ")
                        st.write(" ")
                        if st.button("🧹 Restablecer", use_container_width=True, help="Limpia los archivos y novedades cargadas"):
                            db.eliminar_novedades_importadas(periodo_id)
                            st.session_state.novedades_importadas = {}
                            st.session_state.uploader_key += 1
                            st.rerun()

                    if uploaded_files:
                        res_total = {}
                        diag_total = {'macheos': [], 'no_encontrados': [], 'columnas_detectadas': {}}
                        errores = []
                        for ufile in uploaded_files:
                            res_full = import_data.procesar_excel_novedades(ufile)
                            if "error" in res_full:
                                errores.append(f"Archivo '{ufile.name}': {res_full['error']}")
                            else:
                                novs_file = res_full.get('novedades', {})
                                for eid, v_dict in novs_file.items():
                                    if eid not in res_total:
                                        res_total[eid] = v_dict
                                    else:
                                        # Mezclar datos sumando numéricos
                                        for k, v in v_dict.items():
                                            if isinstance(v, (int, float)):
                                                if k == 'concepto_libre_1_importe':
                                                    res_total[eid][k] += v
                                                elif k != 'concepto_libre_1_nombre':
                                                    res_total[eid][k] += v
                                            elif k == 'concepto_libre_1_nombre' and v:
                                                 if not res_total[eid][k]:
                                                     res_total[eid][k] = v
                                                 elif v not in res_total[eid][k]:
                                                     res_total[eid][k] += f" / {v}"

                                d = res_full.get('diagnostico', {})
                                diag_total['macheos'].extend(d.get('macheos_exitosos', []))
                                diag_total['no_encontrados'].extend(d.get('no_encontrados', []))
                                # Acumular columnas detectadas
                                cols_det = d.get('columnas_detectadas', {})
                                if cols_det:
                                    diag_total['columnas_detectadas'].update(cols_det)
                                cols_xl = d.get('columnas_excel', [])
                                if cols_xl:
                                    diag_total['columnas_excel'] = cols_xl
                        
                        if errores:
                            for err in errores:
                                st.error(err)
                                
                        if res_total:
                            # PERSISTENCIA: Guardar en DB para el periodo actual
                            for eid, v_dict in res_total.items():
                                v_dict['periodo_id'] = periodo_id
                                v_dict['empleado_id'] = eid
                                db.guardar_novedad_importada(v_dict)

                            st.session_state.novedades_importadas = db.get_novedades_importadas(periodo_id)
                            st.success(f"✅ Se procesaron y guardaron novedades para {len(res_total)} empleados en la base de datos.")

                            # Mostrar columnas detectadas del Excel
                            cols_det = diag_total.get('columnas_detectadas', {})
                            nombres_concepto = {
                                'horas_extra_50': 'Hs Extra 50%',
                                'horas_extra_100': 'Hs Extra 100%',
                                'dias_vacaciones': 'Días Vacaciones',
                                'trabajos_varios': 'Trabajos Varios',
                                'viaticos': 'Viáticos',
                                'remplazo_encargado': 'Remplazo Encargado',
                                'concepto_libre_1_nombre': 'Concepto Libre Nombre',
                                'concepto_libre_1_importe': 'Concepto Libre Importe',
                            }
                            with st.expander("📋 Columnas detectadas en el Excel", expanded=True):
                                if cols_det:
                                    for campo, col_excel in cols_det.items():
                                        label = nombres_concepto.get(campo, campo)
                                        st.write(f"✅ **{label}** ← columna: `{col_excel}`")
                                no_detectadas = [nombres_concepto.get(k, k) for k in nombres_concepto if k not in cols_det]
                                if no_detectadas:
                                    for nd in no_detectadas:
                                        st.write(f"⬜ **{nd}** — no detectada")
                                # Mostrar todas las columnas del Excel para referencia
                                cols_excel = diag_total.get('columnas_excel', [])
                                if cols_excel:
                                    st.caption(f"Columnas en el Excel: {', '.join(cols_excel)}")

                            with st.expander("🔍 Ver Detalle de Procesamiento"):
                                if diag_total['macheos']:
                                    st.write("**Filas Procesadas con Éxito:**")
                                    # No usamos set() para que el usuario vea si una persona se sumó varias veces
                                    for match_str in sorted(diag_total['macheos']):
                                        st.write(f"- {match_str}")
                                if diag_total['no_encontrados']:
                                    st.write("**Filas Omitidas / No encontradas:**")
                                    for skip_str in sorted(diag_total['no_encontrados']):
                                        st.warning(f"- {skip_str}")
                                        
                            st.info("💡 Ahora podés ejecutar la liquidación masiva para aplicar estos datos.")

            with t2:
                st.markdown("##### 🚀 Ejecutar Liquidación en Lote")
                alcance = st.radio("Alcance de la liquidación", ["Toda la Nómina", "Por Sector"], horizontal=True)
                sector_sel = None
                if alcance == "Por Sector":
                    sector_sel = st.selectbox("Seleccionar Sector", db.get_secciones(), key="alcance_sector")
                
                st.info("""
                Esta acción procesará a todos los empleados del alcance seleccionado aplicando:
                1. Novedades importadas de Excel (si existen).
                2. Datos fijos (premios, seguros, etc.) de la ficha del empleado.
                3. Valores por defecto (ej: 30 días para mensualizados/gerentes).
                """)
                
                if st.button("🔥 Iniciar Liquidación Masiva", use_container_width=True):
                    # Filtrar empleados por alcance
                    if alcance == "Toda la Nómina":
                        emps_a_liquidar = empleados_activos
                    else:
                        emps_a_liquidar = [e for e in empleados_activos if e['seccion'] == sector_sel]
                    
                    num_liq = 0
                    bar_progress = st.progress(0)
                    for i, e_liq in enumerate(emps_a_liquidar):
                        eid = e_liq['id']
                        # 1. Obtener novedades (Excel > Defaults)
                        nov_imp = st.session_state.get('novedades_importadas', {}).get(eid, {})
                        
                        # Determinar días trabajados default
                        # Determinar días trabajados default (priorizar configuración del legajo)
                        def_dias = float(e_liq.get('dias_liquidacion_mensual', 30.0) or 30.0)
                        
                        novedades = {
                            'horas_comunes': float(nov_imp.get('horas_comunes', e_liq.get('hs_fijas', 0)) or e_liq.get('hs_fijas', 0)),
                            'horas_extra_50': float(nov_imp.get('horas_extra_50', 0)),
                            'horas_extra_100': float(nov_imp.get('horas_extra_100', 0)),
                            'dias_trabajados': float(nov_imp.get('dias_trabajados', def_dias)),
                            'dias_vacaciones': float(nov_imp.get('dias_vacaciones', 0)),
                            'trabajos_varios': float(nov_imp.get('trabajos_varios', 0)),
                            'viaticos': float(nov_imp.get('viaticos', 0)),
                            'remplazo_encargado': float(nov_imp.get('remplazo_encargado', 0)),
                            'prop_aguinaldo': 0.0,
                            'concepto_libre_1_nombre': nov_imp.get('concepto_libre_1_nombre', ''),
                            'concepto_libre_1_importe': float(nov_imp.get('concepto_libre_1_importe', 0)),
                            'concepto_libre_2_nombre': '',
                            'concepto_libre_2_importe': 0.0,
                        }

                        # Calcular
                        res_liq = calculator.calcular_liquidacion(e_liq, m, a, novedades)
                        
                        # Guardar en DB solo si el neto es mayor a cero
                        res_liq['periodo_id'] = periodo_id
                        res_liq['empleado_id'] = eid
                        
                        if res_liq['total_neto'] > 0:
                            db.guardar_liquidacion(res_liq)
                            num_liq += 1
                        
                        bar_progress.progress((i + 1) / len(emps_a_liquidar))
                    
                    st.session_state.msg_liq = f"✅ Se han procesado y guardado {num_liq} liquidaciones exitosamente."
                    st.rerun()

            with t3:
                st.markdown("##### 🗑️ Borrado Masivo")
                st.warning("Cuidado: Esta acción eliminará las liquidaciones guardadas del período actual para el alcance seleccionado.")
                alcance_del = st.radio("Alcance del borrado", ["Toda la Nómina", "Por Sector"], key="alcance_del", horizontal=True)
                sector_del = None
                if alcance_del == "Por Sector":
                    sector_del = st.selectbox("Sector a borrar", db.get_secciones(), key="del_sector")
                
                conf_del = st.checkbox("Confirmo que deseo borrar las liquidaciones seleccionadas", key="conf_del_masivo")
                if st.button("🗑️ Eliminar Liquidaciones en Lote", type="secondary", disabled=not conf_del, use_container_width=True):
                    if alcance_del == "Toda la Nómina":
                        emps_ids = [e['id'] for e in empleados_activos]
                    else:
                        emps_ids = [e['id'] for e in empleados_activos if e['seccion'] == sector_del]
                    
                    db.eliminar_liquidaciones_multiples(periodo_id, emps_ids)
                    st.session_state.msg_liq = f"✅ Se han eliminado las liquidaciones para {len(emps_ids)} empleados correctamente."
                    st.rerun()
    
    # Boton de impresion masiva (fuera del expander de herramientas si ya hay liquidaciones)
    liq_del_periodo = db.get_liquidaciones_periodo(periodo_id)
    if liq_del_periodo:
        st.markdown("---")
        st.markdown("### 🖨️ Acciones por Lote")
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            try:
                emp_dict_print = {e['id']: e for e in db.get_empleados()}
                pdf_lote = reports.generar_recibos_pdf(liq_del_periodo, emp_dict_print, periodo)
                st.download_button(
                    "📄 Descargar PDF con TODOS los recibos",
                    data=pdf_lote,
                    file_name=f"Recibos_{periodo_str.replace('/', '-')}_Completo.pdf",
                    mime="application/pdf"
                )
            except Exception as e:
                st.error(f"Error generando PDF masivo: {e}")
        with col_p2:
            st.info(f"💡 Hay {len(liq_del_periodo)} liquidaciones guardadas en este período.")

    col_sel_liq, col_limp_liq = st.columns([5, 1])
    with col_sel_liq:
        sel_emp = st.selectbox("Seleccionar empleado", opciones_nombres, key=f"sel_emp_liq_{st.session_state.liq_emp_key_cnt}")
    with col_limp_liq:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🗑️", key="btn_limpiar_sel_liq", help="Limpiar selección"):
            st.session_state.liq_emp_key_cnt += 1
            st.rerun()

    if sel_emp and sel_emp != "--- Seleccione un empleado ---":
        emp = opciones_emp[sel_emp]
        emp_id = emp['id']

        # Al seleccionar, limpiar previsualizaciones previas de la sesión para asegurar datos frescos
        if f'last_sel_id' not in st.session_state or st.session_state.last_sel_id != emp_id:
            if f'preview_{emp_id}' in st.session_state: del st.session_state[f'preview_{emp_id}']
            if f'novedades_{emp_id}' in st.session_state: del st.session_state[f'novedades_{emp_id}']
            st.session_state.last_sel_id = emp_id

        # Mostrar info del empleado
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Tipo", emp['tipo'])
        with col2:
            st.metric("Categoría", emp.get('categoria', 'N/A'))
        with col3:
            # Calcular antigüedad: 1%/año + bonus 2% fijo si >= 10 años
            anios = calculator.calcular_antiguedad_anios(emp.get('fecha_ingreso'), date(a, m, 1))
            pct_ant = anios + (2 if anios >= 10 else 0)
            st.metric("Antigüedad", f"{anios} años ({pct_ant}%)")
        with col4:
            if emp.get('fuera_convenio') == 1:
                sb = float(emp.get('sueldo_base', 0))
                if emp['tipo'] == 'MENSUALIZADO':
                    vh_deriv = sb / 187.0
                    st.metric("Sueldo Mensual (Manual)", f"${_fmt_ar(sb)}")
                    st.caption(f"V.Hora: ${_fmt_ar(vh_deriv)} (basico/187)")
                else:
                    st.metric("Valor hora (Manual)", f"${_fmt_ar(sb)}")
            else:
                val = db.get_valor_categoria(emp.get('categoria', ''), m, a)
                vh = val['valor_hora'] if val else 0
                vm = val['valor_mensual'] if val else 0
                if vh > 0:
                    st.metric("Valor hora", f"${_fmt_ar(vh)}")
                elif vm > 0:
                    # Mensualizados: mostrar valor hora derivado = basico/187
                    vh_deriv = vm / 187.0
                    st.metric("Valor mensual", f"${_fmt_ar(vm)}")
                    st.caption(f"V.Hora: ${_fmt_ar(vh_deriv)} (basico/187)")
                
                if not emp.get('liquida_mensual', 0):
                    st.warning("⚠️ Opción '¿Liquida mensual?' desactivada. El Básico será $0,00.")

        # Cargar liquidacion existente o nueva
        liq_row = db.get_liquidacion(periodo_id, emp_id)
        liq_existente = dict(liq_row) if liq_row else None
        nov_imp = st.session_state.get('novedades_importadas', {}).get(emp_id, {})

        st.markdown("---")
        st.markdown("### Novedades de la quincena")

        # Determinar días trabajados default (priorizar configuración del legajo)
        def_dias = float(emp.get('dias_liquidacion_mensual', 30.0) or 30.0)
        pct_pres_emp = float(emp.get('porc_presentismo', 15.0))

        # Usar keys unicos basados en emp_id para que no se mezclen entre empleados
        col1, col2, col3 = st.columns(3)
        with col1:
            if emp['tipo'] == 'MENSUALIZADO':
                val_dt = float(liq_existente.get('dias_trabajados', def_dias) if liq_existente else nov_imp.get('dias_trabajados', def_dias))
                dias_trabajados = st.number_input(
                    "Dias trabajados",
                    value=val_dt,
                    min_value=0.0, max_value=30.0, step=1.0, disabled=es_cerrado,
                    key=f"liq_dt_{emp_id}_{periodo_id}"
                )
                horas_comunes = 0.0  # mensualizados no usan horas comunes
            else:
                val_hc = float(liq_existente.get('horas_comunes', 0) if liq_existente else (nov_imp.get('horas_comunes', emp.get('hs_fijas', 0)) or emp.get('hs_fijas', 0)))
                horas_comunes = st.number_input(
                    "Horas trabajadas",
                    value=val_hc,
                    min_value=0.0, step=0.5, disabled=es_cerrado,
                    key=f"liq_hc_{emp_id}_{periodo_id}"
                )
                dias_trabajados = 0.0
        with col2:
            val_he50 = float(liq_existente.get('horas_extra_50', 0) if liq_existente else nov_imp.get('horas_extra_50', 0))
            horas_extra_50 = st.number_input(
                "Horas extra 50%",
                value=val_he50,
                min_value=0.0, step=0.5, disabled=es_cerrado,
                key=f"liq_he50_{emp_id}_{periodo_id}"
            )
            val_dv = float(liq_existente.get('dias_vacaciones', 0) if liq_existente else nov_imp.get('dias_vacaciones', 0))
            dias_vacaciones = st.number_input(
                "Dias Vacaciones",
                value=val_dv,
                min_value=0.0, step=1.0, disabled=es_cerrado,
                key=f"liq_dv_{emp_id}_{periodo_id}"
            )
        with col3:
            val_he100 = float(liq_existente.get('horas_extra_100', 0) if liq_existente else nov_imp.get('horas_extra_100', 0))
            horas_extra_100 = st.number_input(
                "Horas extra 100%",
                value=val_he100,
                min_value=0.0, step=0.5, disabled=es_cerrado,
                key=f"liq_he100_{emp_id}_{periodo_id}"
            )

        col4, col5 = st.columns(2)
        with col4:
            val_tv = float(liq_existente.get('importe_trabajos_varios', 0) if liq_existente else nov_imp.get('trabajos_varios', 0))
            trabajos_varios = st.number_input(
                "Trabajos varios",
                value=val_tv,
                step=1.0, disabled=es_cerrado,
                key=f"liq_tv_{emp_id}_{periodo_id}"
            )
            val_vi = float(liq_existente.get('importe_viaticos', 0) if liq_existente else nov_imp.get('viaticos', 0))
            viaticos = st.number_input(
                "Viaticos",
                value=val_vi,
                step=1.0, disabled=es_cerrado,
                key=f"liq_vi_{emp_id}_{periodo_id}"
            )
            val_re = float(liq_existente.get('remplazo_encargado', 0) if liq_existente else nov_imp.get('remplazo_encargado', 0))
            remplazo_encargado = st.number_input(
                "HS Remplazo Encargado",
                value=val_re,
                step=1.0, disabled=es_cerrado,
                key=f"liq_re_{emp_id}_{periodo_id}"
            )
            prop_aguinaldo = st.number_input(
                "Prop. Aguinaldo",
                value=float(liq_existente.get('importe_prop_aguinaldo', 0) if liq_existente else 0),
                step=1.0, disabled=es_cerrado,
                key=f"liq_pa_{emp_id}_{periodo_id}"
            )
            # Presentismo se calcula automáticamente al 15% en calculator.py
            if emp.get('liquida_presentismo', 0):
                st.info(f"✅ Presentismo ({pct_pres_emp}%) se calculará automáticamente")
            else:
                st.warning("⚠️ Este empleado NO liquida presentismo")

        with col5:
            val_cl1n = liq_existente.get('concepto_libre_1_nombre', '') if liq_existente else nov_imp.get('concepto_libre_1_nombre', '')
            cl1_nombre = st.text_input(
                "Concepto Libre 1 - Nombre",
                value=val_cl1n,
                disabled=es_cerrado,
                key=f"liq_cl1n_{emp_id}_{periodo_id}"
            )
            val_cl1i = float(liq_existente.get('concepto_libre_1_importe', 0) if liq_existente else nov_imp.get('concepto_libre_1_importe', 0))
            cl1_importe = st.number_input(
                "Concepto Libre 1 - Importe (+/-)",
                value=val_cl1i,
                step=100.0, disabled=es_cerrado,
                key=f"liq_cl1i_{emp_id}_{periodo_id}"
            )
            cl2_nombre = st.text_input(
                "Concepto Libre 2 - Nombre",
                value=liq_existente.get('concepto_libre_2_nombre', '') if liq_existente else '',
                disabled=es_cerrado,
                key=f"liq_cl2n_{emp_id}_{periodo_id}"
            )
            cl2_importe = st.number_input(
                "Concepto Libre 2 - Importe (+/-)",
                value=float(liq_existente.get('concepto_libre_2_importe', 0) if liq_existente else 0),
                step=100.0, disabled=es_cerrado,
                key=f"liq_cl2i_{emp_id}_{periodo_id}"
            )

        if not es_cerrado:
            if st.button("🧮 Calcular y previsualizar", key=f"calc_{emp_id}_{periodo_id}"):
                novedades = {
                    'horas_comunes': horas_comunes,
                    'horas_extra_50': horas_extra_50,
                    'horas_extra_100': horas_extra_100,
                    'dias_trabajados': dias_trabajados,
                    'dias_vacaciones': dias_vacaciones,
                    'trabajos_varios': trabajos_varios,
                    'viaticos': viaticos,
                    'remplazo_encargado': remplazo_encargado,
                    'prop_aguinaldo': prop_aguinaldo,
                    'concepto_libre_1_nombre': cl1_nombre,
                    'concepto_libre_1_importe': cl1_importe,
                    'concepto_libre_2_nombre': cl2_nombre,
                    'concepto_libre_2_importe': cl2_importe,
                }

                resultado = calculator.calcular_liquidacion(emp, m, a, novedades)
                st.session_state[f'preview_{emp_id}'] = resultado
                st.session_state[f'novedades_{emp_id}'] = novedades

        # Mostrar preview
        preview_key = f'preview_{emp_id}'
        if preview_key in st.session_state:
            resultado = st.session_state[preview_key]

            st.markdown("### 📄 Preview del Recibo")
            st.info(f"Tipo de liquidacion: **{resultado['tipo_liquidacion']}**")

            # Tabla de conceptos
            conceptos = []

            if resultado['importe_basico_mensual'] > 0:
                conceptos.append(('DS.MENSUALES', f"{resultado['dias_trabajados']} días", resultado['importe_basico_mensual'], 'haber'))
            if resultado['horas_comunes'] > 0:
                conceptos.append(('HS.COMUN', f"{resultado['horas_comunes']:.1f} hs", resultado['importe_horas_comunes'], 'haber'))
            if resultado['horas_extra_50'] > 0:
                conceptos.append(('HS.EXT.50%', f"{resultado['horas_extra_50']:.1f} hs", resultado['importe_extra_50'], 'haber'))
            if resultado['horas_extra_100'] > 0:
                conceptos.append(('HS.EXT.100%', f"{resultado['horas_extra_100']:.1f} hs", resultado['importe_extra_100'], 'haber'))
            if resultado['importe_antiguedad_total'] > 0:
                pct = resultado['porcentaje_antiguedad']
                det = f"Hs.Com: ${_fmt_ar(resultado['importe_antiguedad_horas'])} + Hs.Ext: ${_fmt_ar(resultado['importe_antiguedad_extras'])}"
                if resultado['importe_antiguedad_basico'] > 0:
                    det += f" + Basico: ${_fmt_ar(resultado['importe_antiguedad_basico'])}"
                conceptos.append((f'%ANTIGUEDAD ({pct}%)', det, resultado['importe_antiguedad_total'], 'haber'))
            if resultado['importe_presentismo'] > 0:
                conceptos.append((f"PRESENTISMO ({resultado.get('porcentaje_presentismo', 15)}%)", '', resultado['importe_presentismo'], 'haber'))
            if resultado['importe_prop_aguinaldo'] > 0:
                conceptos.append(('PROP.AGUINALDO', '', resultado['importe_prop_aguinaldo'], 'haber'))
            if resultado['importe_diferencia_sueldo'] > 0:
                conceptos.append(('DIF.SUELDO', '', resultado['importe_diferencia_sueldo'], 'haber'))
            if resultado['importe_premio_produccion'] > 0:
                conceptos.append(('PREM.PRODUC.', '', resultado['importe_premio_produccion'], 'haber'))
            if resultado['importe_cifra_fija'] > 0:
                conceptos.append(('CIFRA FIJA', '', resultado['importe_cifra_fija'], 'haber'))
            if resultado['importe_trabajos_varios'] > 0:
                conceptos.append(('TRABAJOS VS', '', resultado['importe_trabajos_varios'], 'haber'))
            if resultado['importe_viaticos'] > 0:
                conceptos.append(('VIATICOS', '', resultado['importe_viaticos'], 'haber'))
            if resultado['importe_remplazo_encargado'] > 0:
                conceptos.append(('REMPLAZO ENCARG.', '', resultado['importe_remplazo_encargado'], 'haber'))
            if resultado['importe_vacaciones'] > 0:
                conceptos.append(('VACACIONES', f"{resultado['dias_vacaciones']} días", resultado['importe_vacaciones'], 'haber'))
            if resultado.get('importe_jubilacion', 0) != 0:
                val = resultado['importe_jubilacion']
                conceptos.append(('JUB.', '', val, 'haber' if val > 0 else 'deduccion'))
            if resultado.get('importe_obra_social', 0) != 0:
                val = resultado['importe_obra_social']
                conceptos.append(('OB.SOC.', '', val, 'haber' if val > 0 else 'deduccion'))
            if resultado.get('importe_seguro', 0) != 0:
                val = resultado['importe_seguro']
                conceptos.append(('SEGURO', '', val, 'haber' if val > 0 else 'deduccion'))

            # Anticipos y Otros
            if resultado.get('importe_anticipos', 0) != 0:
                conceptos.append(('ANTICIPO', '', -resultado['importe_anticipos'], 'deduccion'))
            if resultado.get('importe_acreditacion_banco', 0) != 0:
                conceptos.append(('ACREDITACION BANCO', '', -resultado['importe_acreditacion_banco'], 'deduccion'))
            if resultado.get('importe_descuento_premio_prod', 0) != 0:
                conceptos.append(('DESC.PREM.PROD.', '', -resultado['importe_descuento_premio_prod'], 'deduccion'))
            
            imp_otr = resultado.get('importe_otros', 0)
            if imp_otr != 0:
                conceptos.append(('OTROS', '', imp_otr, 'haber' if imp_otr > 0 else 'deduccion'))

            cl1_imp = resultado['concepto_libre_1_importe']
            if cl1_imp != 0:
                cl1_label = resultado['concepto_libre_1_nombre'] or 'C.LIBRE 1'
                tipo_cl = 'haber' if cl1_imp > 0 else 'deduccion'
                conceptos.append((cl1_label, '(+)' if cl1_imp > 0 else '(-)', cl1_imp, tipo_cl))

            cl2_imp = resultado['concepto_libre_2_importe']
            if cl2_imp != 0:
                cl2_label = resultado['concepto_libre_2_nombre'] or 'C.LIBRE 2'
                tipo_cl = 'haber' if cl2_imp > 0 else 'deduccion'
                conceptos.append((cl2_label, '(+)' if cl2_imp > 0 else '(-)', cl2_imp, tipo_cl))

            if conceptos:
                df_preview = pd.DataFrame(conceptos, columns=['Concepto', 'Detalle', 'Importe', 'Tipo'])
                st.dataframe(
                    df_preview[['Concepto', 'Detalle', 'Importe']],
                    use_container_width=True, hide_index=True,
                    column_config={
                        "Concepto": st.column_config.TextColumn("Concepto", width=150),
                        "Detalle": st.column_config.TextColumn("Detalle", width=200),
                        "Importe": st.column_config.NumberColumn("Importe", format="$ %.2f", width=150)
                    }
                )

            col_t1, col_t2, col_t3 = st.columns(3)
            with col_t1:
                st.metric("Total Haberes", f"${_fmt_ar(resultado['total_haberes'])}")
            with col_t2:
                st.metric("Total Deducciones", f"${_fmt_ar(resultado['total_deducciones'])}")
            with col_t3:
                st.metric("TOTAL NETO", f"${_fmt_ar(resultado['total_neto'])}")

            # Botones: Guardar + Descargar PDF
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                if not es_cerrado:
                    if st.button("💾 Guardar liquidacion", key=f"guardar_liq_{emp_id}"):
                        if resultado['total_neto'] <= 0:
                            st.error("❌ No se puede guardar una liquidación con Neto igual o menor a cero.")
                        else:
                            data_liq = {
                                'periodo_id': periodo_id,
                                'empleado_id': emp_id,
                                'dias_vacaciones': dias_vacaciones,
                                **resultado
                            }
                            db.guardar_liquidacion(data_liq)
                            st.session_state.msg_liq = "✅ Liquidacion guardada correctamente"
                            st.session_state.liq_emp_key_cnt += 1
                            st.rerun()
                
                if liq_existente and not es_cerrado:
                    st.write("") # Separation
                    if st.button("🗑️ Eliminar liquidación actual", key=f"borrar_liq_{emp_id}", type="secondary", use_container_width=True):
                        db.eliminar_liquidacion(periodo_id, emp_id)
                        st.session_state.msg_liq = "✅ Liquidación eliminada correctamente."
                        st.session_state.liq_emp_key_cnt += 1
                        st.rerun()
            with col_btn2:
                # Generar PDF del recibo individual (disponible siempre, incluso en modo prueba)
                try:
                    periodo_preview = {'quincena': q, 'mes': m, 'anio': a}
                    pdf_recibo = reports.generar_recibos_pdf([resultado], {emp_id: emp}, periodo_preview)
                    st.download_button(
                        "📄 Descargar recibo PDF",
                        data=pdf_recibo,
                        file_name=f"Recibo_{emp['apellido_nombre'].replace(' ', '_')}_{periodo_str.replace('/', '-')}.pdf",
                        mime="application/pdf",
                        key=f"pdf_preview_{emp_id}"
                    )
                except Exception as ex:
                    st.error(f"Error generando PDF: {ex}")

    # ── Cierre de quincena ──
    if not es_cerrado:
        st.markdown("---")
        st.markdown("### 🔒 Cierre de Quincena")

        liq_periodo = db.get_liquidaciones_periodo(periodo_id)
        st.info(f"Hay {len(liq_periodo)} liquidaciones cargadas para este período.")

        if len(liq_periodo) > 0:
            with st.expander("🗑️ Herramientas de Borrado"):
                st.write("Seleccioná las liquidaciones que deseás eliminar del período actual:")
                
                # Crear mapeo de IDs a Nombres para el multiselect
                dict_liq = {f"{e_id}": db.get_empleado(e_id)['apellido_nombre'] for e_id in [l['empleado_id'] for l in liq_periodo]}
                
                seleccionados = st.multiselect(
                    "Empleados a borrar",
                    options=list(dict_liq.keys()),
                    format_func=lambda x: dict_liq[x],
                    key="multiselect_borrado",
                    help="Hacé clic para seleccionar o escribir nombres"
                )
                
                if seleccionados:
                    st.error(f"⚠️ Estás por borrar {len(seleccionados)} liquidaciones del período actual.")
                    if st.button(f"🗑️ BORRAR LAS {len(seleccionados)} SELECCIONADAS", type="primary", key="btn_borrar_multi", use_container_width=True):
                        db.eliminar_liquidaciones_multiples(periodo_id, [int(s) for s in seleccionados])
                        st.session_state.msg_liq = f"✅ Se eliminaron {len(seleccionados)} liquidaciones correctamente."
                        st.rerun()

            st.markdown("---")
            st.markdown("---")
            st.markdown("### 🔐 Cierre de Período")
            st.info("""
            **El cierre de período realiza las siguientes acciones:**
            1. Bloquea todas las liquidaciones de este período (no se podrán modificar).
            2. Genera un **Backup de Seguridad** automático.
            3. Resetea **Anticipos** y **Acreditación Banco** en las fichas de los empleados.
            4. Permite iniciar el siguiente período de liquidación.
            """)
            
            confirmar = st.checkbox(
                f"⚠️ Confirmo que deseo cerrar el período {periodo_str}. Esta acción es IRREVERSIBLE.",
                key="confirmar_cierre"
            )
            
            if confirmar:
                if st.button("🚀 RESPALDAR Y CERRAR PERIODO", type="primary", key="btn_cerrar", use_container_width=True):
                    # 1. Backup
                    try:
                        path_backup = db.respaldar_db(periodo_str)
                        st.info(f"✅ Backup creado: `{os.path.basename(path_backup)}`")
                    except Exception as eb:
                        st.error(f"Error al crear backup: {eb}")
                    
                    # 2. Cerrar
                    db.cerrar_periodo(periodo_id)
                    
                    # 3. Calcular siguiente periodo
                    # Si q=1 -> q=2, mismo mes. Si q=2 -> q=1, sig mes.
                    next_q = 2 if q == 1 else 1
                    next_m = m if q == 1 else (m + 1 if m < 12 else 1)
                    next_a = a if not (q == 2 and m == 12) else a + 1
                    
                    # Crear si no existe
                    if not db.get_periodo(next_q, next_m, next_a):
                        db.crear_periodo(next_q, next_m, next_a)
                    
                    # Actualizar session_state para que apunte al nuevo
                    st.session_state.periodo_quincena = next_q
                    st.session_state.periodo_mes = next_m
                    st.session_state.periodo_anio = next_a
                    # Sincronizar con las keys de los widgets de la sidebar
                    st.session_state['sel_q'] = next_q
                    st.session_state['sel_m'] = next_m
                    st.session_state['sel_a'] = next_a
                    
                    st.success(f"✅ Período {periodo_str} cerrado. Se ha habilitado el período {next_q:02d}/{next_m:02d}/{next_a}.")
                    st.balloons()
                    st.rerun()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# TAB C — INFORMES
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
with tab_informes:
    st.markdown("## 📊 Listados e Informes")

    sub_c1, sub_c2, sub_c3, sub_c4 = st.tabs([
        "🧾 Recibos", "📋 Listados", "📒 Asiento Contable", "📜 Historial"
    ])

    # Obtener período activo
    q = st.session_state.periodo_quincena
    m = st.session_state.periodo_mes
    a = st.session_state.periodo_anio
    periodo = db.get_periodo(q, m, a)

    with sub_c1:
        st.markdown("### 🧾 Recibos de Sueldo")

        if not periodo:
            st.info("No existe un período para la quincena seleccionada.")
        elif periodo['estado'] == 'CERRADO':
            st.warning("⚠️ Esta quincena está CERRADA. Para consultar datos históricos, por favor dirigite a la pestaña **📜 Historial**.")
        else:
            liq_periodo = db.get_liquidaciones_periodo(periodo['id'])
            if not liq_periodo:
                st.info("No hay liquidaciones para este período.")
            else:
                # Filtros
                filtro_tipo = st.radio(
                    "Generar recibos para:", 
                    ["Toda la quincena", "Empleado individual", "Por sección", "Por categoría"],
                    horizontal=True, key="filtro_recibos"
                )

                liq_filtradas = liq_periodo

                if filtro_tipo == "Empleado individual":
                    nombres = [l['apellido_nombre'] for l in liq_periodo]
                    sel_nombre = st.selectbox("Empleado", nombres, index=None, placeholder="Seleccionar empleado...", key="sel_recibo_emp")
                    if sel_nombre:
                        liq_filtradas = [l for l in liq_periodo if l['apellido_nombre'] == sel_nombre]
                    else:
                        liq_filtradas = []
                elif filtro_tipo == "Por sección":
                    secs = list(set(l['seccion'] for l in liq_periodo))
                    sel_sec = st.selectbox("Sección", secs, key="sel_recibo_sec")
                    liq_filtradas = [l for l in liq_periodo if l['seccion'] == sel_sec]
                elif filtro_tipo == "Por categoría":
                    cats = list(set(l.get('categoria', '') for l in liq_periodo))
                    sel_cat = st.selectbox("Categoría", cats, key="sel_recibo_cat")
                    liq_filtradas = [l for l in liq_periodo if l.get('categoria', '') == sel_cat]

                if not liq_filtradas:
                    if filtro_tipo == "Empleado individual" and not sel_nombre:
                        st.info("Buscá y seleccioná un empleado para generar su recibo.")
                    else:
                        st.warning("No hay liquidaciones que coincidan con el filtro.")
                else:
                    st.info(f"Se generarán {len(liq_filtradas)} recibo/s")

                    # Generar PDF directamente y mostrar boton de descarga
                    emp_dict = {e['id']: e for e in db.get_empleados()}
                    try:
                        pdf_bytes = reports.generar_recibos_pdf(liq_filtradas, emp_dict, periodo)
                        st.download_button(
                            "📄 Descargar Recibos PDF",
                            data=pdf_bytes,
                            file_name=f"Recibos_{periodo_str.replace('/', '-')}.pdf",
                            mime="application/pdf",
                            key="btn_descarga_recibos"
                        )
                    except Exception as ex:
                        st.error(f"Error generando PDF: {ex}")

    with sub_c2:
        st.markdown("### 📋 Listados de Pago")

        if not periodo:
            st.info("No existe un período para la quincena seleccionada.")
        elif periodo['estado'] == 'CERRADO':
            st.warning("⚠️ Esta quincena está CERRADA. Para consultar datos históricos, por favor dirigite a la pestaña **📜 Historial**.")
        else:
            liq_periodo = db.get_liquidaciones_periodo(periodo['id'])
            if not liq_periodo:
                st.info("No hay liquidaciones para este período.")
            else:
                formato = st.radio(
                    "Formato del listado:",
                    ["Resumido", "Detallado"],
                    horizontal=True, key="formato_listado"
                )

                # Filtros
                filtro_list = st.radio(
                    "Filtrar por:",
                    ["Toda la quincena", "Por sección", "Por categoría", "Empleado individual"],
                    horizontal=True, key="filtro_listado"
                )

                liq_filtradas = liq_periodo
                if filtro_list == "Por sección":
                    secs = list(set(l['seccion'] for l in liq_periodo))
                    sel_s = st.selectbox("Sección", secs, key="sel_list_sec")
                    liq_filtradas = [l for l in liq_periodo if l['seccion'] == sel_s]
                elif filtro_list == "Por categoría":
                    cats = list(set(l.get('categoria', '') for l in liq_periodo))
                    sel_c = st.selectbox("Categoría", cats, key="sel_list_cat")
                    liq_filtradas = [l for l in liq_periodo if l.get('categoria', '') == sel_c]
                elif filtro_list == "Empleado individual":
                    nombres = [l['apellido_nombre'] for l in liq_periodo]
                    sel_n = st.selectbox("Empleado", nombres, index=None, placeholder="Seleccionar empleado...", key="sel_list_emp")
                    if sel_n:
                        liq_filtradas = [l for l in liq_periodo if l['apellido_nombre'] == sel_n]
                    else:
                        liq_filtradas = []

                if filtro_list == "Empleado individual" and not sel_n:
                    st.info("Buscá y seleccioná un empleado para ver su listado.")
                elif not liq_filtradas:
                    st.warning("No hay liquidaciones que coincidan con el filtro.")
                else:
                    emp_dict = {e['id']: e for e in db.get_empleados()}

                    if formato == "Resumido":
                        df_list = reports.generar_listado_resumido(liq_filtradas, emp_dict)
                    else:
                        df_list = reports.generar_listado_detallado(liq_filtradas, emp_dict)

                    df_list_fmt = _fmt_df(df_list)
                    st.dataframe(df_list_fmt, use_container_width=True, hide_index=True)

                    # Exportar
                    col_exp1, col_exp2 = st.columns(2)
                    with col_exp1:
                        titulo = f"Listado {'Resumido' if formato == 'Resumido' else 'Detallado'}"
                        try:
                            pdf_bytes = reports.generar_listado_pdf(df_list, titulo, periodo_str)
                            st.download_button(
                                "⬇️ Descargar PDF",
                                data=pdf_bytes,
                                file_name=f"Listado_{formato}_{periodo_str.replace('/', '-')}.pdf",
                                mime="application/pdf",
                                key="btn_list_pdf"
                            )
                        except Exception as ex:
                            st.error(f"Error generando PDF: {ex}")
                    with col_exp2:
                        buffer = io.BytesIO()
                        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                            # Exportamos el original (numérico) no el formateado como texto
                            df_list.to_excel(writer, index=False, sheet_name='Listado')
                            
                            # Formateo de columnas numéricas en el Excel
                            workbook = writer.book
                            worksheet = writer.sheets['Listado']
                            num_fmt = workbook.add_format({'num_format': '#,##0.00'})
                            
                            for idx, col in enumerate(df_list.columns):
                                if df_list[col].dtype.kind in 'if': # numerica
                                    # Aplicamos formato a la columna (desde fila 1 hasta el final)
                                    worksheet.set_column(idx, idx, 15, num_fmt)
                                else:
                                    worksheet.set_column(idx, idx, 25)

                        st.download_button(
                            "⬇️ Descargar Excel (Editable)",
                            data=buffer.getvalue(),
                            file_name=f"Listado_{formato}_{periodo_str.replace('/', '-')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )

    with sub_c3:
        st.markdown("### 📒 Asiento Contable")

        if not periodo:
            st.info("No existe un período para la quincena seleccionada.")
        elif periodo['estado'] == 'CERRADO':
            st.warning("⚠️ Esta quincena está CERRADA. Para consultar datos históricos, por favor dirigite a la pestaña **📜 Historial**.")
        else:
            liq_periodo = db.get_liquidaciones_periodo(periodo['id'])
            if not liq_periodo:
                st.info("No hay liquidaciones para este período.")
            else:
                # Botón de recalculo masivo para sincronizar con fichas
                with st.expander("🔄 Sincronización de Datos"):
                    st.info("Utilice esta opción si realizó cambios en las fichas de los empleados (como Sección, Acreditación Banco, Premios, etc.) y desea que el asiento refleje esos cambios sin volver a cargar manualmente las horas o novedades de cada recibo.")
                    if st.button("🚀 Recalcular Todo el Asiento (Sincronizar con Fichas)", use_container_width=True):
                        bar_rec = st.progress(0)
                        emps_all = {e['id']: e for e in db.get_empleados()}
                        num_upd = 0
                        for i, l_row in enumerate(liq_periodo):
                            l_old = dict(l_row)
                            eid = l_old['empleado_id']
                            e_upd = emps_all.get(eid)
                            if not e_upd: continue
                            
                            # Re-extraer novedades de la liquidación guardada (Snapshot de inputs)
                            # Para horas comunes, si es 0 y el empleado tiene hs_fijas, el motor original las usa.
                            h_com = l_old.get('horas_comunes', 0)
                            
                            nov_rec = {
                                'horas_comunes': float(h_com),
                                'horas_extra_50': float(l_old.get('horas_extra_50', 0)),
                                'horas_extra_100': float(l_old.get('horas_extra_100', 0)),
                                'dias_trabajados': float(l_old.get('dias_trabajados', 30)),
                                'dias_vacaciones': float(l_old.get('dias_vacaciones', 0)),
                                'trabajos_varios': float(l_old.get('importe_trabajos_varios', 0)),
                                'viaticos': float(l_old.get('importe_viaticos', 0)),
                                'remplazo_encargado': float(l_old.get('remplazo_encargado', 0)),
                                'prop_aguinaldo': float(l_old.get('importe_prop_aguinaldo', 0)),
                                'concepto_libre_1_nombre': l_old.get('concepto_libre_1_nombre', ''),
                                'concepto_libre_1_importe': float(l_old.get('concepto_libre_1_importe', 0)),
                                'concepto_libre_2_nombre': l_old.get('concepto_libre_2_nombre', ''),
                                'concepto_libre_2_importe': float(l_old.get('concepto_libre_2_importe', 0)),
                            }
                            
                            # Si horas_comunes es 0 en el registro, pero el empleado tiene hs_fijas en su ficha,
                            # debemos respetar la lógica de la liquidación original (linea 1091).
                            if nov_rec['horas_comunes'] == 0 and e_upd.get('hs_fijas', 0) > 0:
                                nov_rec['horas_comunes'] = float(e_upd.get('hs_fijas', 0))
                            
                            # Recalcular con datos NUEVOS de ficha + novedades VIEJAS
                            res_new = calculator.calcular_liquidacion(e_upd, periodo['mes'], periodo['anio'], nov_rec)
                            res_new['periodo_id'] = periodo['id']
                            res_new['empleado_id'] = eid
                            
                            db.guardar_liquidacion(res_new)
                            num_upd += 1
                            bar_rec.progress((i + 1) / len(liq_periodo))
                        
                        st.session_state.mensaje_exito = f"✅ Se han recalculado y sincronizado {num_upd} liquidaciones."
                        st.rerun()

                emp_dict = {e['id']: e for e in db.get_empleados()}
                lineas = reports.generar_asiento_contable(liq_periodo, emp_dict)

                # Mostrar tabla 4 columnas
                df_asiento = pd.DataFrame(lineas)
                if not df_asiento.empty:
                    total_d = df_asiento['debe'].sum()
                    total_h = df_asiento['haber'].sum()
                    diferencia = round(total_d - total_h, 2)

                    # Fila de total
                    fila_total = pd.DataFrame([{'codigo': '', 'nombre': 'TOTAL', 'debe': total_d, 'haber': total_h}])
                    df_display = pd.concat([df_asiento, fila_total], ignore_index=True)

                    st.dataframe(
                        _fmt_df(df_display.rename(columns={
                            'codigo': 'Código', 'nombre': 'Nombre de Cuenta',
                            'debe': 'Debe', 'haber': 'Haber'
                        })),
                        use_container_width=True, hide_index=True,
                        column_config={
                            'Código': st.column_config.TextColumn('Código', width=130),
                            'Nombre de Cuenta': st.column_config.TextColumn('Nombre de Cuenta', width=250),
                            'Debe': st.column_config.TextColumn('Debe', width=130),
                            'Haber': st.column_config.TextColumn('Haber', width=130),
                        }
                    )

                    # Indicador de diferencia
                    if diferencia == 0:
                        st.success(f"✅ Asiento balanceado — DIFERENCIA: $0,00")
                    else:
                        st.error(f"❌ DIFERENCIA D - H: ${_fmt_ar(abs(diferencia))} — Revisar configuración de cuentas.")

                # Exportar
                col_e1, col_e2 = st.columns(2)
                with col_e1:
                    try:
                        pdf_bytes = reports.generar_asiento_pdf(lineas, periodo_str)
                        st.download_button(
                            "⬇️ Descargar Asiento PDF",
                            data=pdf_bytes,
                            file_name=f"Asiento_{periodo_str.replace('/', '-')}.pdf",
                            mime="application/pdf"
                        )
                    except Exception as ex:
                        st.error(f"Error generando PDF: {ex}")
                with col_e2:
                    buffer = io.BytesIO()
                    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                        df_asiento.rename(columns={
                            'codigo': 'Código', 'nombre': 'Nombre', 'debe': 'Debe', 'haber': 'Haber'
                        }).to_excel(writer, index=False, sheet_name='Asiento')
                    st.download_button(
                        "⬇️ Descargar Asiento Excel",
                        data=buffer.getvalue(),
                        file_name=f"Asiento_{periodo_str.replace('/', '-')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                # Gestión de cuentas contables
                with st.expander("⚙️ Gestión de Cuentas Contables", expanded=False):
                    st.markdown("Configurá el código y nombre contable para cada sección/concepto.")
                    cuentas = db.get_cuentas_asiento()
                    for cta in cuentas:
                        with st.form(f"form_cta_{cta['id']}"):
                            c1, c2, c3, c4 = st.columns([2, 4, 1, 1])
                            with c1:
                                nuevo_cod = st.text_input("Código", value=cta['codigo'], key=f"acc_cod_{cta['id']}")
                            with c2:
                                nuevo_nom = st.text_input("Nombre", value=cta['nombre'], key=f"acc_nom_{cta['id']}")
                            with c3:
                                nuevo_tipo = st.selectbox("Tipo", ["D", "H"], index=0 if cta['tipo'] == 'D' else 1, key=f"acc_tip_{cta['id']}")
                            with c4:
                                st.markdown(f"**`{cta['clave']}`**")
                            if st.form_submit_button("💾 Guardar"):
                                db.guardar_cuenta_asiento(cta['clave'], nuevo_cod, nuevo_nom, nuevo_tipo)
                                st.success(f"✅ Actualizado: {cta['clave']}")
                                st.rerun()

                    # Nueva cuenta
                    st.markdown("---")
                    st.markdown("**Agregar cuenta nueva (para sección no listada):**")
                    with st.form("form_nueva_cta"):
                        nc1, nc2, nc3, nc4 = st.columns([2, 4, 1, 1])
                        with nc1: nueva_clave = st.text_input("Clave (ej: DEPOSITO)")
                        with nc2: nuevo_cod2 = st.text_input("Código", key="nueva_cod")
                        with nc3: nuevo_nom2 = st.text_input("Nombre", key="nueva_nom")
                        with nc4: nuevo_tipo2 = st.selectbox("Tipo", ["D", "H"], key="nueva_tipo")
                        if st.form_submit_button("➕ Agregar"):
                            if nueva_clave:
                                db.guardar_cuenta_asiento(nueva_clave.upper().strip(), nuevo_cod2, nuevo_nom2, nuevo_tipo2)
                                st.success("✅ Cuenta agregada")
                                st.rerun()

    with sub_c4:
        st.markdown("### 📜 Historial")

        # Períodos cerrados
        periodos_cerrados = db.get_periodos(estado='CERRADO')
        if periodos_cerrados:
            st.markdown("#### Quincenas cerradas")
            for p in periodos_cerrados:
                p_str = f"{p['quincena']:02d}/{p['mes']:02d}/{p['anio']}"
                fecha_cierre = p.get('fecha_cierre', 'N/A')
                if fecha_cierre and fecha_cierre != 'N/A':
                    try:
                        fecha_cierre = datetime.strptime(fecha_cierre, '%Y-%m-%d %H:%M:%S').strftime('%d/%m/%Y %H:%M')
                    except:
                        pass
                with st.expander(f"📁 {p_str} — Cerrado el {fecha_cierre}"):
                    liq_hist = db.get_liquidaciones_periodo(p['id'])
                    if liq_hist:
                        emp_dict = {e['id']: e for e in db.get_empleados()}
                        
                        formato_h = st.radio(
                            "Formato del listado:",
                            ["Resumido", "Detallado"],
                            horizontal=True, key=f"formato_h_{p['id']}"
                        )

                        if formato_h == "Resumido":
                            df_hist = reports.generar_listado_resumido(liq_hist, emp_dict)
                        else:
                            df_hist = reports.generar_listado_detallado(liq_hist, emp_dict)

                        st.dataframe(_fmt_df(df_hist), use_container_width=True, hide_index=True)
                        # Buscar columna de total (puede variar segun el reporte)
                        col_total = 'Total Neto a Cobrar' if 'Total Neto a Cobrar' in df_hist.columns else ('Total Neto' if 'Total Neto' in df_hist.columns else None)
                        if col_total:
                            total_q = df_hist[col_total].sum()
                            st.metric("Total de la quincena", f"${_fmt_ar(total_q)}")

                        # Botones de exportacion
                        c_h1, c_h2, c_h3 = st.columns(3)
                        with c_h1:
                            try:
                                pdf_h = reports.generar_listado_pdf(df_hist, f"Listado Quincena {p_str}", p_str)
                                st.download_button(
                                    f"📄 PDF {p_str}",
                                    data=pdf_h,
                                    file_name=f"Listado_Quincena_{p_str.replace('/', '-')}.pdf",
                                    mime="application/pdf",
                                    key=f"btn_pdf_hist_{p['id']}",
                                    use_container_width=True
                                )
                            except Exception as ex:
                                st.error(f"Error generando PDF: {ex}")
                        with c_h2:
                            buffer = io.BytesIO()
                            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                                df_hist.to_excel(writer, index=False, sheet_name='Historial')
                            st.download_button(
                                f"📊 Excel {p_str}",
                                data=buffer.getvalue(),
                                file_name=f"Listado_Quincena_{p_str.replace('/', '-')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                                key=f"btn_xlsx_hist_{p['id']}",
                                use_container_width=True
                            )
                        with c_h3:
                            if st.button(f"🧾 Asiento {p_str}", key=f"btn_v_asiento_{p['id']}", use_container_width=True):
                                st.session_state[f'ver_asiento_h_{p['id']}'] = not st.session_state.get(f'ver_asiento_h_{p['id']}', False)
                        
                        if st.session_state.get(f'ver_asiento_h_{p['id']}', False):
                            st.markdown(f"#### 🧾 Asiento Contable - Periodo {p_str}")
                            lineas_h = reports.generar_asiento_contable(liq_hist, emp_dict)
                            df_ah = pd.DataFrame(lineas_h)
                            if not df_ah.empty:
                                total_dh = df_ah['debe'].sum()
                                total_hh = df_ah['haber'].sum()
                                fila_th = pd.DataFrame([{'codigo': '', 'nombre': 'TOTAL', 'debe': total_dh, 'haber': total_hh}])
                                df_ah_disp = pd.concat([df_ah, fila_th], ignore_index=True)
                                st.dataframe(_fmt_df(df_ah_disp), use_container_width=True, hide_index=True)
        else:
            st.info("No hay quincenas cerradas aún.")

        # Historial por empleado
        st.markdown("---")
        st.markdown("#### Historial por empleado")
        empleados_todos = db.get_empleados()
        if empleados_todos:
            opciones_hist = {f"{e['apellido_nombre']}": e['id'] for e in empleados_todos}
            sel_hist = st.selectbox("Empleado", list(opciones_hist.keys()), index=None, placeholder="Buscá un empleado por nombre...", key="sel_hist_emp")

            if not sel_hist:
                st.info("Buscá y seleccioná un empleado para ver su historial de liquidaciones quincenales.")
            else:
                historial = db.get_historial_empleado(opciones_hist[sel_hist])
                if historial:
                    # Filtro de períodos
                    periodos_disponibles = [f"{h['quincena']:02d}/{h['mes']:02d}/{h['anio']}" for h in historial]
                    col_filtro1, col_filtro2 = st.columns([2, 1])
                    with col_filtro1:
                        periodos_sel = st.multiselect(
                            "Períodos", periodos_disponibles,
                            default=periodos_disponibles,
                            key="sel_hist_periodos",
                            placeholder="Seleccioná uno o más períodos..."
                        )
                    with col_filtro2:
                        modo_hist = st.radio("Vista", ["Resumido", "Detallado"], horizontal=True, key="modo_hist")

                    # Filtrar historial según períodos seleccionados
                    hist_filtrado = [h for h in historial if f"{h['quincena']:02d}/{h['mes']:02d}/{h['anio']}" in periodos_sel]

                    if hist_filtrado:
                        if modo_hist == "Resumido":
                            df_hist_emp = pd.DataFrame([{
                                'Período': f"{h['quincena']:02d}/{h['mes']:02d}/{h['anio']}",
                                'Estado': h.get('periodo_estado', ''),
                                'Tipo': h.get('tipo_liquidacion', ''),
                                'Total Haberes': h.get('total_haberes', 0),
                                'Total Deducciones': h.get('total_deducciones', 0),
                                'Total Neto': h.get('total_neto', 0),
                            } for h in hist_filtrado])
                        else:
                            df_hist_emp = pd.DataFrame([{
                                'Período': f"{h['quincena']:02d}/{h['mes']:02d}/{h['anio']}",
                                'Estado': h.get('periodo_estado', ''),
                                'Tipo': h.get('tipo_liquidacion', ''),
                                'Hs Comunes': h.get('horas_comunes', 0),
                                'Hs Extra 50%': h.get('horas_extra_50', 0),
                                'Hs Extra 100%': h.get('horas_extra_100', 0),
                                'Básico/Hs Comunes': h.get('importe_horas_comunes', 0) or h.get('importe_basico_mensual', 0),
                                'Extra 50%': h.get('importe_extra_50', 0),
                                'Extra 100%': h.get('importe_extra_100', 0),
                                'Antigüedad': h.get('importe_antiguedad_total', 0),
                                'Presentismo': h.get('importe_presentismo', 0),
                                'Dif. Sueldo': h.get('importe_diferencia_sueldo', 0),
                                'Premio Prod.': h.get('importe_premio_produccion', 0),
                                'Cifra Fija': h.get('importe_cifra_fija', 0),
                                'Trab. Varios': h.get('importe_trabajos_varios', 0),
                                'Viáticos': h.get('importe_viaticos', 0),
                                'Vacaciones': h.get('importe_vacaciones', 0),
                                'Prop. Aguinaldo': h.get('importe_prop_aguinaldo', 0),
                                'Jubilación': h.get('importe_jubilacion', 0),
                                'Obra Social': h.get('importe_obra_social', 0),
                                'Anticipos': h.get('importe_anticipos', 0),
                                'Otros': h.get('importe_otros', 0),
                                'Acred. Banco': h.get('importe_acreditacion_banco', 0),
                                'Total Haberes': h.get('total_haberes', 0),
                                'Total Deducciones': h.get('total_deducciones', 0),
                                'Total Neto': h.get('total_neto', 0),
                            } for h in hist_filtrado])

                        st.dataframe(_fmt_df(df_hist_emp), use_container_width=True, hide_index=True)

                        # Exportar historial por empleado
                        c_he1, c_he2 = st.columns(2)
                        with c_he1:
                            try:
                                pdf_he = reports.generar_historial_emp_pdf(df_hist_emp, sel_hist)
                                st.download_button(
                                    "📄 Descargar Historial PDF",
                                    data=pdf_he,
                                    file_name=f"Historial_{sel_hist.replace(' ', '_')}.pdf",
                                    mime="application/pdf"
                                )
                            except Exception as ex:
                                st.error(f"Error generando PDF: {ex}")
                        with c_he2:
                            buffer = io.BytesIO()
                            with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
                                df_hist_emp.to_excel(writer, index=False, sheet_name='Historial')
                            st.download_button(
                                "📊 Descargar Historial Excel",
                                data=buffer.getvalue(),
                                file_name=f"Historial_{sel_hist.replace(' ', '_')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                    else:
                        st.info("Seleccioná al menos un período.")
                else:
                    st.info("Sin liquidaciones registradas para este empleado.")
