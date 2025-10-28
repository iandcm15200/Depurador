# helper UI para Streamlit — versión mínima segura
import streamlit as st
import pandas as pd
import logging
import msal
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

CORRECT_SCOPES = ["Files.ReadWrite", "User.Read"]

def _looks_like_share_url(s: str) -> bool:
    return isinstance(s, str) and s.strip().lower().startswith(("http://", "https://"))

def _looks_like_item_id(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    return bool(re.match(r'^[A-Za-z0-9\-\_\:]{8,250}$', s))

def setup_excel_connection_persistent():
    """
    UI mínima para pedir AZURE_CLIENT_ID y URL/item_id del libro.
    Guarda en st.session_state: excel_access_token, excel_share_url/item_id, excel_sheet_name, excel_connected
    """
    st.sidebar.markdown("### 📊 Conexión a Excel Online (persistente)")
    if "excel_connected" not in st.session_state:
        st.session_state.excel_connected = False

    client_id = st.secrets.get("AZURE_CLIENT_ID") or st.sidebar.text_input("AZURE_CLIENT_ID", type="password")
    if not client_id:
        st.sidebar.info("Define AZURE_CLIENT_ID en Streamlit secrets o escríbelo aquí.")
        return

    share_url = st.sidebar.text_input("🔗 URL del libro de Excel (o item_id)", placeholder="https://...")
    if share_url and len(share_url) > 2000:
        st.sidebar.error("La entrada es demasiado larga y no parece una URL válida.")
        return

    if st.sidebar.button("🔐 Conectar (Device Code)"):
        if not share_url:
            st.sidebar.error("Debes proporcionar la URL o el item_id del libro.")
            return
        share_url = share_url.strip()
        if not (_looks_like_share_url(share_url) or _looks_like_item_id(share_url)):
            st.sidebar.error("La entrada no parece una URL de compartir ni un item_id válido.")
            return

        with st.spinner("Iniciando Device Flow..."):
            try:
                tenant = os.environ.get("AZURE_TENANT_ID", "873b9e93-4463-4b67-a3a9-3dee5f35cec2")
                authority = f"https://login.microsoftonline.com/{tenant}"
                app = msal.PublicClientApplication(client_id, authority=authority)
                flow = app.initiate_device_flow(scopes=CORRECT_SCOPES)
                if "user_code" not in flow:
                    st.sidebar.error("No se pudo iniciar Device Flow (respuesta inesperada).")
                    logger.error("Device flow failed: %s", flow)
                    return
                with st.sidebar.expander("📱 Código de autenticación", expanded=True):
                    st.code(flow.get("user_code", ""), language=None)
                    st.markdown(flow.get("message", ""))

                token = app.acquire_token_by_device_flow(flow)
                if "access_token" not in token:
                    st.sidebar.error("Autenticación fallida.")
                    logger.error("Device flow returned no access_token: %s", token)
                    return

                access_token = token["access_token"]

                # Importar GraphClient aquí para evitar imports top-level y ciclos
                from .graph_client import GraphClient

                gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES, authority=authority)
                gc.access_token = access_token

                # Intentar listar worksheets (la función en graph_client valida share_url vs item_id)
                worksheets = gc.get_workbook_worksheets(share_url)
                if not worksheets:
                    st.sidebar.error("No se encontraron hojas en el libro (o acceso denegado).")
                    return

                st.session_state.excel_access_token = access_token
                st.session_state.excel_share_url = share_url
                st.session_state.excel_client_id = client_id
                st.session_state.temp_worksheets = worksheets
                st.session_state.show_sheet_selector = True
                st.rerun()

            except Exception as e:
                st.sidebar.error(f"Error al conectar: {e}")
                logger.exception("setup_excel_connection_persistent error:")
                return

    # Selector de hoja (después de autenticar)
    if st.session_state.get("show_sheet_selector", False):
        worksheets = st.session_state.temp_worksheets
        sheet_names = [w.get("name") for w in worksheets]
        selected_sheet = st.sidebar.selectbox("📄 Selecciona la hoja", options=sheet_names, key="sheet_selector")
        if st.sidebar.button("✅ Confirmar hoja"):
            st.session_state.excel_sheet_name = selected_sheet
            st.session_state.excel_connected = True
            # mover token/share_url a variables definitivas
            st.session_state.excel_share_url = st.session_state.get("excel_share_url", st.session_state.get("temp_share_url"))
            st.session_state.excel_access_token = st.session_state.get("excel_access_token", st.session_state.get("temp_access_token"))
            # limpiar temporales
            for k in ["temp_access_token", "temp_share_url", "temp_worksheets", "show_sheet_selector"]:
                if k in st.session_state:
                    del st.session_state[k]
            st.sidebar.success(f"Conectado: {selected_sheet}")
            st.rerun()

def send_to_connected_excel(df_to_append: pd.DataFrame, show_preview: bool = True) -> bool:
    """
    Función mínima para enviar df a Excel usando la conexión almacenada en session_state.
    Devuelve True/False. Lanza errores claros si no hay conexión.
    """
    if not st.session_state.get("excel_connected", False):
        st.error("No hay conexión activa a un libro de Excel. Configura la conexión en la barra lateral.")
        return False
    access_token = st.session_state.get("excel_access_token")
    share_or_item = st.session_state.get("excel_share_url")
    sheet_name = st.session_state.get("excel_sheet_name")
    client_id = st.session_state.get("excel_client_id")

    if access_token is None or share_or_item is None or not sheet_name:
        st.error("Faltan datos de conexión. Reconecta al libro.")
        return False

    # Importar GraphClient solo cuando se usa
    from .graph_client import GraphClient

    try:
        gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES)
        gc.access_token = access_token

        # Obtener tablas (graph_client debe exponer get_worksheet_tables)
        tables = gc.get_worksheet_tables(share_or_item, sheet_name)
        if tables:
            table_id = tables[0].get("id")
        else:
            # crear tabla con encabezados del df
            cols = df_to_append.columns.tolist()
            last_col = _col_letter(len(cols) - 1) if len(cols) > 0 else "A"
            header_range = f"{sheet_name}!A1:{last_col}1"
            table_obj = gc.create_table_on_sheet(share_or_item, sheet_name, header_range=header_range, has_headers=True)
            table_id = table_obj.get("id")

        # preparar valores
        values = []
        for _, row in df_to_append.iterrows():
            values.append([("" if pd.isna(row[c]) else str(row[c])) for c in df_to_append.columns])

        # enviar en uno o varios requests
        gc.add_rows_to_table(share_or_item, table_id, values)
        st.success("Datos enviados a Excel.")
        return True

    except Exception as e:
        st.error(f"Error enviando datos a Excel: {e}")
        logger.exception("send_to_connected_excel error:")
        return False

def integrate_ui_and_append(share_url: str, df_to_append: pd.DataFrame):
    """
    Mantener firma para compatibilidad UDLA: usa send_to_connected_excel internamente.
    """
    if df_to_append is None or df_to_append.empty:
        st.info("No hay datos para enviar.")
        return
    # Si no hay conexión, intentar conectar con share_url pegado aquí (no recomendado)
    if not st.session_state.get("excel_connected", False):
        st.info("No hay conexión persistente. Usa la barra lateral para conectar o pásame AZURE_CLIENT_ID.")
        return
    return send_to_connected_excel(df_to_append, show_preview=True)

# helpers internos
def _col_letter(idx: int) -> str:
    letters = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters
