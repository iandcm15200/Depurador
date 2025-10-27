import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import os

from utils.data_processor import depurar_datos, mapear_columnas
from utils.excel_manager import actualizar_maestro, cargar_archivo_maestro
from utils.history_manager import guardar_historial, cargar_historial, mostrar_estadisticas

# Logging básico (puedes mantenerlo a nivel módulo)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DATA_DIR = "data"
HISTORY_DIR = "history"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

DEFAULT_MAESTRO = os.path.join(DATA_DIR, "conglomerado_maestrias.xlsx")
URL_BASE = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"

def main():
    # Configuración de página: se debe llamar antes de cualquier UI
    st.set_page_config(page_title="Sistema de Carga y Depuración CRM - Maestrías", layout="wide")

    # -----------------------
    # Selector de vistas (Anáhuac / UDLA / Licenciatura)
    # -----------------------
    st.sidebar.header("Seleccionar vista")
    vista_global = st.sidebar.radio(
        "Seleccionar vista:",
        ["Anáhuac (versión actual)", "UDLA maestrías", "Licenciatura Maestrías"],
        index=0
    )

    # Cargar vistas condicionalmente para evitar ejecuciones top-level no deseadas
    if vista_global == "UDLA maestrías":
        try:
            import importlib
            depurador_udla = importlib.import_module("depurador_streamlit")
            if hasattr(depurador_udla, "render_udla"):
                depurador_udla.render_udla()
            else:
                st.error("El módulo depurador_streamlit no expone la función render_udla().")
        except Exception as e:
            st.error(f"Error cargando la vista UDLA: {e}")
        st.stop()

    if vista_global == "Licenciatura Maestrías":
        try:
            import importlib
            depurador_lic = importlib.import_module("depurador_licenciaturas")
            if hasattr(depurador_lic, "render_licenciatura"):
                depurador_lic.render_licenciatura()
            else:
                st.error("El módulo depurador_licenciaturas no expone la función render_licenciatura().")
        except Exception as e:
            st.error(f"Error cargando la vista Licenciatura: {e}")
        st.stop()

    # -----------------------
    # Vista Anáhuac (UI original)
    # -----------------------
    st.title("🏢 Sistema de Carga y Depuración CRM - Maestrías")
    st.markdown("Sube un CSV, depura, consolida y gestiona rezagados automáticamente.")

    # Sidebar configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        periodo = st.text_input("Período Actual", value="202592")
        archivo_maestro = st.text_input("Ruta archivo maestro (Excel)", value=DEFAULT_MAESTRO)
        st.markdown("---")
        st.write("**Filtro de tiempo para PaidDate**")
        st.info("🕐 Por defecto: últimas 48 horas desde la fecha/hora actual de carga")
        filtro_personalizado = st.checkbox("Usar filtro personalizado", value=False)
        if filtro_personalizado:
            tipo_filtro = st.radio("Tipo de filtro:", ["Horas", "Días"])
            if tipo_filtro == "Horas":
                rango_horas = st.number_input("Últimas N horas", min_value=1, value=48)
                rango_dias = None
            else:
                rango_dias = st.number_input("Últimos N días", min_value=1, value=1)
                rango_horas = None
        else:
            rango_horas = 48
            rango_dias = None

        st.markdown("---")
        st.write("URL base (se concatena con LEAD)")
        url_base_input = st.text_input("URL base", value=URL_BASE)
        start_from_prev_midnight = st.checkbox("Incluir desde medianoche del día anterior (en lugar de últimas N horas)", value=False)

    # (Resto de la UI idéntico a la versión anterior...)
    # Aquí va el resto de la lógica: tabs, upload, depuración, consolidación, etc.
    # Para brevedad no lo repito en su totalidad; conserva el flujo actual dentro de main().

if __name__ == "__main__":
    main()
