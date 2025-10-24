import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Columnas del CSV original
COLUMNS_KEEP = ['Id', 'Email', 'Nombre', 'Apellido', 'TelefonoMovil', 'Operador', 'Programa', 'PaidDate']

def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None) -> pd.DataFrame:
    """
    Depura el DataFrame del CSV:
    - Filtra por fecha (últimas 24h por defecto)
    - Crea columna 'Nombre Apellido' concatenando Nombre + Apellido
    - Elimina duplicados por LEAD
    """
    try:
        df = df.copy()
        
        if timestamp_referencia is None:
            timestamp_referencia = datetime.now()
        
        logger.info(f"Depurando con timestamp de referencia: {timestamp_referencia}")
        
        # Limpiar nombres de columnas
        df.columns = [c.strip() for c in df.columns]
        
        # Filtrar por PaidDate
        if 'PaidDate' in df.columns:
            logger.info(f"Procesando columna PaidDate. Primeros valores: {df['PaidDate'].head().tolist()}")
            
            # Convertir a datetime
            df['PaidDate'] = pd.to_datetime(df['PaidDate'], dayfirst=True, errors='coerce')
            
            logger.info(f"Fechas parseadas. Rango: {df['PaidDate'].min()} a {df['PaidDate'].max()}")
            
            nulos = df['PaidDate'].isna().sum()
            if nulos > 0:
                logger.warning(f"Se encontraron {nulos} fechas que no pudieron ser parseadas")
            
            # Aplicar filtro temporal
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
        
        # Crear columna 'Nombre Apellido' concatenando
        if 'Nombre Apellido' not in df.columns:
            if 'Nombre' in df.columns and 'Apellido' in df.columns:
                # Concatenar: Apellido + Nombre (como mencionaste)
                df['Nombre Apellido'] = (
                    df['Apellido'].fillna('').astype(str).str.strip() + ' ' +
                    df['Nombre'].fillna('').astype(str).str.strip()
                ).str.strip()
                logger.info("Columna 'Nombre Apellido' creada concatenando Apellido + Nombre")
        
        # Renombrar columna Id a LEAD
        if 'Id' in df.columns:
            df.rename(columns={'Id': 'LEAD'}, inplace=True)
        
        # Limpiar LEAD (sin espacios)
        if 'LEAD' in df.columns:
            df['LEAD'] = df['LEAD'].astype(str).str.strip()
            
            # Eliminar duplicados por LEAD
            before = len(df)
            df = df.drop_duplicates(subset=['LEAD'], keep='first')
            after = len(df)
            if before != after:
                logger.info(f"Se eliminaron {before-after} duplicados por LEAD.")
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        logger.exception("Error en depurar_datos:")
        raise


def mapear_columnas(df: pd.DataFrame, url_base: str = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/") -> pd.DataFrame:
    """
    Mapea columnas del CSV al formato final requerido.
    Genera TODAS las columnas necesarias (incluso vacías).
    Crea URL completa concatenando url_base + LEAD.
    """
    try:
        df = df.copy()
        
        # Mapeo de columnas del CSV a formato final
        mapeo = {
            'Operador': 'Asesor de ventas',
            'TelefonoMovil': 'Telefono Movil',
            'Telefono Movil': 'Telefono Movil'
        }
        
        # Aplicar renombres
        df = df.rename(columns=mapeo)
        
        # Crear columna URL_Lead concatenando url_base + LEAD
        if 'LEAD' in df.columns:
            df['URL_Lead'] = url_base + df['LEAD'].astype(str)
            logger.info(f"Columna URL_Lead creada: {url_base} + LEAD")
        else:
            logger.warning("No se pudo crear URL_Lead porque no existe columna LEAD")
            df['URL_Lead'] = ''
        
        # TODAS las columnas del formato final (en orden)
        columnas_finales = [
            'Asesor de ventas',
            'WEB ID',
            'ID',
            'NIP',
            'LEAD',
            'Email',
            'Nombre Apellido',
            'Telefono Movil',
            'Programa',
            'PaidDate',
            'Materias Pagadas',
            'Monto de pago',
            'Campaña',
            'Factura',
            'Correo Anáhuac',
            'URL_Lead'
        ]
        
        # Crear columnas faltantes como vacías
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''
        
        # Reordenar columnas al formato final
        df = df[columnas_finales]
        
        logger.info(f"Mapeo completado. Columnas finales: {list(df.columns)}")
        
        return df
        
    except Exception as e:
        logger.exception("Error en mapear_columnas:")
        raise
