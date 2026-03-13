"""
import_data.py - Importación de datos iniciales desde Excel y PDF.
"""
import pandas as pd
import re
import database as db


def validar_cuil(cuil_str):
    """
    Valida un CUIL argentino.
    Formato esperado: XX-XXXXXXXX-X o XXXXXXXXXXX (11 dígitos).
    Retorna True si el formato es válido, False en caso contrario.
    """
    if not cuil_str or pd.isna(cuil_str):
        return False

    cuil_str = str(cuil_str).strip()

    # Quitar guiones
    cuil_limpio = cuil_str.replace("-", "")

    # Verificar que tenga 11 dígitos
    if not cuil_limpio.isdigit() or len(cuil_limpio) != 11:
        return False

    # Verificar dígito verificador
    multiplicadores = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    suma = sum(int(cuil_limpio[i]) * multiplicadores[i] for i in range(10))
    resto = suma % 11
    if resto == 0:
        digito_esperado = 0
    elif resto == 1:
        digito_esperado = 9 if cuil_limpio[:2] == '23' else 4
    else:
        digito_esperado = 11 - resto

    return int(cuil_limpio[10]) == digito_esperado


def normalizar_cuil(cuil_str):
    """Normaliza un CUIL a formato XX-XXXXXXXX-X."""
    if not cuil_str or pd.isna(cuil_str):
        return ""
    # Eliminar guiones, puntos y espacios
    cuil_str = str(cuil_str).strip().replace("-", "").replace(".", "").replace(" ", "")
    if len(cuil_str) == 11 and cuil_str.isdigit():
        return f"{cuil_str[:2]}-{cuil_str[2:10]}-{cuil_str[10]}"
    return str(cuil_str).strip()


def mapear_categoria_excel_a_convenio(cat_excel):
    """
    Mapea el nombre de categoría del Excel al nombre del convenio.
    """
    mapeo = {
        'OPERARIO': 'OPERARIO',
        'AUXILIAR': 'AUXILIAR',
        'OPERADOR': 'OPERADOR',
        'OP.CALIFICADO': 'OPERADOR CALIFICADO',
        'OP.ESPECIALIZADO': 'OPERADOR ESPECIALIZADO',
        'OF.ESPECIALIZADO': 'OFICIAL ESPECIALIZADO',
        'OFIC.DE MANT.': 'OFICIAL DE MANTENIMIENTO',
        'MED.OF.MANT.': 'MEDIO OFICIAL DE MANTENIMIENTO',
        'ADM.NIVEL  1': 'NIVEL 1',
        'ADM. NIVEL 1': 'NIVEL 1',
        'ADM.NIVEL  2': 'NIVEL 2',
        'ADM. NIVEL 2': 'NIVEL 2',
        'ADM.NIVEL  3': 'NIVEL 3',
        'ADM. NIVEL 3': 'NIVEL 3',
        'ADM. NIVEL 4': 'NIVEL 4',
        'ADM.NIVEL  4': 'NIVEL 4',
        'CAPATAZ': 'CAPATAZ',
        'CHOFER': 'CHOFER',
        'COND.DE AUTOELEVADOR': 'CONDUCTOR DE AUTOELEVADOR',
        'JEFE PRODUCCION': 'JEFE PRODUCCION',
        'JEFE MATRICERIA': 'JEFE MATRICERIA',
        'JEFE RRHH': 'JEFE RRHH',
        'ENCARG. COMPRAS': 'ENCARGADO COMPRAS',
        'GERENTE': 'GERENTE',
    }
    if not cat_excel or pd.isna(cat_excel):
        return None
    cat_limpia = str(cat_excel).strip()
    return mapeo.get(cat_limpia, cat_limpia)


def determinar_tipo_empleado(cuil_str, seccion):
    """
    Determina el tipo de empleado según el CUIL y la sección.
    Si el CUIL dice EVENTUAL o no es válido, será JORNAL pero con observación.
    Las categorías administrativas se clasifican como MENSUALIZADO.
    """
    cuil = str(cuil_str).strip() if cuil_str and not pd.isna(cuil_str) else ""

    if cuil.upper() == 'EVENTUAL':
        return 'EVENTUAL'

    # Los de SDO.FUERA SIJIP son un caso especial (mensualizados fuera de convenio)
    if seccion and str(seccion).strip().upper() == 'SDO.FUERA SIJIP':
        return 'MENSUALIZADO'

    return 'JORNAL'  # Por defecto; se puede ajustar manualmente


