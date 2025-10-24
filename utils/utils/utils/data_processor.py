import pandas as pd
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Columnas objetivo si el CSV viene crudo (CRM)
COLUMNS_KEEP = ['Id', 'Email', 'Nombre', 'Apellido', 'TelefonoMovil', 'Operador', 'Programa', 'PaidDate']

def depurar_datos(df: pd.DataFrame, hours: int = 24, days: int = None, timestamp_referencia: datetime = None) -> pd.DataFrame:
    """
    Depura el DataFrame:
    - Mantiene solo columnas necesarias si están presentes.
    - Convierte PaidDate a datetime (dayfirst True para dd/mm/yyyy).
    - Filtra por últimas 'hours' horas o últimos 'days' días desde timestamp_referencia.
    - Si timestamp_referencia es None, usa datetime.now()
    - Crea 'Nombre Apellido' si no existe (uniendo Nombre y Apellido).
    - Devuelve DataFrame resultante con columnas base normalizadas.
    """
    try:
        df = df.copy()
        
        # Usar timestamp de referencia o ahora
        if timestamp_referencia is None:
            timestamp_referencia = datetime.now()
        
        logger.info(f"Depurando con timestamp de referencia: {timestamp_referencia}")
        
        # Normalizar nombres de columnas: strip
        df.columns = [c.strip() for c in df.columns]

        # Si el dataframe tiene las columnas separadas Nombre y Apellido, reducir a las necesarias
        existing_keep = [c for c in COLUMNS_KEEP if c in df.columns]
        if set(existing_keep) >= {'Id', 'Email', 'Nombre', 'Apellido', 'TelefonoMovil', 'Operador', 'Programa', 'PaidDate'}:
            df = df[existing_keep]
        else:
            # Si no están, intentamos no eliminar columnas para no perder información
            logger.info("No se encontraron todas las columnas base CRM; se conserva el dataframe tal cual para mapeo posterior.")
        
        # Parse PaidDate si existe
        if 'PaidDate' in df.columns:
            logger.info(f"Procesando columna PaidDate. Primeros valores: {df['PaidDate'].head().tolist()}")
            
            # Intentar múltiples formatos de fecha
            df['PaidDate'] = pd.to_datetime(df['PaidDate'], dayfirst=True, errors='coerce')
            
            # Log de fechas parseadas
            logger.info(f"Fechas parseadas. Rango: {df['PaidDate'].min()} a {df['PaidDate'].max()}")
            
            # Contar valores nulos
            nulos = df['PaidDate'].isna().sum()
            if nulos > 0:
                logger.warning(f"Se encontraron {nulos} fechas que no pudieron ser parseadas")
            
            # Filtrado temporal usando el timestamp de referencia
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

        # Crear 'Nombre Apellido' si no existe
        if 'Nombre Apellido' not in df.columns:
            if ('Nombre' in df.columns) and ('Apellido' in df.columns):
                df['Nombre Apellido'] = (df['Nombre'].fillna('').astype(str).str.strip() + ' ' +
                                         df['Apellido'].fillna('').astype(str).str.strip()).str.strip()
                # Eliminamos columnas originales si existen
                df = df.drop(columns=[c for c in ['Nombre', 'Apellido'] if c in df.columns])
            else:
                logger.info("No existen columnas Nombre/Apellido. Se conservará la estructura original y se intentará mapear por nombre ya existente.")

        # Normalizar nombres de columnas comunes
        df.rename(columns={'Id': 'LEAD', 'TelefonoMovil': 'Telefono Movil'}, inplace=True)

        # Asegurar LEAD como string sin espacios
        if 'LEAD' in df.columns:
            df['LEAD'] = df['LEAD'].astype(str).str.strip()

        # Limpiar duplicados base (no eliminar aún según maestro; aquí solo duplicados directos del csv)
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
    """
    Mapea columnas del DataFrame depurado a la estructura del archivo maestro.
    Añade columna URL_Lead = url_base + LEAD
    """
    try:
        df = df.copy()
        # Mapeo base
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

        # Aplicamos mapeo si la columna existe
        columns_to_rename = {k: v for k, v in mapeo.items() if k in df.columns}
        if columns_to_rename:
            df = df.rename(columns=columns_to_rename)

        # Si no existe LEAD pero existe 'ID' mayúscula en algunas fuentes, tratar
        if 'LEAD' not in df.columns:
            for alt in ['ID', 'Id', 'WEB ID']:
                if alt in df.columns:
                    df = df.rename(columns={alt: 'LEAD'})
                    break

        # Añadir columna URL_Lead
        if 'LEAD' in df.columns:
            df['URL_Lead'] = url_base + df['LEAD'].astype(str)
        else:
            logger.warning("No se pudo crear URL_Lead porque no existe LEAD en el DataFrame.")

        # Asegurar columnas mínimas en orden lógico
        target_order = ['Asesor de ventas', 'LEAD', 'Email', 'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate', 'URL_Lead']
        # Añadir columnas ausentes con NaN para mantener estructura
        for col in target_order:
            if col not in df.columns:
                df[col] = pd.NA

        df = df[target_order + [c for c in df.columns if c not in target_order]]
        return df
    except Exception as e:
        logger.exception("Error en mapear_columnas:")
        raise
```

4. Commit: "Añadir data_processor.py"

---

### **2. `utils/excel_manager.py`**

1. "Add file" → "Create new file"
2. Nombre: `utils/excel_manager.py`
3. **Copia el contenido de tu archivo original** `excel_manager.py` (el que ya tienes)
4. Commit: "Añadir excel_manager.py"

---

### **3. `utils/history_manager.py`**

Ya te lo di antes, pero aquí está de nuevo:

1. "Add file" → "Create new file"
2. Nombre: `utils/history_manager.py`
3. Copia el código que te di anteriormente (el archivo completo con las funciones `guardar_historial`, `cargar_historial`, `mostrar_estadisticas`)
4. Commit: "Añadir history_manager.py"

---

## ✅ **Checklist Final:**

Tu carpeta `utils/` debe tener **EXACTAMENTE** estos 4 archivos:
```
utils/
├── __init__.py          ✅ (ya lo tienes)
├── data_processor.py    ❓ (créalo ahora)
├── excel_manager.py     ❓ (créalo ahora)
└── history_manager.py   ❓ (créalo ahora)
