import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None) -> pd.DataFrame:
    """
    Depura el DataFrame del CSV vwCRMLeads
    """
    try:
        df = df.copy()
        
        if timestamp_referencia is None:
            timestamp_referencia = datetime.now()
        
        logger.info(f"=== INICIANDO DEPURACIÓN ===")
        logger.info(f"Timestamp: {timestamp_referencia}")
        logger.info(f"Total filas originales: {len(df)}")
        logger.info(f"Columnas detectadas: {len(df.columns)}")
        
        # Limpiar espacios en nombres de columnas
        df.columns = [str(c).strip() for c in df.columns]
        
        # BUSCAR COLUMNA PAIDDATE (puede estar en cualquier posición)
        paiddate_col = None
        
        # Buscar por nombre exacto
        if 'PaidDate' in df.columns:
            paiddate_col = 'PaidDate'
        else:
            # Buscar columna que contenga "paid" o "date"
            for col in df.columns:
                if 'paid' in str(col).lower() and 'date' in str(col).lower():
                    paiddate_col = col
                    break
        
        if not paiddate_col:
            logger.warning("⚠️ No se encontró columna PaidDate")
            logger.warning(f"Columnas disponibles: {list(df.columns)[:10]}...")
            return df
        
        logger.info(f"✅ Columna de fecha encontrada: {paiddate_col}")
        logger.info(f"Muestra de valores: {df[paiddate_col].head(3).tolist()}")
        
        # Convertir PaidDate a datetime
        # Formato esperado: 26/09/2025 13:35
        df[paiddate_col] = pd.to_datetime(
            df[paiddate_col], 
            format='%d/%m/%Y %H:%M', 
            errors='coerce'
        )
        
        # Si falló, probar formato sin hora
        if df[paiddate_col].isna().sum() > len(df) * 0.5:
            logger.info("Probando formato sin hora...")
            df[paiddate_col] = pd.to_datetime(
                df[paiddate_col], 
                dayfirst=True, 
                errors='coerce'
            )
        
        # Contar fechas inválidas
        nulos = df[paiddate_col].isna().sum()
        if nulos > 0:
            logger.warning(f"⚠️ {nulos} fechas inválidas encontradas")
        
        logger.info(f"Rango fechas: {df[paiddate_col].min()} a {df[paiddate_col].max()}")
        
        # APLICAR FILTRO TEMPORAL
        antes = len(df)
        
        if hours is not None:
            fecha_limite = timestamp_referencia - timedelta(hours=hours)
            logger.info(f"⏰ Filtrando últimas {hours} horas desde {fecha_limite}")
            df = df[df[paiddate_col] >= fecha_limite]
        elif days is not None:
            fecha_limite = timestamp_referencia - timedelta(days=days)
            logger.info(f"📆 Filtrando últimos {days} días desde {fecha_limite}")
            df = df[df[paiddate_col] >= fecha_limite]
        
        despues = len(df)
        logger.info(f"✅ Filtro aplicado: {antes} → {despues} ({antes-despues} eliminados)")
        
        # Renombrar a PaidDate estándar
        if paiddate_col != 'PaidDate':
            df.rename(columns={paiddate_col: 'PaidDate'}, inplace=True)
        
        # CREAR NOMBRE APELLIDO
        if 'Nombre Apellido' not in df.columns:
            if 'Nombre' in df.columns and 'Apellido' in df.columns:
                df['Nombre Apellido'] = (
                    df['Nombre'].fillna('').astype(str).str.strip() + ' ' +
                    df['Apellido'].fillna('').astype(str).str.strip()
                ).str.strip()
                logger.info("✅ Nombre Apellido creado")
        
        # ELIMINAR DUPLICADOS POR LEAD
        if 'LEAD' in df.columns:
            df['LEAD'] = df['LEAD'].astype(str).str.strip()
            antes_dup = len(df)
            df = df.drop_duplicates(subset=['LEAD'], keep='first')
            despues_dup = len(df)
            
            if antes_dup != despues_dup:
                logger.info(f"✅ {antes_dup-despues_dup} duplicados eliminados")
        
        logger.info(f"=== DEPURACIÓN COMPLETADA: {len(df)} registros ===")
        return df.reset_index(drop=True)
        
    except Exception as e:
        logger.exception("❌ ERROR en depurar_datos:")
        raise


def mapear_columnas(df: pd.DataFrame, url_base: str = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/") -> pd.DataFrame:
    """
    Mapea columnas al formato Base Documentos Anáhuac
    """
    try:
        df = df.copy()
        
        logger.info("=== MAPEANDO COLUMNAS ===")
        
        # Renombrar columnas
        mapeo = {
            'Operador': 'Asesor de ventas',
            'TelefonoMovil': 'Telefono Movil',
        }
        
        df = df.rename(columns=mapeo)
        
        # Crear URL_Lead
        if 'LEAD' in df.columns:
            df['URL_Lead'] = url_base + df['LEAD'].astype(str)
        else:
            df['URL_Lead'] = ''
        
        # Columnas finales formato Anáhuac
        columnas_finales = [
            'Asesor de ventas', 'WEB ID', 'ID', 'NIP', 'LEAD', 'Email',
            'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate',
            'Materias Pagadas', 'Monto de pago', 'Campaña', 'Factura',
            'Correo Anáhuac', 'URL_Lead', 'Asesor', 'Estatus', 'NRC',
            'Materia', 'Agenda', 'Comentarios', 'Descuento',
            'Ciclo de inicio', 'Tickets', 'Activación de saldo'
        ]
        
        # Crear columnas faltantes
        for col in columnas_finales:
            if col not in df.columns:
                df[col] = ''
        
        # Reordenar
        df = df[columnas_finales]
        
        logger.info(f"✅ {len(df.columns)} columnas mapeadas")
        return df
        
    except Exception as e:
        logger.exception("❌ ERROR en mapear_columnas:")
        raise
