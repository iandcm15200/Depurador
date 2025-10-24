import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

COLUMNS_KEEP = ['Id', 'Email', 'Nombre', 'Apellido', 'TelefonoMovil', 'Operador', 'Programa', 'PaidDate']

def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None) -> pd.DataFrame:
    try:
        df = df.copy()
        
        if timestamp_referencia is None:
            timestamp_referencia = datetime.now()
        
        logger.info(f"Depurando con timestamp de referencia: {timestamp_referencia}")
        
        df.columns = [c.strip() for c in df.columns]

        existing_keep = [c for c in COLUMNS_KEEP if c in df.columns]
        if set(existing_keep) >= {'Id', 'Email', 'Nombre', 'Apellido', 'TelefonoMovil', 'Operador', 'Programa', 'PaidDate'}:
            df = df[existing_keep]
        else:
            logger.info("No se encontraron todas las columnas base CRM; se conserva el dataframe tal cual para mapeo posterior.")
        
        if 'PaidDate' in df.columns:
            logger.info(f"Procesando columna PaidDate. Primeros valores: {df['PaidDate'].head().tolist()}")
            
            df['PaidDate'] = pd.to_datetime(df['PaidDate'], dayfirst=True, errors='coerce')
            
            logger.info(f"Fechas parseadas. Rango: {df['PaidDate'].min()} a {df['PaidDate'].max()}")
            
            nulos = df['PaidDate'].isna().sum()
            if nulos > 0:
                logger.warning(f"Se encontraron {nulos} fechas que no pudieron ser parseadas")
            
            if hours is not None:
                fecha_limite = timestamp_referencia - timedelta(hours=hours)
                logger.info(f"Filtrando por últimas {hours} horas. Fecha límite: {fecha_limite}")
                antes = len(df)
                df = df[df['PaidDate'] >= fecha_limite]
                despues = len(df)
                logger.info(f"Filtro de {hours}h aplicado: {antes} -> {despues} registros (eliminados: {antes-despues})")
                
            elif days is not None:
                fecha_limite = timestamp_referencia - timedelta(days=days)
                logger.info(f"Filtrando por últimos {days} días. Fecha límite: {fecha_limite}")
                antes = len(df)
                df = df[df['PaidDate'] >= fecha_limite]
                despues = len(df)
                logger.info(f"Filtro de {days} días aplicado: {antes} -> {despues} registros (eliminados: {antes-despues})")
        else:
            logger.warning("PaidDate no presente: no se aplicará filtro de fecha.")

        if 'Nombre Apellido' not in df.columns:
            if ('Nombre' in df.columns) and ('Apellido' in df.columns):
                df['Nombre Apellido'] = (df['Nombre'].fillna('').astype(str).str.strip() + ' ' +
                                         df['Apellido'].fillna('').astype(str).str.strip()).str.strip()
                df = df.drop(columns=[c for c in ['Nombre', 'Apellido'] if c in df.columns])
            else:
                logger.info("No existen columnas Nombre/Apellido. Se conservará la estructura original y se intentará mapear por nombre ya existente.")

        df.rename(columns={'Id': 'LEAD', 'TelefonoMovil': 'Telefono Movil'}, inplace=True)

        if 'LEAD' in df.columns:
            df['LEAD'] = df['LEAD'].astype(str).str.strip()

        if 'LEAD' in df.columns:
            before = len(df)
            df = df.drop_duplicates(subset=['LEAD'])
            after = len(df)
            if before != after:
                logger.info(f"Se eliminaron {before-after} duplicados presentes en el CSV por LEAD.")
        else:
            logger.info("LEAD no presente: no se eliminaron duplicados por LEAD en la depuración inicial.")

        return df.reset_index(drop=True)
    except Exception as e:
        logger.exception("Error en depurar_datos:")
        raise

def mapear_columnas(df: pd.DataFrame, url_base: str = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/") -> pd.DataFrame:
    try:
        df = df.copy()
        mapeo = {
            'Operador': 'Asesor de ventas',
            'LEAD': 'LEAD',
            'Id': 'LEAD',
            'Email': 'Email',
            'Nombre Apellido': 'Nombre Apellido',
            'Telefono Movil': 'Telefono Movil',
            'TelefonoMovil': 'Telefono Movil',
            'Programa': 'Programa',
            'PaidDate': 'PaidDate'
        }

        columns_to_rename = {k: v for k, v in mapeo.items() if k in df.columns}
        if columns_to_rename:
            df = df.rename(columns=columns_to_rename)

        if 'LEAD' not in df.columns:
            for alt in ['ID', 'Id', 'WEB ID']:
                if alt in df.columns:
                    df = df.rename(columns={alt: 'LEAD'})
                    break

        if 'LEAD' in df.columns:
            df['URL_Lead'] = url_base + df['LEAD'].astype(str)
        else:
            logger.warning("No se pudo crear URL_Lead porque no existe LEAD en el DataFrame.")

        target_order = ['Asesor de ventas', 'LEAD', 'Email', 'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate', 'URL_Lead']
        for col in target_order:
            if col not in df.columns:
                df[col] = pd.NA

        df = df[target_order + [c for c in df.columns if c not in target_order]]
        return df
    except Exception as e:
        logger.exception("Error en mapear_columnas:")
        raise
