# -----------------------
# Selector de vistas (Anáhuac / UDLA / Licenciatura)
# -----------------------
st.sidebar.header("Seleccionar vista")
vista_global = st.sidebar.radio(
    "Seleccionar vista:",
    ["Anáhuac (versión actual)", "UDLA maestrías", "Licenciatura Maestrías"],
    index=0
)

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
        depurador_lic = importlib.import_module("depurador_licenciatura")
        if hasattr(depurador_lic, "render_licenciatura"):
            depurador_lic.render_licenciatura()
        else:
            st.error("El módulo depurador_licenciatura no expone la función render_licenciatura().")
    except Exception as e:
        st.error(f"Error cargando la vista Licenciatura: {e}")
    st.stop()
