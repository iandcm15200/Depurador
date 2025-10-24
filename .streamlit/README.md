# 🏢 Sistema de Carga y Depuración CRM - Maestrías

Sistema automatizado para depurar, consolidar y gestionar datos del CRM de maestrías con filtrado temporal dinámico y seguimiento histórico.

## 🚀 Características

- ✅ Filtro temporal dinámico (últimas 24 horas desde carga)
- ✅ Historial de depuraciones con visualizaciones
- ✅ Gestión automática de rezagados
- ✅ Dashboard con estadísticas
- ✅ Exportación de reportes

## 📦 Instalación
```bash
pip install -r requirements.txt
streamlit run app.py
```

## 🌐 URL de la Aplicación

[https://tu-app.streamlit.app/](https://tu-app.streamlit.app/)

## 📖 Uso

1. Sube un archivo CSV del CRM
2. El sistema filtra automáticamente las últimas 24 horas
3. Revisa los datos depurados
4. Consolida en el archivo maestro Excel
5. Revisa el historial de depuraciones

## 📊 Estructura
```
├── app.py                    # Aplicación principal
├── utilidades/               # Módulos de procesamiento
│   ├── data_processor.py     # Depuración de datos
│   ├── excel_manager.py      # Gestión Excel
│   └── history_manager.py    # Historial
├── data/                     # Archivos de datos
└── history/                  # Historial JSON
```

## 👥 Soporte

Para consultas, contactar al equipo de desarrollo.
