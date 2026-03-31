"""
reports.py - Generacion de recibos PDF (A5), listados y asiento contable.
"""
import io
import os
import sys
from datetime import datetime
from fpdf import FPDF
import pandas as pd
import database as db
from utils import fmt_ar as _fmt_ar, ascii_safe as _ascii, acortar_nombre


def _safe_pdf_output(pdf):
    """Genera bytes del PDF suprimiendo el print() interno de PyFPDF que falla en Windows cp1252."""
    old_stdout = sys.stdout
    try:
        sys.stdout = open(os.devnull, 'w')
        raw = pdf.output(dest='S')
    finally:
        sys.stdout.close()
        sys.stdout = old_stdout
    # PyFPDF 1.7.2 devuelve str, fpdf2 devuelve bytearray
    if isinstance(raw, str):
        return raw.encode('latin-1')
    return bytes(raw)


class ReciboPDF(FPDF):
    """Genera recibos de sueldo en formato A5 horizontal (210 x 148 mm) - Diseno ultra-compacto."""

    def __init__(self):
        # Usar tamaño A4 estándar pero solo dibujaremos en la mitad superior (primeros 148.5mm)
        # Esto asegura que la impresora detecte una hoja normal y no rote el contenido.
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_auto_page_break(auto=False)

    def _fill_rect(self, x, y, w, h, r, g, b):
        """Dibuja un rectangulo con relleno de color."""
        self.set_fill_color(r, g, b)
        self.rect(x, y, w, h, 'F')

    def generar_recibo(self, liquidacion, empleado, periodo):
        """Genera una pagina de recibo A5 horizontal para un empleado."""
        self.add_page()

        # Dimensiones: 210mm ancho x 148mm alto
        page_w = 210
        page_h = 148
        ml = 10      # margen lateral 1cm
        mr = 10
        mt = 5       # margen superior 0.5cm
        aw = page_w - ml - mr  # ancho util = 190mm

        y = mt
        liq = liquidacion

        # ENCABEZADO - Compacto
        header_h = 11
        self._fill_rect(ml, y, aw, header_h, 30, 41, 59) # Slate 800ish

        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 10)
        self.set_xy(ml, y + 1)
        self.cell(aw, 5, 'INGENIERIA PLASTICA ROSARIO S.A.', 0, 1, 'C')
        
        self.set_font('Helvetica', '', 7.5)
        self.set_xy(ml, y + 5.5)
        self.cell(aw, 4, 'CUIT: 30-54897809-9  |  Lugar de pago: V.G. GALVEZ', 0, 1, 'C')
        
        self.set_font('Helvetica', 'B', 7)
        self.set_xy(ml, y + 8.5)
        self.cell(aw, 3, 'RECIBO DE HABERES - Segun Ley de Contrato de Trabajo', 0, 1, 'C')

        self.set_text_color(0, 0, 0)
        y += header_h + 1

        # PERIODO
        q = periodo.get('quincena', '')
        m_per = periodo.get('mes', '')
        a_per = periodo.get('anio', '')
        periodo_str = f"{q:02d}/{m_per:02d}/{str(a_per)[2:]}"
        meses = ['', 'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
                 'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre']
        mes_nombre = meses[int(m_per)] if 1 <= int(m_per) <= 12 else ''
        quincena_txt = '1ra' if q == 1 else '2da'

        per_h = 5
        self._fill_rect(ml, y, aw, per_h, 241, 245, 249)
        self.set_font('Helvetica', 'B', 8)
        self.set_xy(ml, y)
        self.cell(aw, per_h, f'PERIODO: {quincena_txt} Quincena de {_ascii(mes_nombre)} {a_per} ({periodo_str})', 0, 1, 'C')
        y += per_h + 1

        # DATOS DEL EMPLEADO - Dos columnas
        self.set_draw_color(226, 232, 240)
        datos_h = 14
        self.rect(ml, y, aw, datos_h)

        nombre = _ascii(empleado.get('apellido_nombre', ''))
        cuil = empleado.get('cuil', '') or ''
        fi = empleado.get('fecha_ingreso', '') or ''
        cat = _ascii(empleado.get('categoria', '') or '')
        tipo = empleado.get('tipo', '')
        seccion = _ascii(empleado.get('seccion', '') or '')
        hoy_str = datetime.now().strftime('%d/%m/%Y')

        # Columna 1
        self.set_font('Helvetica', 'B', 10)
        self.set_xy(ml + 2, y + 1)
        self.cell(aw - 4, 5, f'{nombre} | CUIL: {cuil}', 0, 1)

        self.set_font('Helvetica', '', 8)
        self.set_xy(ml + 2, y + 6)
        self.cell(aw*0.5, 4, f'CATEGORIA: {cat}', 0, 0)
        self.cell(aw*0.5 - 4, 4, f'TIPO: {tipo}', 0, 1, 'R')
        
        if fi:
            try:
                # Intentar varios formatos si viene de la DB en ISO
                for fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                    try:
                        fi_dt = datetime.strptime(fi, fmt)
                        fi = fi_dt.strftime('%d/%m/%Y')
                        break
                    except ValueError:
                        continue
            except:
                pass
        self.cell(aw*0.25, 4, f'INGRESO: {fi}', 0, 0)
        self.cell(aw*0.25, 4, f'SECCION: {seccion}', 0, 0)
        
        vh = liq.get('valor_hora_usado', 0)
        vm = liq.get('valor_mensual_usado', 0)
        val_str = f"$ {_fmt_ar(vh)}" if vh > 0 else (f"$ {_fmt_ar(vm)}" if vm > 0 else "")
        label_val = "VALOR HORA:" if vh > 0 else "VALOR MENSUAL:"
        self.cell(aw*0.25, 4, f'{label_val} {val_str}', 0, 0)
        
        ant = liq.get('porcentaje_antiguedad', 0)
        self.cell(aw*0.25 - 4, 4, f'ANTIGUEDAD: {ant}%', 0, 1, 'R')

        y += datos_h + 1

        # TABLA DE CONCEPTOS
        cant_w = 25
        imp_w = 45
        conc_w = aw - cant_w - imp_w

        # Cabecera
        self._fill_rect(ml, y, aw, 5, 51, 65, 85)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 7.5)
        self.set_xy(ml, y)
        self.cell(cant_w, 5, 'CANTIDAD', 1, 0, 'C')
        self.cell(conc_w, 5, 'CONCEPTO', 1, 0, 'C')
        self.cell(imp_w, 5, 'IMPORTE ($)', 1, 1, 'C')
        self.set_text_color(0, 0, 0)
        y += 5

        row_h = 3.8
        row_count = 0

        def fila(cant, conc, imp, neg=False):
            nonlocal y, row_count
            if row_count % 2 == 1:
                self._fill_rect(ml, y, aw, row_h, 248, 250, 252)
            
            self.set_font('Helvetica', '', 8)
            self.set_xy(ml, y)
            
            c_str = f"{cant:.1f}" if (isinstance(cant, (int, float)) and cant != 0) else ""
            i_str = _fmt_ar(abs(imp)) if imp != 0 else ""
            if neg and i_str: i_str = f"- {i_str}"

            self.cell(cant_w, row_h, c_str, 'LR', 0, 'C')
            self.cell(conc_w, row_h, f" {_ascii(conc)}", 'LR', 0, 'L')
            self.cell(imp_w, row_h, i_str, 'LR', 1, 'R')
            y += row_h
            row_count += 1

        # Lista de conceptos
        if liq.get('importe_basico_mensual', 0) > 0:
            fila(liq.get('dias_trabajados', 0), 'DS. MENSUALES', liq['importe_basico_mensual'])
        if liq.get('horas_comunes', 0) > 0: fila(liq['horas_comunes'], 'HS. COMUNES', liq['importe_horas_comunes'])
        if liq.get('horas_extra_50', 0) > 0: fila(liq['horas_extra_50'], 'HS. EXTRA 50%', liq['importe_extra_50'])
        if liq.get('horas_extra_100', 0) > 0: fila(liq['horas_extra_100'], 'HS. EXTRA 100%', liq['importe_extra_100'])
        if liq.get('importe_antiguedad_total', 0) > 0:
            pct = liq.get('porcentaje_antiguedad', 0)
            fila('', f'ANTIGUEDAD ({pct}%)', liq['importe_antiguedad_total'])
        if liq.get('importe_presentismo', 0) > 0:
            pct_p = liq.get('porcentaje_presentismo', 15)
            # Quitar decimales si es .0
            if float(pct_p) == int(float(pct_p)): pct_p = int(float(pct_p))
            fila('', f'PRESENTISMO ({pct_p}%)', liq['importe_presentismo'])
        if liq.get('importe_prop_aguinaldo', 0) > 0: fila('', 'PROP. AGUINALDO', liq['importe_prop_aguinaldo'])
        if liq.get('importe_diferencia_sueldo', 0) > 0: fila('', 'DIF. SUELDO', liq['importe_diferencia_sueldo'])
        if liq.get('importe_premio_produccion', 0) > 0: fila('', 'PREMIO PRODUCCION', liq['importe_premio_produccion'])
        if liq.get('importe_cifra_fija', 0) > 0: fila('', 'CIFRA FIJA', liq['importe_cifra_fija'])
        if liq.get('importe_trabajos_varios', 0) > 0: fila('', 'TRABAJOS VARIOS', liq['importe_trabajos_varios'])
        if liq.get('importe_viaticos', 0) > 0: fila('', 'VIATICOS', liq['importe_viaticos'])
        if liq.get('importe_remplazo_encargado', 0) > 0: fila('', 'REMPLAZO ENCARGADO', liq['importe_remplazo_encargado'])
        if liq.get('importe_vacaciones', 0) > 0:
            fila(liq.get('dias_vacaciones', 0), 'VACACIONES', liq['importe_vacaciones'])
        
        # Conceptos libres
        for i in [1, 2]:
            c_nom = liq.get(f'concepto_libre_{i}_nombre')
            c_imp = liq.get(f'concepto_libre_{i}_importe', 0)
            if c_imp != 0:
                fila('', c_nom or f'C. LIBRE {i}', abs(c_imp), neg=(c_imp < 0))

        if liq.get('importe_jubilacion', 0) != 0:
            imp_jub = liq['importe_jubilacion']
            fila('', 'JUBILACION', abs(imp_jub), neg=(imp_jub < 0))
        
        if liq.get('importe_obra_social', 0) != 0:
            imp_os = liq['importe_obra_social']
            fila('', 'OBRA SOCIAL', abs(imp_os), neg=(imp_os < 0))
            
        if liq.get('importe_seguro', 0) != 0:
            imp_seg = liq['importe_seguro']
            fila('', 'SEGURO', abs(imp_seg), neg=(imp_seg < 0))
        
        # Nuevos Conceptos
        if liq.get('importe_anticipos', 0) > 0:
            fila('', 'ANTICIPOS', liq['importe_anticipos'], neg=True)
        
        if liq.get('importe_acreditacion_banco', 0) > 0:
            fila('', 'ACREDITACION BANCO', liq['importe_acreditacion_banco'], neg=True)
        
        if liq.get('importe_descuento_premio_prod', 0) > 0:
            fila('', 'DESC. PREM. PROD.', liq['importe_descuento_premio_prod'], neg=True)
        
        imp_otros = liq.get('importe_otros', 0)
        if imp_otros != 0:
            fila('', 'OTROS CONCEPTOS', abs(imp_otros), neg=(imp_otros < 0))

        # Completar espacio de tabla si hay pocas filas para mantener estructura
        while row_count < 10:
            fila('', '', 0)

        self.line(ml, y, ml + aw, y) # Cierre tabla

        # TOTALES Y FIRMA
        y += 2
        total_box_w = 60
        self.set_xy(ml + aw - total_box_w, y)
        self._fill_rect(ml + aw - total_box_w, y, total_box_w, 18, 248, 250, 252)
        self.rect(ml + aw - total_box_w, y, total_box_w, 18)
        
        self.set_font('Helvetica', '', 8)
        self.set_xy(ml + aw - total_box_w + 2, y + 1)
        self.cell(total_box_w - 4, 4, 'TOTAL HABERES', 0, 0)
        self.cell(0, 4, f"$ {_fmt_ar(liq.get('total_haberes', 0))}", 0, 1, 'R')
        
        self.set_xy(ml + aw - total_box_w + 2, y + 5)
        self.cell(total_box_w - 4, 4, 'DEDUCCIONES', 0, 0)
        self.cell(0, 4, f"$ {_fmt_ar(liq.get('total_deducciones', 0))}", 0, 1, 'R')
        
        self.line(ml + aw - total_box_w + 2, y + 10, ml + aw - 2, y + 10)
        
        self.set_font('Helvetica', 'B', 9)
        self.set_xy(ml + aw - total_box_w + 2, y + 11)
        self.cell(total_box_w - 4, 6, 'NETO A COBRAR', 0, 0)
        self.cell(0, 6, f"$ {_fmt_ar(liq.get('total_neto', 0))}", 0, 1, 'R')

        # FIRMA - Mas espacio vertical para firmar
        firma_y = page_h - 12 # 12mm desde el fondo
        self.set_font('Helvetica', 'B', 8)
        self.set_xy(ml, firma_y - 10) # Mas espacio antes de la linea
        self.cell(aw, 4, 'RECIBI CONFORME EL IMPORTE DEL PRESENTE', 0, 1, 'R')
        
        # Observaciones al pie
        obs = liq.get('observaciones', '')
        if obs:
            self.set_font('Helvetica', 'I', 6.5)
            self.set_xy(ml, firma_y - 6)
            self.cell(aw - 65, 4, f"OBS: {_ascii(obs)}", 0, 0, 'L')
        
        # Fecha y lugar de pago
        self.set_font('Helvetica', '', 7.5)
        self.set_xy(ml, firma_y)
        self.cell(100, 4, f'Lugar y fecha de pago: V.G. GALVEZ, {hoy_str}', 0, 0, 'L')

        self.line(ml + aw - 60, firma_y, ml + aw - 5, firma_y)
        self.set_xy(ml + aw - 60, firma_y + 1)
        self.cell(55, 4, 'FIRMA', 0, 0, 'C')


