"""
Integración Excel Online (Microsoft Graph) — VERSIÓN SIMPLIFICADA
Busca archivos por nombre en lugar de usar URLs complejas de SharePoint.
"""
import streamlit as st
import pandas as pd
from typing import Optional
import logging
import msal
import os
import requests

logger = logging.getLogger(__name__)

# ⭐ SCOPES CORRECTOS - Sin offline_access (MSAL lo agrega automáticamente)
CORRECT_SCOPES = ["Files.ReadWrite", "User.Read"]

class GraphClient:
    """
    Cliente ligero para Microsoft Graph usado por la app.
    Provee:
    - self.app: instancia msal.PublicClientApplication
    - self.access_token: token de acceso (string)
    Métodos usados por la app:
    - search_file_by_name(name) -> list[dict]
    - get_workbook_worksheets(share_url_or_item) -> list[dict]
    - get_workbook_worksheets_by_item_id(item_id) -> list[dict]
    """
    def __init__(self, client_id: str, scopes: list, authority: Optional[str] = None):
        self.client_id = client_id
        self.scopes = scopes
        tenant = os.environ.get("AZURE_TENANT_ID")
        # Construir authority si no se pasó
        if authority:
            auth = authority
        else:
            auth = f"https://login.microsoftonline.com/{tenant}" if tenant else None

        # Crear app MSAL (authority es opcional)
        if auth:
            self.app = msal.PublicClientApplication(client_id, authority=auth)
        else:
            self.app = msal.PublicClientApplication(client_id)

        self.access_token: Optional[str] = None

    def _headers(self):
        if not self.access_token:
            raise RuntimeError("GraphClient: access_token no configurado")
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    def search_file_by_name(self, name: str):
        """
        Buscar archivos en el drive del usuario por nombre.
        Devuelve la lista 'value' de la respuesta o [].
        """
        GRAPH_BASE = "https://graph.microsoft.com/v1.0"
        # Usamos el endpoint search sobre root
        url = f"{GRAPH_BASE}/me/drive/root/search(q='{name}')"
        r = requests.get(url, headers=self._headers())
        r.raise_for_status()
        return r.json().get("value", [])

    def get_workbook_worksheets_by_item_id(self, item_id: str):
        """
        Obtener worksheets usando el item id del drive.
        """
        GRAPH_BASE = "https://graph.microsoft.com/v1.0"
        url = f"{GRAPH_BASE}/me/drive/items/{item_id}/workbook/worksheets"
        r = requests.get(url, headers=self._headers())
        r.raise_for_status()
        return r.json().get("value", [])

    def get_workbook_worksheets(self, share_url_or_item: str):
        """
        Intentar obtener worksheets desde una URL de compartido (share URL) o desde item id.
        Primero intenta el endpoint de shares; si falla, intenta tratar el argumento como item_id.
        """
        GRAPH_BASE = "https://graph.microsoft.com/v1.0"
        try:
            # Intento con shares (encodificar el share URL)
            share_id = requests.utils.quote(share_url_or_item, safe='')
            url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/worksheets"
            r = requests.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json().get("value", [])
        except Exception:
            # Fallback: tratar como item id
            return self.get_workbook_worksheets_by_item_id(share_url_or_item)

def _col_letter(idx: int) -> str:
    """Convierte índice 0->A, 25->Z, 26->AA."""
    letters = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

