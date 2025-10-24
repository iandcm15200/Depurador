import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

# Configuración básica - SIN imports problemáticos
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
DEFAULT_MAESTRO = os.path.join(DATA_DIR, "conglomerado_maestrias.xlsx")
URL_BASE = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"

# Funciones básicas de procesamiento (TODO en un solo archivo)
def depurar_datos(df, hours=24, days=None):
    """Función de depuración simplificada"""
    try:
        # Mantener solo columnas necesarias
        columnas_necesarias = ['Id', 'Email', 'Nombre', 'Apellido', 
                             'TelefonoMovil', 'Operador', 'Programa', 'PaidDate']
        
        # Filtrar columnas que existen
        columnas_existentes = [col for col in columnas_necesarias if col in df.columns]
        df_limpio = df[columnas_existentes].copy()
        
        # Procesar fecha si existe
        if 'PaidDate' in df_limpio.columns:
            df_limpio['PaidDate'] = pd.to_datetime(df_limpio['PaidDate'], errors='coerce', dayfirst=True)
            
            # Aplicar filtro de tiempo
            if hours:
                fecha_limite = datetime.now() - timedelta(hours=hours)
                df_filtrado = df_limpio[df_limpio['PaidDate'] >= fecha_limite]
            elif days:
                fecha_limite = datetime.now() - timedelta(days=days)
                df_filtrado = df_limpio[df_limpio['PaidDate'] >= fecha_limite]
            else:
                df_filtrado = df_limpio
        else:
            df_filtrado = df_limpio
        
        return df_filtrado
        
    except Exception as e:
        st.error(f"Error en depuración: {str(e)}")
        return df

def mapear_columnas(df, url_base=URL_BASE):
    """Mapeo de columnas simplificado"""
    try:
        df_mapeado = df.copy()
        
        # Concatenar Nombre + Apellido
        if 'Nombre' in df_mapeado.columns and 'Apellido' in df_mapeado.columns:
            df_mapeado['Nombre Apellido'] = df_mapeado['Nombre'] + ' ' + df_mapeado['Apellido']
            df_mapeado = df_mapeado.drop(['Nombre', 'Apellido'], axis=1, errors='ignore')
        
        # Renombrar columnas
        mapeo = {
            'Operador': 'Asesor de ventas',
            'Id': 'LEAD', 
            'Email': 'Email',
            'TelefonoMovil': 'Telefono Movil',
            'Programa': 'Programa',
            'PaidDate': 'PaidDate'
        }
        
        df_mapeado = df_mapeado.rename(columns=mapeo)
        
        # Añadir URL si existe LEAD
        if 'LEAD' in df_mapeado.columns:
            df_mapeado['URL_Lead'] = url_base + df_mapeado['LEAD'].astype(str)
        
        return df_mapeado
        
    except Exception as e:
        st.error(f"Error en mapeo: {str(e)}")
        return df

def actualizar_maestro(df_nuevo, archivo_maestro, periodo):
    """Función simplificada para guardar en Excel"""
    try:
        hoja_ventas = f"Ventas Nuevas Maestrías {periodo}"
        
        # Si el archivo maestro existe, cargarlo
        if os.path.exists(archivo_maestro):
            try:
                with pd.ExcelFile(archivo_maestro) as xls:
                    if hoja_ventas in xls.sheet_names:
                        df_existente = pd.read_excel(archivo_maestro, sheet_name=hoja_ventas)
                    else:
                        df_existente = pd.DataFrame()
            except:
                df_existente = pd.DataFrame()
        else:
            df_existente = pd.DataFrame()
        
        # Combinar datos
        if not df_existente.empty and not df_nuevo.empty:
            df_combinado = pd.concat([df_existente, df_nuevo], ignore_index=True)
            # Eliminar duplicados por LEAD
            if 'LEAD' in df_combinado.columns:
                df_combinado = df_combinado.drop_duplicates(subset=['LEAD'])
        elif not df_nuevo.empty:
            df_combinado = df_nuevo
        else:
            df_combinado = df_existente
        
        # Guardar
        with pd.ExcelWriter(archivo_maestro, engine='openpyxl') as writer:
            df_combinado.to_excel(writer, sheet_name=hoja_ventas, index=False)
        
        registros_agregados = len(df_nuevo) if not df_nuevo.empty else 0
        return registros_agregados, 0  # rezagados_movidos = 0 por ahora
        
    except Exception as e:
        st.error(f"Error guardando Excel: {str(e)}")
        return 0, 0

