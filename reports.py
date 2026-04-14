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


# ──────────────────────────────────────────────
# IMPORTE EN LETRAS (para "Son pesos:" en recibo)
# ──────────────────────────────────────────────

_UNIDADES_TXT = ['','UNO','DOS','TRES','CUATRO','CINCO','SEIS','SIETE','OCHO','NUEVE','DIEZ',
                 'ONCE','DOCE','TRECE','CATORCE','QUINCE','DIECISEIS','DIECISIETE','DIECIOCHO','DIECINUEVE','VEINTE']
_DECENAS_TXT = ['','','VEINTI','TREINTA','CUARENTA','CINCUENTA','SESENTA','SETENTA','OCHENTA','NOVENTA']
_CENTENAS_TXT = ['','CIENTO','DOSCIENTOS','TRESCIENTOS','CUATROCIENTOS','QUINIENTOS',
                 'SEISCIENTOS','SETECIENTOS','OCHOCIENTOS','NOVECIENTOS']

def _menor_mil_txt(n):
    if n == 0: return ''
    if n == 100: return 'CIEN'
    c = n // 100; resto = n % 100
    res = _CENTENAS_TXT[c] if c else ''
    if resto == 0: return res.strip()
    if resto <= 20:
        pal = _UNIDADES_TXT[resto]
    else:
        d = resto // 10; u = resto % 10
        if d == 2:
            pal = 'VEINTI' + _UNIDADES_TXT[u] if u else 'VEINTE'
        else:
            pal = _DECENAS_TXT[d] + (' Y ' + _UNIDADES_TXT[u] if u else '')
    return (res + ' ' + pal).strip()

def _numero_a_letras(n):
    """Convierte un entero a su representacion en letras (para 'Son pesos:')."""
    try:
        n = int(round(float(n)))
    except Exception:
        return ''
    if n < 0:
        return 'MENOS ' + _numero_a_letras(-n)
    if n == 0: return 'CERO'
    millones = n // 1_000_000
    miles = (n % 1_000_000) // 1000
    unidades = n % 1000
    partes = []
    if millones:
        partes.append('UN MILLON' if millones == 1 else _menor_mil_txt(millones) + ' MILLONES')
    if miles:
        partes.append('MIL' if miles == 1 else _menor_mil_txt(miles) + ' MIL')
    if unidades:
        partes.append(_menor_mil_txt(unidades))
    return ' '.join(partes)


