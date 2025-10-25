# app.py - Integración del selector de vistas (Anáhuac / UDLA)
# NOTA IMPORTANTE:
# - Si tu app.py original ya contiene st.set_page_config(...), Pega este bloque
#   justo DESPUÉS de esa llamada para evitar duplicados.
# - Este archivo llama a depurador_streamlit.render_udla() cuando el usuario
#   selecciona la vista "UDLA maestrías".
# - Después del bloque marcado como "ORIGINAL APP CONTENT", debes pegar el
#   contenido real de tu app.py (la UI actual de Anáhuac). Si ya lo moviste
#   a otro sitio, deja el placeholder como referencia.
#
# Pasos:
# 1) Coloca depurador_streamlit.py en la misma carpeta que app.py (ya lo agregaste).
# 2) Reemplaza/edita este archivo en tu repo con el contenido siguiente.
# 3) Si tienes st.set_page_config en el "ORIGINAL APP CONTENT", evita duplicarlo:
#    solo debe existir una llamada set_page_config en la app.
#
# -------------------------
import streamlit as st

# Importa el módulo que contiene la vista UDLA (depurador_streamlit.render_udla)
# Asegúrate de que depurador_streamlit.py está en el mismo directorio o en PYTHONPATH.
import depurador_streamlit as depurador_udla

# --- Selector global de vistas (añade en la sidebar) ---
# Coloca este bloque justo después de set_page_config(...) si tu app lo usa.
st.sidebar.header("Seleccionar vista")
vista_global = st.sidebar.radio(
    "Seleccionar vista:",
    ["Anáhuac (versión actual)", "UDLA maestrías"],
    index=0
)

# Si el usuario elige la vista UDLA, renderizamos solo esa vista y detenemos
# la ejecución de app.py para evitar que se muestre la UI actual.
if vista_global == "UDLA maestrías":
    # Llama a la función que definimos en depurador_streamlit.py
    depurador_udla.render_udla()
    st.stop()

# --------------------------
# A partir de aquí continúa la ejecución normal de tu app.py (vista Anáhuac).
# --------------------------
# PEGAR EL CONTENIDO ORIGINAL DE app.py ABIJO DE ESTE COMENTARIO
# -----------------------------------------------------------------
# Si ya tienes el contenido original en el archivo actual, asegúrate de:
#  - No duplicar st.set_page_config (si existe, la llamada debe permanecer donde estaba).
#  - Mantener las importaciones necesarias (puedes mover importaciones arriba si lo prefieres).
# -----------------------------------------------------------------
#
# --- ORIGINAL APP CONTENT START ---
#
# (Pega aquí el contenido original completo de tu app.py que renderiza
#  la interfaz del "Sistema de Carga y Depuración CRM - Maestrías".)
#
# Ejemplo ilustrativo (REMPLAZAR por tu código real):
#
# st.set_page_config(page_title="Sistema de Carga y Depuración CRM - Maestrías", layout="wide")
# st.title("Sistema de Carga y Depuración CRM - Maestrías")
# st.markdown("Sube un CSV, depura, consolida y gestiona rezagados automáticamente.")
#
# with st.sidebar:
#     st.header("Configuración")
#     periodo_actual = st.text_input("Periodo Actual", value="202592")
#     # ... resto de widgets de la sidebar original ...
#
# st.subheader("Carga y Procesamiento de Archivos CRM")
# st.info("Arrastra y suelta tu CSV o usa 'Browse files'.")
# uploaded = st.file_uploader("Drag and drop file here", type=["csv"])
# if uploaded:
#     df = pd.read_csv(uploaded)
#     st.dataframe(df.head(10))
#
# # ... resto de la lógica original ...
#
# --- ORIGINAL APP CONTENT END ---
#
# --------------------------
# FIN del archivo app.py
# --------------------------
