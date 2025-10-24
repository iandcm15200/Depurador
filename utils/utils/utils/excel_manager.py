import pandas as pd
import os
import logging

logger = logging.getLogger(__name__)

COLUMNAS_VENTAS = [
    'Asesor de ventas', 'LEAD', 'Email', 'Nombre Apellido',
    'Telefono Movil', 'Programa', 'PaidDate', 'URL_Lead'
]

COLUMNAS_REZAGADOS = [
    'Asesor de ventas', 'WEB ID', 'ID', 'NIP', 'LEAD', 'Email',
    'Nombre Apellido', 'Telefono Movil', 'Programa', 'PaidDate',
    'Materias Pagadas', 'Monto de pago', 'Campaña', 'Factura',
    'Correo Anáhuac', 'URL_Lead', 'Asesor', 'Estatus', 'NRC',
    'Materia', 'Agenda', 'Comentarios', 'Descuento',
    'Ciclo de inicio', 'Tickets', 'Activación de saldo'
]

def cargar_archivo_maestro(ruta: str) -> dict:
    if not os.path.exists(ruta):
        logger.info(f"Archivo maestro {ruta} no existe.")
        return {}
    try:
        sheets = pd.read_excel(ruta, sheet_name=None)
        logger.info(f"Cargadas hojas: {list(sheets.keys())}")
        return sheets
    except Exception as e:
        logger.exception("Error cargando archivo maestro:")
        raise

def _ensure_maestro_structure(sheets: dict, periodo: str) -> dict:
    hoja_ventas = f"Ventas Nuevas Maestrías {periodo}"
    hoja_rezagados = f"Rezagados Maestrías {periodo}"

    if hoja_ventas not in sheets:
        sheets[hoja_ventas] = pd.DataFrame(columns=COLUMNAS_VENTAS)
    if hoja_rezagados not in sheets:
        sheets[hoja_rezagados] = pd.DataFrame(columns=COLUMNAS_REZAGADOS)

    return sheets

def actualizar_maestro(df_depurado: pd.DataFrame, ruta: str, periodo: str, only_manage_rezagados: bool = False) -> tuple:
    hoja_ventas = f"Ventas Nuevas Maestrías {periodo}"
    hoja_rezagados = f"Rezagados Maestrías {periodo}"

    sheets = {}
    if os.path.exists(ruta):
        try:
            sheets = pd.read_excel(ruta, sheet_name=None)
        except Exception as e:
            logger.exception("Error leyendo archivo maestro existente:")
            raise

    sheets = _ensure_maestro_structure(sheets, periodo)

    df_ventas_existente = sheets.get(hoja_ventas, pd.DataFrame(columns=COLUMNAS_VENTAS))
    df_rezagados_existente = sheets.get(hoja_rezagados, pd.DataFrame(columns=COLUMNAS_REZAGADOS))

    rezagados_moved = 0
    added = 0

    if not only_manage_rezagados and df_depurado is not None and not df_depurado.empty:
        for col in COLUMNAS_VENTAS:
            if col not in df_depurado.columns:
                df_depurado[col] = pd.NA

        df_concat = pd.concat([df_ventas_existente, df_depurado], ignore_index=True)
        if 'LEAD' in df_concat.columns:
            before = len(df_concat)
            df_concat = df_concat.drop_duplicates(subset=['LEAD'], keep='first')
            after = len(df_concat)
            logger.info(f"De {before} filas concatenadas se quitaron {before-after} duplicados por LEAD.")
        else:
            logger.warning("LEAD no presente en concatenación: no se eliminaron duplicados.")

        df_ventas_actualizado = df_concat.reset_index(drop=True)
        added = max(0, len(df_ventas_actualizado) - len(df_ventas_existente))
    else:
        df_ventas_actualizado = df_ventas_existente.copy()

    rezagado_mask = None
    if 'Estatus' in df_ventas_actualizado.columns:
        rezagado_mask = df_ventas_actualizado['Estatus'].astype(str).str.lower().str.contains('pospone', na=False)
    else:
        possible_status_cols = [c for c in df_ventas_actualizado.columns if 'estatus' in c.lower()]
        if possible_status_cols:
            col = possible_status_cols[0]
            rezagado_mask = df_ventas_actualizado[col].astype(str).str.lower().str.contains('pospone', na=False)

    if rezagado_mask is not None and rezagado_mask.any():
        rezagados = df_ventas_actualizado[rezagado_mask].copy()
        for col in COLUMNAS_REZAGADOS:
            if col not in rezagados.columns:
                rezagados[col] = pd.NA

        df_rezagados_actualizado = pd.concat([df_rezagados_existente, rezagados], ignore_index=True)
        if 'LEAD' in df_rezagados_actualizado.columns:
            df_rezagados_actualizado = df_rezagados_actualizado.drop_duplicates(subset=['LEAD'], keep='first')

        df_ventas_actualizado = df_ventas_actualizado[~rezagado_mask].reset_index(drop=True)

        rezagados_moved = len(rezagados)
    else:
        df_rezagados_actualizado = df_rezagados_existente

    df_ventas_actualizado = df_ventas_actualizado.reindex(columns=COLUMNAS_VENTAS + [c for c in df_ventas_actualizado.columns if c not in COLUMNAS_VENTAS], fill_value=pd.NA)
    df_rezagados_actualizado = df_rezagados_actualizado.reindex(columns=COLUMNAS_REZAGADOS + [c for c in df_rezagados_actualizado.columns if c not in COLUMNAS_REZAGADOS], fill_value=pd.NA)

    try:
        with pd.ExcelWriter(ruta, engine="openpyxl") as writer:
            df_ventas_actualizado.to_excel(writer, sheet_name=hoja_ventas, index=False)
            df_rezagados_actualizado.to_excel(writer, sheet_name=hoja_rezagados, index=False)
            for sheet_name, df_sheet in sheets.items():
                if sheet_name not in [hoja_ventas, hoja_rezagados]:
                    if isinstance(df_sheet, pd.DataFrame):
                        df_sheet.to_excel(writer, sheet_name=sheet_name, index=False)
        logger.info(f"Archivo maestro actualizado: {ruta}")
    except Exception as e:
        logger.exception("Error guardando archivo maestro:")
        raise

    return added, rezagados_moved
