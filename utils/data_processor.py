import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None) -> pd.DataFrame:
    """
    Depura el DataFrame del CSV vwCRMLeads:
    - Filtra por PaidDate (últimas 24h por defecto)
    - Prepara datos para formato Base Documentos Anáhuac
    """
    try:
        df = df.copy()
        
        if timestamp_referencia is None:
            timestamp_referencia = datetime.now()
        
        logger.info(f"=== INICIANDO DEPURACIÓN ===")
        logger.info(f"Timestamp de referencia: {timestamp_referencia}")
        logger.info(f"Columnas en CSV: {list(df.columns)}")
        logger.info(f"Total filas originales: {len(df)}")
        
        # Limpiar nombres de columnas
        df.columns = [c.strip() for c in df.columns]
        
        # FILTRAR POR PAIDDATE
        if 'PaidDate' in df.columns:
            logger.info(f"📅 Procesando columna PaidDate")
            logger.info(f"Muestra de fechas: {df['PaidDate'].head(3).tolist()}")
            
            # Convertir a datetime (formato: 26/09/2025 13:35)
            df['PaidDate'] = pd.to_datetime(df['PaidDate'], format='%d/%m/%Y %H:%M', errors='coerce')
            
            # Si el formato anterior falló, probar con formato alternativo
            if df['PaidDate'].isna().all():
                logger.info("Probando formato alternativo de fecha...")
                df['PaidDate'] = pd.to_datetime(df['PaidDate'], dayfirst=True, errors='coerce')
            
            logger.info(f"Rango de fechas: {df['PaidDate'].min()} a {df['PaidDate'].max()}")
            
            nulos = df['PaidDate'].isna().sum()
            if nulos > 0:
                logger.warning(f"⚠️ {nulos} fechas no pudieron parsearse")
            
            # APLICAR FILTRO TEMPORAL
            if hours is not None:
                fecha_limite = timestamp_referencia - timedelta(hours=hours)
                logger.info(f"⏰ Filtrando últimas {hours} horas desde {fecha_limite}")
                
                antes = len(df)
                df = df[df['PaidDate'] >= fecha_limite]
                despues = len(df)
                
                logger.info(f"✅ Filtro aplicado: {antes} → {despues} registros ({antes-despues} eliminados)")
                
            elif days is not None:
                fecha_limite = timestamp_referencia - timedelta(days=days)
                logger.info(f"📆 Filtrando últimos {days} días desde {fecha_limite}")
                
                antes = len(df)
                df = df[df['PaidDate'] >= fecha_limite]
                despues = len(df)
                
                logger.info(f"✅ Filtro aplicado: {antes} → {despues} registros ({antes-despues} eliminados)")
        else:
            logger.warning("⚠️ Columna PaidDate no encontrada - NO se filtró por fecha")
        
        # CREAR NOMBRE APELLIDO (del CSV vwCRMLeads viene como Nombre y Apellido separados)
        if 'Nombre Apellido' not in df.columns:
            if 'Apellido' in df.columns and 'Nombre' in df.columns:
                df['Nombre Apellido'] = (
                    df['Nombre'].fillna('').astype(str).str.strip() + ' ' +
                    df['Apellido'].fillna('').astype(str).str.strip()
                ).str.strip()
                logger.info("✅ Columna 'Nombre Apellido' creada (Nombre + Apellido)")
        
        # ELIMINAR DUPLICADOS POR LEAD
        if 'LEAD' in df.columns:
            df['LEAD'] = df['LEAD'].astype(str).str.strip()
            
            antes = len(df)
            df = df.drop_duplicates(subset=['LEAD'], keep='first')
            despues = len(df)
            
            if antes != despues:
                logger.info(f"✅ Eliminados {antes-despues} duplicados por LEAD")
        
        logger.info(f"=== DEPURACIÓN COMPLETADA: {len(df)} registros finales ===")
        
        return df.reset_index(drop=True)
        
    except Exception as e:
        logger.exception("❌ ERROR en depurar_datos:")
        raise


