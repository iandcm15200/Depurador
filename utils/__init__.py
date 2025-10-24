# Este archivo convierte la carpeta utils en un paquete Python

__version__ = '2.0.0'
__author__ = 'Sistema CRM Maestrías'

from .data_processor import depurar_datos, mapear_columnas
from .excel_manager import actualizar_maestro, cargar_archivo_maestro
from .history_manager import guardar_historial, cargar_historial, mostrar_estadisticas

__all__ = [
    'depurar_datos',
    'mapear_columnas',
    'actualizar_maestro',
    'cargar_archivo_maestro',
    'guardar_historial',
    'cargar_historial',
    'mostrar_estadisticas'
]
