import json
import os
from datetime import datetime
import pandas as pd
import streamlit as st
import logging

logger = logging.getLogger(__name__)

def guardar_historial(info_depuracion: dict, history_dir: str):
    try:
        history_file = os.path.join(history_dir, "historial_depuraciones.json")
        
        historial = []
        if os.path.exists(history_file):
            try:
                with open(history_file, 'r', encoding='utf-8') as f:
                    historial = json.load(f)
            except json.JSONDecodeError:
                logger.warning("Archivo de historial corrupto, creando uno nuevo")
                historial = []
        
        historial.append(info_depuracion)
        
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(historial, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Historial guardado exitosamente en {history_file}")
        
    except Exception as e:
        logger.exception(f"Error guardando historial: {e}")
        raise

def cargar_historial(history_dir: str) -> list:
    try:
        history_file = os.path.join(history_dir, "historial_depuraciones.json")
        
        if not os.path.exists(history_file):
            return []
        
        with open(history_file, 'r', encoding='utf-8') as f:
            historial = json.load(f)
        
        return historial
        
    except Exception as e:
        logger.exception(f"Error cargando historial: {e}")
        return []

def mostrar_estadisticas(historial: list):
    if not historial:
        st.info("📭 No hay datos en el historial")
        return
    
    df_hist = pd.DataFrame(historial)
    df_hist['timestamp'] = pd.to_datetime(df_hist['timestamp'])
    df_hist = df_hist.sort_values('timestamp', ascending=False)
    
    st.subheader("📊 Resumen General")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total depuraciones", len(df_hist))
    with col2:
        st.metric("Total registros procesados", df_hist['filas_originales'].sum())
    with col3:
        st.metric("Total registros depurados", df_hist['filas_depuradas'].sum())
    with col4:
        st.metric("Total rezagados", df_hist['rezagados_movidos'].sum())
    
    st.subheader("📋 Historial Detallado")
    
    df_display = df_hist.copy()
    df_display['Fecha/Hora'] = df_display['timestamp'].dt.strftime('%d/%m/%Y %H:%M:%S')
    df_display['Archivo'] = df_display['archivo']
    df_display['Originales'] = df_display['filas_originales']
    df_display['Depuradas'] = df_display['filas_depuradas']
    df_display['Agregadas'] = df_display['filas_agregadas']
    df_display['Rezagados'] = df_display['rezagados_movidos']
    df_display['Filtro'] = df_display.apply(
        lambda x: f"{x['filtro_horas']}h" if x['filtro_horas'] else f"{x['filtro_dias']}d", 
        axis=1
    )
    df_display['Período'] = df_display['periodo']
    
    columns_to_show = ['Fecha/Hora', 'Archivo', 'Originales', 'Depuradas', 'Agregadas', 'Rezagados', 'Filtro', 'Período']
    st.dataframe(
        df_display[columns_to_show],
        use_container_width=True,
        hide_index=True
    )
    
    st.subheader("📈 Visualizaciones")
    
    tab1, tab2, tab3 = st.tabs(["Registros por día", "Eficiencia de depuración", "Rezagados"])
    
    with tab1:
        df_por_dia = df_hist.copy()
        df_por_dia['Fecha'] = df_por_dia['timestamp'].dt.date
        df_agrupado = df_por_dia.groupby('Fecha').agg({
            'filas_originales': 'sum',
            'filas_depuradas': 'sum',
            'filas_agregadas': 'sum'
        }).reset_index()
        
        st.write("Registros procesados por día")
        st.line_chart(df_agrupado.set_index('Fecha')[['filas_originales', 'filas_depuradas', 'filas_agregadas']])
    
    with tab2:
        df_hist['eficiencia'] = (df_hist['filas_depuradas'] / df_hist['filas_originales'] * 100).round(2)
        
        st.write("Porcentaje de registros que pasaron el filtro de depuración")
        st.bar_chart(df_hist.set_index('timestamp')['eficiencia'])
        
        st.metric(
            "Eficiencia promedio", 
            f"{df_hist['eficiencia'].mean():.2f}%",
            help="Porcentaje promedio de registros que pasan el filtro de depuración"
        )
    
    with tab3:
        st.write("Rezagados identificados por depuración")
        st.bar_chart(df_hist.set_index('timestamp')['rezagados_movidos'])
        
        st.metric("Total rezagados histórico", df_hist['rezagados_movidos'].sum())
    
    st.subheader("💾 Exportar Historial")
    
    csv = df_display[columns_to_show].to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Descargar historial como CSV",
        data=csv,
        file_name=f"historial_depuraciones_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv",
    )