class ReciboPDF(FPDF):
    """Genera recibos de sueldo en formato A5 horizontal (210 x 148 mm).
    Layout profesional: haberes y deducciones en columnas separadas, ficha de
    empleado en grilla, caja destacada de NETO A COBRAR y firma unica del empleado.
    """

    # Paleta
    SLATE_DARK    = (30, 41, 59)
    SLATE_MID     = (51, 65, 85)
    SLATE_SOFT    = (241, 245, 249)
    SLATE_LINE    = (203, 213, 225)
    TEXT_MUTED    = (100, 116, 139)
    ACCENT_BG     = (236, 242, 248)
    SUBTOTAL_BG   = (226, 232, 240)

    def __init__(self):
        # A4 vertical, pero se dibuja solo en los primeros 148mm (area A5 horizontal).
        super().__init__(orientation='P', unit='mm', format='A4')
        self.set_auto_page_break(auto=False)

    def _fill_rect(self, x, y, w, h, r, g, b):
        self.set_fill_color(r, g, b)
        self.rect(x, y, w, h, 'F')

    def _fill(self, x, y, w, h, rgb):
        self.set_fill_color(*rgb)
        self.rect(x, y, w, h, 'F')

    def generar_recibo(self, liquidacion, empleado, periodo):
        """Genera una pagina de recibo A5 horizontal para un empleado."""
        self.add_page()

        page_w = 210
        page_h = 148
        ml, mr, mt = 8, 8, 5
        aw = page_w - ml - mr  # 194

        y = mt
        liq = liquidacion

        # ══════════════════════════════════════════
        # 1. ENCABEZADO
        # ══════════════════════════════════════════
        header_h = 13
        self._fill(ml, y, aw, header_h, self.SLATE_DARK)

        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 12)
        self.set_xy(ml + 2, y + 1.5)
        self.cell(aw - 4, 5, 'INGENIERIA  PLASTICA  ROSARIO  S.A.', 0, 1, 'C')

        self.set_font('Helvetica', '', 7.5)
        self.set_xy(ml + 2, y + 6.5)
        self.cell(aw - 4, 3.5, 'CUIT: 30-54897809-9    -    Lugar de pago: V.G. GALVEZ', 0, 1, 'C')

        # Sub-banda dentro del header
        self._fill(ml, y + header_h - 3, aw, 3, self.SLATE_MID)
        self.set_font('Helvetica', 'B', 6.5)
        self.set_xy(ml + 2, y + header_h - 3)
        self.cell((aw - 4) / 2, 3, 'RECIBO DE HABERES   -   LCT Art. 138 a 146', 0, 0, 'L')
        nro_rec = liq.get('nro_recibo', '') or ''
        self.set_xy(ml + aw / 2, y + header_h - 3)
        self.cell((aw - 4) / 2, 3, (f'N  {nro_rec}' if nro_rec else ''), 0, 1, 'R')

        self.set_text_color(0, 0, 0)
        y += header_h + 2

        # ══════════════════════════════════════════
        # 2. FICHA EMPLEADO + PERIODO
        # ══════════════════════════════════════════
        ficha_h = 20
        ficha_w = aw - 50    # 144
        per_w = 48           # tag periodo a la derecha

        self.set_draw_color(*self.SLATE_LINE)
        self.rect(ml, y, ficha_w, ficha_h)

        nombre   = _ascii(empleado.get('apellido_nombre', '') or '')
        cuil     = empleado.get('cuil', '') or ''
        fi       = empleado.get('fecha_ingreso', '') or ''
        ant_pct  = liq.get('porcentaje_antiguedad', 0)
        anos_ant = liq.get('anos_antiguedad', '') or ''
        cat      = _ascii(empleado.get('categoria', '') or '')
        sec      = _ascii(empleado.get('seccion', '') or '')
        tipo     = empleado.get('tipo', '') or ''
        vh       = liq.get('valor_hora_usado', 0)
        vm       = liq.get('valor_mensual_usado', 0)

        # Normalizar fecha de ingreso a dd/mm/yyyy
        if fi:
            for _fmt in ('%Y-%m-%d', '%d/%m/%Y'):
                try:
                    fi = datetime.strptime(fi, _fmt).strftime('%d/%m/%Y')
                    break
                except ValueError:
                    continue

        # Linea 1: APELLIDO Y NOMBRE
        self.set_text_color(*self.TEXT_MUTED)
        self.set_font('Helvetica', '', 5.5)
        self.set_xy(ml + 2, y + 1.2)
        self.cell(ficha_w - 4, 2.5, 'APELLIDO Y NOMBRE', 0, 1, 'L')
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', 'B', 11)
        self.set_xy(ml + 2, y + 3.5)
        self.cell(ficha_w - 4, 5, nombre, 0, 1, 'L')

        # separador
        self.set_draw_color(*self.SLATE_LINE)
        self.line(ml + 2, y + 9.5, ml + ficha_w - 2, y + 9.5)

        # Fila 2: CUIL | FECHA INGRESO | ANTIGUEDAD | VALOR HORA/MENSUAL
        col_w = (ficha_w - 4) / 4
        val_str = f'$ {_fmt_ar(vh)}' if vh > 0 else (f'$ {_fmt_ar(vm)}' if vm > 0 else '')
        lbl_val = 'VALOR HORA' if vh > 0 else 'VALOR MENSUAL'
        ant_txt = f'{anos_ant} ({ant_pct}%)' if anos_ant else f'{ant_pct}%'
        labels1 = ['CUIL', 'FECHA DE INGRESO', 'ANTIGUEDAD', lbl_val]
        values1 = [cuil, fi, ant_txt, val_str]
        for i, (lb, vl) in enumerate(zip(labels1, values1)):
            x = ml + 2 + i * col_w
            self.set_text_color(*self.TEXT_MUTED)
            self.set_font('Helvetica', '', 5.5)
            self.set_xy(x, y + 10.3)
            self.cell(col_w, 2.5, lb, 0, 0, 'L')
            self.set_text_color(0, 0, 0)
            self.set_font('Helvetica', 'B', 8)
            self.set_xy(x, y + 12.8)
            self.cell(col_w, 3.5, _ascii(str(vl)), 0, 0, 'L')

        # Fila 3: CATEGORIA | SECCION | TIPO
        col_w3 = (ficha_w - 4) / 3
        labels2 = ['CATEGORIA', 'SECCION', 'TIPO']
        values2 = [cat, sec, tipo]
        for i, (lb, vl) in enumerate(zip(labels2, values2)):
            x = ml + 2 + i * col_w3
            self.set_text_color(*self.TEXT_MUTED)
            self.set_font('Helvetica', '', 5.5)
            self.set_xy(x, y + 16)
            self.cell(col_w3, 2.5, lb, 0, 0, 'L')
            self.set_text_color(0, 0, 0)
            self.set_font('Helvetica', 'B', 8)
            self.set_xy(x, y + 17.8)
            self.cell(col_w3, 2.5, _ascii(str(vl)), 0, 0, 'L')

        # Tag de PERIODO a la derecha
        per_x = ml + ficha_w + 2
        self._fill(per_x, y, per_w, ficha_h, self.SLATE_DARK)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', '', 6)
        self.set_xy(per_x, y + 1.5)
        self.cell(per_w, 3, 'PERIODO LIQUIDADO', 0, 1, 'C')

        q = periodo.get('quincena', 1)
        mp = periodo.get('mes', 1)
        ap = periodo.get('anio', 0)
        meses = ['', 'ENERO', 'FEBRERO', 'MARZO', 'ABRIL', 'MAYO', 'JUNIO',
                 'JULIO', 'AGOSTO', 'SEPTIEMBRE', 'OCTUBRE', 'NOVIEMBRE', 'DICIEMBRE']
        try:
            mes_nombre = meses[int(mp)]
        except Exception:
            mes_nombre = ''
        q_txt = '1ra  QUINCENA' if q == 1 else '2da  QUINCENA'
        self.set_font('Helvetica', 'B', 9)
        self.set_xy(per_x, y + 5)
        self.cell(per_w, 5, q_txt, 0, 1, 'C')
        self.set_font('Helvetica', 'B', 10)
        self.set_xy(per_x, y + 10)
        self.cell(per_w, 5, f'{mes_nombre}  {ap}', 0, 1, 'C')
        self.set_font('Helvetica', '', 7)
        self.set_xy(per_x, y + 15)
        try:
            periodo_str = f'{int(q):02d}/{int(mp):02d}/{str(ap)[2:]}'
        except Exception:
            periodo_str = ''
        self.cell(per_w, 4, periodo_str, 0, 1, 'C')

        self.set_text_color(0, 0, 0)
        y += ficha_h + 2

        # ══════════════════════════════════════════
        # 3. TABLA DE CONCEPTOS (Haberes / Deducciones separadas)
        # ══════════════════════════════════════════
        conc_w = 78
        cant_w = 22
        pct_w  = 14
        hab_w  = 35
        ded_w  = aw - conc_w - cant_w - pct_w - hab_w

        head_h = 5.5
        self._fill(ml, y, aw, head_h, self.SLATE_MID)
        self.set_text_color(255, 255, 255)
        self.set_font('Helvetica', 'B', 7)
        self.set_xy(ml, y)
        self.cell(conc_w, head_h, '  CONCEPTO', 0, 0, 'L')
        self.cell(cant_w, head_h, 'CANT. / REF.', 0, 0, 'C')
        self.cell(pct_w,  head_h, '%', 0, 0, 'C')
        self.cell(hab_w,  head_h, 'HABERES', 0, 0, 'R')
        self.cell(ded_w,  head_h, 'DEDUCCIONES  ', 0, 1, 'R')
        self.set_text_color(0, 0, 0)
        y += head_h

        row_h = 3.9
        y_ref = [y]
        row_i = [0]

        def fila(concepto, cant='', pct='', haberes=0, deducciones=0):
            cy = y_ref[0]
            if row_i[0] % 2 == 1:
                self._fill(ml, cy, aw, row_h, self.SLATE_SOFT)
            self.set_font('Helvetica', '', 7.8)
            self.set_xy(ml, cy)
            self.cell(conc_w, row_h, '  ' + _ascii(concepto), 0, 0, 'L')
            # cantidad: numero o string
            if isinstance(cant, (int, float)) and cant != 0:
                c_str = f"{cant:.1f}" if isinstance(cant, float) else str(cant)
            else:
                c_str = str(cant) if cant not in (None, '', 0) else ''
            self.cell(cant_w, row_h, c_str, 0, 0, 'C')
            p_str = ''
            if pct not in (None, '', 0):
                try:
                    pf = float(pct)
                    p_str = f'{int(pf)}%' if pf == int(pf) else f'{pf}%'
                except Exception:
                    p_str = f'{pct}%'
            self.cell(pct_w, row_h, p_str, 0, 0, 'C')
            self.cell(hab_w, row_h, (_fmt_ar(haberes) if haberes else ''), 0, 0, 'R')
            self.cell(ded_w, row_h, ((_fmt_ar(deducciones) + '  ') if deducciones else ''), 0, 1, 'R')
            y_ref[0] += row_h
            row_i[0] += 1

        # ── HABERES ──
        if liq.get('importe_basico_mensual', 0) > 0:
            fila('DS. MENSUALES', liq.get('dias_trabajados', 0), '', haberes=liq['importe_basico_mensual'])
        if liq.get('horas_comunes', 0) > 0:
            fila('HS. COMUNES', liq['horas_comunes'], '', haberes=liq['importe_horas_comunes'])
        if liq.get('horas_extra_50', 0) > 0:
            fila('HS. EXTRA 50%', liq['horas_extra_50'], '50', haberes=liq['importe_extra_50'])
        if liq.get('horas_extra_100', 0) > 0:
            fila('HS. EXTRA 100%', liq['horas_extra_100'], '100', haberes=liq['importe_extra_100'])
        if liq.get('importe_antiguedad_total', 0) > 0:
            fila('ANTIGUEDAD', '', liq.get('porcentaje_antiguedad', 0), haberes=liq['importe_antiguedad_total'])
        if liq.get('importe_presentismo', 0) > 0:
            fila('PRESENTISMO', '', liq.get('porcentaje_presentismo', 15), haberes=liq['importe_presentismo'])
        if liq.get('importe_prop_aguinaldo', 0) > 0:
            fila('PROP. AGUINALDO', '', '', haberes=liq['importe_prop_aguinaldo'])
        if liq.get('importe_diferencia_sueldo', 0) > 0:
            fila('DIF. SUELDO', '', '', haberes=liq['importe_diferencia_sueldo'])
        if liq.get('importe_premio_produccion', 0) > 0:
            fila('PREMIO PRODUCCION', '', '', haberes=liq['importe_premio_produccion'])
        if liq.get('importe_cifra_fija', 0) > 0:
            fila('CIFRA FIJA', '', '', haberes=liq['importe_cifra_fija'])
        if liq.get('importe_trabajos_varios', 0) > 0:
            fila('TRABAJOS VARIOS', '', '', haberes=liq['importe_trabajos_varios'])
        if liq.get('importe_viaticos', 0) > 0:
            fila('VIATICOS', '', '', haberes=liq['importe_viaticos'])
        if liq.get('importe_remplazo_encargado', 0) > 0:
            fila('REMPLAZO ENCARGADO', '', '', haberes=liq['importe_remplazo_encargado'])
        if liq.get('importe_vacaciones', 0) > 0:
            fila('VACACIONES', liq.get('dias_vacaciones', 0), '', haberes=liq['importe_vacaciones'])

        # Conceptos libres: pueden ser haber (positivo) o deduccion (negativo)
        for i in (1, 2):
            c_nom = liq.get(f'concepto_libre_{i}_nombre') or f'C. LIBRE {i}'
            c_imp = liq.get(f'concepto_libre_{i}_importe', 0) or 0
            if c_imp > 0:
                fila(c_nom, '', '', haberes=c_imp)
            elif c_imp < 0:
                fila(c_nom, '', '', deducciones=abs(c_imp))

        # ── DEDUCCIONES ──
        imp_jub = liq.get('importe_jubilacion', 0) or 0
        if imp_jub != 0:
            if imp_jub > 0:
                fila('JUBILACION', '', '', deducciones=imp_jub)
            else:
                fila('JUBILACION', '', '', haberes=abs(imp_jub))

        imp_os = liq.get('importe_obra_social', 0) or 0
        if imp_os != 0:
            if imp_os > 0:
                fila('OBRA SOCIAL', '', '', deducciones=imp_os)
            else:
                fila('OBRA SOCIAL', '', '', haberes=abs(imp_os))

        imp_seg = liq.get('importe_seguro', 0) or 0
        if imp_seg != 0:
            if imp_seg > 0:
                fila('SEGURO', '', '', deducciones=imp_seg)
            else:
                fila('SEGURO', '', '', haberes=abs(imp_seg))

        if liq.get('importe_anticipos', 0) > 0:
            fila('ANTICIPOS', '', '', deducciones=liq['importe_anticipos'])
        if liq.get('importe_acreditacion_banco', 0) > 0:
            fila('ACREDITACION BANCO', '', '', deducciones=liq['importe_acreditacion_banco'])
        if liq.get('importe_descuento_premio_prod', 0) > 0:
            fila('DESC. PREM. PROD.', '', '', deducciones=liq['importe_descuento_premio_prod'])

        imp_otros = liq.get('importe_otros', 0) or 0
        if imp_otros != 0:
            if imp_otros > 0:
                fila('OTROS CONCEPTOS', '', '', haberes=imp_otros)
            else:
                fila('OTROS CONCEPTOS', '', '', deducciones=abs(imp_otros))

        # Relleno para mantener estructura si hay pocas filas
        while row_i[0] < 14:
            fila('', '', '', 0, 0)

        y = y_ref[0]
        # Borde contenedor (header + filas)
        self.set_draw_color(*self.SLATE_LINE)
        self.rect(ml, y - row_h * row_i[0] - head_h, aw, row_h * row_i[0] + head_h)

        # Subtotales
        sub_h = 5
        self._fill(ml, y, aw, sub_h, self.SUBTOTAL_BG)
        self.set_font('Helvetica', 'B', 7.5)
        self.set_xy(ml, y)
        self.cell(conc_w + cant_w + pct_w, sub_h, '  SUBTOTALES', 0, 0, 'L')
        self.cell(hab_w, sub_h, f"$ {_fmt_ar(liq.get('total_haberes', 0))}", 0, 0, 'R')
        self.cell(ded_w, sub_h, f"$ {_fmt_ar(liq.get('total_deducciones', 0))}  ", 0, 1, 'R')
        y += sub_h + 2

        # ══════════════════════════════════════════
        # 4. CIERRE: son pesos / neto a cobrar
        # ══════════════════════════════════════════
        cierre_h = 14
        left_w = aw - 68
        neto_w = 68

        self.set_draw_color(*self.SLATE_LINE)
        self.rect(ml, y, left_w, cierre_h)

        neto_val = liq.get('total_neto', 0) or 0
        letras = _numero_a_letras(neto_val)

        self.set_font('Helvetica', 'B', 6.5)
        self.set_text_color(*self.TEXT_MUTED)
        self.set_xy(ml + 2, y + 1)
        self.cell(left_w - 4, 3, 'SON PESOS', 0, 1, 'L')
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', 'B', 7.5)
        self.set_xy(ml + 2, y + 4)
        self.cell(left_w - 4, 3.5, _ascii(letras + ' CON 00/100'), 0, 1, 'L')

        hoy_str = datetime.now().strftime('%d/%m/%Y')
        self.set_font('Helvetica', '', 7)
        self.set_text_color(*self.TEXT_MUTED)
        self.set_xy(ml + 2, y + 8.5)
        self.cell(left_w - 4, 3, 'LUGAR Y FECHA DE PAGO', 0, 1, 'L')
        self.set_text_color(0, 0, 0)
        self.set_font('Helvetica', 'B', 8)
        self.set_xy(ml + 2, y + 11)
        self.cell(left_w - 4, 3, f'V.G. GALVEZ,  {hoy_str}', 0, 1, 'L')

        neto_x = ml + left_w + 2
        neto_real_w = neto_w - 2
        self._fill(neto_x, y, neto_real_w, cierre_h, self.ACCENT_BG)
        self.set_draw_color(*self.SLATE_DARK)
        self.rect(neto_x, y, neto_real_w, cierre_h)

        self.set_font('Helvetica', 'B', 7)
        self.set_text_color(*self.TEXT_MUTED)
        self.set_xy(neto_x, y + 1)
        self.cell(neto_real_w, 3, 'NETO A COBRAR', 0, 1, 'C')
        self.set_text_color(*self.SLATE_DARK)
        self.set_font('Helvetica', 'B', 16)
        self.set_xy(neto_x, y + 4.5)
        self.cell(neto_real_w, 8, f'$ {_fmt_ar(neto_val)}', 0, 1, 'C')

        self.set_text_color(0, 0, 0)
        y += cierre_h + 1

        # ══════════════════════════════════════════
        # 5. OBSERVACIONES + FIRMA UNICA DEL EMPLEADO
        # ══════════════════════════════════════════
        obs = liq.get('observaciones', '') or ''
        if obs:
            self.set_font('Helvetica', 'I', 6.5)
            self.set_text_color(*self.TEXT_MUTED)
            self.set_xy(ml, y)
            self.cell(aw, 3, f'Observaciones: {_ascii(obs)}', 0, 1, 'L')
            self.set_text_color(0, 0, 0)
            y += 3

        # Leyenda Art. 140 LCT
        legend_y = page_h - 22
        self.set_font('Helvetica', 'I', 6)
        self.set_text_color(*self.TEXT_MUTED)
        self.set_xy(ml, legend_y)
        self.cell(aw, 3, 'Recibi conforme el importe del presente recibo - Art. 140 L.C.T.', 0, 1, 'R')
        self.set_text_color(0, 0, 0)

        # Firma UNICA del empleado, centrada y mas abajo
        firma_y = page_h - 11
        f_w = 85
        f_x = ml + (aw - f_w) / 2
        self.set_draw_color(120, 120, 120)
        self.line(f_x, firma_y, f_x + f_w, firma_y)
        self.set_font('Helvetica', 'B', 7.5)
        self.set_xy(f_x, firma_y + 0.8)
        self.cell(f_w, 3, 'FIRMA  DEL  EMPLEADO', 0, 0, 'C')
        # Apellido y nombre en fuente mas grande
        self.set_font('Helvetica', 'B', 9)
        self.set_text_color(0, 0, 0)
        self.set_xy(f_x, firma_y + 4.2)
        self.cell(f_w, 3.5, nombre, 0, 0, 'C')
        self.set_font('Helvetica', '', 6.5)
        self.set_text_color(*self.TEXT_MUTED)
        self.set_xy(f_x, firma_y + 7.8)
        self.cell(f_w, 2.5, f'CUIL {cuil}', 0, 0, 'C')
        self.set_text_color(0, 0, 0)



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
