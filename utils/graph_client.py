import os
import base64
import json
import requests
import msal
import urllib.parse

GRAPH_BASE = "https://graph.microsoft.com/v1.0"

class GraphClient:
    """
    Cliente ligero para Microsoft Graph usando MSAL (Device Code Flow).
    Requiere:
      - AZURE_CLIENT_ID en env o pasado al constructor.
      - opcional: AZURE_TENANT_ID (si no, usa 'common')
    """

    def __init__(self, client_id: str = None, tenant: str = None, scopes=None):
        self.client_id = client_id or os.environ.get("AZURE_CLIENT_ID")
        if not self.client_id:
            raise ValueError("AZURE_CLIENT_ID no configurado (env var o parámetro).")
        self.tenant = tenant or os.environ.get("AZURE_TENANT_ID") or "common"
        self.authority = f"https://login.microsoftonline.com/{self.tenant}"
        # ⭐ CORREGIDO: Eliminado "offline_access" - MSAL lo agrega automáticamente
        self.scopes = scopes or ["Files.ReadWrite", "User.Read"]
        self.app = msal.PublicClientApplication(self.client_id, authority=self.authority)
        self.access_token = None

    def device_flow_auth(self):
        """
        Inicia Device Code Flow y bloquea hasta que el usuario complete el login.
        Devuelve access_token en caso de éxito.
        """
        flow = self.app.initiate_device_flow(scopes=self.scopes)
        if "user_code" not in flow:
            raise RuntimeError("No se pudo iniciar device flow: " + str(flow))
        # El caller (UI) debe mostrar flow["message"] al usuario
        token = self.app.acquire_token_by_device_flow(flow)  # bloqueante (polling)
        if "access_token" in token:
            self.access_token = token["access_token"]
            return self.access_token
        else:
            raise RuntimeError("Autenticación fallida: " + json.dumps(token, ensure_ascii=False))

    def _headers(self):
        if not self.access_token:
            raise RuntimeError("Sin access_token. Llama a device_flow_auth() primero.")
        return {"Authorization": f"Bearer {self.access_token}", "Content-Type": "application/json"}

    @staticmethod
    def _share_url_to_share_id(share_url: str) -> str:
        """
        Convierte una sharing URL en shareId requerido por Graph:
        base64urlEncode(sharedUrl) y prefijo 'u!'.
        """
        s = share_url.strip()
        enc = base64.urlsafe_b64encode(s.encode("utf-8")).decode("utf-8").rstrip("=")
        return f"u!{enc}"

    def get_workbook_worksheets(self, share_url: str):
        share_id = self._share_url_to_share_id(share_url)
        url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/worksheets"
        r = requests.get(url, headers=self._headers())
        r.raise_for_status()
        return r.json().get("value", [])

    def get_worksheet_tables(self, share_url: str, sheet_name: str):
        share_id = self._share_url_to_share_id(share_url)
        sheet_quoted = urllib.parse.quote(sheet_name, safe="")
        url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/worksheets/{sheet_quoted}/tables"
        r = requests.get(url, headers=self._headers())
        r.raise_for_status()
        return r.json().get("value", [])

    def create_table_on_sheet(self, share_url: str, sheet_name: str, header_range: str = "A1:Z1", has_headers: bool = True):
        share_id = self._share_url_to_share_id(share_url)
        if "!" in header_range:
            address = header_range
        else:
            address = f"{sheet_name}!{header_range}"
        address_q = urllib.parse.quote(address, safe="")
        url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/tables/add?address={address_q}"
        body = {"hasHeaders": bool(has_headers)}
        r = requests.post(url, headers=self._headers(), json=body)
        r.raise_for_status()
        return r.json()

    def add_rows_to_table(self, share_url: str, table_id: str, values: list):
        share_id = self._share_url_to_share_id(share_url)
        table_q = urllib.parse.quote(table_id, safe="")
        url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/tables/{table_q}/rows/add"
        body = {"values": values}
        r = requests.post(url, headers=self._headers(), json=body)
        r.raise_for_status()
        return r.json()

    def get_table_headers(self, share_url: str, table_id: str):
        share_id = self._share_url_to_share_id(share_url)
        url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/tables/{urllib.parse.quote(table_id, safe='')}/columns"
        r = requests.get(url, headers=self._headers())
        r.raise_for_status()
        cols = r.json().get("value", [])
        return [c.get("name") for c in cols]

    def get_table_by_name_in_sheet(self, share_url: str, sheet_name: str, table_name: str):
        tables = self.get_worksheet_tables(share_url, sheet_name)
        for t in tables:
            if t.get("name") == table_name or t.get("displayName") == table_name:
                return t
        return None
