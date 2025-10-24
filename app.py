import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import os

from utils.data_processor import depurar_datos, mapear_columnas
from utils.excel_manager import actualizar_maestro, cargar_archivo_maestro
from utils.history_manager import guardar_historial, cargar_historial, mostrar_estadisticas

# Logging básico
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DATA_DIR = "data"
HISTORY_DIR = "history"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

DEFAULT_MAESTRO = os.path.join(DATA_DIR, "conglomerado_maestrias.xlsx")
URL_BASE = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"

def main():
    st.set_page_config(page_title="Sistema de Carga y Depuración CRM - Maestrías", layout="wide")
    st.title("🏢 Sistema de Carga y Depuración CRM - Maestrías")
    st.markdown("Sube un CSV, depura, consolida y gestiona rezagados automáticamente.")

    # Sidebar configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        periodo = st.text_input("Período Actual", value="202592")
        archivo_maestro = st.text_input("Ruta archivo maestro (Excel)", value=DEFAULT_MAESTRO)
        st.markdown("---")
        st.write("**Filtro de tiempo para PaidDate**")
        st.info("🕐 Por defecto: últimas 24 horas desde la fecha/hora actual de carga")
        filtro_personalizado = st.checkbox("Usar filtro personalizado", value=False)
        if filtro_personalizado:
            tipo_filtro = st.radio("Tipo de filtro:", ["Horas", "Días"])
            if tipo_filtro == "Horas":
                rango_horas = st.number_input("Últimas N horas", min_value=1, value=24)
                rango_dias = None
            else:
                rango_dias = st.number_input("Últimos N días", min_value=1, value=1)
                rango_horas = None
        else:
            rango_horas = 24
            rango_dias = None
        
        st.markdown("---")
        st.write("URL base (se concatena con LEAD)")
        url_base_input = st.text_input("URL base", value=URL_BASE)

    tab1, tab2, tab3, tab4 = st.tabs(["📤 Carga de Datos", "📊 Dashboard", "🔄 Rezagados", "📈 Historial"])

    with tab1:
        st.header("Carga y Procesamiento de Archivos CRM")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader("Subir archivo CSV del CRM (vwCRMLeads)", type=["csv"])
        with col2:
            st.info(f"📅 Fecha/Hora actual:\n{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        mostrar_preview = st.checkbox("Mostrar vista previa del CSV original (primeras 10 filas)", value=True)

        if uploaded_file is not None:
            try:
                # Timestamp de carga
                timestamp_carga = datetime.now()
                
                # Leer CSV
                raw_df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False, encoding='utf-8')
                total_filas_originales = len(raw_df)
                
                st.success(f"✅ Archivo cargado: {uploaded_file.name}")
                st.write(f"📊 Total de registros en CSV: **{total_filas_originales}**")
                
            except Exception as e:
                st.error(f"❌ No se pudo leer el CSV: {e}")
                st.stop()

            if mostrar_preview:
                st.subheader("👀 Preview del CSV Original")
                st.dataframe(raw_df.head(10), use_container_width=True)

            # Depuración
            st.markdown("---")
            st.subheader("🔄 Depurando datos...")
            
            with st.spinner("Procesando..."):
                try:
                    if filtro_personalizado and rango_dias is not None:
                        df_depurado = depurar_datos(raw_df, hours=None, days=int(rango_dias), timestamp_referencia=timestamp_carga)
                    else:
                        df_depurado = depurar_datos(raw_df, hours=int(rango_horas), days=None, timestamp_referencia=timestamp_carga)
                except Exception as e:
                    st.error(f"❌ Error durante la depuración: {e}")
                    st.stop()
            
            if df_depurado is None or df_depurado.empty:
                st.warning("⚠️ No hay registros después de la depuración / filtro de fechas.")
                st.info("💡 Sugerencias:")
                st.write("- Verifica que el CSV tenga la columna **PaidDate**")
                st.write("- Verifica que las fechas estén en formato: **DD/MM/YYYY HH:MM**")
                st.write("- Intenta usar un filtro de más días si el filtro de 24h es muy restrictivo")
                
                # Guardar historial incluso si está vacío
                info_depuracion = {
                    'timestamp': timestamp_carga.strftime('%Y-%m-%d %H:%M:%S'),
                    'archivo': uploaded_file.name,
                    'filas_originales': total_filas_originales,
                    'filas_depuradas': 0,
                    'filas_agregadas': 0,
                    'rezagados_movidos': 0,
                    'filtro_horas': rango_horas if rango_dias is None else None,
                    'filtro_dias': rango_dias,
                    'periodo': periodo
                }
                guardar_historial(info_depuracion, HISTORY_DIR)
                
            else:
                filas_depuradas = len(df_depurado)
                st.success(f"✅ Depuración finalizada: **{filas_depuradas}** registros")
                
                # Mostrar estadísticas de depuración
                st.subheader("📊 Estadísticas de Depuración")
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Filas originales", total_filas_originales)
                with col2:
                    st.metric("Filas depuradas", filas_depuradas)
                with col3:
                    eliminadas = total_filas_originales - filas_depuradas
                    porcentaje = (eliminadas/total_filas_originales*100) if total_filas_originales > 0 else 0
                    st.metric("Filas eliminadas", eliminadas, delta=f"-{porcentaje:.1f}%")
                
                # MAPEAR Y MOSTRAR DATOS DEPURADOS
                st.markdown("---")
                st.subheader("✅ Datos Depurados - Formato Base Documentos Anáhuac")
                st.write(f"**Total registros:** {filas_depuradas}")
                
                try:
                    df_mapeado = mapear_columnas(df_depurado, url_base=url_base_input)
                    
                    # Mostrar DataFrame completo con scroll
                    st.dataframe(
                        df_mapeado,
                        use_container_width=True,
                        height=400
                    )
                    
                    # Botón para descargar CSV depurado
                    csv_depurado = df_mapeado.to_csv(index=False, encoding='utf-8-sig')
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.download_button(
                            label="📥 Descargar CSV Depurado",
                            data=csv_depurado.encode('utf-8-sig'),
                            file_name=f"depurado_{uploaded_file.name.replace('.csv', '')}_{timestamp_carga.strftime('%Y%m%d_%H%M%S')}.csv",
                            mime="text/csv",
                            help="Descarga el archivo depurado para copiar a Excel"
                        )
                    
                    with col2:
                        st.info("💡 **Tip:** Puedes seleccionar todo en la tabla (Ctrl+A) y copiar (Ctrl+C) para pegar directamente en Excel")
                    
                except Exception as e:
                    st.error(f"❌ Error al mapear columnas: {e}")
                    st.stop()

                # Botón para consolidar en Excel Maestro
                st.markdown("---")
                st.subheader("💾 Consolidar en Excel Maestro")
                
                if st.button("🚀 Consolidar en Excel Maestro", type="primary"):
                    with st.spinner("📝 Consolidando en archivo maestro..."):
                        try:
                            added, moved_rezagados = a
