# Este archivo convierte la carpeta utils en un paquete Python
# Mantener solo metadata ligera aquí. Evitar imports que carguen otros submódulos
# para prevenir importaciones circulares durante el arranque.

__version__ = "2.0.0"
__author__ = "Sistema CRM Maestrías"

# Los submódulos deben importarse explícitamente donde se usen, por ejemplo:
# from utils.data_processor import depurar_datos
__all__ = []