def importar_personal_excel(filepath):
    """
    Importa el archivo Excel de datos del personal.
    Retorna: (cantidad_importados, lista_errores_cuil)
    """
    df = pd.read_excel(filepath)

    # Renombrar columnas para uniformidad
    col_map = {}
    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'personal' in col_lower:
            col_map[col] = 'personal'
        elif 'c.u.i.l' in col_lower or 'cuil' in col_lower:
            col_map[col] = 'cuil'
        elif 'seccion' in col_lower or 'sección' in col_lower:
            col_map[col] = 'seccion'
        elif 'categoria' in col_lower or 'categoría' in col_lower:
            col_map[col] = 'categoria'
        elif 'fecha' in col_lower and 'ingreso' in col_lower:
            col_map[col] = 'fecha_ingreso'
        elif 'diferencia' in col_lower or 'dif' in col_lower:
            col_map[col] = 'diferencia_sueldo'
        elif 'premio' in col_lower or 'product' in col_lower:
            col_map[col] = 'premio_produccion'
        elif 'seguro' in col_lower:
            col_map[col] = 'seguro'
        elif 'cifra' in col_lower or 'fija' in col_lower:
            col_map[col] = 'cifra_fija'

    df.rename(columns=col_map, inplace=True)

    # Las columnas "Otro" y "Otro.1" las mapeo a conceptos libres
    otros_cols = [c for c in df.columns if str(c).lower().startswith('otro')]

    importados = 0
    errores_cuil = []

    for _, row in df.iterrows():
        nombre = str(row.get('personal', '')).strip()
        if not nombre:
            continue

        cuil_raw = row.get('cuil', '')
        cuil_str = str(cuil_raw).strip() if cuil_raw and not pd.isna(cuil_raw) else ""
        seccion = str(row.get('seccion', '')).strip() if not pd.isna(row.get('seccion', '')) else ''
        categoria_excel = row.get('categoria', '')
        categoria = mapear_categoria_excel_a_convenio(categoria_excel)

        # Fecha de ingreso
        fecha_ingreso = None
        if 'fecha_ingreso' in row and not pd.isna(row['fecha_ingreso']):
            try:
                fecha_ingreso = pd.to_datetime(row['fecha_ingreso']).strftime('%Y-%m-%d')
            except Exception:
                fecha_ingreso = None

        # Determinar tipo
        tipo = determinar_tipo_empleado(cuil_str, seccion)

        # Normalizar CUIL
        cuil_normalizado = normalizar_cuil(cuil_str) if cuil_str.upper() != 'EVENTUAL' else ''

        # Validar CUIL
        cuil_ok = validar_cuil(cuil_normalizado) if cuil_normalizado else False
        if not cuil_ok and tipo != 'EVENTUAL' and cuil_str.upper() != 'EVENTUAL':
            errores_cuil.append({
                'nombre': nombre,
                'cuil_original': cuil_str,
                'motivo': 'CUIL vacío o inválido'
            })

        # Valores numéricos
        dif_sueldo = float(row.get('diferencia_sueldo', 0) or 0) if not pd.isna(row.get('diferencia_sueldo', 0)) else 0
        premio = float(row.get('premio_produccion', 0) or 0) if not pd.isna(row.get('premio_produccion', 0)) else 0
        seguro = float(row.get('seguro', 0) or 0) if not pd.isna(row.get('seguro', 0)) else 0
        cifra_fija = float(row.get('cifra_fija', 0) or 0) if not pd.isna(row.get('cifra_fija', 0)) else 0

        data = {
            'apellido_nombre': nombre,
            'cuil': cuil_normalizado,
            'tipo': tipo,
            'seccion': seccion,
            'categoria': categoria if categoria else (str(categoria_excel).strip() if not pd.isna(categoria_excel) else ''),
            'fecha_ingreso': fecha_ingreso,
            'liquida_mensual': 1 if tipo == 'MENSUALIZADO' else 0,
            'liquida_antiguedad_basico': 0 if tipo == 'EVENTUAL' else 1,
            'liquida_presentismo': 0 if tipo == 'EVENTUAL' else 1,
            'estado': 'ACTIVO',
            'diferencia_sueldo': dif_sueldo,
            'premio_produccion': premio,
            'cifra_fija': cifra_fija,
            'seguro': seguro,
            'jubilacion': 0,
            'obra_social': 0,
        }

        # Lógica de Actualización (Upsert)
        existentes = db.get_empleados(busqueda=nombre)
        match = None
        for e in existentes:
            if e['apellido_nombre'].upper().strip() == nombre.upper().strip():
                match = e
                break
        
        if match:
            db.actualizar_empleado(match['id'], data)
        else:
            db.crear_empleado(data)
            
        importados += 1

    return importados, errores_cuil