def generar_recibos_pdf(liquidaciones, empleados_dict, periodo):
    """
    Genera un PDF con multiples recibos A5.
    Retorna bytes del PDF.
    """
    pdf = ReciboPDF()
    for liq in liquidaciones:
        emp_id = liq.get('empleado_id')
        emp = empleados_dict.get(emp_id) if emp_id else None
        if not emp and len(empleados_dict) == 1:
            emp = list(empleados_dict.values())[0]
        if emp:
            pdf.generar_recibo(liq, emp, periodo)

    return _safe_pdf_output(pdf)


def generar_listado_resumido(liquidaciones, empleados_dict):
    """Genera listado resumido: Nombre | Total Neto. Retorna DataFrame."""
    data = []
    for liq in liquidaciones:
        emp = empleados_dict.get(liq['empleado_id'], {})
        data.append({
            'Empleado': acortar_nombre(emp.get('apellido_nombre', '')),
            'Total Neto a Cobrar': liq.get('total_neto', 0)
        })
    df = pd.DataFrame(data)
    df = df.sort_values('Empleado').reset_index(drop=True)
    return df


def generar_listado_detallado(liquidaciones, empleados_dict):
    """Genera listado detallado con columna por concepto. Retorna DataFrame."""
    data = []
    for liq in liquidaciones:
        emp = empleados_dict.get(liq['empleado_id'], {})
        row = {
            'Empleado': acortar_nombre(emp.get('apellido_nombre', '')),
            'C. 50%': liq.get('horas_extra_50', 0),
            'C. 100%': liq.get('horas_extra_100', 0),
            'Basico': liq.get('importe_basico_mensual', 0),
            'Hs. Com.': liq.get('importe_horas_comunes', 0),
            'Extra 50%': liq.get('importe_extra_50', 0),
            'Extra 100%': liq.get('importe_extra_100', 0),
            'Antig.': liq.get('importe_antiguedad_total', 0),
            'Dif. Sdo': liq.get('importe_diferencia_sueldo', 0),
            'Premio': liq.get('importe_premio_produccion', 0),
            'Desc.Prem.': -abs(liq.get('importe_descuento_premio_prod', 0)) if liq.get('importe_descuento_premio_prod', 0) else 0,
            'Cifra Fija': liq.get('importe_cifra_fija', 0),
            'Trab. Vs': liq.get('importe_trabajos_varios', 0),
            'Viaticos': liq.get('importe_viaticos', 0),
            'Vacac.': liq.get('importe_vacaciones', 0),
            'Presnt.': liq.get('importe_presentismo', 0),
            'Aguinal.': liq.get('importe_prop_aguinaldo', 0),
            'Jubilac.': liq.get('importe_jubilacion', 0),
            'Os. Soc.': liq.get('importe_obra_social', 0),
            'C.Lib 1': liq.get('concepto_libre_1_importe', 0),
            'C.Lib 2': liq.get('concepto_libre_2_importe', 0),
            'Seguro': -abs(liq.get('importe_seguro', 0)) if liq.get('importe_seguro', 0) else 0,
            'Total Neto': liq.get('total_neto', 0),
        }
        data.append(row)
    df = pd.DataFrame(data).fillna(0)
    
    # Reordenar: Total Neto siempre al final
    cols = df.columns.tolist()
    if 'Total Neto' in cols:
        cols.remove('Total Neto')
        cols.append('Total Neto')
        df = df[cols]

    df = df.sort_values('Empleado').reset_index(drop=True)
    return df


