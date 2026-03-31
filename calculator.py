"""
calculator.py - Motor de cálculo de liquidación de sueldos.
Implementa las reglas de cálculo de haberes, deducciones y antigüedad.
"""
from datetime import date, datetime
import database as db


def calcular_antiguedad_anios(fecha_ingreso, fecha_referencia):
    """
    Calcula los años completos de antigüedad al último día del mes de referencia.
    """
    if not fecha_ingreso:
        return 0

    if isinstance(fecha_ingreso, str) and fecha_ingreso:
        # Intentar varios formatos comunes
        for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%Y/%m/%d'):
            try:
                fecha_ingreso = datetime.strptime(fecha_ingreso, fmt).date()
                break
            except ValueError:
                continue
        if isinstance(fecha_ingreso, str):
            return 0

    if isinstance(fecha_referencia, str):
        fecha_referencia = datetime.strptime(fecha_referencia, '%Y-%m-%d').date()

    # Último día del mes de referencia
    if fecha_referencia.month == 12:
        ultimo_dia = date(fecha_referencia.year, 12, 31)
    else:
        ultimo_dia = date(fecha_referencia.year, fecha_referencia.month + 1, 1)
        from datetime import timedelta
        ultimo_dia = ultimo_dia - timedelta(days=1)

    # Años completos
    anios = ultimo_dia.year - fecha_ingreso.year
    if (ultimo_dia.month, ultimo_dia.day) < (fecha_ingreso.month, fecha_ingreso.day):
        anios -= 1

    return max(0, anios)


