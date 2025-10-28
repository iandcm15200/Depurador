"""
Integración Excel Online (Microsoft Graph) — helper UI para Streamlit CON SESIÓN PERSISTENTE.

Esta versión mantiene la conexión al libro de Excel durante toda la sesión del usuario,
permitiendo envíos múltiples sin reconectar cada vez.

Funciones principales:
- connect_with_device_flow_gc(gc): muestra instrucciones de Device Code y obtiene token.
- setup_excel_connection_persistent(): UI para conectar libro UNA VEZ y guardar en session_state
- send_to_connected_excel(df_to_append): envía datos al libro ya conectado
"""
import streamlit as st
import pandas as pd
from typing import Optional
import logging
import msal
import os

# NO importar GraphClient - vamos a usar MSAL directamente para evitar conflictos de scopes
logger = logging.getLogger(__name__)

# ⭐ SCOPES CORRECTOS - Sin offline_access (MSAL lo agrega automáticamente)
CORRECT_SCOPES = ["Files.ReadWrite", "User.Read"]

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
    Configura la conexión al libro de Excel UNA VEZ y la guarda en session_state.
    Esta función debe llamarse en la sidebar o al inicio de las vistas de Anáhuac.
    
    Guarda en st.session_state:
    - excel_gc: instancia con access_token
    - excel_share_url: URL del libro conectado
    - excel_sheet_name: nombre de la hoja seleccionada
    - excel_connected: bool que indica si hay conexión activa
    """
    st.sidebar.markdown("### 📊 Conexión a Excel Online")
    
    # Inicializar variables de sesión si no existen
    if "excel_connected" not in st.session_state:
        st.session_state.excel_connected = False
    if "excel_access_token" not in st.session_state:
        st.session_state.excel_access_token = None
    if "excel_share_url" not in st.session_state:
        st.session_state.excel_share_url = ""
    if "excel_sheet_name" not in st.session_state:
        st.session_state.excel_sheet_name = ""
    
    # Mostrar estado de conexión
    if st.session_state.excel_connected:
        st.sidebar.success(f"✅ Conectado a Excel")
        st.sidebar.info(f"📄 Hoja: **{st.session_state.excel_sheet_name}**")
        
        # Botón para desconectar
        if st.sidebar.button("🔌 Desconectar y cambiar libro"):
            st.session_state.excel_connected = False
            st.session_state.excel_access_token = None
            st.session_state.excel_share_url = ""
            st.session_state.excel_sheet_name = ""
            st.rerun()
        return
    
    # Si no está conectado, mostrar formulario de conexión
    st.sidebar.info("📋 Configura tu libro de Excel para enviar resultados")
    
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
        help="Pega aquí el enlace de compartir del libro de Excel"
    )
    
    # Botón para iniciar conexión
    if st.sidebar.button("🔐 Conectar a Excel", type="primary"):
        if not share_url:
            st.sidebar.error("❌ Debes proporcionar la URL del libro")
            return
        
        with st.spinner("Conectando a Microsoft Graph..."):
            try:
                # ⭐ Crear MSAL app directamente con scopes correctos
                # Usar tenant específico de la organización
                tenant = os.environ.get("AZURE_TENANT_ID", "873b9e93-4463-4b67-a3a9-3dee5f35cec2")
                authority = f"https://login.microsoftonline.com/{tenant}"
                app = msal.PublicClientApplication(client_id, authority=authority)
                
                # ⭐ Iniciar Device Flow CON SCOPES CORRECTOS
                flow = app.initiate_device_flow(scopes=CORRECT_SCOPES)
                
                if "user_code" not in flow:
                    st.sidebar.error("❌ No se pudo iniciar Device Flow")
                    
                    # Mostrar error detallado
                    if "error" in flow:
                        st.sidebar.error(f"**Error:** {flow.get('error')}")
                        st.sidebar.error(f"**Descripción:** {flow.get('error_description', 'Sin descripción')}")
                    
                    st.sidebar.warning("**Posibles causas:**")
                    st.sidebar.write("1. Client ID incorrecto")
                    st.sidebar.write("2. Permisos de API no configurados en Azure")
                    st.sidebar.write("3. App no configurada como 'Cliente público'")
                    
                    logger.error("Device flow initiation failed: %s", flow)
                    
                    # Mostrar respuesta completa en expander
                    with st.sidebar.expander("🔍 Ver respuesta completa de MSAL"):
                        st.json(flow)
                    
                    return
                
                # Mostrar código de dispositivo en un expander
                with st.sidebar.expander("📱 Código de autenticación", expanded=True):
                    st.code(flow.get("user_code", ""), language=None)
                    st.markdown(flow.get("message", ""))
                
                # Esperar autenticación
                token = app.acquire_token_by_device_flow(flow)
                
                if "access_token" not in token:
                    st.sidebar.error("❌ Autenticación fallida")
                    logger.error("Device flow returned no access_token: %s", token)
                    return
                
                access_token = token["access_token"]
                
                # Importar GraphClient solo para usar sus métodos de API
                from .graph_client import GraphClient
                
                # Crear cliente temporal solo para listar hojas
                temp_gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES)
                temp_gc.access_token = access_token
                
                # Listar hojas del libro
                worksheets = temp_gc.get_workbook_worksheets(share_url)
                
                if not worksheets:
                    st.sidebar.error("❌ No se encontraron hojas en el libro")
                    return
                
                # Guardar temporalmente para selección de hoja
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
    
    # Selector de hoja (aparece después de autenticar)
    if st.session_state.get("show_sheet_selector", False):
        worksheets = st.session_state.temp_worksheets
        sheet_names = [w.get("name") for w in worksheets]
        
        selected_sheet = st.sidebar.selectbox(
            "📄 Selecciona la hoja",
            options=sheet_names,
            key="sheet_selector"
        )
        
        if st.sidebar.button("✅ Confirmar hoja", type="primary"):
            # Guardar conexión en session_state
            st.session_state.excel_access_token = st.session_state.temp_access_token
            st.session_state.excel_share_url = st.session_state.temp_share_url
            st.session_state.excel_sheet_name = selected_sheet
            st.session_state.excel_client_id = st.session_state.temp_client_id
            st.session_state.excel_connected = True
            
            # Limpiar temporales
            del st.session_state.temp_access_token
            del st.session_state.temp_share_url
            del st.session_state.temp_worksheets
            del st.session_state.temp_client_id
            del st.session_state.show_sheet_selector
            
            st.sidebar.success(f"✅ Conectado a la hoja: {selected_sheet}")
            st.rerun()

def send_to_connected_excel(df_to_append: pd.DataFrame, show_preview: bool = True) -> bool:
    """
    Envía un DataFrame al libro de Excel ya conectado.
    
    Args:
        df_to_append: DataFrame con los datos a enviar
        show_preview: Si True, muestra preview de los datos antes de enviar
    
    Returns:
        True si el envío fue exitoso, False en caso contrario
    """
    # Validar que hay conexión activa
    if not st.session_state.get("excel_connected", False):
        st.warning("⚠️ No hay ningún libro de Excel conectado. Configura la conexión en la barra lateral.")
        return False
    
    if df_to_append is None or df_to_append.empty:
        st.info("ℹ️ No hay datos para enviar a Excel")
        return False
    
    # Preview de datos (opcional)
    if show_preview:
        with st.expander("👁️ Preview de datos a enviar", expanded=False):
            st.dataframe(df_to_append.head(20), use_container_width=True)
            st.info(f"Total de filas: {len(df_to_append)}")
    
    # Obtener datos de conexión
    access_token = st.session_state.excel_access_token
    share_url = st.session_state.excel_share_url
    sheet_name = st.session_state.excel_sheet_name
    client_id = st.session_state.excel_client_id
    
    try:
        with st.spinner(f"📤 Enviando {len(df_to_append)} filas a Excel..."):
            # Importar GraphClient
            from .graph_client import GraphClient
            
            # Crear cliente con el token guardado
            gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES)
            gc.access_token = access_token
            
            # Verificar si existe una tabla en la hoja
            tables = gc.get_worksheet_tables(share_url, sheet_name)
            
            # Si hay tablas, usar la primera; si no, crear una nueva
            if tables:
                table_id = tables[0].get("id")
                table_name = tables[0].get("name", "Tabla1")
                st.info(f"📋 Usando tabla existente: {table_name}")
                headers = gc.get_table_headers(share_url, table_id)
            else:
                # Crear tabla nueva con los encabezados del DataFrame
                cols = df_to_append.columns.tolist()
                last_col = _col_letter(len(cols) - 1)
                address = f"{sheet_name}!A1:{last_col}1"
                
                st.info("📋 Creando nueva tabla en Excel...")
                table_obj = gc.create_table_on_sheet(share_url, sheet_name, header_range=address, has_headers=True)
                table_id = table_obj.get("id")
                headers = gc.get_table_headers(share_url, table_id) or cols
                st.success("✅ Tabla creada exitosamente")
            
            # Preparar datos para enviar
            values = []
            for _, row in df_to_append.iterrows():
                row_vals = []
                for h in headers:
                    # Buscar columna que coincida con el header (case-insensitive)
                    match_col = next(
                        (c for c in df_to_append.columns if c.strip().lower() == str(h).strip().lower()),
                        None
                    )
                    if match_col:
                        row_vals.append("" if pd.isna(row[match_col]) else str(row[match_col]))
                    else:
                        row_vals.append("")
                values.append(row_vals)
            
            if not values:
                st.warning("⚠️ No hay filas válidas para enviar")
                return False
            
            # Enviar en lotes de 100 filas
            batch_size = 100
            total_added = 0
            progress_bar = st.progress(0)
            
            for i in range(0, len(values), batch_size):
                chunk = values[i:i+batch_size]
                gc.add_rows_to_table(share_url, table_id, chunk)
                total_added += len(chunk)
                
                # Actualizar barra de progreso
                progress = min((i + batch_size) / len(values), 1.0)
                progress_bar.progress(progress)
            
            progress_bar.empty()
            st.success(f"✅ Se enviaron {total_added} filas a Excel exitosamente")
            return True
            
    except Exception as e:
        st.error(f"❌ Error al enviar datos a Excel: {str(e)}")
        logger.exception("send_to_connected_excel error:")
        return False

# Mantener la función original para compatibilidad (UDLA)
def integrate_ui_and_append(share_url: str, df_to_append: pd.DataFrame):
    """
    UI helper ORIGINAL para Streamlit (mantener para compatibilidad con UDLA).
    Esta versión NO usa sesión persistente.
    """
    from .graph_client import GraphClient
    
    client_id = st.secrets.get("AZURE_CLIENT_ID") or st.sidebar.text_input("AZURE_CLIENT_ID (temporal)")
    if not client_id:
        st.warning("Se requiere AZURE_CLIENT_ID. Defínelo en Streamlit secrets o escríbelo en la caja lateral.")
        return

    gc = GraphClient(client_id=client_id, scopes=CORRECT_SCOPES)

    # Botón de conexión / Device Code
    if st.button("Conectar a Excel Online (Device Code)"):
        try:
            flow = gc.app.initiate_device_flow(scopes=CORRECT_SCOPES)
            if "user_code" not in flow:
                st.error("No se pudo iniciar Device Flow (respuesta inesperada).")
                return
            st.info(flow.get("message", "Sigue las instrucciones para autenticarte en Microsoft."))
            token = gc.app.acquire_token_by_device_flow(flow)
            if "access_token" in token:
                gc.access_token = token["access_token"]
                st.success("✅ Autenticación completada correctamente.")
            else:
                st.error("❌ Autenticación fallida.")
                return
        except Exception as e:
            st.error("❌ Error durante Device Code Flow.")
            st.exception(e)
            return

    # Si no hay token aún, pedir al usuario que se conecte
    if not getattr(gc, "access_token", None):
        st.info("Presiona 'Conectar a Excel Online (Device Code)' para iniciar autenticación.")
        return

    # Resto del código original...
    try:
        worksheets = gc.get_workbook_worksheets(share_url)
    except Exception as e:
        st.error("No se pudieron listar las hojas del workbook.")
        st.exception(e)
        return

    if not worksheets:
        st.warning("No se encontraron worksheets en el archivo.")
        return

    sheet_names = [w.get("name") for w in worksheets]
    sheet_choice = st.selectbox("Selecciona la hoja (worksheet)", options=sheet_names)

    try:
        tables = gc.get_worksheet_tables(share_url, sheet_choice)
    except Exception as e:
        st.error("Error listando tablas en la hoja seleccionada.")
        st.exception(e)
        return

    table_options = [t.get("name") or t.get("id") for t in tables]
    table_choice = st.selectbox("Selecciona tabla (o crear nueva)", options=["<crear nueva>"] + table_options)

    if table_choice == "<crear nueva>":
        create_header_range = st.text_input("Rango de encabezado a usar (ej. A1:Z1)", value="A1:Z1")
        if st.button("Crear tabla y usarla"):
            try:
                table_obj = gc.create_table_on_sheet(share_url, sheet_choice, header_range=create_header_range, has_headers=True)
                st.success("Tabla creada: " + (table_obj.get("name") or "<sin nombre>"))
                tables = gc.get_worksheet_tables(share_url, sheet_choice)
                table_options = [t.get("name") or t.get("id") for t in tables]
                table_choice = table_obj.get("name") or table_obj.get("id")
            except Exception as e:
                st.error("No se pudo crear la tabla.")
                st.exception(e)
                return

    st.subheader("Preview de datos a enviar (primeras 10 filas)")
    if df_to_append is None or df_to_append.empty:
        st.info("El DataFrame a enviar está vacío.")
    else:
        st.dataframe(df_to_append.head(10), use_container_width=True)

    if st.button("Enviar resultados a Excel (append)"):
        try:
            if table_choice in table_options:
                selected_table = next((t for t in tables if (t.get("name") == table_choice or t.get("id") == table_choice)), None)
                table_id = selected_table.get("id")
                headers = gc.get_table_headers(share_url, table_id)
            else:
                cols = df_to_append.columns.tolist()
                last_col = _col_letter(len(cols) - 1)
                address = f"{sheet_choice}!A1:{last_col}1"
                table_obj = gc.create_table_on_sheet(share_url, sheet_choice, header_range=address, has_headers=True)
                table_id = table_obj.get("id")
                headers = gc.get_table_headers(share_url, table_id) or cols

            df = df_to_append.copy()
            values = []
            for _, row in df.iterrows():
                row_vals = []
                for h in headers:
                    match_col = next((c for c in df.columns if c.strip().lower() == str(h).strip().lower()), None)
                    if match_col:
                        row_vals.append("" if pd.isna(row[match_col]) else str(row[match_col]))
                    else:
                        row_vals.append("")
                values.append(row_vals)

            if not values:
                st.info("No hay filas para enviar.")
                return

            batch_size = 100
            total_added = 0
            for i in range(0, len(values), batch_size):
                chunk = values[i:i+batch_size]
                gc.add_rows_to_table(share_url, table_id, chunk)
                total_added += len(chunk)
                st.info(f"Se envió lote {i//batch_size + 1}, filas: {len(chunk)}")
            st.success(f"✅ Se añadieron {total_added} filas a la tabla.")
        except Exception as e:
            st.error("Error enviando filas a Excel Online.")
            st.exception(e)
