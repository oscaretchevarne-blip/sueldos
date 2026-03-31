"""
utils.py - Funciones utilitarias compartidas entre módulos.
Centraliza funciones duplicadas para evitar inconsistencias.
"""
import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


# ──────────────────────────────────────────────
# CARGA DE VARIABLES DE ENTORNO (.env)
# ──────────────────────────────────────────────

def load_env():
    """Carga variables desde .env. Usa python-dotenv si está disponible, sino parseo manual."""
    env_path = os.path.join(BASE_DIR, '.env')
    try:
        from dotenv import load_dotenv
        load_dotenv(env_path)
        return
    except ImportError:
        pass

    # Fallback manual: parsear .env línea por línea
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, _, value = line.partition('=')
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value

# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

LOG_DIR = os.path.join(BASE_DIR, "logs")

try:
    os.makedirs(LOG_DIR, exist_ok=True)
    LOG_PATH = os.path.join(LOG_DIR, "sueldos.log")
    _LOG_FILE_OK = True
except OSError:
    LOG_PATH = None
    _LOG_FILE_OK = False


def get_logger(name="sueldos"):
    """Obtiene un logger configurado con salida a archivo y consola.
    Si no se puede escribir archivo (ej: Streamlit Cloud), solo usa consola."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)

        # Archivo rotativo (si el directorio es escribible)
        if _LOG_FILE_OK and LOG_PATH:
            try:
                from logging.handlers import RotatingFileHandler
                fh = RotatingFileHandler(LOG_PATH, maxBytes=5*1024*1024, backupCount=3, encoding='utf-8')
                fh.setLevel(logging.INFO)
                fh.setFormatter(logging.Formatter(
                    '%(asctime)s | %(levelname)-7s | %(name)s | %(message)s',
                    datefmt='%Y-%m-%d %H:%M:%S'
                ))
                logger.addHandler(fh)
            except OSError:
                pass  # No se puede escribir archivo, solo consola

        # Consola (solo errores para no ensuciar Streamlit)
        ch = logging.StreamHandler()
        ch.setLevel(logging.WARNING)
        ch.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        logger.addHandler(ch)

    return logger


# ──────────────────────────────────────────────
# FORMATO ARGENTINO
# ──────────────────────────────────────────────

def fmt_ar(n, decimales=2):
    """Formato argentino: punto para miles, coma para decimales.
    Ej: 1234567.89 -> '1.234.567,89'
    """
    if n is None:
        return '0,00' if decimales == 2 else '0'
    fmt_us = f"{abs(n):,.{decimales}f}"
    fmt_ar = fmt_us.replace(',', '@').replace('.', ',').replace('@', '.')
    if n < 0:
        return f"-{fmt_ar}"
    return fmt_ar


# ──────────────────────────────────────────────
# TEXTO SEGURO PARA PDF (ASCII/Latin-1)
# ──────────────────────────────────────────────

_REPLACEMENTS = {
    '\u00e1': 'a', '\u00e9': 'e', '\u00ed': 'i', '\u00f3': 'o', '\u00fa': 'u',
    '\u00c1': 'A', '\u00c9': 'E', '\u00cd': 'I', '\u00d3': 'O', '\u00da': 'U',
    '\u00f1': 'n', '\u00d1': 'N', '\u00fc': 'u', '\u00dc': 'U',
    '\u00b0': 'o', '\x9c': 'oe', '\xa0': ' ',
    '\u2013': '-', '\u2014': '-', '\u2018': "'", '\u2019': "'",
    '\u201c': '"', '\u201d': '"', '\u2026': '...', '\u20ac': 'EUR',
}


def ascii_safe(texto):
    """Convierte texto a ASCII seguro para FPDF (evita UnicodeEncodeError)."""
    if not texto:
        return ''
    result = str(texto)
    for k, v in _REPLACEMENTS.items():
        result = result.replace(k, v)
    result = result.encode('latin-1', errors='replace').decode('latin-1')
    return result


# ──────────────────────────────────────────────
# NOMBRE CORTO
# ──────────────────────────────────────────────

def acortar_nombre(nombre_completo, max_len=20):
    """Acorta un nombre completo a 'Apellido Nombre' truncado a max_len chars."""
    nombre_completo = (nombre_completo or '').strip()
    nombre_corto = nombre_completo
    if ',' in nombre_completo:
        partes = nombre_completo.split(',')
        apellido = partes[0].strip()
        resto = partes[1].strip().split(' ')[0]
        nombre_corto = f"{apellido} {resto}"
    elif ' ' in nombre_completo:
        partes = nombre_completo.split(' ')
        apellido = partes[0].strip()
        nombre = partes[1].strip()
        nombre_corto = f"{apellido} {nombre}"
    return nombre_corto[:max_len]
