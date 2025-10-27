"""
Integración Excel Online (Microsoft Graph) — helper UI para Streamlit.

Funciones principales:
- connect_with_device_flow_gc(gc): muestra instrucciones de Device Code y obtiene token.
- integrate_ui_and_append(share_url, df_to_append): UI completa que lista worksheets/tables,
  permite crear tabla y añade (append) filas.
"""
import streamlit as st
import pandas as pd
from typing import Optional
from .graph_client import GraphClient
import logging

logger = logging.getLogger(__name__)

def connect_with_device_flow_gc(gc: GraphClient) -> bool:
    """
    Inicia Device Code Flow y espera a que el usuario complete el login.
    Muestra el mensaje de Device Code en la UI (flow["message"]).
    Devuelve True si la autenticación fue exitosa.
    """
    try:
        flow = gc.app.initiate_device_flow(scopes=gc.scopes)
        if "user_code" not in flow:
            st.error("No se pudo iniciar Device Flow (respuesta inesperada).")
            logger.error("Device flow initiation failed: %s", flow)
            return False
        # Mostrar mensaje con instrucciones al usuario
        st.info(flow.get("message", "Sigue las instrucciones para autenticarte en Microsoft."))
        token = gc.app.acquire_token_by_device_flow(flow)  # polling interno
        if "access_token" in token:
            gc.access_token = token["access_token"]
            st.success("Autenticación completada correctamente.")
            return True
        else:
            st.error("Autenticación fallida. Revisa errores en la consola.")
            logger.error("Device flow returned no access_token: %s", token)
            return False
    except Exception as e:
        st.error("Error durante Device Code Flow.")
        st.exception(e)
        logger.exception("connect_with_device_flow_gc error:")
        return False

def _col_letter(idx: int) -> str:
    """Convierte índice 0->A, 25->Z, 26->AA."""
    letters = ""
    n = idx + 1
    while n:
        n, rem = divmod(n - 1, 26)
        letters = chr(65 + rem) + letters
    return letters

def integrate_ui_and_append(share_url: str, df_to_append: pd.DataFrame):
    """
    UI helper para Streamlit:
    - solicita AZURE_CLIENT_ID (desde streamlit secrets o input temporal)
    - conecta con Graph (Device Code)
    - lista worksheets y tablas
    - permite crear tabla si es necesario
    - hace append de filas (en lotes)
    """
    client_id = st.secrets.get("AZURE_CLIENT_ID") or st.sidebar.text_input("AZURE_CLIENT_ID (temporal)")
    if not client_id:
        st.warning("Se requiere AZURE_CLIENT_ID. Defínelo en Streamlit secrets o escríbelo en la caja lateral.")
        return

    gc = GraphClient(client_id=client_id)

    # Botón de conexión / Device Code
    if st.button("Conectar a Excel Online (Device Code)"):
        ok = connect_with_device_flow_gc(gc)
        if not ok:
            return

    # Si no hay token aún, pedir al usuario que se conecte
    if not getattr(gc, "access_token", None):
        st.info("Presiona 'Conectar a Excel Online (Device Code)' para iniciar autenticación.")
        return

    # Listar worksheets
    try:
        worksheets = gc.get_workbook_worksheets(share_url)
    except Exception as e:
        st.error("No se pudieron listar las hojas del workbook.")
        st.exception(e)
        logger.exception("get_workbook_worksheets error:")
        return

    if not worksheets:
        st.warning("No se encontraron worksheets en el archivo (¿URL de sharing válida?).")
        return

    sheet_names = [w.get("name") for w in worksheets]
    sheet_choice = st.selectbox("Selecciona la hoja (worksheet)", options=sheet_names)

    # Listar tablas de la hoja
    try:
        tables = gc.get_worksheet_tables(share_url, sheet_choice)
    except Exception as e:
        st.error("Error listando tablas en la hoja seleccionada.")
        st.exception(e)
        logger.exception("get_worksheet_tables error:")
        return

    table_options = [t.get("name") or t.get("id") for t in tables]
    table_choice = st.selectbox("Selecciona tabla (o crear nueva)", options=["<crear nueva>"] + table_options)

    # Crear tabla nueva si el usuario lo pide
    if table_choice == "<crear nueva>":
        create_header_range = st.text_input("Rango de encabezado a usar (ej. A1:Z1)", value="A1:Z1")
        if st.button("Crear tabla y usarla"):
            try:
                table_obj = gc.create_table_on_sheet(share_url, sheet_choice, header_range=create_header_range, has_headers=True)
                st.success("Tabla creada: " + (table_obj.get("name") or table_obj.get("id") or "<sin nombre>"))
                # refrescar listas
                tables = gc.get_worksheet_tables(share_url, sheet_choice)
                table_options = [t.get("name") or t.get("id") for t in tables]
                table_choice = table_obj.get("name") or table_obj.get("id")
            except Exception as e:
                st.error("No se pudo crear la tabla.")
                st.exception(e)
                logger.exception("create_table_on_sheet error:")
                return

    # Preview de datos a enviar
    st.subheader("Preview de datos a enviar (primeras 10 filas)")
    if df_to_append is None or df_to_append.empty:
        st.info("El DataFrame a enviar está vacío.")
    else:
        st.dataframe(df_to_append.head(10), use_container_width=True)

    # Enviar filas (append)
    if st.button("Enviar resultados a Excel (append)"):
        try:
            if table_choice in table_options:
                selected_table = next((t for t in tables if (t.get("name") == table_choice or t.get("id") == table_choice)), None)
                table_id = selected_table.get("id")
                headers = gc.get_table_headers(share_url, table_id)
                st.info(f"Usando tabla existente: id={table_id}")
            else:
                # crear tabla usando encabezado del df
                cols = df_to_append.columns.tolist()
                last_col = _col_letter(len(cols) - 1)
                address = f"{sheet_choice}!A1:{last_col}1"
                table_obj = gc.create_table_on_sheet(share_url, sheet_choice, header_range=address, has_headers=True)
                table_id = table_obj.get("id")
                headers = gc.get_table_headers(share_url, table_id) or cols
                st.success("Tabla creada y seleccionada.")

            # Mapear columnas del df al orden de headers
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

            # Enviar en lotes de 100
            batch_size = 100
            total_added = 0
            for i in range(0, len(values), batch_size):
                chunk = values[i:i+batch_size]
                resp = gc.add_rows_to_table(share_url, table_id, chunk)
                total_added += len(chunk)
                st.info(f"Se envió lote {i//batch_size + 1}, filas: {len(chunk)}")
            st.success(f"✅ Se añadieron {total_added} filas a la tabla.")
        except Exception as e:
            st.error("Error enviando filas a Excel Online.")
            st.exception(e)
            logger.exception("integrate_ui_and_append append error:")
            return
