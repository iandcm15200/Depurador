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
    - soporte básico para llamadas necesarias (crear tabla, añadir filas) puede añadirse si hace falta
    """
    def __init__(self, client_id: str, scopes: list = None, authority: Optional[str] = None):
        self.client_id = client_id
        self.scopes = scopes or CORRECT_SCOPES
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

    # Métodos auxiliares (opcionales). Si los necesitas puedes extenderlos.
    def get_worksheet_tables(self, share_url_or_item: str, sheet_name: str):
        """
        Obtener tablas de una hoja dada. share_url_or_item puede ser share URL o item_id.
        """
        GRAPH_BASE = "https://graph.microsoft.com/v1.0"
        try:
            # Intento por shares
            share_id = requests.utils.quote(share_url_or_item, safe='')
            url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/worksheets/{requests.utils.quote(sheet_name)}/tables"
            r = requests.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json().get("value", [])
        except Exception:
            # Fallback a item id
            url = f"{GRAPH_BASE}/me/drive/items/{share_url_or_item}/workbook/worksheets/{requests.utils.quote(sheet_name)}/tables"
            r = requests.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json().get("value", [])

    def create_table_on_sheet(self, item_id_or_share: str, sheet_name: str, header_range: str, has_headers: bool = True):
        """
        Crear tabla en la hoja usando item_id o share_url. Devuelve el objeto tabla retornado por Graph.
        """
        GRAPH_BASE = "https://graph.microsoft.com/v1.0"
        # Si es share_url, intentar convertir a driveItem vía /shares/.../driveItem
        try:
            share_id = requests.utils.quote(item_id_or_share, safe='')
            url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/tables/add"
            body = {"address": header_range, "hasHeaders": has_headers}
            r = requests.post(url, headers=self._headers(), json=body)
            r.raise_for_status()
            return r.json()
        except Exception:
            url = f"{GRAPH_BASE}/me/drive/items/{item_id_or_share}/workbook/tables/add"
            body = {"address": header_range, "hasHeaders": has_headers}
            r = requests.post(url, headers=self._headers(), json=body)
            r.raise_for_status()
            return r.json()

    def add_rows_to_table(self, item_id_or_share: str, table_id: str, values: list):
        """
        Añadir filas a una tabla dada usando table_id. values es lista de listas.
        """
        GRAPH_BASE = "https://graph.microsoft.com/v1.0"
        try:
            # Primero intentar como share
            share_id = requests.utils.quote(item_id_or_share, safe='')
            url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/tables/{requests.utils.quote(table_id)}/rows/add"
            r = requests.post(url, headers=self._headers(), json={"values": values})
            r.raise_for_status()
            return r.json()
        except Exception:
            url = f"{GRAPH_BASE}/me/drive/items/{item_id_or_share}/workbook/tables/{requests.utils.quote(table_id)}/rows/add"
            r = requests.post(url, headers=self._headers(), json={"values": values})
            r.raise_for_status()
            return r.json()

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
    (Función mantenida para compatibilidad; usa GraphClient definido arriba)
    """
    st.sidebar.markdown("### 📊 Conexión a Excel Online")
    # (el resto del cuerpo de la función puede permanecer como en tu código original,
    #  ya que usa la clase GraphClient que ahora está definida en este archivo)
    # Aquí no repetimos todo el UI, porque ya está en tu versión original.
    pass
