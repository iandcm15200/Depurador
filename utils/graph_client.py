# --- fragmento a reemplazar / mejorar en utils/graph_client.py ---

import re

def _looks_like_item_id(s: str) -> bool:
    """Validación simple para un item_id plausible (sin espacios, longitud razonable)."""
    if not isinstance(s, str):
        return False
    s = s.strip()
    # item_id plausible: caracteres alfanuméricos, guiones, guion bajo, dos puntos; longitud 8-250
    return bool(re.match(r'^[A-Za-z0-9\-\_\:]{8,250}$', s))

def get_workbook_worksheets(self, share_url_or_item: str):
    """
    Obtener worksheets desde una share URL o desde item_id.
    Validamos la entrada y devolvemos un error claro si la cadena no es ni URL ni item_id plausible.
    """
    GRAPH_BASE = "https://graph.microsoft.com/v1.0"
    if not isinstance(share_url_or_item, str):
        raise ValueError("El identificador proporcionado no es una cadena. Proporciona la URL de compartir o el item_id.")
    share_url_or_item = share_url_or_item.strip()

    # Si es una posible share URL, usar /shares/{shareId}/driveItem/...
    if share_url_or_item.lower().startswith(("http://", "https://")):
        # Convertir a shareId y llamar a /shares/{shareId}/driveItem/workbook/worksheets
        try:
            share_id = _share_id_from_url(share_url_or_item)
            url = f"{GRAPH_BASE}/shares/{share_id}/driveItem/workbook/worksheets"
            r = requests.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json().get("value", [])
        except requests.HTTPError as he:
            # Re-lanzamos para que el UI muestre el error HTTP que Graph devuelva
            raise he
        except Exception as e:
            raise RuntimeError(f"No se pudo usar la share URL: {e}")

    # Si no es URL, verificar si parece item_id válido
    if _looks_like_item_id(share_url_or_item):
        try:
            url = f"{GRAPH_BASE}/me/drive/items/{share_url_or_item}/workbook/worksheets"
            r = requests.get(url, headers=self._headers())
            r.raise_for_status()
            return r.json().get("value", [])
        except requests.HTTPError as he:
            raise he
        except Exception as e:
            raise RuntimeError(f"Error consultando por item_id: {e}")

    # Si llega aquí, la entrada no es ni URL ni item_id válido -> lanzar error claro
    raise ValueError("El valor proporcionado no parece una URL de compartir (https://...) ni un item_id válido. Pega la URL de compartir de OneDrive/SharePoint o el item_id correcto.")
# --- fin del fragmento ---
