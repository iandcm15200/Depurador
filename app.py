import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import logging
import os

# Importea la vista UDLA (archivo: depurador_streamlit.py)
from depurador_streamlit import render_udla

from utils.data_processor import depurar_datos, mapear_columnas
from utils.excel_manager import actualizar_maestro, cargar_archivo_maestro
from utils.history_manager import guardar_historial, cargar_historial, mostrar_estadisticas

# ⭐ NUEVO: Importar funciones para conexión persistente (Anáhuac)
# y mantener la función original para UDLA
from utils.excel_integration_ui_persistent import (
    setup_excel_connection_persistent,
    send_to_connected_excel,
    integrate_ui_and_append  # Mantener para UDLA (compatibilidad)
)

# Logging básico
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

DATA_DIR = "data"
HISTORY_DIR = "history"
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(HISTORY_DIR, exist_ok=True)

DEFAULT_MAESTRO = os.path.join(DATA_DIR, "conglomerado_maestrias.xlsx")
URL_BASE = "https://apmanager.aplatam.com/admin/Ventas/Consulta/Lead/"

def main():
    st.set_page_config(page_title="Sistema de Carga y Depuración CRM", layout="wide")
    st.title("🏢 Sistema de Carga y Depuración CRM")
    st.markdown("Sube un CSV, depura, consolida y gestiona rezagados automáticamente.")

    # Sidebar configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        periodo = st.text_input("Período Actual", value="202592")
        archivo_maestro = st.text_input("Ruta archivo maestro (Excel)", value=DEFAULT_MAESTRO)
        st.markdown("---")
        st.write("**Filtro de tiempo para PaidDate**")
        st.info("🕐 Por defecto: últimas 48 horas desde la fecha/hora actual de carga")
        filtro_personalizado = st.checkbox("Usar filtro personalizado", value=False)
        if filtro_personalizado:
            tipo_filtro = st.radio("Tipo de filtro:", ["Horas", "Días"])
            if tipo_filtro == "Horas":
                rango_horas = st.number_input("Últimas N horas", min_value=1, value=48)
                rango_dias = None
            else:
                rango_dias = st.number_input("Últimos N días", min_value=1, value=1)
                rango_horas = None
        else:
            rango_horas = 48
            rango_dias = None
        
        st.markdown("---")
        st.write("URL base (se concatena con LEAD)")
        url_base_input = st.text_input("URL base", value=URL_BASE)

        # Nueva opción: iniciar desde medianoche del día anterior
        start_from_prev_midnight = st.checkbox("Incluir desde medianoche del día anterior (en lugar de últimas N horas)", value=False)

        st.markdown("---")
        # Control: Tipo de programa (UDLA / Maestrías / Licenciaturas Anáhuac)
        program_type = st.selectbox("Tipo de programa a procesar", ["UDLA", "Maestrías", "Licenciaturas Anáhuac"])

        # ⭐ NUEVO: Si es Maestrías o Licenciaturas, mostrar panel de conexión Excel persistente
        if program_type in ["Maestrías", "Licenciaturas Anáhuac"]:
            st.markdown("---")
            setup_excel_connection_persistent()

    # Si el usuario selecciona UDLA, delegamos a la vista especializada que ya funciona
    if program_type == "UDLA":
        render_udla()
        return

    # Para Maestrías y Licenciaturas seguimos con el flujo general
    tab1, tab2, tab3, tab4 = st.tabs(["📤 Carga de Datos", "📊 Dashboard", "🔄 Rezagados", "📈 Historial"])

    with tab1:
        st.header(f"Carga y Procesamiento de Archivos CRM — {program_type}")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            uploaded_file = st.file_uploader(f"Subir archivo CSV del CRM (vwCRMLeads) - {program_type}", type=["csv"])
        with col2:
            st.info(f"📅 Fecha/Hora actual:\n{datetime.now().strftime('%d/%m/%Y %H:%M:%S')}")
        
        mostrar_preview = st.checkbox("Mostrar vista previa del CSV original (primeras 10 filas)", value=True)

        if uploaded_file is not None:
            try:
                # Timestamp de carga
                timestamp_carga = datetime.now()
                
                # Leer CSV
                raw_df = pd.read_csv(uploaded_file, dtype=str, keep_default_na=False, encoding='utf-8')
                total_filas_originales = len(raw_df)
                
                st.success(f"✅ Archivo cargado: {uploaded_file.name}")
                st.write(f"📊 Total de registros en CSV: **{total_filas_originales}**")
                
            except Exception as e:
                st.error(f"❌ No se pudo leer el CSV: {e}")
                st.stop()

            if mostrar_preview:
                st.subheader("👀 Preview del CSV Original")
                st.dataframe(raw_df.head(10), use_container_width=True)

            # Depuración
            st.markdown("---")
            st.subheader(f"🔄 Depurando datos para {program_type}...")
            
            with st.spinner("Procesando..."):
                try:
                    # Pasamos program_type a depurar_datos para que el procesador haga el comportamiento correcto
                    if filtro_personalizado and rango_dias is not None:
                        df_depurado = depurar_datos(raw_df,
                                                    hours=None,
                                                    days=int(rango_dias),
                                                    timestamp_referencia=timestamp_carga,
                                                    start_from_prev_midnight=start_from_prev_midnight,
                                                    program_type=program_type)
                    else:
                        df_depurado = depurar_datos(raw_df,
                                                    hours=int(rango_horas),
                                                    days=None,
                                                    timestamp_referencia=timestamp_carga,
                                                    start_from_prev_midnight=start_from_prev_midnight,
                                                    program_type=program_type)
                except TypeError:
                    # Fallback si la versión de depurar_datos no acepta start_from_prev_midnight/program_type
                    if filtro_personalizado and rango_dias is not None:
                        df_depurado = depurar_datos(raw_df, hours=None, days=int(rango_dias), timestamp_referencia=timestamp_carga, program_type=program_type)
                    else:
                        df_depurado = depurar_datos(raw_df, hours=int(rango_horas), days=None, timestamp_referencia=timestamp_carga, program_type=program_type)
                except Exception as e:
                    st.error(f"❌ Error durante la depuración: {e}")
                    st.exception(e)
                    st.stop()
            
            if df_depurado is None or df_depurado.empty:
                st.warning("⚠️ No hay registros después de la depuración / filtro de fechas.")
                st.info("💡 Sugerencias:")
                st.write("- Verifica que el CSV tenga la columna **PaidDate** (si aplica)")
                st.write("- Verifica que las fechas estén en formato: **DD/MM/YYYY HH:MM**")
                st.write("- Intenta usar un filtro de más días si el filtro de 48h es muy restrictivo")
                
                # Guardar historial incluso si está vacío
                info_depuracion = {
                    'timestamp': timestamp_carga.strftime('%Y-%m-%d %H:%M:%S'),
                    'archivo': uploaded_file.name,
                    'filas_originales': total_filas_originales,
                    'filas_depuradas': 0,
                    'filas_agregadas': 0,
                    'rezagados_movidos': 0,
                    'filtro_horas': rango_horas if rango_dias is None else None,
                    'filtro_dias': rango_dias,
                    'periodo': periodo,
                    'program_type': program_type
                }
                guardar_historial(info_depuracion, HISTORY_DIR)
                st.stop()
            
            # Si hay datos depurados
            filas_depuradas = len(df_depurado)
            st.success(f"✅ Depuración completada: **{filas_depuradas}** registros")
            
            if filas_depuradas == 0:
                st.warning("⚠️ No hay registros después de aplicar filtros de fecha.")
                
                info_depuracion = {
                    'timestamp': timestamp_carga.strftime('%Y-%m-%d %H:%M:%S'),
                    'archivo': uploaded_file.name,
                    'filas_originales': total_filas_originales,
                    'filas_depuradas': 0,
                    'filas_agregadas': 0,
                    'rezagados_movidos': 0,
                    'filtro_horas': rango_horas if rango_dias is None else None,
                    'filtro_dias': rango_dias,
                    'periodo': periodo,
                    'program_type': program_type
                }
                guardar_historial(info_depuracion, HISTORY_DIR)
                st.stop()
            
            # Preview de datos depurados
            st.subheader("📋 Preview Datos Depurados")
            st.dataframe(df_depurado.head(20), use_container_width=True)
            
            # Mapeo para Excel/Maestro
            st.markdown("---")
            st.subheader("🗂️ Mapeo de Columnas")
            
            with st.spinner("Mapeando columnas..."):
                try:
                    df_mapeado = mapear_columnas(df_depurado, url_base_input)
                    st.session_state['last_df_mapeado'] = df_mapeado
                    
                    st.success(f"✅ Datos mapeados: {len(df_mapeado)} registros")
                    
                    st.write("**Vista previa (primeras 10 filas):**")
                    st.dataframe(df_mapeado.head(10), use_container_width=True)
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        csv_depurado = df_mapeado.to_csv(index=False, encoding='utf-8-sig')
                        filename = f"depurado_{program_type.replace(' ', '_')}_{uploaded_file.name.replace('.csv', '')}_{timestamp_carga.strftime('%Y%m%d_%H%M%S')}.csv"
                        st.download_button(
                            label="📥 Descargar CSV Depurado",
                            data=csv_depurado.encode('utf-8-sig'),
                            file_name=filename,
                            mime="text/csv",
                            help="Descarga el archivo depurado para copiar a Excel"
                        )
                    
                    with col2:
                        st.info("💡 **Tip:** Puedes seleccionar todo en la tabla (Ctrl+A) y copiar (Ctrl+C) para pegar directamente en Excel")
                    
                except Exception as e:
                    st.error(f"❌ Error al mapear columnas: {e}")
                    st.exception(e)
                    st.stop()

                # ⭐ NUEVO: Exportar a Excel Online con conexión persistente (solo Maestrías/Licenciaturas)
                st.markdown("---")
                st.subheader("📤 Enviar a Excel Online")
                
                # Verificar si hay conexión activa
                if st.session_state.get("excel_connected", False):
                    st.info(f"✅ Conectado al libro de Excel - Hoja: **{st.session_state.get('excel_sheet_name', 'N/A')}**")
                    
                    # Botón para enviar datos
                    if st.button("📊 Enviar datos depurados a Excel Online", type="primary", key=f"send_excel_{program_type}"):
                        with st.spinner("📤 Enviando datos a Excel..."):
                            success = send_to_connected_excel(
                                df_to_append=df_mapeado,
                                show_preview=True
                            )
                            
                            if success:
                                st.balloons()
                                st.success("🎉 ¡Datos enviados exitosamente a Excel Online!")
                            else:
                                st.error("❌ Hubo un problema al enviar los datos")
                else:
                    st.warning("⚠️ No hay ningún libro de Excel conectado")
                    st.info("💡 Configura la conexión en la barra lateral (📊 Conexión a Excel Online)")

                # Botón para consolidar en Excel Maestro (local)
                st.markdown("---")
                st.subheader("💾 Consolidar en Excel Maestro")
                
                if st.button("🚀 Consolidar en Excel Maestro", type="primary"):
                    with st.spinner("📝 Consolidando en archivo maestro..."):
                        try:
                            # Si quieres maestros separados por tipo, adapta actualizar_maestro para aceptar program_type.
                            added, moved_rezagados = actualizar_maestro(df_mapeado, archivo_maestro, periodo)
                        except Exception as e:
                            st.error(f"❌ Error al consolidar: {e}")
                            st.exception(e)
                            st.stop()
                    
                    st.success(f"✅ **Consolidación completada!**")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Registros añadidos", added)
                    with col2:
                        st.metric("Rezagados movidos", moved_rezagados)
                    
                    st.info(f"💾 Archivo maestro guardado en: `{archivo_maestro}`")
                    
                    # Guardar historial
                    info_depuracion = {
                        'timestamp': timestamp_carga.strftime('%Y-%m-%d %H:%M:%S'),
                        'archivo': uploaded_file.name,
                        'filas_originales': total_filas_originales,
                        'filas_depuradas': filas_depuradas,
                        'filas_agregadas': added,
                        'rezagados_movidos': moved_rezagados,
                        'filtro_horas': rango_horas if rango_dias is None else None,
                        'filtro_dias': rango_dias,
                        'periodo': periodo,
                        'program_type': program_type
                    }
                    guardar_historial(info_depuracion, HISTORY_DIR)
                    st.success("📊 Historial actualizado")

    with tab2:
        st.header("📊 Dashboard rápido")
        st.write("Carga el archivo maestro para ver conteos por hoja.")
        
        if st.button("🔍 Cargar estadísticas del maestro"):
            try:
                sheets = cargar_archivo_maestro(archivo_maestro)
                
                if not sheets:
                    st.warning("No se encontró el archivo maestro o está vacío")
                else:
                    st.success(f"✅ Archivo maestro cargado: {len(sheets)} hojas detectadas")
                    
                    # Crear tabla resumen
                    resumen_data = []
                    for name, df in sheets.items():
                        resumen_data.append({
                            'Hoja': name,
                            'Registros': len(df),
                            'Columnas': len(df.columns)
                        })
                    
                    df_resumen = pd.DataFrame(resumen_data)
                    st.dataframe(df_resumen, use_container_width=True)
                    
                    # Gráfico
                    if not df_resumen.empty:
                        st.subheader("📊 Distribución de Registros")
                        st.bar_chart(df_resumen.set_index('Hoja')['Registros'])
                        
            except Exception as e:
                st.error(f"❌ Error cargando maestro: {e}")
                st.exception(e)

    with tab3:
        st.header("🔄 Gestión manual de Rezagados")
        st.write("Puedes forzar la ejecución del proceso de detección/movimiento de rezagados en el maestro.")
        
        if st.button("🔍 Ejecutar mover rezagados ahora", type="primary"):
            try:
                # Cargar hojas
                sheets = cargar_archivo_maestro(archivo_maestro)
                if not sheets:
                    st.warning("No se encontró el archivo maestro")
                else:
                    # Llamamos a actualizar_maestro con df vacío para forzar la gestión de rezagados
                    added, moved = actualizar_maestro(pd.DataFrame(), archivo_maestro, periodo, only_manage_rezagados=True)
                    st.success(f"✅ Rezagados movidos: **{moved}**")
            except Exception as e:
                st.error(f"❌ Error moviendo rezagados: {e}")
                st.exception(e)

    with tab4:
        st.header("📈 Historial de Depuraciones")
        st.write("Registro histórico de todas las depuraciones realizadas")
        
        # Cargar y mostrar historial
        historial = cargar_historial(HISTORY_DIR)
        
        if historial:
            mostrar_estadisticas(historial)
        else:
            st.info("📭 No hay historial de depuraciones aún")

if __name__ == "__main__":
    main()