def cargar_categorias_convenio():
    """
    Carga las categorías y valores del convenio desde los datos extraídos del PDF.
    Valores vigentes a febrero 2026.
    """
    # Datos extraídos del PDF del convenio CCT 797/22
    categorias_produccion = [
        # (nombre, valor_hora_feb2026)
        ('OPERARIO', 5643.34),
        ('AUXILIAR', 6085.10),
        ('OPERADOR', 6548.30),
        ('OPERADOR CALIFICADO', 6841.23),
        ('OPERADOR ESPECIALIZADO', 7127.34),
        ('OFICIAL ESPECIALIZADO', 7910.35),
    ]

    categorias_mantenimiento = [
        ('MEDIO OFICIAL DE MANTENIMIENTO', 7367.19),
        ('OFICIAL DE MANTENIMIENTO', 7912.14),
    ]

    categorias_administrativas = [
        # (nombre, valor_mensual_feb2026)
        ('NIVEL 1', 1128961),
        ('NIVEL 2', 1146237),
        ('NIVEL 3', 1210515),
        ('NIVEL 4', 1259382),
        ('NIVEL 5', 1384917),
        ('CAPATAZ', 1413840),
        ('CHOFER', 1269108),
        ('AYUDANTE DE CHOFER', 1142832),
        ('CONDUCTOR DE AUTOELEVADOR', 1417181),
    ]

    # Categorías adicionales que están en el Excel pero no en el convenio
    categorias_extra = [
        ('JEFE PRODUCCION', 'OTRA'),
        ('JEFE MATRICERIA', 'OTRA'),
        ('JEFE RRHH', 'OTRA'),
        ('ENCARGADO COMPRAS', 'OTRA'),
        ('GERENTE', 'OTRA'),
    ]

    creadas = 0

    # Producción
    for nombre, valor_hora in categorias_produccion:
        existing = db.get_categoria_por_nombre(nombre)
        if not existing:
            cat_id = db.crear_categoria(nombre, 'PRODUCCION')
            db.crear_valor_categoria(cat_id, valor_hora, 0, 2, 2026)
            creadas += 1

    # Mantenimiento
    for nombre, valor_hora in categorias_mantenimiento:
        existing = db.get_categoria_por_nombre(nombre)
        if not existing:
            cat_id = db.crear_categoria(nombre, 'MANTENIMIENTO')
            db.crear_valor_categoria(cat_id, valor_hora, 0, 2, 2026)
            creadas += 1

    # Administrativas
    for nombre, valor_mensual in categorias_administrativas:
        existing = db.get_categoria_por_nombre(nombre)
        if not existing:
            cat_id = db.crear_categoria(nombre, 'ADMINISTRATIVAS')
            db.crear_valor_categoria(cat_id, 0, valor_mensual, 2, 2026)
            creadas += 1

    # Categorías extra (sin valores del convenio)
    for nombre, grupo in categorias_extra:
        existing = db.get_categoria_por_nombre(nombre)
        if not existing:
            db.crear_categoria(nombre, grupo)
            creadas += 1

    return creadas


