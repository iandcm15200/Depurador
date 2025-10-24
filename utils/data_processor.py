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


def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None, start_from_prev_midnight: bool = False) -> pd.DataFrame:
    """
    Depura el DataFrame del CSV vwCRMLeads.
    Parámetros adicionales:
      - hours / days: filtro temporal (por defecto 24 horas).
      - timestamp_referencia: punto final del filtro (por defecto ahora).
      - start_from_prev_midnight: si True, ignora `hours` y toma desde la medianoche del día anterior hasta timestamp_referencia.
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

        # Encontrar columna de PaidDate
        paid_candidates = ['PaidDate', 'paiddate', 'paid_date', 'Paid Date', 'FechaPago', 'Fecha Pago', 'paid']
        paid_col = _find_column(df, paid_candidates)

        if not paid_col:
            logger.warning("No se encontró columna PaidDate.")
            return pd.DataFrame()

        # Parsear PaidDate
        df[paid_col] = df[paid_col].replace('', pd.NA)
        try:
            df[paid_col] = pd.to_datetime(df[paid_col], format='%d/%m/%Y %H:%M', errors='coerce')
        except Exception:
            df[paid_col] = pd.to_datetime(df[paid_col], dayfirst=True, errors='coerce')
        if df[paid_col].isna().sum() > len(df) * 0.5:
            df[paid_col] = pd.to_datetime(df[paid_col].astype(str).str.split().str[0], dayfirst=True, errors='coerce')

        # Renombrar a 'PaidDate'
        if paid_col != 'PaidDate':
            df.rename(columns={paid_col: 'PaidDate'}, inplace=True)

        # Eliminar filas sin PaidDate válido
        df = df[df['PaidDate'].notna()]

        # APLICAR FILTRO TEMPORAL
        antes = len(df)
        if start_from_prev_midnight:
            # Desde la medianoche del día anterior hasta timestamp_referencia
            prev_midnight = (timestamp_referencia - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            fecha_inicio = prev_midnight
            fecha_fin = timestamp_referencia
            logger.info(f"📌 Filtrando desde medianoche del día anterior: {fecha_inicio} → {fecha_fin}")
            df = df[(df['PaidDate'] >= fecha_inicio) & (df['PaidDate'] <= fecha_fin)]
        else:
            if hours is not None:
                fecha_limite = timestamp_referencia - timedelta(hours=hours)
                logger.info(f"⏰ Filtrando últimas {hours} horas desde {fecha_limite} hasta {timestamp_referencia}")
                df = df[(df['PaidDate'] >= fecha_limite) & (df['PaidDate'] <= timestamp_referencia)]
            elif days is not None:
                fecha_limite = timestamp_referencia - timedelta(days=days)
                logger.info(f"📆 Filtrando últimos {days} días desde {fecha_limite} hasta {timestamp_referencia}")
                df = df[(df['PaidDate'] >= fecha_limite) & (df['PaidDate'] <= timestamp_referencia)]
        despues = len(df)
        logger.info(f"Filtro temporal aplicado: {antes} → {despues}")

        if df.empty:
            logger.info("No quedan registros después del filtro temporal.")
            return pd.DataFrame()

        # Crear Nombre Apellido (Apellido + Nombre) si es posible
        nombre_col = _find_column(df, ['Nombre', 'nombre', 'name'])
        apellido_col = _find_column(df, ['Apellido', 'apellido', 'last_name', 'lastname', 'apellido_paterno', 'Apellido Paterno'])
        if 'Nombre Apellido' not in df.columns:
            if apellido_col and nombre_col:
                df['Nombre Apellido'] = (df[apellido_col].fillna('').astype(str).str.strip() + ' ' +
                                         df[nombre_col].fillna('').astype(str).str.strip()).str.strip()
            elif nombre_col:
                df['Nombre Apellido'] = df[nombre_col].astype(str).str.strip()
            elif apellido_col:
                df['Nombre Apellido'] = df[apellido_col].astype(str).str.strip()
            else:
                df['Nombre Apellido'] = ''

        # Normalizar LEAD
        lead_col = _find_column(df, ['LEAD', 'Lead', 'Id', 'ID', 'id'])
        if lead_col:
            df['LEAD'] = df[lead_col].astype(str).str.strip()
        else:
            df['LEAD'] = ''

        # Eliminar duplicados por LEAD
        if 'LEAD' in df.columns and df['LEAD'].astype(str).str.strip().replace('', pd.NA).notna().any():
            antes_dup = len(df)
            df = df.drop_duplicates(subset=['LEAD'], keep='first')
            despues_dup = len(df)
            logger.info(f"Duplicados por LEAD eliminados: {antes_dup - despues_dup}")

        # Normalizar otras columnas solicitadas
        operador_col = _find_column(df, ['Operador', 'operador', 'Asesor', 'Asesor de ventas', 'AsesorVentas'])
        df['Asesor de ventas'] = df[operador_col].astype(str).str.strip() if operador_col else ''
        email_col = _find_column(df, ['Email', 'email', 'Correo', 'correo'])
        df['Email'] = df[email_col].astype(str).str.strip() if email_col else ''
        telefono_col = _find_column(df, ['Telefono Movil', 'TelefonoMovil', 'Telefono', 'telefono movil', 'telefono_movil', 'movil'])
        df['Telefono Movil'] = df[telefono_col].astype(str).str.strip() if telefono_col else ''
        programa_col = _find_column(df, ['Programa', 'programa', 'Plan'])
        df['Programa'] = df[programa_col].astype(str).str.strip() if programa_col else ''

        # Columnas finales requeridas
        columnas_finales = [
            'Asesor de ventas', 'WEB ID', 'ID', 'NIP', 'LEAD', 'Email',
            'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate',
            'Materias Pagadas', 'Monto de pago', 'Campaña', 'Factura',
            'Correo Anáhuac', 'URL_Lead'
        ]
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''

        # Formatear PaidDate como texto DD/MM/YYYY HH:MM
        df['PaidDate'] = pd.to_datetime(df['PaidDate'], errors='coerce')
        df['PaidDate'] = df['PaidDate'].dt.strftime('%d/%m/%Y %H:%M').fillna('')

        # Construir URL_Lead
        url_base = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"
        df['URL_Lead'] = df['LEAD'].apply(lambda x: url_base + str(x).strip() if str(x).strip() != '' else '')

        df_final = df[columnas_finales].reset_index(drop=True)
        logger.info(f"=== DEPURACIÓN COMPLETADA: {len(df_final)} registros ===")
        return df_final

    except Exception as e:
        logger.exception("ERROR en depurar_datos:")
        raise


def mapear_columnas(df: pd.DataFrame, url_base: str = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/") -> pd.DataFrame:
    """
    Asegura que el DataFrame tenga exactamente las columnas finales en el orden esperado.
    """
    try:
        df = df.copy()
        columnas_finales = [
            'Asesor de ventas', 'WEB ID', 'ID', 'NIP', 'LEAD', 'Email',
            'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate',
            'Materias Pagadas', 'Monto de pago', 'Campaña', 'Factura',
            'Correo Anáhuac', 'URL_Lead'
        ]
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''
        if 'LEAD' in df.columns:
            df['URL_Lead'] = df['LEAD'].apply(lambda x: url_base + str(x).strip() if str(x).strip() != '' else '')
        else:
            df['URL_Lead'] = ''
        df = df[columnas_finales]
        return df
    except Exception as e:
        logger.exception("ERROR en mapear_columnas:")
        raise