def mapear_columnas(df: pd.DataFrame, url_base: str = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/") -> pd.DataFrame:
    """
    Mapea del formato vwCRMLeads al formato Base Documentos Anáhuac
    
    Mapeo:
    - Asesor de ventas → viene como "Operador" en vwCRMLeads
    - LEAD → viene como "LEAD" en vwCRMLeads
    - Email → viene como "Email" en vwCRMLeads
    - Nombre Apellido → se crea concatenando Nombre + Apellido
    - Telefono Movil → viene como "TelefonoMovil" en vwCRMLeads
    - Programa → viene como "Programa" en vwCRMLeads
    - PaidDate → viene como "PaidDate" en vwCRMLeads
    - URL_Lead → se crea: url_base + LEAD
    """
    try:
        df = df.copy()
        
        logger.info("=== INICIANDO MAPEO DE COLUMNAS ===")
        logger.info(f"Columnas disponibles: {list(df.columns)}")
        
        # MAPEO DE COLUMNAS del CSV vwCRMLeads
        mapeo = {
            'Operador': 'Asesor de ventas',
            'TelefonoMovil': 'Telefono Movil',
        }
        
        df = df.rename(columns=mapeo)
        logger.info(f"Columnas renombradas: {mapeo}")
        
        # CREAR URL_LEAD
        if 'LEAD' in df.columns:
            df['URL_Lead'] = url_base + df['LEAD'].astype(str)
            logger.info(f"✅ URL_Lead creada: {url_base} + LEAD")
        else:
            df['URL_Lead'] = ''
            logger.warning("⚠️ No se pudo crear URL_Lead (falta LEAD)")
        
        # ESTRUCTURA FINAL: Formato Base Documentos Anáhuac
        # Hoja: Ventas Nuevas Maestrías 202592
        columnas_finales = [
            'Asesor de ventas',      # Operador del CSV
            'WEB ID',                # Vacío (no viene en vwCRMLeads)
            'ID',                    # Vacío (no viene en vwCRMLeads)
            'NIP',                   # Vacío (no viene en vwCRMLeads)
            'LEAD',                  # LEAD del CSV
            'Email',                 # Email del CSV
            'Nombre Apellido',       # Concatenación de Nombre + Apellido
            'Telefono Movil',        # TelefonoMovil del CSV
            'Programa',              # Programa del CSV
            'PaidDate',              # PaidDate del CSV
            'Materias Pagadas',      # Vacío (no viene en vwCRMLeads)
            'Monto de pago',         # Vacío (no viene en vwCRMLeads)
            'Campaña',               # Vacío (no viene en vwCRMLeads)
            'Factura',               # Vacío (no viene en vwCRMLeads)
            'Correo Anáhuac',        # Vacío (no viene en vwCRMLeads)
            'URL_Lead',              # url_base + LEAD
            'Asesor',                # Vacío (no viene en vwCRMLeads)
            'Estatus',               # Vacío (no viene en vwCRMLeads)
            'NRC',                   # Vacío (no viene en vwCRMLeads)
            'Materia',               # Vacío (no viene en vwCRMLeads)
            'Agenda',                # Vacío (no viene en vwCRMLeads)
            'Comentarios',           # Vacío (no viene en vwCRMLeads)
            'Descuento',             # Vacío (no viene en vwCRMLeads)
            'Ciclo de inicio',       # Vacío (no viene en vwCRMLeads)
            'Tickets',               # Vacío (no viene en vwCRMLeads)
            'Activación de saldo'    # Vacío (no viene en vwCRMLeads)
        ]
        
        # Crear columnas faltantes como vacías
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''
        
        # Reordenar al formato final
        df = df[columnas_finales]
        
        logger.info(f"✅ Mapeo completado - Total columnas: {len(df.columns)}")
        logger.info(f"Columnas finales: {list(df.columns)}")
        
        return df
        
    except Exception as e:
        logger.exception("❌ ERROR en mapear_columnas:")
        raise
