import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


def _find_column(df: pd.DataFrame, candidates):
    """
    Busca en df.columns cualquiera de las cadenas en candidates (case-insensitive).
    Devuelve el nombre real de la columna si encuentra, sino None.
    """
    cols_low = {str(c).strip().lower(): c for c in df.columns}
    # búsqueda exacta normalizada
    for cand in candidates:
        key = str(cand).strip().lower()
        if key in cols_low:
            return cols_low[key]
    # búsqueda por contiene
    for cand in candidates:
        kc = str(cand).strip().lower()
        for k, real in cols_low.items():
            if kc in k:
                return real
    return None


def depurar_datos(df: pd.DataFrame, hours: int = 48, days: int = None, timestamp_referencia: datetime = None) -> pd.DataFrame:
    """
    Depura el DataFrame del CSV vwCRMLeads:
    - Detecta y parsea PaidDate (varias variaciones).
    - Filtra registros que estén dentro de las últimas `hours` horas (por defecto 48)
      contadas desde `timestamp_referencia` (por defecto ahora).
    - Crea 'Nombre Apellido' concatenando Apellido + Nombre si es posible.
    - Elimina duplicados por LEAD (queda la primera ocurrencia).
    - Devuelve solo las columnas finales solicitadas en el orden esperado.
    """
    try:
        df = df.copy()
        if timestamp_referencia is None:
            timestamp_referencia = datetime.now()

        logger.info("=== INICIANDO DEPURACIÓN ===")
        logger.info(f"Timestamp referencia: {timestamp_referencia}")
        logger.info(f"Filas originales: {len(df)}")

        # Normalizar nombres de columnas (trim)
        df.columns = [str(c).strip() for c in df.columns]

        # Buscar columna de fecha (PaidDate u otras variantes)
        paid_candidates = ['PaidDate', 'paiddate', 'paid_date', 'Paid Date', 'FechaPago', 'Fecha Pago', 'paid', 'fecha_pago', 'Fecha']
        paid_col = _find_column(df, paid_candidates)

        if not paid_col:
            logger.warning("No se encontró columna PaidDate. Asegúrate que el CSV tenga la columna de fecha.")
            return pd.DataFrame()

        # Normalizar valores vacíos y parsear a datetime
        df[paid_col] = df[paid_col].replace('', pd.NA)

        # Intentos de parseo: formato esperado DD/MM/YYYY HH:MM, si falla usar dayfirst general
        df[paid_col] = pd.to_datetime(df[paid_col], format='%d/%m/%Y %H:%M', errors='coerce')
        # Si muchos nulos, intentar con dayfirst=True como fallback
        if df[paid_col].isna().sum() > 0:
            fallback = pd.to_datetime(df[paid_col], dayfirst=True, errors='coerce')
            df[paid_col] = df[paid_col].fillna(fallback)

        # Si aún hay muchos nulos, intentar extracciones básicas (solo parte fecha)
        if df[paid_col].isna().sum() > len(df) * 0.5:
            df[paid_col] = pd.to_datetime(df[paid_col].astype(str).str.split().str[0], dayfirst=True, errors='coerce')

        nulos = df[paid_col].isna().sum()
        if nulos > 0:
            logger.warning(f"{nulos} filas con PaidDate inválido (serán descartadas)")

        # Normalizar columna al nombre estándar 'PaidDate' (datetime)
        if paid_col != 'PaidDate':
            df.rename(columns={paid_col: 'PaidDate'}, inplace=True)

        # Eliminar filas sin PaidDate válido
        df = df[df['PaidDate'].notna()]

        if df.empty:
            logger.info("No quedan registros con PaidDate válido tras el parseo.")
            return pd.DataFrame()

        # Aplicar filtro temporal: últimas `hours` horas (por defecto 48) hasta timestamp_referencia
        antes = len(df)
        if hours is not None:
            fecha_limite = timestamp_referencia - timedelta(hours=hours)
            logger.info(f"⏰ Filtrando registros con PaidDate entre {fecha_limite} y {timestamp_referencia} (últimas {hours} horas)")
            df = df[(df['PaidDate'] >= fecha_limite) & (df['PaidDate'] <= timestamp_referencia)]
        elif days is not None:
            fecha_limite = timestamp_referencia - timedelta(days=days)
            logger.info(f"📆 Filtrando registros con PaidDate >= {fecha_limite} (últimos {days} días)")
            df = df[(df['PaidDate'] >= fecha_limite) & (df['PaidDate'] <= timestamp_referencia)]
        despues = len(df)
        logger.info(f"Filtro temporal aplicado: {antes} → {despues}")

        if df.empty:
            logger.info("No quedan registros después del filtro temporal.")
            return pd.DataFrame()

        # Crear 'Nombre Apellido' concatenando Apellido + Nombre (si existen)
        nombre_col = _find_column(df, ['Nombre', 'nombre', 'name'])
        apellido_col = _find_column(df, ['Apellido', 'apellido', 'last_name', 'lastname', 'apellido_paterno', 'Apellido Paterno'])
        if 'Nombre Apellido' not in df.columns:
            if apellido_col and nombre_col and apellido_col in df.columns and nombre_col in df.columns:
                df['Nombre Apellido'] = (df[apellido_col].fillna('').astype(str).str.strip() + ' ' +
                                         df[nombre_col].fillna('').astype(str).str.strip()).str.strip()
                logger.info("✅ Nombre Apellido creado (Apellido + Nombre).")
            elif nombre_col and nombre_col in df.columns:
                df['Nombre Apellido'] = df[nombre_col].astype(str).str.strip()
            elif apellido_col and apellido_col in df.columns:
                df['Nombre Apellido'] = df[apellido_col].astype(str).str.strip()
            else:
                df['Nombre Apellido'] = ''

        # Detectar y normalizar LEAD
        lead_col = _find_column(df, ['LEAD', 'Lead', 'Id', 'ID', 'id'])
        if lead_col and lead_col in df.columns:
            df['LEAD'] = df[lead_col].astype(str).str.strip()
        else:
            df['LEAD'] = ''

        # Eliminar duplicados por LEAD (primera ocurrencia)
        if 'LEAD' in df.columns and df['LEAD'].astype(str).str.strip().replace('', pd.NA).notna().any():
            antes_dup = len(df)
            df = df.drop_duplicates(subset=['LEAD'], keep='first')
            despues_dup = len(df)
            if antes_dup != despues_dup:
                logger.info(f"✅ {antes_dup - despues_dup} duplicados por LEAD eliminados")

        # Normalizar/renombrar otras columnas solicitadas
        operador_col = _find_column(df, ['Operador', 'operador', 'Asesor', 'Asesor de ventas', 'AsesorVentas'])
        df['Asesor de ventas'] = df[operador_col].astype(str).str.strip() if operador_col and operador_col in df.columns else ''

        email_col = _find_column(df, ['Email', 'email', 'Correo', 'correo'])
        df['Email'] = df[email_col].astype(str).str.strip() if email_col and email_col in df.columns else ''

        telefono_col = _find_column(df, ['Telefono Movil', 'TelefonoMovil', 'Telefono', 'telefono movil', 'telefono_movil', 'movil'])
        df['Telefono Movil'] = df[telefono_col].astype(str).str.strip() if telefono_col and telefono_col in df.columns else ''

        programa_col = _find_column(df, ['Programa', 'programa', 'Plan'])
        df['Programa'] = df[programa_col].astype(str).str.strip() if programa_col and programa_col in df.columns else ''

        # Columnas finales requeridas (se crean vacías si no existen)
        columnas_finales = [
            'Asesor de ventas', 'WEB ID', 'ID', 'NIP', 'LEAD', 'Email',
            'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate',
            'Materias Pagadas', 'Monto de pago', 'Campaña', 'Factura',
            'Correo Anáhuac', 'URL_Lead'
        ]
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''

        # Formatear PaidDate como texto DD/MM/YYYY HH:MM para salida
        df['PaidDate'] = pd.to_datetime(df['PaidDate'], errors='coerce')
        df['PaidDate'] = df['PaidDate'].dt.strftime('%d/%m/%Y %H:%M').fillna('')

        # Construir URL_Lead con la base y el LEAD
        url_base = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"
        df['URL_Lead'] = df['LEAD'].apply(lambda x: url_base + str(x).strip() if str(x).strip() != '' else '')

        # Seleccionar solo las columnas finales y devolver
        df_final = df[columnas_finales].copy().reset_index(drop=True)

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
