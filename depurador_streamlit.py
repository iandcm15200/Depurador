import streamlit as st
import pandas as pd
import io, csv, unicodedata, html

st.set_page_config(page_title="Depurador - Maestrías", layout="wide")

# -----------------------
# Interfaz principal
# -----------------------
st.title("Sistema de Depuración - Maestrías (Streamlit)")
st.markdown("Sube o pega un CSV/TSV con encabezados y elige la vista (Anáhuac o UDLA). Se conservarán solo: Alumno, Correo, Identificación Alumno, Nombre Pago.")

# Sidebar: interruptor/vista
st.sidebar.header("Seleccionar vista")
vista = st.sidebar.radio("Vista activa:", ["Anáhuac (versión actual)", "UDLA maestrías"], index=0)

# Si hay maestrías específicas, se pueden elegir (solo para información)
if vista == "UDLA maestrías":
    maestria = st.sidebar.selectbox("Maestría (UDLA)", ["UDLA maestrías"])
else:
    maestria = st.sidebar.selectbox("Maestría (Anáhuac)", ["anahuac maestrías"])

# -----------------------
# Helpers de lectura y normalización
# -----------------------
def normalize_header(s):
    if s is None:
        return ""
    s = str(s).strip().lower()
    # quitar acentos
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
        # fallback: prefer tab if found, else comma
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

# Mapas comunes de encabezados -> nombres de salida
COMMON_HEADER_MAP = {
    # Alumno
    "alumno":"Alumno", "alum":"Alumno", "estudiante":"Alumno", "nombre alumno":"Alumno", "nombre":"Alumno", "alumno nombre":"Alumno", "alumno completo":"Alumno",
    # Correo
    "correo":"Correo", "email":"Correo", "e-mail":"Correo", "correo alumno":"Correo", "email alumno":"Correo",
    # Identificación
    "identificacion alumno":"Identificación Alumno", "identificacion":"Identificación Alumno", "identificación alumno":"Identificación Alumno", "id alumno":"Identificación Alumno",
    # Nombre pago
    "nombre pago":"Nombre Pago", "nombre_pago":"Nombre Pago", "nombre del pago":"Nombre Pago", "concepto pago":"Nombre Pago", "descripcion pago":"Nombre Pago", "nombrepago":"Nombre Pago"
}

# Si UDLA tiene variaciones de encabezado específicas, agrégalas aquí
UDLA_HEADER_MAP = {
    # ejemplos comunes que UDLA podría usar
    "student_name":"Alumno", "student_email":"Correo", "student_id":"Identificación Alumno",
    "nombre_estudiante":"Alumno", "correo_estudiante":"Correo", "id_estudiante":"Identificación Alumno"
}

# Merge maps for convenience (priority: specific -> common)
def merged_header_map(vista_key):
    m = COMMON_HEADER_MAP.copy()
    if vista_key == "UDLA":
        for k,v in UDLA_HEADER_MAP.items(): m[k]=v
    return m

TARGET_COLUMNS = ["Alumno", "Correo", "Identificación Alumno", "Nombre Pago"]

# -----------------------
# Inputs (archivo o pegar)
# -----------------------
uploaded = st.file_uploader("Subir archivo CSV / TSV", type=["csv", "txt"], accept_multiple_files=False)
text_area = st.text_area("O pega aquí los datos (CSV/TSV) — incluye la fila de encabezados", height=180)

content_text = None
if uploaded is not None:
    try:
        raw = uploaded.read()
        try:
            content_text = raw.decode("utf-8")
        except Exception:
            content_text = raw.decode("latin-1")
    except Exception as e:
        st.error(f"Error leyendo archivo: {e}")

if text_area and not content_text:
    content_text = text_area

# -----------------------
# Procesado según vista
# -----------------------
if content_text:
    st.info(f"Procesando para vista: {vista}...")
    df = read_text_to_df(content_text)

    # construir mapa de encabezados normalizados
    header_map = merged_header_map("UDLA" if vista=="UDLA maestrías" else None)
    mapping = {}
    for col in df.columns:
        n = normalize_header(col)
        mapped = header_map.get(n)
        if not mapped:
            mapped = COMMON_HEADER_MAP.get(n)
        if mapped:
            mapping[col] = mapped

    # Construir dataframe de salida con las columnas objetivo
    out = pd.DataFrame(columns=TARGET_COLUMNS)
    for raw_col, mapped_col in mapping.items():
        out[mapped_col] = df[raw_col].astype(str).fillna("")

    # Asegurar columnas en orden y existencia
    for c in TARGET_COLUMNS:
        if c not in out.columns:
            out[c] = ""
    out = out[TARGET_COLUMNS]

    # Aplicar transformaciones por vista (si se requieren)
    if vista == "Anáhuac (versión actual)":
        # Mantener comportamiento actual (sin cambios)
        pass
    elif vista == "UDLA maestrías":
        # Ejemplo de reglas específicas para UDLA:
        # - Limpiar espacios y guiones en identificación
        # - Normalizar correos a minúsculas
        out["Identificación Alumno"] = out["Identificación Alumno"].astype(str).apply(lambda s: s.replace(" ", "").replace("-", ""))
        out["Correo"] = out["Correo"].astype(str).apply(lambda s: s.strip().lower())

    # Mostrar resultados
    st.subheader("Vista previa - datos depurados")
    st.dataframe(out.head(1000))

    st.markdown(f"**Vista seleccionada:** {vista} — Maestría: {maestria}")

    # Botones: descargar CSV y copiar TSV (TSV recomendado para pegar en Excel)
    csv_bytes = out.to_csv(index=False).encode("utf-8")
    tsv_text = out.to_csv(index=False, sep="\t")

    st.download_button("Descargar CSV", data=csv_bytes, file_name=f"depurado_{('udla' if vista=='UDLA maestrías' else 'anahuac')}.csv", mime="text/csv")

    # Botón para copia al portapapeles usando componente HTML+JS
    copy_html = f"""
    <button id="copyBtn">Copiar como TSV (pegar en Excel)</button>
    <script>
    // Crear textarea temporal con el TSV y copiar al portapapeles
    const tsv = `{tsv_text.replace("`","\\`")}`;
    document.getElementById('copyBtn').addEventListener('click', function(){ 
      const ta = document.createElement('textarea');
      ta.value = tsv;
      document.body.appendChild(ta);
      ta.select();
      try {{
        document.execCommand('copy');
        alert('TSV copiado al portapapeles. Pega en Excel (Ctrl+V).');
      }} catch(e) {{
        alert('No se pudo copiar automáticamente desde el navegador.');
      }}
      document.body.removeChild(ta);
    });
    </script>
    """
    st.components.v1.html(copy_html, height=60)

    st.success(f"Procesadas {len(out)} filas. Usa 'Descargar CSV' o 'Copiar como TSV' para pegar en Excel.")
else:
    st.info("Sube un archivo CSV/TSV o pega los datos para comenzar.")
