python name=utils/data_processor.py url=https://github.com/iandcm15200/Depurador/blob/95d7d75c963781124bd7d529e77d7d24fa34e442/utils/data_processor.py
import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def _find_column(df: pd.DataFrame, candidates):
    """
    Busca en df.columns cualquiera de las cadenas en candidates (case-insensitive).
    Devuelve el nombre real de la columna si encuentra, sino None.
    """
    cols_low = {c.lower(): c for c in df.columns}
    for cand in candidates:
        for c_low, c_real in cols_low.items():
            if cand.lower() == c_low:
                return c_real
    # permitir coincidencia por contiene
    for cand in candidates:
        for c_low, c_real in cols_low.items():
            if cand.lower() in c_low:
                return c_real
    return None


def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None) -> pd.DataFrame:
    """
    Depura el DataFrame del CSV vwCRMLeads segun los requerimientos del usuario:
    - Detecta y parsea PaidDate (diferentes variantes)
    - Filtra últimos `hours` horas (por defecto 24) desde `timestamp_referencia`
    - Crea la columna 'Nombre Apellido' concatenando Apellido + ' ' + Nombre (si existen)
    - Elimina columnas que no pertenezcan al set final requerido
    - Elimina duplicados por LEAD (queda 1 registro por LEAD)
    - Devuelve el DF listo para mapear columnas finales (o ya con columnas finales)
    """
    try:
        df = df.copy()
        if timestamp_referencia is None:
            timestamp_referencia = datetime.now()

        logger.info(f"=== INICIANDO DEPURACIÓN ===")
        logger.info(f"Timestamp referencia: {timestamp_referencia}")
        logger.info(f"Filas originales: {len(df)}")

        # Normalizar nombres de columnas (trim)
        df.columns = [str(c).strip() for c in df.columns]

        # 1) Encontrar columna de PaidDate (busca por nombre exacto o por contiene)
        paid_candidates = ['PaidDate', 'paiddate', 'paid_date', 'Paid Date', 'FechaPago', 'Fecha Pago', 'paid']
        paid_col = _find_column(df, paid_candidates)

        if not paid_col:
            logger.warning("No se encontró columna PaidDate. Asegúrate que exista una columna con fecha de pago.")
            return pd.DataFrame()  # devolver vacío para que UI muestre sugerencias

        # 2) Parsear PaidDate a datetime
        # Intentar formatos previsibles
        df[paid_col] = df[paid_col].replace('', pd.NA)
        try:
            df[paid_col] = pd.to_datetime(df[paid_col], format='%d/%m/%Y %H:%M', errors='coerce')
        except Exception:
            df[paid_col] = pd.to_datetime(df[paid_col], dayfirst=True, errors='coerce')

        # Si demasiados nulos, intentar sin hora
        if df[paid_col].isna().sum() > len(df) * 0.5:
            df[paid_col] = pd.to_datetime(df[paid_col].astype(str).str.split().str[0], dayfirst=True, errors='coerce')

        nulos = df[paid_col].isna().sum()
        if nulos > 0:
            logger.warning(f"{nulos} filas con PaidDate inválido (serán descartadas)")

        # Renombrar a 'PaidDate' estándar
        if paid_col != 'PaidDate':
            df.rename(columns={paid_col: 'PaidDate'}, inplace=True)

        # Eliminar filas sin PaidDate válido
        df = df[df['PaidDate'].notna()]

        # 3) Aplicar filtro temporal (horas o días)
        antes = len(df)
        if hours is not None:
            fecha_limite = timestamp_referencia - timedelta(hours=hours)
            logger.info(f"Filtrando registros con PaidDate >= {fecha_limite} (últimas {hours} horas)")
            df = df[df['PaidDate'] >= fecha_limite]
        elif days is not None:
            fecha_limite = timestamp_referencia - timedelta(days=days)
            logger.info(f"Filtrando registros con PaidDate >= {fecha_limite} (últimos {days} días)")
            df = df[df['PaidDate'] >= fecha_limite]
        despues = len(df)
        logger.info(f"Filtro temporal aplicado: {antes} → {despues}")

        if df.empty:
            logger.info("No quedan registros después del filtro temporal.")
            return pd.DataFrame()

        # 4) Crear 'Nombre Apellido' concatenando Apellido + ' ' + Nombre (si existen)
        nombre_col = _find_column(df, ['Nombre', 'nombre', 'name'])
        apellido_col = _find_column(df, ['Apellido', 'apellido', 'last_name', 'lastname', 'apellido_paterno', 'Apellido Paterno'])
        if 'Nombre Apellido' not in df.columns:
            if apellido_col and nombre_col:
                df['Nombre Apellido'] = (df[apellido_col].fillna('').astype(str).str.strip() + ' ' +
                                         df[nombre_col].fillna('').astype(str).str.strip()).str.strip()
                logger.info("Creada columna 'Nombre Apellido' (Apellido + Nombre).")
            elif nombre_col:
                df['Nombre Apellido'] = df[nombre_col].astype(str).str.strip()
            elif apellido_col:
                df['Nombre Apellido'] = df[apellido_col].astype(str).str.strip()
            else:
                df['Nombre Apellido'] = ''

        # 5) Detectar columna LEAD (id) y normalizar
        lead_col = _find_column(df, ['LEAD', 'Lead', 'Id', 'ID', 'id'])
        if lead_col:
            df['LEAD'] = df[lead_col].astype(str).str.strip()
        else:
            # Si no hay LEAD, crear vacía (pero se recomienda tenerla)
            df['LEAD'] = ''

        # 6) Eliminar duplicados por LEAD (quedarse con la primera ocurrencia)
        if 'LEAD' in df.columns and df['LEAD'].astype(str).str.strip().replace('', pd.NA).notna().any():
            antes_dup = len(df)
            df = df.drop_duplicates(subset=['LEAD'], keep='first')
            despues_dup = len(df)
            logger.info(f"Duplicados por LEAD eliminados: {antes_dup - despues_dup}")
        else:
            logger.info("No se detectaron LEADs válidos para deduplicar (se omite deduplicación).")

        # 7) Normalizar/renombrar otras columnas solicitadas (Operador -> Asesor de ventas, Email, Telefono Movil, Programa)
        # Buscamos variantes comunes
        operador_col = _find_column(df, ['Operador', 'operador', 'Asesor', 'Asesor de ventas', 'AsesorVentas'])
        if operador_col:
            df['Asesor de ventas'] = df[operador_col].astype(str).str.strip()
        else:
            df['Asesor de ventas'] = ''

        email_col = _find_column(df, ['Email', 'email', 'Correo', 'correo'])
        if email_col:
            df['Email'] = df[email_col].astype(str).str.strip()
        else:
            df['Email'] = ''

        telefono_col = _find_column(df, ['Telefono Movil', 'TelefonoMovil', 'Telefono', 'telefono movil', 'telefono_movil', 'movil'])
        if telefono_col:
            df['Telefono Movil'] = df[telefono_col].astype(str).str.strip()
        else:
            df['Telefono Movil'] = ''

        programa_col = _find_column(df, ['Programa', 'programa', 'Plan'])
        if programa_col:
            df['Programa'] = df[programa_col].astype(str).str.strip()
        else:
            df['Programa'] = ''

        # 8) Otras columnas solicitadas en el output: crear vacías si no existen
        # Columnas finales requeridas en el orden solicitado por el usuario (y para facilitar copia/pegado)
        columnas_finales = [
            'Asesor de ventas', 'WEB ID', 'ID', 'NIP', 'LEAD', 'Email',
            'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate',
            'Materias Pagadas', 'Monto de pago', 'Campaña', 'Factura',
            'Correo Anáhuac', 'URL_Lead'
        ]

        # Rellenar columnas que no existan
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''

        # 9) Formatear PaidDate a string legible para copiar/pegar (DD/MM/YYYY HH:MM)
        df['PaidDate'] = pd.to_datetime(df['PaidDate'], errors='coerce')
        df['PaidDate'] = df['PaidDate'].dt.strftime('%d/%m/%Y %H:%M').fillna('')

        # 10) Construir URL_Lead con la base y el LEAD
        url_base = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"
        df['URL_Lead'] = df['LEAD'].apply(lambda x: url_base + str(x).strip() if str(x).strip() != '' else '')

        # 11) Seleccionar SOLO las columnas finales y devolver
        df_final = df[columnas_finales].copy()

        # Reset index
        df_final = df_final.reset_index(drop=True)

        logger.info(f"=== DEPURACIÓN COMPLETADA: {len(df_final)} registros ===")
        return df_final

    except Exception as e:
        logger.exception("ERROR en depurar_datos:")
        raise


def mapear_columnas(df: pd.DataFrame, url_base: str = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/") -> pd.DataFrame:
    """
    Asegura que el DataFrame tenga exactamente las columnas finales en el orden esperado.
    Si recibe el DF ya depurado, esto solo reordena y rellena columnas faltantes.
    """
    try:
        df = df.copy()

        columnas_finales = [
            'Asesor de ventas', 'WEB ID', 'ID', 'NIP', 'LEAD', 'Email',
            'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate',
            'Materias Pagadas', 'Monto de pago', 'Campaña', 'Factura',
            'Correo Anáhuac', 'URL_Lead'
        ]

        # Asegurar columnas
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''

        # Asegurar URL_Lead consistente con url_base + LEAD
        if 'LEAD' in df.columns:
            df['URL_Lead'] = df['LEAD'].apply(lambda x: url_base + str(x).strip() if str(x).strip() != '' else '')
        else:
            df['URL_Lead'] = ''

        # Reordenar y devolver
        df = df[columnas_finales]
        return df

    except Exception as e:
        logger.exception("ERROR en mapear_columnas:")
        raise
