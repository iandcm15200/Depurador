# INSTRUCCIONES:
# - Si tu app.py ya contiene st.set_page_config(...), pega este bloque **después**
#   de esa llamada (no llamar set_page_config dos veces).
# - Coloca depurador_streamlit.py en la misma carpeta (ya lo agregaste).
# - Este archivo agrega un selector en la sidebar para cambiar a la vista "UDLA maestrías".
#   Cuando el usuario seleccione esa vista, llamará a depurador_streamlit.render_udla()
#   y detendrá la ejecución del resto de app.py (st.stop()) para no renderizar la UI actual.
#
# Pega el resto del contenido original de tu app.py donde se indica más abajo.

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
# Pega aquí el contenido ORIGINAL de tu app.py (todo lo que renderiza la interfaz
# actual de "Sistema de Carga y Depuración CRM - Maestrías").
#
# Ejemplo (sólo ilustrativo — sustituye con tu código real):
#
# st.set_page_config(page_title="Sistema de Carga y Depuración CRM - Maestrías", layout="wide")
# st.title("Sistema de Carga y Depuración CRM - Maestrías")
# ...
#
# IMPORTANTE: No olvides eliminar del inicio del contenido original cualquier
# importación o st.set_page_config duplicada si ya las tienes arriba.
#
# --------------------------
# FIN: pega el resto de tu app.py aquí
# --------------------------
