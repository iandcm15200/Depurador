import streamlit as st
import pandas as pd
from .graph_client import GraphClient

def connect_with_device_flow_gc(gc: GraphClient):
    try:
        flow = gc.app.initiate_device_flow(scopes=gc.scopes)
        if "user_code" not in flow:
            st.error("No se pudo iniciar Device Flow.")
            return False
        st.info("Sigue las instrucciones de login: " + flow["message"])
        token = gc.app.acquire_token_by_device_flow(flow)
        if "access_token" in token:
            gc.access_token = token["access_token"]
            st.success("Autenticación completada.")
            return True
        else:
            st.error("Autenticación fallida: " + str(token))
            return False
    except Exception as e:
        st.error(f"Error en Device Flow: {e}")
        return False

def integrate_ui_and_append(share_url: str, df_to_append: pd.DataFrame):
    client_id = st.secrets.get("AZURE_CLIENT_ID") or st.sidebar.text_input("AZURE_CLIENT_ID (temporal)")
    if not client_id:
        st.warning("Se requiere AZURE_CLIENT_ID. Defínelo en streamlit secrets o en la caja lateral.")
        return

    gc = GraphClient(client_id=client_id)

    if st.button("Conectar a Excel Online (Device Code)"):
        ok = connect_with_device_flow_gc(gc)
        if not ok:
            return

    if not getattr(gc, "access_token", None):
        st.info("Conéctate primero usando 'Conectar a Excel Online (Device Code)'.")
        return

    try:
        worksheets = gc.get_workbook_worksheets(share_url)
    except Exception as e:
        st.error(f"No se pudo listar worksheets: {e}")
        return

    sheet_map = {w.get("name"): w for w in worksheets}
    sheet_choice = st.selectbox("Selecciona la hoja (worksheet)", options=list(sheet_map.keys()) if sheet_map else [])
    if not sheet_choice:
        st.info("Selecciona una hoja válida.")
        return

    try:
        tables = gc.get_worksheet_tables(share_url, sheet_choice)
    except Exception as e:
        st.error(f"No se pudo listar tablas en la hoja: {e}")
        return

    table_names = [t.get("name") or t.get("id") for t in tables]
    table_choice = st.selectbox("Selecciona tabla (o crear nueva)", options=["<crear nueva>"] + table_names)

    if table_choice == "<crear nueva>":
        create_header_range = st.text_input("Rango de encabezado a usar (ej. A1:Z1)", value="A1:Z1")
        if st.button("Crear tabla y usarla"):
            try:
                table_obj = gc.create_table_on_sheet(share_url, sheet_choice, header_range=create_header_range, has_headers=True)
                st.success("Tabla creada: " + table_obj.get("name", table_obj.get("id", "<sin nombre>")))
                table_choice = table_obj.get("name") or table_obj.get("id")
                tables = gc.get_worksheet_tables(share_url, sheet_choice)
                table_names = [t.get("name") or t.get("id") for t in tables]
            except Exception as e:
                st.error("No se pudo crear tabla: " + str(e))
                return

    st.subheader("Preview de datos a enviar (primeras 10 filas)")
    st.dataframe(df_to_append.head(10))

    if st.button("Enviar resultados a Excel (append)"):
        try:
            if table_choice in table_names:
                selected_table = next((t for t in tables if (t.get("name") == table_choice or t.get("id") == table_choice)), None)
                table_id = selected_table.get("id")
                headers = gc.get_table_headers(share_url, table_id)
            else:
                cols = df_to_append.columns.tolist()
                def col_letter(idx):
                    letters = ""
                    idx += 1
                    while idx:
                        idx, rem = divmod(idx-1, 26)
                        letters = chr(65+rem) + letters
                    return letters
                last_col = col_letter(len(cols)-1)
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
                        row_vals.append(str(row[match_col]) if pd.notna(row[match_col]) else "")
                    else:
                        row_vals.append("")
                values.append(row_vals)

            batch_size = 100
            total_added = 0
            for i in range(0, len(values), batch_size):
                chunk = values[i:i+batch_size]
                gc.add_rows_to_table(share_url, table_id, chunk)
                total_added += len(chunk)
            st.success(f"✅ Se añadieron {total_added} filas a la tabla.")
        except Exception as e:
            st.error(f"Error enviando filas: {e}")
            return
