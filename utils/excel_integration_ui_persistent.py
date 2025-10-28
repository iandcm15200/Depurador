# (fragmento principal modificado: añade validación de share_url antes de usarlo)

import streamlit as st
import pandas as pd
from typing import Optional
import logging
import msal
import os
import re

logger = logging.getLogger(__name__)

# ⭐ SCOPES CORRECTOS - Sin offline_access (MSAL lo agrega automáticamente)
CORRECT_SCOPES = ["Files.ReadWrite", "User.Read"]

def _looks_like_share_url(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    return s.lower().startswith(("http://", "https://"))

def _looks_like_item_id(s: str) -> bool:
    if not isinstance(s, str):
        return False
    s = s.strip()
    # item_id plausible: sin espacios, longitud razonable y caracteres alfanum/-/_/:.
    return bool(re.match(r'^[A-Za-z0-9\-\_\:]{8,250}$', s))

def setup_excel_connection_persistent():
    st.sidebar.markdown("### 📊 Conexión a Excel Online")
    # inicialización session_state (mantener tu código)
    if "excel_connected" not in st.session_state:
        st.session_state.excel_connected = False
    # ... (el resto de inicialización)

    # Obtener Client ID
    client_id = st.secrets.get("AZURE_CLIENT_ID") or st.sidebar.text_input(
        "AZURE_CLIENT_ID",
        type="password",
        help="Client ID de Azure AD"
    )
    if not client_id:
        st.sidebar.warning("⚠️ Se requiere AZURE_CLIENT_ID")
        return

    # URL del libro de Excel
    share_url = st.sidebar.text_input(
        "🔗 URL del libro de Excel",
        placeholder="https://tu-org.sharepoint.com/...",
        help="Pega aquí el enlace de compartir del libro de Excel (debe empezar por https://)"
    )

    # Si el usuario pega accidentalmente código largo, detectarlo y mostrar mensaje claro
    if share_url and len(share_url) > 2000:
        st.sidebar.error("La entrada parece demasiado larga y no es una URL válida. Pega la URL de compartir del libro (https://...).")
        return

    # Botón para iniciar conexión
    if st.sidebar.button("🔐 Conectar a Excel", type="primary"):
        if not share_url:
            st.sidebar.error("❌ Debes proporcionar la URL del libro")
            return

        share_url = share_url.strip()

        # Validación clara antes de proceder
        if not _looks_like_share_url(share_url) and not _looks_like_item_id(share_url):
            st.sidebar.error("❌ La entrada no parece una URL de compartir (https://...) ni un item_id válido. Por favor pega la URL de compartir del libro en OneDrive/SharePoint o el item_id correcto.")
            st.sidebar.info("Ejemplo de URL válida: https://aplatamh-my.sharepoint.com/:x:/r/personal/usuario_tu_org/... (pulsar 'Compartir' → 'Copiar vínculo')")
            return

        # Si pasa la validación, continua con el flujo normal (Device Flow / MSAL)
        with st.spinner("Conectando a Microsoft Graph..."):
            try:
                tenant = os.environ.get("AZURE_TENANT_ID", "873b9e93-4463-4b67-a3a9-3dee5f35cec2")
                authority = f"https://login.microsoftonline.com/{tenant}"
                app = msal.PublicClientApplication(client_id, authority=authority)

                flow = app.initiate_device_flow(scopes=CORRECT_SCOPES)
                if "user_code" not in flow:
                    st.sidebar.error("❌ No se pudo iniciar Device Flow")
                    return

                with st.sidebar.expander("📱 Código de autenticación", expanded=True):
                    st.code(flow.get("user_code", ""), language=None)
                    st.markdown(flow.get("message", ""))

                token = app.acquire_token_by_device_flow(flow)
                if "access_token" not in token:
                    st.sidebar.error("❌ Autenticación fallida")
                    return

                access_token = token["access_token"]

                # Importar GraphClient (se importa aquí para evitar ciclos)
                from .graph_client import GraphClient

                temp_gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES, authority=authority)
                temp_gc.access_token = access_token

                # Llamada segura: get_workbook_worksheets validará internamente el parámetro
                worksheets = temp_gc.get_workbook_worksheets(share_url)

                if not worksheets:
                    st.sidebar.error("❌ No se encontraron hojas en el libro")
                    return

                st.session_state.temp_access_token = access_token
                st.session_state.temp_share_url = share_url
                st.session_state.temp_worksheets = worksheets
                st.session_state.temp_client_id = client_id
                st.session_state.show_sheet_selector = True

                st.rerun()

            except Exception as e:
                st.sidebar.error(f"❌ Error al conectar: {str(e)}")
                logger.exception("setup_excel_connection_persistent error:")
                return

    # Resto del selector de hoja (sin cambios)
    if st.session_state.get("show_sheet_selector", False):
        worksheets = st.session_state.temp_worksheets
        sheet_names = [w.get("name") for w in worksheets]
        selected_sheet = st.sidebar.selectbox("📄 Selecciona la hoja", options=sheet_names, key="sheet_selector")
        if st.sidebar.button("✅ Confirmar hoja", type="primary"):
            st.session_state.excel_access_token = st.session_state.temp_access_token
            st.session_state.excel_share_url = st.session_state.temp_share_url
            st.session_state.excel_sheet_name = selected_sheet
            st.session_state.excel_client_id = st.session_state.temp_client_id
            st.session_state.excel_connected = True
            del st.session_state.temp_access_token
            del st.session_state.temp_share_url
            del st.session_state.temp_worksheets
            del st.session_state.temp_client_id
            del st.session_state.show_sheet_selector
            st.sidebar.success(f"✅ Conectado a la hoja: {selected_sheet}")
            st.rerun()