def aplicar_aumento_fuera_convenio(mes_nuevo, anio_nuevo):
    """
    Calcula el porcentaje de aumento promedio entre los valores del nuevo mes
    y los anteriores, y lo aplica a los sueldo_base de los fuera de convenio.
    """
    print(f"Calculando aumento proporcional para fuera de convenio ({mes_nuevo}/{anio_nuevo})...")
    
    # Calcular mes anterior
    mes_ant = mes_nuevo - 1
    anio_ant = anio_nuevo
    if mes_ant == 0:
        mes_ant = 12
        anio_ant = anio_nuevo - 1

    categorias = db.get_categorias()
    incrementos = []

    for cat in categorias:
        val_nuevo = db.get_valor_categoria(cat['nombre'], mes_nuevo, anio_nuevo)
        # Buscar el valor estrictamente anterior (evitando que get_valor_categoria nos devuelva el mismo nuevo si no hay anterior)
        # get_valor_categoria devuelve el último si no encuentra exacto. 
        # Vamos a forzar la búsqueda del anterior en database.py o aquí mismo.
        
        # Para simplificar, comparamos el valor nuevo con el valor registrado antes de este mes.
        val_ant = None
        conn = db.get_connection()
        row_ant = conn.execute("""
            SELECT cv.* FROM categoria_valores cv
            JOIN categorias c ON cv.categoria_id = c.id
            WHERE c.nombre = ? AND (cv.vigencia_anio < ? OR (cv.vigencia_anio = ? AND cv.vigencia_mes < ?))
            ORDER BY cv.vigencia_anio DESC, cv.vigencia_mes DESC LIMIT 1
        """, (cat['nombre'], anio_nuevo, anio_nuevo, mes_nuevo)).fetchone()
        conn.close()
        
        if row_ant:
            val_ant = dict(row_ant)

        if val_nuevo and val_ant:
            # Usar valor_mensual o valor_hora segun disponibilidad
            n = val_nuevo['valor_mensual'] if val_nuevo['valor_mensual'] > 0 else val_nuevo['valor_hora']
            a = val_ant['valor_mensual'] if val_ant['valor_mensual'] > 0 else val_ant['valor_hora']
            
            if a > 0 and n > a:
                incrementos.append(n / a)

    if not incrementos:
        print("No se detectaron incrementos de convenio para aplicar.")
        return 0, 0

    factor_promedio = sum(incrementos) / len(incrementos)
    porcentaje = (factor_promedio - 1) * 100
    
    # Aplicar a empleados fuera de convenio
    empleados = db.get_empleados()
    actualizados = 0
    for emp in empleados:
        emp_full = db.get_empleado(emp['id'])
        if emp_full.get('fuera_convenio') == 1 and emp_full.get('sueldo_base', 0) > 0:
            nuevo_sueldo = round(emp_full['sueldo_base'] * factor_promedio, 2)
            db.actualizar_empleado(emp['id'], {'sueldo_base': nuevo_sueldo})
            actualizados += 1
            
    print(f"Aumento del {porcentaje:.2f}% aplicado a {actualizados} empleados fuera de convenio.")
    return porcentaje, actualizados


def extraer_tabla_convenio_pdf(file_bytes):
    """
    Extrae una tabla de valores de convenio desde un PDF usando pdfplumber.
    Retorna un DataFrame con columnas estandarizadas, o None si no pudo extraer datos.
    
    Busca tablas con datos numéricos que parecen valores de hora/mensual.
    """
    try:
        import pdfplumber
        import io

        filas = []
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                tablas = page.extract_tables()
                for tabla in tablas:
                    if not tabla or len(tabla) < 2:
                        continue
                    # Primera fila como encabezado   
                    headers = [str(h).strip().lower() if h else '' for h in tabla[0]]
                    for row in tabla[1:]:
                        if len(row) < 2:
                            continue
                        fila_dict = {}
                        for i, val in enumerate(row):
                            if i < len(headers):
                                fila_dict[headers[i]] = val
                        filas.append(fila_dict)
        
        if not filas:
            return None
        
        df_raw = pd.DataFrame(filas)
        
        # Intentar normalizar a columnas estándar
        def _limpia_num(v):
            """Convierte formato argentino '1.234.567,89' a float."""
            if v is None or str(v).strip() in ('', '-', 'None'):
                return 0.0
            s = str(v).strip()
            # Quitar puntos de miles, reemplazar coma decimal
            s = s.replace('.', '').replace(',', '.')
            try:
                return float(s)
            except ValueError:
                return 0.0
        
        # Detectar columna de categoría
        col_cat_raw = next((c for c in df_raw.columns if any(k in c for k in ['categ', 'descrip', 'nombre', 'cargo'])), None)
        # Detectar columna de valor hora y mensual
        col_vh_raw = next((c for c in df_raw.columns if 'hora' in c), None)
        col_vm_raw = next((c for c in df_raw.columns if 'mensual' in c or 'sueldo' in c or 'basico' in c), None)
        # Detectar columnas de mes y año
        col_mes_raw = next((c for c in df_raw.columns if c in ('mes', 'mes vigencia')), None)
        col_anio_raw = next((c for c in df_raw.columns if c in ('año', 'anio', 'año vigencia')), None)
        
        if not col_cat_raw:
            # Sin columna de categoría identificable, retornar raw para que el usuario vea
            return df_raw
        
        # Construir DataFrame limpio
        rows_limpias = []
        for _, r in df_raw.iterrows():
            cat = str(r.get(col_cat_raw, '')).strip()
            if not cat or cat.lower() in ('none', 'nan', ''):
                continue
            rows_limpias.append({
                'Mes': int(_limpia_num(r.get(col_mes_raw))) if col_mes_raw else None,
                'Anio': int(_limpia_num(r.get(col_anio_raw))) if col_anio_raw else None,
                'Categoria': cat,
                'ValorHora': _limpia_num(r.get(col_vh_raw)) if col_vh_raw else 0.0,
                'ValorMensual': _limpia_num(r.get(col_vm_raw)) if col_vm_raw else 0.0,
            })
        
        if not rows_limpias:
            return df_raw  # Retornar raw para inspección
        
        return pd.DataFrame(rows_limpias)

    except Exception as e:
        raise RuntimeError(f"Error al leer PDF: {e}")


def procesar_excel_novedades(file_path):
    """
    Lee un Excel con novedades de liquidación y retorna un diccionario
    mapeando empleado_id -> dict de novedades.
    
    Columnas esperadas: CUIL, HS VACACIONES, HS EXTRAS 50%, HS EXTRAS 100%, 
    TRABAJOS VARIOS, VIATICOS, REMPLAZO ENCARGADO, OTRO CONCEPTO NOMBRE, OTRO CONCEPTO IMPORTE.
    """
    try:
        # Leemos las primeras 20 filas sin cabecera para buscar dónde están los títulos reales
        df_raw = pd.read_excel(file_path, header=None, nrows=20)
        header_idx = 0
        for idx, row in df_raw.iterrows():
            row_str = " ".join([str(val).upper() for val in row if pd.notna(val)])
            # Buscamos palabras clave que indiquen que esta es la fila de encabezados
            if any(x in row_str for x in ['CUIL', 'NOMBRE', 'APELLIDO', 'EMPLEADO']):
                header_idx = idx
                break
                
        # Ahora sí leemos el Excel usando la fila correcta como cabecera
        df = pd.read_excel(file_path, header=header_idx)
    except Exception as e:
        return {"error": f"No se pudo leer el Excel: {str(e)}"}

    # Mapeo de columnas (normalización de nombres por si hay variaciones de espacios/mayúsculas)
    # Buscamos columnas que contengan ciertos términos
    col_cuil = next((c for c in df.columns if 'CUIL' in str(c).upper()), None)
    col_nombre = next((c for c in df.columns if any(x in str(c).upper().strip() for x in ['NOMBRE', 'APELLIDO', 'EMPLEADO', 'PERSONAL', 'LEGAJO'])), None)
    
    if not col_cuil and not col_nombre:
        return {"error": "No se encontró la columna 'CUIL' ni 'Nombre' en el archivo."}

    def _norm_nombre(n):
        if pd.isna(n): return ""
        import unicodedata
        import re
        # Normalizar a NFKD y eliminar marcas (acentos)
        n_norm = unicodedata.normalize('NFKD', str(n))
        n_str = "".join([c for c in n_norm if not unicodedata.combining(c)])
        n_str = n_str.upper().replace(',', ' ').replace('.', ' ')
        return re.sub(r'\s+', ' ', n_str).strip()

    def _get_words(n):
        # Retorna el set de palabras significativas (más de 2 letras)
        return set(w for w in _norm_nombre(n).split() if len(w) > 2)

    novedades_por_emp = {}
    diagnostico = {
        'procesados': 0,
        'macheos_exitosos': [],
        'no_encontrados': [],
        'errores': []
    }
    empleados_db = db.get_empleados()
    
    # Mapeos para búsqueda rápida
    cuil_to_id = {normalizar_cuil(e['cuil']): e['id'] for e in empleados_db if e.get('cuil')}
    nombre_to_id = {_norm_nombre(e['apellido_nombre']): e['id'] for e in empleados_db if e.get('apellido_nombre')}
    db_words = {e['id']: _get_words(e['apellido_nombre']) for e in empleados_db}

    for _, row in df.iterrows():
        cuil_raw = row.get(col_cuil) if col_cuil else None
        nombre_raw = row.get(col_nombre) if col_nombre else None
        
        is_cuil_empty = pd.isna(cuil_raw) or str(cuil_raw).strip() == ""
        is_nombre_empty = pd.isna(nombre_raw) or str(nombre_raw).strip() == ""
        
        if is_cuil_empty and is_nombre_empty: 
            continue
            
        nombre_str = _norm_nombre(nombre_raw)
        
        # Saltarse filas que parecen cabeceras o títulos (solo si la fila entera se parece a cabeceras)
        fila_str = " ".join([str(v).upper() for v in row if pd.notna(v)])
        if len(nombre_str) < 3 or (any(x in nombre_str for x in ['CUIL', 'LEGAJO']) and len(nombre_str) < 15):
            continue
        if 'CATEGORIA' in fila_str and 'SUELDO' in fila_str: # Probable cabecera repetida
            continue

        emp_id = None
        
        # 1. Intentar buscar por CUIL
        if not is_cuil_empty:
            cuil = normalizar_cuil(cuil_raw)
            # Re-normalizar: solo números
            cuil_solo_numeros = "".join(filter(str.isdigit, str(cuil_raw)))
            
            emp_id = cuil_to_id.get(cuil)
            if not emp_id and len(cuil_solo_numeros) == 11:
                # Probar formateado estándar
                cuil_f = f"{cuil_solo_numeros[:2]}-{cuil_solo_numeros[2:10]}-{cuil_solo_numeros[10]}"
                emp_id = cuil_to_id.get(cuil_f)
            
            if not emp_id:
                # Búsqueda inversa: ver si el CUIL sin guiones del Excel está en algún CUIL de la DB
                for db_cuil, db_id in cuil_to_id.items():
                    if cuil_solo_numeros == "".join(filter(str.isdigit, str(db_cuil))):
                        emp_id = db_id
                        break
                    
        # 2. Si no lo encuentra o no hay CUIL, buscar por Nombre
        if not emp_id and nombre_str:
            # Match Exacto
            emp_id = nombre_to_id.get(nombre_str)
            
            # 2.5 Fuzzy/Word match si no lo encuentra exacto
            if not emp_id:
                words_excel = _get_words(nombre_raw)
                posibles = []
                if len(words_excel) >= 2:
                    for db_id, w_set in db_words.items():
                        # Si las palabras del Excel están contenidas en la DB o viceversa
                        if words_excel.issubset(w_set) or w_set.issubset(words_excel):
                            posibles.append(db_id)
                
                if len(posibles) == 1:
                    emp_id = posibles[0]
                elif len(posibles) == 0:
                    # Último intento: substring puro
                    for db_name, db_id in nombre_to_id.items():
                        if nombre_str in db_name or db_name in nombre_str:
                            posibles.append(db_id)
                    if len(posibles) == 1:
                        emp_id = posibles[0]
            
            # 3. Si tampoco existe, comprobar si amerita crearlo como Eventual
            # MODIFICACIÓN: Filtrar nombres que NO parecen personas (conceptos contables)
            forbidden_keywords = ['SUELDOS', 'SEGURO', 'ACRED', 'TOTAL', 'BANCO', 'SIJIP', 'QUINCENA']
            is_accounting_concept = any(k in nombre_str for k in forbidden_keywords)
            
            es_eventual_aparente = (is_cuil_empty or 'EVENTUAL' in str(cuil_raw).strip().upper()) and not is_accounting_concept
            
            if not emp_id and es_eventual_aparente and len(nombre_str) > 5:
                nuevo_emp = {
                    'apellido_nombre': str(nombre_raw).strip(),
                    'cuil': '',
                    'tipo': 'JORNAL',
                    'condicion': 'EVENTUAL',
                    'estado': 'ACTIVO',
                    'seccion': 'FABRICA',
                    'categoria': 'OPERARIO'
                }
                try:
                    emp_id = db.crear_empleado(nuevo_emp)
                    # Actualizar diccionarios en memoria
                    emp_full = db.get_empleado_por_id(emp_id)
                    nombre_to_id[nombre_str] = emp_id
                    db_words[emp_id] = _get_words(nombre_raw)
                except Exception as e:
                    continue

        if emp_id:
            def _get_val(keys):
                for k in keys:
                    for c in df.columns:
                        if k.upper() in str(c).upper().replace(' ', ''):
                            val = row[c]
                            if pd.isna(val) or str(val).strip() == '':
                                continue
                            val_str = str(val).replace('$', '').replace(' ', '').replace(',', '.')
                            try:
                                return float(val_str)
                            except ValueError:
                                continue
                return 0.0

            row_novs = {
                'dias_vacaciones': _get_val(['DIASVACACIONES', 'VACACIONES', 'VAC']),
                'horas_extra_50': _get_val(['50%', '50', 'HS50', 'HORAS50']),
                'horas_extra_100': _get_val(['100%', '100', 'HS100', 'HORAS100']),
                'trabajos_varios': _get_val(['TRABAJOSVARIOS', 'VARIOS', 'TRABVARIOS']),
                'viaticos': _get_val(['C2VIATICOS', 'VIATICOS', 'VIATICO']),
                'remplazo_encargado': _get_val(['REMPLAZOENCARGADO', 'REEMPLAZO', 'REEMPLAZOENCARGADO', 'ENCARGADO']),
                'concepto_libre_1_nombre': str(row.get('OTRO CONCEPTO NOMBRE', '')) if pd.notna(row.get('OTRO CONCEPTO NOMBRE')) else '',
                'concepto_libre_1_importe': float(row.get('OTRO CONCEPTO IMPORTE', 0)) if pd.notna(row.get('OTRO CONCEPTO IMPORTE')) else 0.0
            }
            
            # FILTRO DE SEGURIDAD REBAJADO: Solo omitir si la fila es genuinamente vacía
            # No omitiremos si hay ceros, para capturar a empleados que vengan sin horas
            # pero identificados por nombre/CUIL.
            has_numeric_cols = any(isinstance(v, (int, float)) and pd.notna(v) for v in row)
            if not has_numeric_cols:
                diagnostico['no_encontrados'].append(f"Fila {_+header_idx+2}: Vacía o sin números")
                continue

            if emp_id not in novedades_por_emp:
                novedades_por_emp[emp_id] = row_novs
            else:
                # Sumar valores si el empleado aparece más de una vez (ej: Caruso en dos planillas unificadas)
                for k, v in row_novs.items():
                    if isinstance(v, (int, float)) and k != 'concepto_libre_1_importe':
                        novedades_por_emp[emp_id][k] += v
                # Tratar importe libre aparte
                if row_novs['concepto_libre_1_importe'] > 0:
                    novedades_por_emp[emp_id]['concepto_libre_1_importe'] += row_novs['concepto_libre_1_importe']
                    if not novedades_por_emp[emp_id]['concepto_libre_1_nombre']:
                         novedades_por_emp[emp_id]['concepto_libre_1_nombre'] = row_novs['concepto_libre_1_nombre']
            
            # Registrar éxito con montos para diagnóstico
            emp_info = next((e for e in empleados_db if e['id'] == emp_id), None)
            nombre_db = emp_info['apellido_nombre'] if emp_info else "ID " + str(emp_id)
            
            vals_desc = []
            if row_novs['horas_extra_50'] > 0: vals_desc.append(f"50%:{row_novs['horas_extra_50']}")
            if row_novs['horas_extra_100'] > 0: vals_desc.append(f"100%:{row_novs['horas_extra_100']}")
            if row_novs['viaticos'] > 0: vals_desc.append(f"Viat:{row_novs['viaticos']}")
            
            desc_total = f" ({', '.join(vals_desc)})" if vals_desc else ""
            diagnostico['macheos_exitosos'].append(f"{str(nombre_raw).strip()} -> {nombre_db}{desc_total}")
        else:
            razon = "No se encontró CUIL ni nombre similar"
            if not is_cuil_empty and not is_nombre_empty:
                razon = f"CUIL {cuil_raw} no existe y nombre '{nombre_raw}' no tiene coincidencias"
            elif is_cuil_empty:
                razon = f"Sin CUIL y nombre '{nombre_raw}' sin coincidencias"
            
            diagnostico['no_encontrados'].append(f"{str(nombre_raw).strip()} ({razon})")
        
        diagnostico['procesados'] += 1

    return {"novedades": novedades_por_emp, "diagnostico": diagnostico}