def setup_excel_connection_persistent():
    """
    Configura la conexión buscando archivos por NOMBRE en lugar de URL.
    """
    st.sidebar.markdown("### 📊 Conexión a Excel Online")
    
    # Inicializar variables de sesión
    if "excel_connected" not in st.session_state:
        st.session_state.excel_connected = False
    if "excel_access_token" not in st.session_state:
        st.session_state.excel_access_token = None
    if "excel_item_id" not in st.session_state:
        st.session_state.excel_item_id = ""
    if "excel_sheet_name" not in st.session_state:
        st.session_state.excel_sheet_name = ""
    if "excel_file_name" not in st.session_state:
        st.session_state.excel_file_name = ""
    
    # Mostrar estado de conexión
    if st.session_state.excel_connected:
        st.sidebar.success(f"✅ Conectado a Excel")
        st.sidebar.info(f"📄 Archivo: **{st.session_state.excel_file_name}**")
        st.sidebar.info(f"📄 Hoja: **{st.session_state.excel_sheet_name}**")
        
        if st.sidebar.button("🔌 Desconectar y cambiar archivo"):
            st.session_state.excel_connected = False
            st.session_state.excel_access_token = None
            st.session_state.excel_item_id = ""
            st.session_state.excel_sheet_name = ""
            st.session_state.excel_file_name = ""
            st.rerun()
        return
    
    # Si no está conectado
    st.sidebar.info("📋 Busca tu archivo de Excel")
    
    # Obtener Client ID
    client_id = st.secrets.get("AZURE_CLIENT_ID") or st.sidebar.text_input(
        "AZURE_CLIENT_ID", 
        type="password",
        help="Client ID de Azure AD"
    )
    
    if not client_id:
        st.sidebar.warning("⚠️ Se requiere AZURE_CLIENT_ID")
        return
    
    # Nombre del archivo (en lugar de URL)
    file_name = st.sidebar.text_input(
        "📁 Nombre del archivo Excel",
        placeholder="Base Documentos Anáhuac.xlsx",
        help="Escribe el nombre exacto del archivo (con extensión .xlsx)"
    )
    
    # Botón para buscar y conectar
    if st.sidebar.button("🔍 Buscar y Conectar", type="primary"):
        if not file_name:
            st.sidebar.error("❌ Debes escribir el nombre del archivo")
            return
        
        with st.spinner("Conectando a Microsoft Graph..."):
            try:
                # Crear MSAL app
                tenant = os.environ.get("AZURE_TENANT_ID", "873b9e93-4463-4b67-a3a9-3dee5f35cec2")
                authority = f"https://login.microsoftonline.com/{tenant}"
                app = msal.PublicClientApplication(client_id, authority=authority)
                
                # Device Flow
                flow = app.initiate_device_flow(scopes=CORRECT_SCOPES)
                
                if "user_code" not in flow:
                    st.sidebar.error("❌ No se pudo iniciar Device Flow")
                    return
                
                # Mostrar código
                with st.sidebar.expander("📱 Código de autenticación", expanded=True):
                    st.code(flow.get("user_code", ""), language=None)
                    st.markdown(flow.get("message", ""))
                
                # Autenticar
                token = app.acquire_token_by_device_flow(flow)
                
                if "access_token" not in token:
                    st.sidebar.error("❌ Autenticación fallida")
                    return
                
                access_token = token["access_token"]
                
                # Crear un GraphClient temporal para buscar archivos
                gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES, authority=authority)
                gc.access_token = access_token
                
                # ⭐ BUSCAR ARCHIVO POR NOMBRE
                st.info(f"🔍 Buscando archivo: {file_name}")
                files = gc.search_file_by_name(file_name)
                
                if not files:
                    st.sidebar.error(f"❌ No se encontró el archivo '{file_name}'")
                    st.sidebar.info("💡 Verifica:")
                    st.sidebar.write("- El nombre esté correcto (con .xlsx)")
                    st.sidebar.write("- Tengas acceso al archivo")
                    st.sidebar.write("- El archivo esté en tu OneDrive o SharePoint")
                    return
                
                # Si hay múltiples archivos con ese nombre, usar el primero
                if len(files) > 1:
                    st.sidebar.warning(f"⚠️ Se encontraron {len(files)} archivos con ese nombre. Usando el primero.")
                
                item = files[0]
                item_id = item["id"]
                st.success(f"✅ Archivo encontrado: {item['name']}")
                
                # Obtener hojas
                worksheets = gc.get_workbook_worksheets_by_item_id(item_id)
                
                if not worksheets:
                    st.sidebar.error("❌ No se encontraron hojas en el archivo")
                    return
                
                # Guardar para selector
                st.session_state.temp_access_token = access_token
                st.session_state.temp_item_id = item_id
                st.session_state.temp_worksheets = worksheets
                st.session_state.temp_client_id = client_id
                st.session_state.temp_file_name = item['name']
                st.session_state.show_sheet_selector = True
                
                st.rerun()
                
            except Exception as e:
                st.sidebar.error(f"❌ Error: {str(e)}")
                logger.exception("setup_excel_connection_persistent error:")
                return
    
    # Selector de hoja
    if st.session_state.get("show_sheet_selector", False):
        worksheets = st.session_state.temp_worksheets
        sheet_names = [w.get("name") for w in worksheets]
        
        selected_sheet = st.sidebar.selectbox(
            "📄 Selecciona la hoja",
            options=sheet_names,
            key="sheet_selector"
        )
        
        if st.sidebar.button("✅ Confirmar hoja", type="primary"):
            st.session_state.excel_access_token = st.session_state.temp_access_token
            st.session_state.excel_item_id = st.session_state.temp_item_id
            st.session_state.excel_sheet_name = selected_sheet
            st.session_state.excel_client_id = st.session_state.temp_client_id
            st.session_state.excel_file_name = st.session_state.temp_file_name
            st.session_state.excel_connected = True
            
            # Limpiar temporales
            del st.session_state.temp_access_token
            del st.session_state.temp_item_id
            del st.session_state.temp_worksheets
            del st.session_state.temp_client_id
            del st.session_state.temp_file_name
            del st.session_state.show_sheet_selector
            
            st.sidebar.success(f"✅ Conectado a: {selected_sheet}")
            st.rerun()

