# Reemplaza la función _try_parse_dates por esta versión optimizada

import time
import json
# (asegúrate de tener import pandas as pd, re y logging en el módulo)

def _try_parse_dates(series: pd.Series) -> pd.Series:
    """
    Parsea una serie de strings intentando primero una conversión vectorizada y
    usando infer_datetime_format (rápida). Para los valores que queden sin parsear
    se aplica extracción por regex y un segundo intento. Devuelve una Serie datetime.
    """
    t0 = time.time()
    s = series.astype(str).replace({'': pd.NA, 'nan': pd.NA})
    s = s.str.strip().replace({'\u200b': ''}, regex=True)

    # Primer intento: parseo vectorizado, infer_datetime_format True (rápido)
    try:
        parsed = pd.to_datetime(s, dayfirst=True, errors="coerce", infer_datetime_format=True)
    except Exception:
        # fallback seguro
        parsed = pd.Series([pd.NaT] * len(s), index=s.index)

    n_parsed = parsed.notna().sum()

    # Si la mayoría ya se parseó, devolvemos. Si no, intentamos extraer por regex.
    if n_parsed / max(1, len(s)) >= 0.95:
        # suficiente porcentaje parseado, devolvemos
        logging.getLogger(__name__).info(f"_try_parse_dates: vectorized parsed {n_parsed}/{len(s)} rows in {time.time()-t0:.2f}s")
        return parsed

    # Segundo intento (solo para filas sin parse): extraer por regex patrones comunes
    mask_na = parsed.isna()
    if mask_na.any():
        # Patrón que captura dd/mm/YYYY hh:mm(:ss)? o YYYY-mm-dd hh:mm(:ss)? u otras variantes
        pattern = r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?)|(\d{4}-\d{2}-\d{2}(?:[ T]\d{1,2}:\d{2}(?::\d{2})?)?)'
        extracted = s[mask_na].str.extract(pattern, expand=False)
        # extracted puede ser DataFrame con 2 columnas: tomamos la primera no-nula por fila
        if isinstance(extracted, pd.DataFrame):
            combined = extracted.fillna('').apply(lambda row: (row[0] or row[1]), axis=1)
        else:
            combined = extracted.fillna('')

        # Reintentar parseo sobre lo extraído
        try:
            parsed_extra = pd.to_datetime(combined.replace('', pd.NaT), dayfirst=True, errors="coerce", infer_datetime_format=True)
        except Exception:
            parsed_extra = pd.Series([pd.NaT] * len(combined), index=combined.index)

        # Poner resultados donde estaban NaT
        parsed.loc[mask_na] = parsed_extra

    # Último recurso: intentar parse general nuevamente para cualquier resto
    if parsed.isna().any():
        try:
            remainder = s[parsed.isna()]
            parsed_fallback = pd.to_datetime(remainder, dayfirst=True, errors="coerce")
            parsed.loc[parsed.isna()] = parsed_fallback
        except Exception:
            pass

    logging.getLogger(__name__).info(f"_try_parse_dates: total parsed {parsed.notna().sum()}/{len(s)} rows in {time.time()-t0:.2f}s")
    return parsed
