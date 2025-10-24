import pandas as pd
from datetime import datetime, timedelta
import logging
import re

logger = logging.getLogger(__name__)


def _find_column(df: pd.DataFrame, candidates):
    """
    Busca en df.columns cualquiera de las cadenas en candidates (case-insensitive).
    Devuelve el nombre real de la columna si encuentra, sino None.
    """
    cols_low = {str(c).strip().lower(): c for c in df.columns}
    # Búsqueda exacta (normalizada)
    for cand in candidates:
        key = str(cand).strip().lower()
        if key in cols_low:
            return cols_low[key]
    # Búsqueda por contiene
    for cand in candidates:
        kc = str(cand).strip().lower()
        for k, real in cols_low.items():
            if kc in k:
                return real
    return None


def _try_parse_dates(series: pd.Series) -> pd.Series:
    """
    Intenta parsear una serie de strings con múltiples formatos posibles.
    Devuelve una serie datetime (na si no se puede parsear).
    """
    s = series.astype(str).replace({'': pd.NA, 'nan': pd.NA})
    s = s.str.strip().replace({'\\u200b': ''}, regex=True)

    formats = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%d/%m/%Y",
        "%Y-%m-%d",
    ]

    parsed = pd.to_datetime(pd.Series([pd.NaT] * len(s)), errors="coerce")

    for fmt in formats:
        try:
            this_try = pd.to_datetime(s, format=fmt, dayfirst=True, errors="coerce")
            parsed = parsed.fillna(this_try)
        except Exception:
            continue

    if parsed.isna().sum() > 0:
        fallback = pd.to_datetime(s, dayfirst=True, errors="coerce")
        parsed = parsed.fillna(fallback)

    def clean_iso(x):
        if isinstance(x, str):
            m = re.match(r".*?(\d{4}-\d{2}-\d{2}).*?(\d{2}:\d{2}(:\d{2})?).*", x)
            if m:
                return pd.to_datetime(m.group(1) + " " + m.group(2), dayfirst=False, errors="coerce")
        return x

    if parsed.isna().sum() > 0:
        mask = parsed.isna()
        if mask.any():
            remaining = s[mask].apply(clean_iso)
            parsed.loc[mask] = pd.to_datetime(remaining, errors="coerce")

    return parsed