def generar_asiento_contable(liquidaciones, empleados_dict):
    """
    Genera el asiento contable simplificado.
    
    Reglas:
    - DEBITO por Sección = Σ (Neto + Seguros + Anticipos) de cada empleado.
    - CREDITOS = Sueldos a Pagar (Σ Neto), Seguros (Σ Seguros), Anticipos (Indiv./Varios).
    - Se elimina 'Acreditación Banco' del asiento.
    """
    # Lookup de códigos desde DB
    cuentas_raw = db.get_cuentas_asiento()
    cuentas_map = {c['clave']: c for c in cuentas_raw}

    def _cuenta(clave):
        """Búsqueda flexible."""
        c = cuentas_map.get(clave)
        if c:
            return c.get('codigo', ''), c.get('nombre', clave)
        c = cuentas_map.get(clave.upper())
        if c:
            return c.get('codigo', ''), c.get('nombre', clave)
        clave_up = clave.upper().strip()
        for k, v in cuentas_map.items():
            k_up = k.upper().strip()
            if k_up in clave_up or clave_up in k_up:
                return v.get('codigo', ''), v.get('nombre', clave)
        return '', clave

    # ── Acumuladores ──
    debe_seccion = {}   # seccion_key → importe
    haber_sueldos_pagar = 0
    haber_seguros = 0
    haber_anticipos_individuales = []   # {codigo, nombre, importe}
    haber_anticipos_varios = 0

    for l in liquidaciones:
        emp = empleados_dict.get(l['empleado_id'], {})
        seccion = emp.get('seccion', 'SIN SECCION')
        neto = l.get('total_neto', 0)
        seguro = abs(l.get('importe_seguro', 0))
        anticipo = abs(l.get('importe_anticipos', 0))
        
        # El COSTO por sección es Neto + Seguros + Anticipos
        costo_linea = round(neto + seguro + anticipo, 2)
        
        sec_debito_ext = (emp.get('seccion_debito_externo') or '').strip()
        target_sec = sec_debito_ext if sec_debito_ext else seccion
        
        debe_seccion[target_sec] = debe_seccion.get(target_sec, 0) + costo_linea

        # HABER
        haber_sueldos_pagar += neto
        haber_seguros += seguro
        
        if anticipo > 0:
            cod_contable = (emp.get('codigo_contable') or '').strip()
            if cod_contable:
                haber_anticipos_individuales.append({
                    'codigo': cod_contable,
                    'nombre': emp.get('apellido_nombre', ''),
                    'importe': anticipo
                })
            else:
                haber_anticipos_varios += anticipo

    # ── Construir líneas ──
    lineas = []

    # 1. DEBE — Secciones (Agrupadas por cuenta)
    debe_cuentas = {} # (cod, nom) -> importe
    for sec_key, importe in debe_seccion.items():
        cod, nom = _cuenta(sec_key)
        key = (cod, nom)
        debe_cuentas[key] = debe_cuentas.get(key, 0) + importe

    for (cod, nom), importe in sorted(debe_cuentas.items(), key=lambda x: (x[0][0] == '', x[0][0], x[0][1])):
        importe = round(importe, 2)
        if importe <= 0: continue
        lineas.append({'codigo': cod, 'nombre': nom, 'debe': importe, 'haber': 0})

    # 2. HABER
    # Sueldos a Pagar (Total Netos)
    if haber_sueldos_pagar:
        cod, nom = _cuenta('SUELDOS_A_PAGAR')
        lineas.append({'codigo': cod, 'nombre': nom, 'debe': 0, 'haber': round(haber_sueldos_pagar, 2)})

    # Seguros
    if haber_seguros:
        cod, nom = _cuenta('SEGUROS')
        lineas.append({'codigo': cod, 'nombre': nom, 'debe': 0, 'haber': round(haber_seguros, 2)})

    # Anticipos individuales (Ej: Asad)
    for item in sorted(haber_anticipos_individuales, key=lambda x: x['nombre']):
        lineas.append({'codigo': item['codigo'], 'nombre': item['nombre'], 'debe': 0, 'haber': round(item['importe'], 2)})

    # Anticipos varios
    if haber_anticipos_varios:
        lineas.append({'codigo': '', 'nombre': 'Anticipos Varios', 'debe': 0, 'haber': round(haber_anticipos_varios, 2)})

    return lineas


