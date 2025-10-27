import streamlit as st
from datetime import datetime
import pandas as pd
import io

from utils.data_processor import depurar_datos, mapear_columnas
from utils.excel_manager import actualizar_maestro, cargar_archivo_maestro

DEFAULT_MAESTRO = "data/conglomerado_licenciaturas.xlsx"
URL_BASE = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"

def render_licenciatura():
    st.title("🏫 Licenciatura - Sistema de Carga y Depuración CRM")
    st.markdown("Vista: Licenciatura Maestría — sube o pega un CSV/TSV. Esta vista replica la lógica de Maestrías (Anáhuac).")

    periodo = st.text_input("Período Actual", value="202592")
    archivo_maestro = st.text_input("Ruta archivo maestro (Excel)", value=DEFAULT_MAESTRO)

    rango_horas = st.number_input("Últimas N horas", min_value=1, value=48)
    start_from_prev_midnight = st.checkbox("Incluir desde medianoche del día anterior", value=False)

    uploaded_file = st.file_uploader("Subir archivo CSV del CRM (vwCRMLeads)", type=["csv","txt"])
    text_area = st.text_area("O pega aquí los datos (CSV/TSV) — incluye la fila de encabezados", height=180)

    content_text = None
    if uploaded_file is not None:
        try:
            raw = uploaded_file.read()
            try:
                content_text = raw.decode("utf-8")
            except Exception:
                content_text = raw.decode("latin-1")
        except Exception as e:
            st.error(f"Error leyendo archivo: {e}")

    if text_area and not content_text:
        content_text = text_area

    if not content_text:
        st.info("Sube un archivo CSV/TSV o pega los datos para comenzar.")
        return

    try:
        df_raw = pd.read_csv(io.StringIO(content_text), dtype=str, keep_default_na=False, sep=None, engine="python")
    except Exception:
        try:
            df_raw = pd.read_csv(io.StringIO(content_text), dtype=str, keep_default_na=False)
        except Exception as e:
            st.error(f"No se pudo leer el CSV: {e}")
            return

    timestamp_carga = datetime.now()
    st.success(f"Archivo cargado: {len(df_raw)} filas detectadas")

    with st.spinner("Depurando..."):
        df_depurado = depurar_datos(df_raw, hours=int(rango_horas), timestamp_referencia=timestamp_carga, start_from_prev_midnight=start_from_prev_midnight, vista="licenciatura")

    if df_depurado is None or df_depurado.empty:
        st.warning("No hay registros tras la depuración.")
        return

    st.dataframe(df_depurado.head(100), use_container_width=True)

    if st.button("🚀 Consolidar en Excel Maestro"):
        with st.spinner("Consolidando..."):
            added, moved = actualizar_maestro(df_depurado, archivo_maestro, periodo)
        st.success(f"Consolidación completada. Añadidos: {added}, Rezagados movidos: {moved}")

    if st.button("🔍 Cargar estadísticas del maestro"):
        sheets = cargar_archivo_maestro(archivo_maestro)
        if not sheets:
            st.warning("No se encontró el archivo maestro")
        else:
            resumen = [{ "Hoja": k, "Registros": len(v) } for k, v in sheets.items()]
            st.table(resumen)