def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None, start_from_prev_midnight: bool = False) -> pd.DataFrame:
    """
    Depura el DataFrame del CSV vwCRMLeads.
    Parámetros:
      - hours (int): ventana en horas para filtrar (por defecto 24).
      - days (int): alternativa para filtrar por días (si se usa).
      - timestamp_referencia (datetime): punto final de la ventana (por defecto ahora).
      - start_from_prev_midnight (bool): si True, ignora `hours` y toma desde la medianoche del día anterior hasta timestamp_referencia.
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
        paid_candidates = ['PaidDate', 'paiddate', 'paid_date', 'Paid Date', 'FechaPago', 'Fecha Pago', 'paid', 'fecha_pago', 'Fecha']
        paid_col = _find_column(df, paid_candidates)

        if not paid_col:
            logger.warning("No se encontró columna PaidDate. Columnas disponibles: %s", list(df.columns))
            return pd.DataFrame()

        logger.info(f"Columna detectada para fecha: '{paid_col}' - primeras 5: {df[paid_col].head(5).tolist()}")

        # Parsear PaidDate con múltiples estrategias
        parsed = _try_parse_dates(df[paid_col])
        df['_PaidDate_parsed'] = parsed

        n_valid = df['_PaidDate_parsed'].notna().sum()
        logger.info(f"Fechas parseadas válidas: {n_valid} / {len(df)}")
        if n_valid > 0:
            logger.info(f"Rango fechas parseadas: {df['_PaidDate_parsed'].min()} -> {df['_PaidDate_parsed'].max()}")
        else:
            logger.warning("Ninguna fecha pudo ser parseada correctamente. Revisar formato en el CSV.")

        # Establecer PaidDate con el valor parsed (datetime)
        df['PaidDate'] = df['_PaidDate_parsed']

        # Eliminar filas sin PaidDate válido
        antes_sin_fecha = len(df)
        df = df[df['PaidDate'].notna()]
        despues_sin_fecha = len(df)
        if antes_sin_fecha != despues_sin_fecha:
            logger.info(f"Eliminadas {antes_sin_fecha - despues_sin_fecha} filas sin PaidDate válido.")

        if df.empty:
            logger.info("No quedan registros con PaidDate válido después de eliminar nulos.")
            return pd.DataFrame()

        # APLICAR FILTRO TEMPORAL (incluye <= timestamp_referencia)
        antes = len(df)
        if start_from_prev_midnight:
            prev_midnight = (timestamp_referencia - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            fecha_inicio = prev_midnight
            fecha_fin = timestamp_referencia
            logger.info(f"Filtrando desde medianoche del día anterior: {fecha_inicio} -> {fecha_fin}")
            df = df[(df['PaidDate'] >= fecha_inicio) & (df['PaidDate'] <= fecha_fin)]
        else:
            if hours is not None:
                fecha_limite = timestamp_referencia - timedelta(hours=hours)
                fecha_inicio = fecha_limite
                fecha_fin = timestamp_referencia
                logger.info(f"Filtrando últimas {hours} horas: {fecha_inicio} -> {fecha_fin}")
                df = df[(df['PaidDate'] >= fecha_inicio) & (df['PaidDate'] <= fecha_fin)]
            elif days is not None:
                fecha_limite = timestamp_referencia - timedelta(days=days)
                fecha_inicio = fecha_limite
                fecha_fin = timestamp_referencia
                logger.info(f"Filtrando últimos {days} días: {fecha_inicio} -> {fecha_fin}")
                df = df[(df['PaidDate'] >= fecha_inicio) & (df['PaidDate'] <= fecha_fin)]
        despues = len(df)
        logger.info(f"Filtro temporal aplicado: {antes} -> {despues} ({antes - despues} eliminados)")

        if df.empty:
            logger.info("Después del filtro temporal no quedan registros.")
            return pd.DataFrame()

        # Crear Nombre Apellido (Apellido + Nombre) si es posible
        nombre_col = _find_column(df, ['Nombre', 'nombre', 'name'])
        apellido_col = _find_column(df, ['Apellido', 'apellido', 'last_name', 'lastname', 'apellido_paterno', 'Apellido Paterno'])
        if 'Nombre Apellido' not in df.columns:
            if apellido_col and nombre_col and apellido_col in df.columns and nombre_col in df.columns:
                df['Nombre Apellido'] = (df[apellido_col].fillna('').astype(str).str.strip() + ' ' +
                                         df[nombre_col].fillna('').astype(str).str.strip()).str.strip()
            elif nombre_col and nombre_col in df.columns:
                df['Nombre Apellido'] = df[nombre_col].astype(str).str.strip()
            elif apellido_col and apellido_col in df.columns:
                df['Nombre Apellido'] = df[apellido_col].astype(str).str.strip()
            else:
                df['Nombre Apellido'] = ''

        # Normalizar LEAD
        lead_col = _find_column(df, ['LEAD', 'Lead', 'Id', 'ID', 'id'])
        if lead_col and lead_col in df.columns:
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
        df['Asesor de ventas'] = df[operador_col].astype(str).str.strip() if operador_col and operador_col in df.columns else ''
        email_col = _find_column(df, ['Email', 'email', 'Correo', 'correo'])
        df['Email'] = df[email_col].astype(str).str.strip() if email_col and email_col in df.columns else ''
        telefono_col = _find_column(df, ['Telefono Movil', 'TelefonoMovil', 'Telefono', 'telefono movil', 'telefono_movil', 'movil'])
        df['Telefono Movil'] = df[telefono_col].astype(str).str.strip() if telefono_col and telefono_col in df.columns else ''
        programa_col = _find_column(df, ['Programa', 'programa', 'Plan'])
        df['Programa'] = df[programa_col].astype(str).str.strip() if programa_col and programa_col in df.columns else ''

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