def generar_listado_pdf(df, titulo, periodo_str):
    """Genera un PDF a partir de un DataFrame (listado)."""
    # Usar márgenes mínimos para maximizar el ancho
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.set_margins(5, 10, 5) 
    pdf.add_page()
    
    pdf.set_font('Helvetica', 'B', 12)
    pdf.cell(0, 8, _ascii(titulo), 0, 1, 'C')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, _ascii(f'Periodo: {periodo_str}'), 0, 1, 'C')
    pdf.ln(2)

    cols = df.columns.tolist()
    col_widths = []
    for c in cols:
        if c == 'Empleado':
            col_widths.append(38)
        elif 'Total' in c:
            col_widths.append(26)
        elif 'C.' in c: # Cantidades
            col_widths.append(12)
        else:
            col_widths.append(15.5) # Ancho base para montos 10 dígitos

    total_w = sum(col_widths)
    available = 287 # 297mm - 10mm margins
    if total_w > available:
        factor = available / total_w
        col_widths = [w * factor for w in col_widths]

    def _imprimir_cabecera():
        pdf.set_font('Helvetica', 'B', 5.5)
        for i, c in enumerate(cols):
            pdf.cell(col_widths[i], 4, _ascii(c), 1, 0, 'C')
        pdf.ln()

    _imprimir_cabecera()

    pdf.set_font('Helvetica', '', 5.5)
    for _, row in df.iterrows():
        # Chequeo de espacio para nueva página (A4 landscape es ~210mm alto)
        if pdf.get_y() > 188:
            pdf.add_page()
            _imprimir_cabecera()
            pdf.set_font('Helvetica', '', 5.5)

        for i, c in enumerate(cols):
            val = row[c]
            if isinstance(val, (int, float)):
                txt = _fmt_ar(val)
                align = 'R'
            else:
                txt = _ascii(str(val))
                align = 'L'
            pdf.cell(col_widths[i], 3.8, txt, 1, 0, align)
        pdf.ln()

    # --- FILA DE TOTALES ---
    if pdf.get_y() > 185:
        pdf.add_page()
        _imprimir_cabecera()

    pdf.set_font('Helvetica', 'B', 5.5)
    for i, c in enumerate(cols):
        if c == 'Empleado':
            pdf.cell(col_widths[i], 4.5, 'TOTALES', 1, 0, 'C')
        else:
            if df[c].dtype.kind in 'if':
                total_val = df[c].sum()
                txt = _fmt_ar(total_val)
                pdf.cell(col_widths[i], 4.5, txt, 1, 0, 'R')
            else:
                pdf.cell(col_widths[i], 4.5, '', 1, 0, 'C')
    pdf.ln(5.5)
    
    # Repetir cabecera al final si hay espacio
    if pdf.get_y() < 195:
        _imprimir_cabecera()

    return _safe_pdf_output(pdf)