def calcular_liquidacion(empleado, periodo_mes, periodo_anio, novedades):
    """
    Calcula todos los conceptos de una liquidación.

    Args:
        empleado: dict con datos del empleado
        periodo_mes: mes del período
        periodo_anio: año del período
        novedades: dict con:
            - horas_comunes: float
            - horas_extra_50: float
            - horas_extra_100: float
            - trabajos_varios: float
            - viaticos: float
            - presentismo: float
            - prop_aguinaldo: float
            - concepto_libre_1_nombre: str
            - concepto_libre_1_importe: float
            - concepto_libre_2_nombre: str
            - concepto_libre_2_importe: float

    Returns:
        dict con todos los importes calculados
    """
    resultado = {}

    # ── Determinar tipo de liquidación ──
    from import_data import validar_cuil
    cuil = empleado.get('cuil', '')
    tipo = empleado.get('tipo', 'JORNAL')

    # Si no tiene CUIL válido al momento de liquidar => EVENTUAL
    if not validar_cuil(cuil) and tipo != 'MENSUALIZADO':
        tipo_liquidacion = 'EVENTUAL'
    else:
        tipo_liquidacion = tipo

    resultado['tipo_liquidacion'] = tipo_liquidacion

    # ── Obtener valores de la categoría ──
    categoria = empleado.get('categoria', '')
    valores = db.get_valor_categoria(categoria, periodo_mes, periodo_anio)

    valor_hora = valores['valor_hora'] if valores else 0
    valor_mensual = valores['valor_mensual'] if valores else 0

    # Si es FUERA DE CONVENIO, priorizar sueldo_base manual
    if empleado.get('fuera_convenio') == 1:
        if tipo_liquidacion == 'MENSUALIZADO':
            valor_mensual = float(empleado.get('sueldo_base', 0))
        else:
            valor_hora = float(empleado.get('sueldo_base', 0))

    # ── Horas y dias ──
    horas_comunes = float(novedades.get('horas_comunes', 0) or 0)
    horas_extra_50 = float(novedades.get('horas_extra_50', 0) or 0)
    horas_extra_100 = float(novedades.get('horas_extra_100', 0) or 0)
    dias_trabajados = float(novedades.get('dias_trabajados', 0) or 0)
    dias_vacaciones = float(novedades.get('dias_vacaciones', 0) or 0)

    resultado['horas_comunes'] = horas_comunes
    resultado['horas_extra_50'] = horas_extra_50
    resultado['horas_extra_100'] = horas_extra_100
    resultado['dias_trabajados'] = dias_trabajados

    # ── Calculo segun tipo ──
    importe_basico_mensual = 0
    importe_horas_comunes = 0

    if tipo_liquidacion == 'MENSUALIZADO':
        # Valor hora del mensualizado: basico / 187 (hs promedio del mes)
        if valor_mensual > 0:
            valor_hora = round(valor_mensual / 187.0, 2)

        # Basico proporcional segun dias trabajados (que app.py ya pre-completa con el legajo)
        dias_a_liq = dias_trabajados if dias_trabajados > 0 else float(empleado.get('dias_liquidacion_mensual', 30.0) or 30.0)

        if empleado.get('liquida_mensual', 0):
            importe_basico_mensual = valor_mensual * (dias_a_liq / 30.0)
            # Asegurar que el reporte refleje los dias que usamos para liquidar
            resultado['dias_trabajados'] = dias_a_liq
    else:
        # JORNAL / EVENTUAL: si no hay valor_hora pero sí valor_mensual, derivarlo
        if valor_hora == 0 and valor_mensual > 0:
            valor_hora = round(valor_mensual / 187.0, 2)
        # Calculo por horas comunes
        importe_horas_comunes = horas_comunes * valor_hora

    # Extras: ambos tipos usan valor_hora (para mensualizado es basico/187)
    importe_extra_50 = horas_extra_50 * valor_hora * 1.50
    importe_extra_100 = horas_extra_100 * valor_hora * 2.00

    resultado['valor_hora_usado'] = round(valor_hora, 2)
    resultado['valor_mensual_usado'] = valor_mensual
    resultado['importe_horas_comunes'] = round(importe_horas_comunes, 2)
    resultado['importe_extra_50'] = round(importe_extra_50, 2)
    resultado['importe_extra_100'] = round(importe_extra_100, 2)
    resultado['importe_basico_mensual'] = round(importe_basico_mensual, 2)

    resultado['dias_vacaciones'] = dias_vacaciones
    # Fórmula: (Días * 9hs * ValorHoraComun) + Antigüedad proporcional + Premio proporcional
    base_vaca = 0
    if dias_vacaciones > 0:
        if tipo_liquidacion == 'MENSUALIZADO':
            base_vaca = dias_vacaciones * (valor_mensual / 25.0)
        else:
            base_vaca = dias_vacaciones * 9.0 * valor_hora
    
    # Calcular proporcionales de antiguedad y presentismo para vacaciones
    # Regla: Base + (Base * %Antig) + (Base * %Presentismo)
    imp_ant_vaca = 0
    imp_pres_vaca = 0
    
    anios_ant = calcular_antiguedad_anios(empleado.get('fecha_ingreso'), date(periodo_anio, periodo_mes, 1))
    
    # Solo calcular si no es gerente Y tiene habilitada la antigüedad
    if empleado.get('categoria', '').upper() != 'GERENTE' and empleado.get('liquida_antiguedad_basico', 0):
        pct_ant = (anios_ant + (2 if anios_ant >= 10 else 0)) / 100.0
    else:
        pct_ant = 0
    
    if base_vaca > 0:
        imp_ant_vaca = base_vaca * pct_ant
        # Determinar presentismo proporcional (sobre base_vaca UNICAMENTE, sin antigüedad)
        pct_pres_vaca = float(empleado.get('porc_presentismo', 15.0)) / 100.0
        if empleado.get('liquida_presentismo', 0) and empleado.get('categoria', '').upper() != 'GERENTE':
            imp_pres_vaca = base_vaca * pct_pres_vaca

    importe_vacaciones = base_vaca + imp_ant_vaca + imp_pres_vaca
    resultado['importe_vacaciones'] = round(importe_vacaciones, 2)
    # Guardamos los proporcionales para eventuales diagnósticos
    resultado['_proporcional_ant_vaca'] = imp_ant_vaca
    resultado['_proporcional_pres_vaca'] = imp_pres_vaca

    # ── Antigüedad ──
    # Regla: 1% por cada año completo. A partir de 10 años se suma un 2% adicional fijo.
    fecha_ref = date(periodo_anio, periodo_mes, 1)
    anios_antiguedad = calcular_antiguedad_anios(empleado.get('fecha_ingreso'), fecha_ref)

    # Conceptos fijos que impactan bases
    dif_sueldo = float(empleado.get('diferencia_sueldo', 0) or 0)
    premio = float(empleado.get('premio_produccion', 0) or 0)
    cifra_fija = float(empleado.get('cifra_fija', 0) or 0)
    seguro = float(empleado.get('seguro', 0) or 0)
    jubilacion = float(empleado.get('jubilacion', 0) or 0)
    obra_social = float(empleado.get('obra_social', 0) or 0)
    desc_premio_prod = float(empleado.get('descuento_premio_prod', 0) or 0)

    if empleado.get('categoria', '').upper() == 'GERENTE' or not empleado.get('liquida_antiguedad_basico', 0) or tipo_liquidacion == 'EVENTUAL':
        porcentaje_antiguedad_pct = 0
    else:
        porcentaje_antiguedad_pct = anios_antiguedad
        if anios_antiguedad >= 10:
            porcentaje_antiguedad_pct += 2

    porcentaje_antiguedad = porcentaje_antiguedad_pct / 100.0
    resultado['porcentaje_antiguedad'] = round(porcentaje_antiguedad_pct, 2)

    importe_antiguedad_horas = 0
    importe_antiguedad_extras = 0
    importe_antiguedad_basico = 0
    importe_antiguedad_vaca = 0

    if porcentaje_antiguedad > 0:
        if tipo_liquidacion == 'MENSUALIZADO':
            if importe_basico_mensual > 0:
                importe_antiguedad_basico = importe_basico_mensual * porcentaje_antiguedad
        else:
            if horas_comunes > 0:
                # La diferencia de sueldo NO lleva antigüedad
                importe_antiguedad_basico = importe_horas_comunes * porcentaje_antiguedad
        
        # Antiguedad sobre extras (ambos tipos)
        if horas_extra_50 > 0 or horas_extra_100 > 0:
            importe_antiguedad_extras = ((horas_extra_50 + horas_extra_100) * porcentaje_antiguedad) * valor_hora
            
    resultado['importe_antiguedad_horas'] = round(importe_antiguedad_horas, 2)
    resultado['importe_antiguedad_extras'] = round(importe_antiguedad_extras, 2)
    resultado['importe_antiguedad_basico'] = round(importe_antiguedad_basico, 2)
    # Volvemos a incluir importe_antiguedad_vaca si fuera necesario, 
    # pero el usuario dice que Vacaciones es independiente.
    # Así que el rubro general solo lleva lo trabajado (con extras).
    resultado['importe_antiguedad_total'] = round(
        importe_antiguedad_horas + importe_antiguedad_extras + importe_antiguedad_basico, 2
    )

    # ── Conceptos fijos del empleado ──
    resultado['importe_diferencia_sueldo'] = round(dif_sueldo, 2)
    # Premio Producción: Pago mensual fijo (no se reduce por vacaciones)
    resultado['importe_premio_produccion'] = round(max(0, premio), 2)
    cifra_fija_efectiva = cifra_fija if empleado.get('cobra_cifra_fija', 0) == 1 else 0.0
    resultado['importe_cifra_fija'] = round(cifra_fija_efectiva, 2)
    resultado['importe_seguro'] = round(seguro, 2)
    resultado['importe_jubilacion'] = round(jubilacion, 2)
    resultado['importe_obra_social'] = round(obra_social, 2)

    # ── Conceptos variables (novedades de la quincena) ──
    trabajos_varios = float(novedades.get('trabajos_varios', 0) or 0)
    viaticos = float(novedades.get('viaticos', 0) or 0)
    hs_remplazo_encargado = float(novedades.get('remplazo_encargado', 0) or 0)
    prop_aguinaldo = float(novedades.get('prop_aguinaldo', 0) or 0)

    # Fórmula Remplazo Encargado: (Horas * ValHora50) + %Antigüedad + %Presentismo
    importe_remplazo = 0
    imp_ant_remplazo = 0
    imp_pres_remplazo = 0
    base_remplazo = 0

    if hs_remplazo_encargado > 0:
        # Base = horas * valor_hora * 1.5
        v_h_50 = valor_hora * 1.5
        base_remplazo = hs_remplazo_encargado * v_h_50
        
        # Proporcionales: Antigüedad sobre base 100%, Presentismo sobre base 150%
        imp_ant_remplazo = (hs_remplazo_encargado * valor_hora) * porcentaje_antiguedad
        imp_pres_remplazo = 0
        pct_pres = empleado.get('porc_presentismo', 15.0) / 100.0
        if empleado.get('liquida_presentismo', 0) and empleado.get('categoria', '').upper() != 'GERENTE':
            imp_pres_remplazo = base_remplazo * pct_pres
        
        importe_remplazo = base_remplazo + imp_ant_remplazo + imp_pres_remplazo

    resultado['importe_remplazo_encargado'] = round(importe_remplazo, 2)
    # Guardamos para descontar del total general y no duplicar
    resultado['_proporcional_ant_remplazo'] = imp_ant_remplazo
    resultado['_proporcional_pres_remplazo'] = imp_pres_remplazo

    # ── Presentismo automatico ──
    presentismo = 0
    pct_pres = empleado.get('porc_presentismo', 15.0) / 100.0
    if empleado.get('liquida_presentismo', 0) and empleado.get('categoria', '').upper() != 'GERENTE':
        # La base incluye Básico + Extras - NO incluye Antigüedad ni Vacaciones ni Diferencia Sueldo
        if tipo_liquidacion == 'MENSUALIZADO':
            base_presentismo = importe_basico_mensual + importe_extra_50 + importe_extra_100
        else:
            base_presentismo = importe_horas_comunes + importe_extra_50 + importe_extra_100
        presentismo = round(base_presentismo * pct_pres, 2)
    
    resultado['porcentaje_presentismo'] = float(empleado.get('porc_presentismo', 15.0))

    resultado['remplazo_encargado'] = hs_remplazo_encargado
    resultado['importe_trabajos_varios'] = round(trabajos_varios, 2)
    resultado['importe_viaticos'] = round(viaticos, 2)

    # Ya no restamos proporcionales porque no los incluimos en la base arriba
    resultado['importe_presentismo'] = round(max(0, presentismo), 2)
    resultado['importe_prop_aguinaldo'] = round(prop_aguinaldo, 2)

    # ── Conceptos libres ──
    cl1_nombre = novedades.get('concepto_libre_1_nombre', '')
    cl1_importe = float(novedades.get('concepto_libre_1_importe', 0) or 0)
    cl2_nombre = novedades.get('concepto_libre_2_nombre', '')
    cl2_importe = float(novedades.get('concepto_libre_2_importe', 0) or 0)

    resultado['concepto_libre_1_nombre'] = cl1_nombre
    resultado['concepto_libre_1_importe'] = round(cl1_importe, 2)
    resultado['concepto_libre_2_nombre'] = cl2_nombre
    resultado['concepto_libre_2_importe'] = round(cl2_importe, 2)

    # ── TOTAL HABERES ──
    total_haberes = (
        importe_horas_comunes +
        importe_basico_mensual +
        importe_extra_50 +
        importe_extra_100 +
        importe_vacaciones +
        resultado['importe_antiguedad_total'] +
        dif_sueldo +
        resultado['importe_premio_produccion'] +
        resultado.get('importe_remplazo_encargado', 0) +
        cifra_fija +
        trabajos_varios +
        viaticos +
        resultado.get('importe_presentismo', 0) +
        prop_aguinaldo +
        (cl1_importe if cl1_importe > 0 else 0) +
        (cl2_importe if cl2_importe > 0 else 0) +
        (empleado.get('otros', 0) if empleado.get('otros', 0) > 0 else 0) +
        (seguro if seguro > 0 else 0) +
        (jubilacion if jubilacion > 0 else 0) +
        (obra_social if obra_social > 0 else 0)
    )

    # ── TOTAL DEDUCCIONES ──
    otros_neg = abs(empleado.get('otros', 0)) if empleado.get('otros', 0) < 0 else 0
    seg_neg = abs(seguro) if seguro < 0 else 0
    jub_neg = abs(jubilacion) if jubilacion < 0 else 0
    os_neg = abs(obra_social) if obra_social < 0 else 0
    
    total_deducciones = seg_neg + jub_neg + os_neg + abs(empleado.get('anticipos', 0)) + abs(empleado.get('acreditacion_banco', 0)) + otros_neg + desc_premio_prod
    if cl1_importe < 0:
        total_deducciones += abs(cl1_importe)
    if cl2_importe < 0:
        total_deducciones += abs(cl2_importe)

    # ── TOTAL NETO Y REDONDEO ──
    real_neto = total_haberes - total_deducciones
    
    # Lógica de redondeo sobre números enteros (múltiplos de $50 o $100)
    # Umbrales solicitados: < 25 -> 00, >= 25 y < 75 -> 50, >= 75 -> 100
    # Ejemplo: 1021 -> 1000, 1045.50 -> 1050, 1080 -> 1100, 1060 -> 1050
    parte_entera = int(real_neto)
    resto = parte_entera % 100
    
    if resto < 25:
        neto_redondeado = (parte_entera // 100) * 100
    elif resto < 75:
        neto_redondeado = (parte_entera // 100) * 100 + 50
    else:
        neto_redondeado = (parte_entera // 100 + 1) * 100
        
    ajuste_redondeo = neto_redondeado - real_neto

    resultado['total_haberes'] = round(total_haberes, 2)
    resultado['total_deducciones'] = round(total_deducciones, 2)
    resultado['total_neto'] = float(neto_redondeado)
    resultado['redondeo'] = round(ajuste_redondeo, 2)
    
    resultado['importe_anticipos'] = round(abs(empleado.get('anticipos', 0)), 2)
    resultado['importe_acreditacion_banco'] = round(abs(empleado.get('acreditacion_banco', 0)), 2)
    resultado['importe_descuento_premio_prod'] = round(desc_premio_prod, 2)
    resultado['importe_otros'] = round(empleado.get('otros', 0), 2)
    resultado['observaciones'] = empleado.get('observaciones', '')
    
    return resultado