def main():
    st.set_page_config(
        page_title="Sistema de Carga y Depuración CRM - Maestrías", 
        layout="wide"
    )
    
    st.title("🏢 Sistema de Carga y Depuración CRM - Maestrías")
    st.markdown("Sube un CSV, depura, consolida y gestiona rezagados automáticamente.")

    # Sidebar configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        periodo = st.text_input("Período Actual", value="202592")
        archivo_maestro = st.text_input("Ruta archivo maestro", value=DEFAULT_MAESTRO)
        st.markdown("---")
        st.write("Filtro de tiempo para PaidDate")
        filtro_24h = st.checkbox("Filtrar por últimas 24 horas", value=True)
        if not filtro_24h:
            rango_dias = st.number_input("Filtrar por últimos N días", min_value=1, value=7)
        st.markdown("---")
        st.write("URL base para links")
        url_base_input = st.text_input("URL base", value=URL_BASE)

    tab1, tab2 = st.tabs(["📤 Carga de Datos", "📊 Dashboard"])

    with tab1:
        st.header("Carga y Procesamiento de Archivos CRM")
        uploaded_file = st.file_uploader("Subir archivo CSV del CRM", type=["csv"])
        
        if uploaded_file is not None:
            try:
                # Leer archivo
                raw_df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False, encoding='latin-1')
                st.success(f"✅ Archivo cargado: {len(raw_df)} registros")
                
                # Vista previa
                with st.expander("📋 Vista previa del CSV original"):
                    st.dataframe(raw_df.head(10))
                    st.write(f"**Columnas detectadas:** {list(raw_df.columns)}")

                # Depuración
                with st.spinner("🔄 Depurando datos..."):
                    if filtro_24h:
                        df_depurado = depurar_datos(raw_df, hours=24)
                    else:
                        df_depurado = depurar_datos(raw_df, days=int(rango_dias))
                
                if df_depurado.empty:
                    st.warning("⚠️ No hay registros después del filtro de fecha.")
                    st.info("💡 Prueba desactivar el filtro de 24 horas o verifica las fechas en tu CSV")
                else:
                    st.success(f"✅ Datos depurados: {len(df_depurado)} registros")
                    
                    # Mapeo
                    df_mapeado = mapear_columnas(df_depurado, url_base=url_base_input)
                    
                    with st.expander("👀 Vista de datos mapeados"):
                        st.dataframe(df_mapeado)
                    
                    # Consolidación
                    if st.button("🚀 Consolidar en Excel Maestro", type="primary"):
                        with st.spinner("💾 Guardando en archivo maestro..."):
                            added, moved = actualizar_maestro(df_mapeado, archivo_maestro, periodo)
                        
                        st.success(f"""
                        ✅ **Proceso completado:**
                        - Registros añadidos: **{added}**
                        - Archivo guardado en: `{archivo_maestro}`
                        """)
                        
                        # Opción para descargar resultado
                        csv = df_mapeado.to_csv(index=False)
                        st.download_button(
                            label="📥 Descargar CSV depurado",
                            data=csv,
                            file_name=f"depurado_{periodo}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime="text/csv"
                        )
                        
            except Exception as e:
                st.error(f"❌ Error procesando archivo: {str(e)}")
                st.info("💡 Verifica que el archivo CSV tenga el formato correcto")

    with tab2:
        st.header("📊 Dashboard")
        st.write("Estadísticas del sistema")
        
        if st.button("📈 Ver estado del archivo maestro"):
            try:
                if os.path.exists(archivo_maestro):
                    with pd.ExcelFile(archivo_maestro) as xls:
                        hojas = xls.sheet_names
                    
                    st.success(f"✅ Archivo maestro encontrado: {len(hojas)} hojas")
                    
                    for hoja in hojas:
                        df_hoja = pd.read_excel(archivo_maestro, sheet_name=hoja)
                        st.write(f"**{hoja}:** {len(df_hoja)} registros")
                else:
                    st.info("📝 El archivo maestro aún no existe. Procesa un CSV primero.")
                    
            except Exception as e:
                st.error(f"Error leyendo archivo maestro: {e}")

if __name__ == "__main__":
    main()
