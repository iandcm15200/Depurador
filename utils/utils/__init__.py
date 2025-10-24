# Este archivo convierte la carpeta utils en un paquete Python
# Permite importar módulos como: from utils.data_processor import depurar_datos

__version__ = '2.0.0'
__author__ = 'Sistema CRM Maestrías'

# Importaciones para facilitar el acceso
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
```

4. Commit: "Crear carpeta utils con __init__.py"

---

### **Paso 2: Copiar los otros 3 archivos a `utils/`**

**a) Crear `utils/data_processor.py`:**
1. "Add file" → "Create new file"
2. Nombre: `utils/data_processor.py`
3. Copia el contenido de tu archivo actual `data_processor.py`
4. Commit

**b) Crear `utils/excel_manager.py`:**
1. "Add file" → "Create new file"
2. Nombre: `utils/excel_manager.py`
3. Copia el contenido de tu archivo actual `excel_manager.py`
4. Commit

**c) Crear `utils/history_manager.py`:**
1. Ya lo tienes como `administrador_de_historial.py`
2. "Add file" → "Create new file"
3. Nombre: `utils/history_manager.py`
4. Copia el contenido que te di anteriormente (el código completo de history_manager)
5. Commit

---

### **Paso 3: Eliminar carpeta `utilidades` vieja**

1. Ve a cada archivo dentro de `utilidades/`
2. Click en el archivo → botón "🗑️" (Delete) → Commit
3. Repite para todos los archivos
4. La carpeta desaparecerá sola cuando esté vacía

---

## 📂 **Estructura Final Correcta:**
```
Depurador/
├── utils/                      ← Nueva carpeta
│   ├── __init__.py
│   ├── data_processor.py
│   ├── excel_manager.py
│   └── history_manager.py
├── data/
│   └── .gitkeep
├── history/
│   └── .gitkeep
├── app.py
├── requirements.txt
└── .gitignore
