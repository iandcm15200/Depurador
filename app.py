import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import os
import json

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
            uploaded_file = st.file_uploader("Subir archivo CSV del CRM", type=["csv"])
        with col2:
            st.info(f"📅 Fecha/Hora actual:\n{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        mostrar_preview = st.checkbox("Mostrar vista previa del CSV (primeras filas)", value=True)

        if uploaded_file is not None:
            try:
                # Timestamp de carga
                timestamp_carga = datetime.now()
                
                raw_df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
                total_filas_originales = len(raw_df)
                
                st.success(f"✅ Archivo cargado: {uploaded_file.name}")
                st.write(f"📊 Total de registros en CSV: **{total_filas_originales}**")
                
            except Exception as e:
                st.error(f"❌ No se pudo leer el CSV: {e}")
                st.stop()

            if mostrar_preview:
                st.subheader("Preview del CSV cargado")
                st.dataframe(raw_df.head(10))

            # Depuración
            with st.spinner("🔄 Depurando datos..."):
                if filtro_personalizado and rango_dias is not None:
                    df_depurado = depurar_datos(raw_df, hours=None, days=int(rango_dias), timestamp_referencia=timestamp_carga)
                else:
                    df_depurado = depurar_datos(raw_df, hours=int(rango_horas), days=None, timestamp_referencia=timestamp_carga)
            
            if df_depurado is None or df_depurado.empty:
                st.warning("⚠️ No hay registros después de la depuración / filtro de fechas.")
                
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
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Filas originales", total_filas_originales)
                with col2:
                    st.metric("Filas depuradas", filas_depuradas)
                with col3:
                    eliminadas = total_filas_originales - filas_depuradas
                    st.metric("Filas eliminadas", eliminadas, delta=f"-{(eliminadas/total_filas_originales*100):.1f}%")
                
                st.subheader("Datos depurados (mapeo hacia maestro)")
                df_mapeado = mapear_columnas(df_depurado, url_base=url_base_input)
                st.dataframe(df_mapeado.head(20))

                # Botón para consolidar
                if st.button("🚀 Consolidar en Excel Maestro", type="primary"):
                    with st.spinner("📝 Consolidando en archivo maestro..."):
                        added, moved_rezagados = actualizar_maestro(df_mapeado, archivo_maestro, periodo)
                    
                    st.success(f"✅ **Consolidación completada!**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Registros añadidos", added)
                    with col2:
                        st.metric("Rezagados movidos", moved_rezagados)
                    
                    st.info(f"💾 Archivo maestro guardado en: `{archivo_maestro}`")
                    
                    # Guardar historial
                    info_depuracion = {
                        'timestamp': timestamp_carga.strftime('%Y-%m-%d %H:%M:%S'),
                        'archivo': uploaded_file.name,
                        'filas_originales': total_filas_originales,
                        'filas_depuradas': filas_depuradas,
                        'filas_agregadas': added,
                        'rezagados_movidos': moved_rezagados,
                        'filtro_horas': rango_horas if rango_dias is None else None,
                        'filtro_dias': rango_dias,
                        'periodo': periodo
                    }
                    guardar_historial(info_depuracion, HISTORY_DIR)
                    st.success("📊 Historial actualizado")

    with tab2:
        st.header("📊 Dashboard rápido")
        st.write("Carga el archivo maestro para ver conteos por hoja.")
        
        if st.button("🔍 Cargar estadísticas del maestro"):
            try:
                sheets = cargar_archivo_maestro(archivo_maestro)
                
                if not sheets:
                    st.warning("No se encontró el archivo maestro o está vacío")
                else:
                    st.success(f"✅ Archivo maestro cargado: {len(sheets)} hojas detectadas")
                    
                    # Crear tabla resumen
                    resumen_data = []
                    for name, df in sheets.items():
                        resumen_data.append({
                            'Hoja': name,
                            'Registros': len(df),
                            'Columnas': len(df.columns)
                        })
                    
                    df_resumen = pd.DataFrame(resumen_data)
                    st.dataframe(df_resumen, use_container_width=True)
                    
                    # Gráfico
                    if not df_resumen.empty:
                        st.bar_chart(df_resumen.set_index('Hoja')['Registros'])
                        
            except Exception as e:
                st.error(f"❌ Error cargando maestro: {e}")

    with tab3:
        st.header("🔄 Gestión manual de Rezagados")
        st.write("Puedes forzar la ejecución del proceso de detección/movimiento de rezagados en el maestro.")
        
        if st.button("🔍 Ejecutar mover rezagados ahora", type="primary"):
            try:
                # Cargar hojas
                sheets = cargar_archivo_maestro(archivo_maestro)
                if not sheets:
                    st.warning("No se encontró el archivo maestro")
                else:
                    # Llamamos a actualizar_maestro con df vacío para forzar la gestión de rezagados
                    added, moved = actualizar_maestro(pd.DataFrame(), archivo_maestro, periodo, only_manage_rezagados=True)
                    st.success(f"✅ Rezagados movidos: **{moved}**")
            except Exception as e:
                st.error(f"❌ Error moviendo rezagados: {e}")

    with tab4:
        st.header("📈 Historial de Depuraciones")
        st.write("Registro histórico de todas las depuraciones realizadas")
        
        # Cargar y mostrar historial
        historial = cargar_historial(HISTORY_DIR)
        
        if historial:
            mostrar_estadisticas(historial)
        else:
            st.info("📭 No hay historial de depuraciones aún")

if __name__ == "__main__":
    main()