def send_to_connected_excel(df_to_append: pd.DataFrame, show_preview: bool = True) -> bool:
    """
    Envía datos al archivo Excel conectado (usando item_id en lugar de URL).
    """
    if not st.session_state.get("excel_connected", False):
        st.warning("⚠️ No hay conexión activa. Configura en la barra lateral.")
        return False
    
    if df_to_append is None or df_to_append.empty:
        st.info("ℹ️ No hay datos para enviar")
        return False
    
    if show_preview:
        with st.expander("👁️ Preview de datos", expanded=False):
            st.dataframe(df_to_append.head(20), use_container_width=True)
            st.info(f"Total: {len(df_to_append)} filas")
    
    access_token = st.session_state.excel_access_token
    item_id = st.session_state.excel_item_id
    sheet_name = st.session_state.excel_sheet_name
    client_id = st.session_state.excel_client_id
    
    try:
        with st.spinner(f"📤 Enviando {len(df_to_append)} filas..."):
            gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES)
            gc.access_token = access_token
            
            # Usar item_id directo
            GRAPH_BASE = "https://graph.microsoft.com/v1.0"
            headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
            
            # Obtener tablas
            sheet_quoted = requests.utils.quote(sheet_name)
            url = f"{GRAPH_BASE}/me/drive/items/{item_id}/workbook/worksheets/{sheet_quoted}/tables"
            r = requests.get(url, headers=headers)
            r.raise_for_status()
            tables = r.json().get("value", [])
            
            # Si hay tabla, usarla; si no, crear
            if tables:
                table_id = tables[0]["id"]
                st.info(f"📋 Tabla: {tables[0].get('name', 'Tabla1')}")
                
                # Obtener headers
                url_cols = f"{GRAPH_BASE}/me/drive/items/{item_id}/workbook/tables/{requests.utils.quote(table_id)}/columns"
                r = requests.get(url_cols, headers=headers)
                r.raise_for_status()
                cols = r.json().get("value", [])
                table_headers = [c.get("name") for c in cols]
            else:
                # Crear tabla
                cols = df_to_append.columns.tolist()
                last_col = _col_letter(len(cols) - 1)
                address = f"{sheet_name}!A1:{last_col}1"
                
                url_create = f"{GRAPH_BASE}/me/drive/items/{item_id}/workbook/tables/add"
                body = {"address": address, "hasHeaders": True}
                r = requests.post(url_create, headers=headers, json=body)
                r.raise_for_status()
                table_obj = r.json()
                table_id = table_obj["id"]
                table_headers = cols
                st.success("✅ Tabla creada")
            
            # Preparar datos
            values = []
            for _, row in df_to_append.iterrows():
                row_vals = []
                for h in table_headers:
                    match_col = next((c for c in df_to_append.columns if c.strip().lower() == str(h).strip().lower()), None)
                    row_vals.append("" if match_col is None or pd.isna(row[match_col]) else str(row[match_col]))
                values.append(row_vals)
            
            # Enviar en lotes
            batch_size = 100
            total = 0
            progress_bar = st.progress(0)
            
            url_add = f"{GRAPH_BASE}/me/drive/items/{item_id}/workbook/tables/{requests.utils.quote(table_id)}/rows/add"
            
            for i in range(0, len(values), batch_size):
                chunk = values[i:i+batch_size]
                body = {"values": chunk}
                r = requests.post(url_add, headers=headers, json=body)
                r.raise_for_status()
                total += len(chunk)
                progress_bar.progress(min((i + batch_size) / len(values), 1.0))
            
            progress_bar.empty()
            st.success(f"✅ Enviadas {total} filas")
            return True
            
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        logger.exception("send_to_connected_excel error:")
        return False

# Mantener función para UDLA
def integrate_ui_and_append(share_url: str, df_to_append: pd.DataFrame):
    """Función original para UDLA (compatibilidad)."""
    st.warning("Esta función usa el método antiguo. Considera usar la nueva versión.")