def generar_asiento_pdf(lineas, periodo_str):
    """Genera un PDF del asiento contable con 4 columnas: Codigo / Nombre / Debe / Haber."""
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 8, 'ASIENTO CONTABLE', 0, 1, 'C')
    pdf.set_font('Helvetica', '', 9)
    pdf.cell(0, 5, _ascii(f'Periodo: {periodo_str}'), 0, 1, 'C')
    pdf.ln(4)

    # Anchos de columna: Código | Nombre | Debe | Haber
    cw = [32, 80, 35, 35]
    total_w = sum(cw)

    # ── Encabezado ──
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(26, 33, 62)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(cw[0], 7, 'CODIGO', 1, 0, 'C', fill=True)
    pdf.cell(cw[1], 7, 'NOMBRE DE CUENTA', 1, 0, 'C', fill=True)
    pdf.cell(cw[2], 7, 'DEBE', 1, 0, 'C', fill=True)
    pdf.cell(cw[3], 7, 'HABER', 1, 1, 'C', fill=True)
    pdf.set_text_color(0, 0, 0)

    pdf.set_font('Helvetica', '', 8)
    total_d = 0
    total_h = 0
    fill = False

    for linea in lineas:
        debe = linea.get('debe', 0)
        haber = linea.get('haber', 0)
        total_d += debe
        total_h += haber
        cod = _ascii(linea.get('codigo', ''))
        nom = _ascii(linea.get('nombre', ''))

        # Alternar fondo de fila
        pdf.set_fill_color(245, 247, 250)
        pdf.cell(cw[0], 5, cod, 1, 0, 'L', fill=fill)
        pdf.cell(cw[1], 5, nom, 1, 0, 'L', fill=fill)
        pdf.cell(cw[2], 5, _fmt_ar(debe) if debe else '', 1, 0, 'R', fill=fill)
        pdf.cell(cw[3], 5, _fmt_ar(haber) if haber else '', 1, 1, 'R', fill=fill)
        fill = not fill

    # ── Fila de Totales ──
    pdf.ln(1)
    pdf.set_font('Helvetica', 'B', 8)
    pdf.set_fill_color(215, 220, 235)
    pdf.cell(cw[0] + cw[1], 6, 'TOTAL', 1, 0, 'C', fill=True)
    pdf.cell(cw[2], 6, _fmt_ar(total_d), 1, 0, 'R', fill=True)
    pdf.cell(cw[3], 6, _fmt_ar(total_h), 1, 1, 'R', fill=True)

    # ── Diferencia ──
    diferencia = round(total_d - total_h, 2)
    if diferencia == 0:
        dif_label = 'DIFERENCIA: 0,00  OK'
        pdf.set_text_color(40, 167, 69)
    else:
        dif_label = f'DIFERENCIA: {_fmt_ar(abs(diferencia))}  (!)'
        pdf.set_text_color(220, 53, 69)
    pdf.set_font('Helvetica', 'B', 9)
    pdf.cell(total_w, 7, _ascii(dif_label), 1, 1, 'C')
    pdf.set_text_color(0, 0, 0)

    return _safe_pdf_output(pdf)


def generar_listado_empleados_pdf(df_empl):
    """Genera un PDF con el listado de empleados."""
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'LISTADO DE PERSONAL', 0, 1, 'C')
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(0, 5, f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
    pdf.ln(5)

    # Columnas con nuevos campos
    col_widths = [10, 50, 27, 22, 22, 28, 30, 25, 16, 16, 16, 20, 15]
    headers = ['ID', 'Apellido y Nombre', 'CUIL', 'Tipo', 'Condic.', 'Seccion', 'Categoria', 'Basico/Hora', 'L.Bas', 'A.Bas', 'Pres.', 'F.Ingreso', 'Estado']
    col_keys = ['id', 'apellido_nombre', 'cuil', 'tipo', 'condicion', 'seccion', 'categoria', 'basico_hora', 'liq_basico', 'ant_basico', 'liq_present', 'fecha_ingreso', 'estado']

    def _print_header():
        pdf.set_font('Helvetica', 'B', 7.5)
        pdf.set_fill_color(240, 240, 240)
        for i, h in enumerate(headers):
            pdf.cell(col_widths[i], 7, _ascii(h), 1, 0, 'C', fill=True)
        pdf.ln()

    _print_header()

    pdf.set_font('Helvetica', '', 7.5)
    for _, row in df_empl.iterrows():
        if pdf.get_y() > 180:
            pdf.add_page()
            _print_header()
            pdf.set_font('Helvetica', '', 7.5)

        for i, key in enumerate(col_keys):
            val = str(row.get(key, ''))
            align = 'C' if key in ('id', 'liq_basico', 'ant_basico', 'liq_present', 'estado') else 'L'
            pdf.cell(col_widths[i], 5.5, _ascii(val), 1, 0, align)
        pdf.ln()

    return _safe_pdf_output(pdf)


def generar_historial_emp_pdf(df_hist, nombre_emp):
    """Genera un PDF con el historial de liquidaciones de un empleado."""
    pdf = FPDF(orientation='P', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_font('Helvetica', 'B', 14)
    pdf.cell(0, 10, 'HISTORIAL DE LIQUIDACIONES', 0, 1, 'C')
    pdf.set_font('Helvetica', 'B', 11)
    pdf.cell(0, 7, _ascii(f'Empleado: {nombre_emp}'), 0, 1, 'C')
    pdf.set_font('Helvetica', '', 8)
    pdf.cell(0, 5, f'Generado el: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 1, 'R')
    pdf.ln(5)

    col_widths = [40, 40, 60, 50]
    headers = ['Período', 'Estado', 'Tipo de Liq.', 'Total Neto']

    pdf.set_font('Helvetica', 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 8, _ascii(h), 1, 0, 'C', fill=True)
    pdf.ln()

    pdf.set_font('Helvetica', '', 10)
    total_acumulado = 0
    for _, row in df_hist.iterrows():
        pdf.cell(col_widths[0], 7, _ascii(row.get('Período', '')), 1, 0, 'C')
        pdf.cell(col_widths[1], 7, _ascii(row.get('Estado', '')), 1, 0, 'C')
        pdf.cell(col_widths[2], 7, _ascii(row.get('Tipo', '')), 1, 0)
        
        neto = row.get('Total Neto', 0)
        total_acumulado += neto
        pdf.cell(col_widths[3], 7, f"$ {_fmt_ar(neto)}", 1, 1, 'R')

    pdf.set_font('Helvetica', 'B', 10)
    pdf.cell(sum(col_widths[:3]), 8, 'TOTAL ACUMULADO', 1, 0, 'R', fill=True)
    pdf.cell(col_widths[3], 8, f"$ {_fmt_ar(total_acumulado)}", 1, 1, 'R', fill=True)

    return _safe_pdf_output(pdf)
