import streamlit as st
import pandas as pd
import io, csv, unicodedata, html, json

# Módulo que expone render_udla() y render_licenciaturas_anahuac()
# Evita ejecutar trabajo costoso en el import.

def normalize_header(s):
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = s.replace("_", " ").replace("-", " ").replace(".", " ")
    s = " ".join(s.split())
    return s

def detect_delimiter(sample):
    try:
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(sample[:4096])
        return dialect.delimiter
    except Exception:
        if "\t" in sample:
            return "\t"
        return ","

def read_text_to_df(text):
    sep = detect_delimiter(text)
    try:
        df = pd.read_csv(io.StringIO(text), sep=sep, engine='python', dtype=str)
    except Exception:
        df = pd.read_csv(io.StringIO(text), sep=",", dtype=str, engine='python')
    return df

COMMON_HEADER_MAP = {
    "alumno":"Alumno","alum":"Alumno","estudiante":"Alumno","nombre alumno":"Alumno","nombre":"Alumno","alumno nombre":"Alumno","alumno completo":"Alumno",
    "correo":"Correo","email":"Correo","e-mail":"Correo","correo alumno":"Correo","email alumno":"Correo",
    "identificacion alumno":"Identificación Alumno","identificacion":"Identificación Alumno","identificación alumno":"Identificación Alumno","id alumno":"Identificación Alumno",
    "nombre pago":"Nombre Pago","nombre_pago":"Nombre Pago","nombre del pago":"Nombre Pago","concepto pago":"Nombre Pago","descripcion pago":"Nombre Pago","nombrepago":"Nombre Pago"
}

UDLA_HEADER_MAP = {
    "student_name":"Alumno","student_email":"Correo","student_id":"Identificación Alumno",
    "nombre_estudiante":"Alumno","correo_estudiante":"Correo","id_estudiante":"Identificación Alumno"
}

def merged_header_map(vista_key):
    m = COMMON_HEADER_MAP.copy()
    if vista_key == "UDLA":
        for k,v in UDLA_HEADER_MAP.items():
            m[k]=v
    return m

TARGET_COLUMNS = ["Alumno","Correo","Identificación Alumno","Nombre Pago"]

def _render_generic(title, description, header_map_key=None, download_name="depurado.csv"):
    st.title(title)
    st.markdown(description)

    debug = st.checkbox("Modo debug (mostrar logs)", value=False, key=f"debug_{title}")

    uploaded = st.file_uploader("Subir archivo CSV / TSV", type=["csv","txt"], accept_multiple_files=False, key=f"uploader_{title}")
    text_area = st.text_area("O pega aquí los datos (CSV/TSV) — incluye la fila de encabezados", height=180, key=f"paste_{title}")
    content_text = None
    if uploaded is not None:
        try:
            raw = uploaded.read()
            try:
                content_text = raw.decode("utf-8")
            except Exception:
                content_text = raw.decode("latin-1")
            if debug: st.write("Archivo cargado en memoria (bytes):", len(raw))
        except Exception as e:
            st.error(f"Error leyendo archivo: {e}")
    if text_area and not content_text:
        content_text = text_area
        if debug: st.write("Contenido pegado en textarea, longitud:", len(content_text))

    if not content_text:
        st.info("Sube un archivo CSV/TSV o pega los datos para comenzar.")
        return

    st.info("Procesando...")
    df = read_text_to_df(content_text)
    if debug: st.write("Columnas detectadas:", list(df.columns)[:20])

    header_map = merged_header_map(header_map_key)
    mapping = {}
    for col in df.columns:
        n = normalize_header(col)
        mapped = header_map.get(n) or COMMON_HEADER_MAP.get(n)
        if mapped:
            mapping[col] = mapped

    out = pd.DataFrame(columns=TARGET_COLUMNS)
    for raw_col, mapped_col in mapping.items():
        out[mapped_col] = df[raw_col].astype(str).fillna("")

    for c in TARGET_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    out = out[TARGET_COLUMNS]

    # Reglas por defecto
    out["Identificación Alumno"] = out["Identificación Alumno"].astype(str).apply(lambda s: s.replace(" ", "").replace("-", ""))
    out["Correo"] = out["Correo"].astype(str).apply(lambda s: s.strip().lower())

    st.subheader("Vista previa - datos depurados")
    st.dataframe(out.head(1000))

    csv_bytes = out.to_csv(index=False).encode("utf-8")
    # NOTA: no serializamos TSV aquí para evitar bloqueo en render.
    st.download_button("Descargar CSV", data=csv_bytes, file_name=download_name, mime="text/csv")

    # Botón para preparar la copia TSV: solo cuando el usuario lo requiera construimos el string JS
    if st.button("Preparar copia TSV para pegar en Excel"):
        # construir tsv_text solo aquí (evita trabajo en cada render)
        tsv_text = out.to_csv(index=False, sep="\t")
        # si es muy grande, advertir
        size_bytes = len(tsv_text.encode("utf-8"))
        if size_bytes > 2_000_000:  # 2MB arbitrario
            st.warning(f"El TSV tiene {size_bytes/1_000_000:.1f} MB. La copia al portapapeles puede tardar o fallar en navegadores.")
        tsv_js = json.dumps(tsv_text)
        copy_html = (
            "<button id=\"copyBtn\">Copiar como TSV (pegar en Excel)</button>\n"
            "<script>\n"
            "const tsv = " + tsv_js + ";\n"
            "document.getElementById('copyBtn').addEventListener('click', function(){\n"
            "  const ta = document.createElement('textarea');\n"
            "  ta.value = tsv;\n"
            "  document.body.appendChild(ta);\n"
            "  ta.select();\n"
            "  try {\n"
            "    document.execCommand('copy');\n"
            "    alert('TSV copiado al portapapeles. Pega en Excel (Ctrl+V).');\n"
            "  } catch(e) {\n"
            "    alert('No se pudo copiar automáticamente desde el navegador.');\n"
            "  }\n"
            "  document.body.removeChild(ta);\n"
            "});\n"
            "</script>\n"
        )
        st.components.v1.html(copy_html, height=70)

def render_udla():
    _render_generic(
        title="Depurador - UDLA maestrías",
        description="Sube o pega un CSV/TSV con encabezados. Se conservarán solo: Alumno, Correo, Identificación Alumno, Nombre Pago.",
        header_map_key="UDLA",
        download_name="depurado_udla.csv"
    )

def render_licenciaturas_anahuac():
    _render_generic(
        title="Depurador - Licenciaturas Anáhuac",
        description="Sube o pega un CSV/TSV para Licenciaturas Anáhuac. Se conservarán solo: Alumno, Correo, Identificación Alumno, Nombre Pago.",
        header_map_key=None,
        download_name="depurado_licenciaturas_anahuac.csv"
    )

if __name__ == "__main__":
    render_udla()
