import streamlit as st
import pandas as pd
from datetime import timedelta
import logging
import os

from utils.data_processor import depurar_datos, mapear_columnas
from utils.excel_manager import actualizar_maestro, cargar_archivo_maestro

# Logging básico
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)
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
        st.write("Filtro de tiempo para PaidDate")
        filtro_24h = st.checkbox("Filtrar por últimas 24 horas (sí)", value=True)
        if not filtro_24h:
            rango_dias = st.number_input("Filtrar por últimos N días (si no se usa 24h)", min_value=1, value=7)
        st.markdown("---")
        st.write("URL base (se concatena con LEAD)")
        url_base_input = st.text_input("URL base", value=URL_BASE)

    tab1, tab2, tab3 = st.tabs(["📤 Carga de Datos", "📊 Dashboard", "🔄 Rezagados"])

    with tab1:
        st.header("Carga y Procesamiento de Archivos CRM")
        uploaded_file = st.file_uploader("Subir archivo CSV del CRM", type=["csv"])
        mostrar_preview = st.checkbox("Mostrar vista previa del CSV (primeras filas)", value=True)

        if uploaded_file is not None:
            try:
                raw_df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False)
            except Exception as e:
                st.error(f"No se pudo leer el CSV: {e}")
                st.stop()

            if mostrar_preview:
                st.subheader("Preview del CSV cargado")
                st.dataframe(raw_df.head(10))

            # Depuración
            with st.spinner("Depurando datos..."):
                if filtro_24h:
                    df_depurado = depurar_datos(raw_df, hours=24)
                else:
                    df_depurado = depurar_datos(raw_df, hours=None, days=int(rango_dias))
            if df_depurado is None or df_depurado.empty:
                st.warning("No hay registros después de la depuración / filtro de fechas.")
            else:
                st.success(f"Depuración finalizada: {len(df_depurado)} registros")
                st.subheader("Datos depurados (mapeo hacia maestro)")
                df_mapeado = mapear_columnas(df_depurado, url_base=url_base_input)
                st.dataframe(df_mapeado.head(20))

                if st.button("🚀 Consolidar en Excel Maestro"):
                    with st.spinner("Consolidando en archivo maestro..."):
                        added, moved_rezagados = actualizar_maestro(df_mapeado, archivo_maestro, periodo)
                    st.success(f"Registros añadidos: {added} — Rezagados movidos: {moved_rezagados}")
                    st.write(f"Archivo maestro guardado en: {archivo_maestro}")

    with tab2:
        st.header("📊 Dashboard rápido")
        st.write("Carga el archivo maestro para ver conteos por hoja.")
        if st.button("Cargar estadísticas del maestro"):
            try:
                sheets = cargar_archivo_maestro(archivo_maestro)
                st.write("Hojas detectadas:", list(sheets.keys()))
                for name, df in sheets.items():
                    st.write(f"- {name}: {len(df)} registros")
            except Exception as e:
                st.error(f"Error cargando maestro: {e}")

    with tab3:
        st.header("🔄 Gestión manual de Rezagados")
        st.write("Puedes forzar la ejecución del proceso de detección/movimiento de rezagados en el maestro.")
        if st.button("🔁 Ejecutar mover rezagados ahora"):
            try:
                # Cargar hojas
                sheets = cargar_archivo_maestro(archivo_maestro)
                # Llamamos a actualizar_maestro con df vacío para forzar la gestión de rezagados
                added, moved = actualizar_maestro(pd.DataFrame(), archivo_maestro, periodo, only_manage_rezagados=True)
                st.success(f"Rezagados movidos: {moved}")
            except Exception as e:
                st.error(f"Error moviendo rezagados: {e}")

if __name__ == "__main__":

    main()
