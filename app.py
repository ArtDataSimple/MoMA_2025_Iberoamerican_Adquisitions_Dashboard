import re
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(
    page_title="MoMA | Dashboard de adquisiciones",
    page_icon="🎨",
    layout="wide",
)


DEFAULT_DATA_FILES = [
    Path("data/3_MoMA_2025_Acquisitions_Clean.csv"),
    Path("3_MoMA_2025_Acquisitions_Clean.csv"),
    Path("data/MoMA_final_transformed.xlsx"),
    Path("data/MoMA_final_transformed.csv"),
    Path("MoMA_final_transformed.xlsx"),
    Path("MoMA_final_transformed.csv"),
]

DATA_SEARCH_DIRS = [Path("data"), Path(".")]


def find_default_data_file() -> Path | None:
    # 1) exact preferred filenames
    for p in DEFAULT_DATA_FILES:
        if p.exists():
            return p

    # 2) any CSV/XLSX in data/ or repo root
    for folder in DATA_SEARCH_DIRS:
        if folder.exists():
            for pattern in ("*.xlsx", "*.xls", "*.csv"):
                matches = sorted(folder.glob(pattern))
                if matches:
                    return matches[0]

    return None


ARTICLE_TEXT = """
# Cómo entra América Latina al museo

Una colección nunca es una suma inocente de obras. Incluso cuando adopta la forma de un inventario técnico, toda colección contiene una narrativa:
dice qué merece ser conservado, qué trayectorias se consideran centrales, qué geografías ganan visibilidad y bajo qué condiciones materiales esas obras consiguen entrar en la institución.

En este subconjunto del MoMA aparecen énfasis muy claros: Argentina pesa especialmente, el grabado y el libro ilustrado dominan sobre medios más esperables como la pintura, y la donación emerge como una estructura clave para entender cómo se construye el relato museístico.
"""


NEWSLETTER_TEXT = """
# Newsletter breve

Este conjunto de adquisiciones del MoMA no dibuja una representación neutra de lo latinoamericano e ibérico. Dibujan, más bien, una narrativa con énfasis muy claros:
Argentina lidera en presencia, José Guadalupe Posada concentra un volumen llamativo de obras, y la donación aparece como el mecanismo de ingreso dominante.

La colección no solo conserva objetos. También conserva redes, apoyos y decisiones institucionales.
"""


DESCRIPTIONS = {
    "Título": "Título de la obra o trabajo adquirido.",
    "Artista": "Nombre del artista asociado a la obra.",
    "País": "País estandarizado de nacimiento/origen del artista.",
    "Nacimiento": "Año de nacimiento del artista.",
    "Fallecimiento": "Año de fallecimiento del artista, si aplica.",
    "Fecha Creacion": "Primer año extraído como fecha de creación de la obra.",
    "Forma Ingreso": "Forma en que la obra ingresó en la colección.",
    "Clasificación": "Clasificación estandarizada de la obra.",
    "Departamento": "Departamento del museo responsable de la obra.",
    "Fecha Adquisición": "Fecha de adquisición de la obra por el museo.",
    "Enlace": "URL del registro de la obra en el MoMA.",
}


GENERIC_PATTERNS = [
    r"^Donación del artista$",
    r"^Donación anónima$",
    r"^Fondo para América Latina y el Caribe$",
    r"^Fondo para el Twenty-First Century$",
    r"^Regalo del Arquitecto/a$",
    r"^Donación del fabricante$",
    r"^Donación del Diseñor/a$",
    r"^Compra de Grasshopper Films$",
]


def is_named_donation(x) -> bool:
    if pd.isna(x):
        return False
    s = str(x).strip()
    for pat in GENERIC_PATTERNS:
        if re.match(pat, s):
            return False
    return any(keyword in s for keyword in [
        "Donación de ", "Donación del Legado de", "Legado de ",
        "Fondo de Dotación", "Fondo John", "Fondo Familia",
        "gracias a la generosidad de", "en honor de", "en honor a",
        "Caterina Heil Stewart", "Barbara Jakobson", "Philip Sills",
        "Jaime Davidovich Foundation", "Helen and Sam Zell",
        "Deborah Wye", "Nina and Gordon Bunshaft"
    ])


@st.cache_data
def load_dataframe(uploaded_file=None) -> pd.DataFrame:
    if uploaded_file is not None:
        suffix = Path(uploaded_file.name).suffix.lower()
        if suffix in [".xlsx", ".xls"]:
            df = pd.read_excel(uploaded_file)
        else:
            df = pd.read_csv(uploaded_file)
    else:
        found = find_default_data_file()
        if found is None:
            raise FileNotFoundError(
                "No se encontró un archivo de datos por defecto. "
                "Sube un CSV/XLSX o añade tu archivo dentro de la carpeta `data/` del repositorio."
            )
        if found.suffix.lower() == ".xlsx":
            df = pd.read_excel(found)
        else:
            df = pd.read_csv(found)

    # Normalización suave
    for col in ["Nacimiento", "Fallecimiento", "Fecha Creacion"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    if "Fecha Adquisición" in df.columns:
        df["Fecha Adquisición"] = pd.to_datetime(df["Fecha Adquisición"], errors="coerce")

    return df


def build_profile(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for col in df.columns:
        s = df[col]
        row = {
            "Columna": col,
            "Tipo": str(s.dtype),
            "Descripción": DESCRIPTIONS.get(col, ""),
            "Faltantes": int(s.isna().sum()),
            "Únicos": int(s.nunique(dropna=True)),
            "Mínimo": "",
            "Máximo": "",
            "Media": "",
            "Mediana": "",
            "Desv. estándar": "",
        }
        if pd.api.types.is_numeric_dtype(s):
            nums = pd.to_numeric(s, errors="coerce")
            row.update({
                "Mínimo": nums.min(),
                "Máximo": nums.max(),
                "Media": round(float(nums.mean()), 2) if nums.notna().any() else "",
                "Mediana": nums.median(),
                "Desv. estándar": round(float(nums.std()), 2) if nums.notna().sum() > 1 else "",
            })
        rows.append(row)
    return pd.DataFrame(rows)


def add_common_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filtros")

    countries = sorted(df["País"].dropna().unique().tolist()) if "País" in df.columns else []
    classes = sorted(df["Clasificación"].dropna().unique().tolist()) if "Clasificación" in df.columns else []
    depts = sorted(df["Departamento"].dropna().unique().tolist()) if "Departamento" in df.columns else []

    selected_countries = st.sidebar.multiselect("País", countries, default=countries)
    selected_classes = st.sidebar.multiselect("Clasificación", classes, default=classes)
    selected_depts = st.sidebar.multiselect("Departamento", depts, default=depts)

    min_year = int(df["Fecha Creacion"].dropna().min()) if "Fecha Creacion" in df.columns and df["Fecha Creacion"].notna().any() else 1800
    max_year = int(df["Fecha Creacion"].dropna().max()) if "Fecha Creacion" in df.columns and df["Fecha Creacion"].notna().any() else 2030
    year_range = st.sidebar.slider("Rango de Fecha Creacion", min_year, max_year, (min_year, max_year))

    text_query = st.sidebar.text_input("Buscar en título o artista")

    filt = df.copy()

    if "País" in filt.columns:
        filt = filt[filt["País"].isin(selected_countries)]
    if "Clasificación" in filt.columns:
        filt = filt[filt["Clasificación"].isin(selected_classes)]
    if "Departamento" in filt.columns:
        filt = filt[filt["Departamento"].isin(selected_depts)]
    if "Fecha Creacion" in filt.columns:
        filt = filt[filt["Fecha Creacion"].between(year_range[0], year_range[1], inclusive="both")]

    if text_query:
        mask = pd.Series(False, index=filt.index)
        if "Título" in filt.columns:
            mask = mask | filt["Título"].fillna("").str.contains(text_query, case=False, regex=False)
        if "Artista" in filt.columns:
            mask = mask | filt["Artista"].fillna("").str.contains(text_query, case=False, regex=False)
        filt = filt[mask]

    return filt


def metric_row(df: pd.DataFrame):
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Filas", len(df))
    c2.metric("Artistas únicos", df["Artista"].nunique() if "Artista" in df.columns else 0)
    c3.metric("Países", df["País"].nunique() if "País" in df.columns else 0)
    c4.metric("Clasificaciones", df["Clasificación"].nunique() if "Clasificación" in df.columns else 0)
    c5.metric("Departamentos", df["Departamento"].nunique() if "Departamento" in df.columns else 0)


def plot_top_artists(df: pd.DataFrame, key_suffix: str = ""):
    counts = df["Artista"].value_counts().head(15).sort_values(ascending=True)
    fig = px.bar(
        x=counts.values,
        y=counts.index,
        orientation="h",
        text=counts.values,
        labels={"x": "Número de obras", "y": "Artista"},
        title="Artistas con más obras adquiridas",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_top_artists_{key_suffix}")


def plot_unique_artists_by_country(df: pd.DataFrame, key_suffix: str = ""):
    counts = df.groupby("País")["Artista"].nunique().sort_values(ascending=False)
    fig = px.bar(
        x=counts.index,
        y=counts.values,
        text=counts.values,
        labels={"x": "País", "y": "Número de artistas únicos"},
        title="Número de artistas únicos por país",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_unique_artists_by_country_{key_suffix}")


def plot_living_vs_deceased(df: pd.DataFrame, key_suffix: str = ""):
    status = df.groupby("Artista")["Fallecimiento"].apply(
        lambda s: "Fallecidos" if s.notna().any() else "Vivos"
    ).value_counts()
    fig = px.bar(
        x=status.index,
        y=status.values,
        text=status.values,
        labels={"x": "Estado del artista", "y": "Número de artistas"},
        title="Artistas vivos y fallecidos",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_living_vs_deceased_{key_suffix}")


def plot_hist_birth(df: pd.DataFrame, key_suffix: str = ""):
    fig = px.histogram(
        df.dropna(subset=["Nacimiento"]),
        x="Nacimiento",
        nbins=20,
        title="Años de nacimiento de los artistas",
        labels={"Nacimiento": "Año de nacimiento", "count": "Frecuencia"},
    )
    st.plotly_chart(fig, width="stretch", key=f"plot_hist_birth_{key_suffix}")


def plot_hist_creation(df: pd.DataFrame, key_suffix: str = ""):
    fig = px.histogram(
        df.dropna(subset=["Fecha Creacion"]),
        x="Fecha Creacion",
        nbins=20,
        title="Años de creación de las obras",
        labels={"Fecha Creacion": "Año de creación", "count": "Frecuencia"},
    )
    st.plotly_chart(fig, width="stretch", key=f"plot_hist_creation_{key_suffix}")


def plot_forma_ingreso(df: pd.DataFrame, key_suffix: str = ""):
    counts = df["Forma Ingreso"].fillna("Faltante").value_counts().head(15).sort_values(ascending=True)
    fig = px.bar(
        x=counts.values,
        y=counts.index,
        orientation="h",
        text=counts.values,
        labels={"x": "Cantidad", "y": "Forma de ingreso"},
        title="Tipos de ingreso o donación más frecuentes",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_forma_ingreso_{key_suffix}")


def plot_named_donors(df: pd.DataFrame, key_suffix: str = ""):
    counts = df.loc[df["Forma Ingreso"].apply(is_named_donation), "Forma Ingreso"].value_counts().head(15).sort_values(ascending=True)
    fig = px.bar(
        x=counts.values,
        y=counts.index,
        orientation="h",
        text=counts.values,
        labels={"x": "Cantidad", "y": "Donante o fondo"},
        title="Donantes o fondos nominales más frecuentes",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_named_donors_{key_suffix}")


def plot_classification(df: pd.DataFrame, key_suffix: str = ""):
    counts = df["Clasificación"].value_counts().sort_values(ascending=False)
    fig = px.bar(
        x=counts.index,
        y=counts.values,
        text=counts.values,
        labels={"x": "Clasificación", "y": "Cantidad"},
        title="Clasificación de las obras",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_classification_{key_suffix}")


def plot_department(df: pd.DataFrame, key_suffix: str = ""):
    counts = df["Departamento"].value_counts().sort_values(ascending=False)
    fig = px.bar(
        x=counts.index,
        y=counts.values,
        text=counts.values,
        labels={"x": "Departamento", "y": "Cantidad"},
        title="Departamento de las obras",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_department_{key_suffix}")


def plot_cumulative_acq(df: pd.DataFrame, key_suffix: str = ""):
    temp = df.dropna(subset=["Fecha Adquisición"])["Fecha Adquisición"].value_counts().sort_index().cumsum()
    temp_df = pd.DataFrame({"Fecha Adquisición": temp.index, "Acumulado": temp.values})
    fig = px.line(
        temp_df,
        x="Fecha Adquisición",
        y="Acumulado",
        markers=True,
        title="Adquisiciones acumuladas a lo largo del tiempo",
        labels={"Fecha Adquisición": "Fecha de adquisición", "Acumulado": "Acumulado de obras"},
    )
    st.plotly_chart(fig, width="stretch", key=f"plot_cumulative_acq_{key_suffix}")


def plot_country_classification_heatmap(df: pd.DataFrame, key_suffix: str = ""):
    heat = pd.crosstab(df["País"], df["Clasificación"])
    fig = px.imshow(
        heat,
        aspect="auto",
        labels=dict(x="Clasificación", y="País", color="Cantidad"),
        title="País por clasificación",
    )
    st.plotly_chart(fig, width="stretch", key=f"plot_country_classification_heatmap_{key_suffix}")


def plot_box_creation_by_classification(df: pd.DataFrame, key_suffix: str = ""):
    temp = df.dropna(subset=["Clasificación", "Fecha Creacion"]).copy()
    fig = px.box(
        temp,
        x="Clasificación",
        y="Fecha Creacion",
        title="Fecha de creación por clasificación",
        labels={"Clasificación": "Clasificación", "Fecha Creacion": "Fecha de creación"},
    )
    st.plotly_chart(fig, width="stretch", key=f"plot_box_creation_by_classification_{key_suffix}")


def plot_acq_year(df: pd.DataFrame, key_suffix: str = ""):
    temp = df.dropna(subset=["Fecha Adquisición"]).copy()
    temp["Año adquisición"] = temp["Fecha Adquisición"].dt.year
    counts = temp["Año adquisición"].value_counts().sort_index()
    fig = px.bar(
        x=counts.index.astype(str),
        y=counts.values,
        text=counts.values,
        labels={"x": "Año de adquisición", "y": "Cantidad"},
        title="Obras por año de adquisición",
    )
    fig.update_traces(textposition="outside")
    st.plotly_chart(fig, width="stretch", key=f"plot_acq_year_{key_suffix}")


st.title("🎨 Dashboard Streamlit | Adquisiciones MoMA")
st.caption("Exploración interactiva del dataset transformado, con filtros, métricas, visualizaciones y texto editorial.")

uploaded = st.sidebar.file_uploader("Sube tu CSV o Excel final", type=["csv", "xlsx", "xls"])

try:
    df = load_dataframe(uploaded)
except Exception as e:
    st.error(str(e))
    st.stop()

filtered = add_common_filters(df)

tabs = st.tabs(["Resumen", "Visualizaciones", "Datos", "Perfil", "Narrativa", "Descargas"])

with tabs[0]:
    st.subheader("Resumen ejecutivo del dashboard")
    metric_row(filtered)

    c1, c2 = st.columns(2)
    with c1:
        if {"País", "Clasificación"}.issubset(filtered.columns):
            plot_country_classification_heatmap(filtered, "resumen_heatmap")
    with c2:
        if "Forma Ingreso" in filtered.columns:
            plot_forma_ingreso(filtered, "resumen_forma")

    c3, c4 = st.columns(2)
    with c3:
        if "Artista" in filtered.columns:
            plot_top_artists(filtered, "resumen_top_artists")
    with c4:
        if "Fecha Adquisición" in filtered.columns:
            plot_cumulative_acq(filtered, "resumen_cumulative")

with tabs[1]:
    st.subheader("Visualizaciones")
    c1, c2 = st.columns(2)
    with c1:
        plot_top_artists(filtered, "viz_top_artists")
        plot_living_vs_deceased(filtered, "viz_living")
        plot_hist_birth(filtered, "viz_hist_birth")
        plot_classification(filtered, "viz_classification")
        plot_country_classification_heatmap(filtered, "viz_heatmap_country_class")
        plot_box_creation_by_classification(filtered, "viz_box_creation_class")
    with c2:
        plot_unique_artists_by_country(filtered, "viz_unique_artists_country")
        plot_hist_creation(filtered, "viz_hist_creation")
        plot_forma_ingreso(filtered, "viz_forma_ingreso")
        plot_named_donors(filtered, "viz_named_donors")
        plot_department(filtered, "viz_department")
        plot_acq_year(filtered, "viz_acq_year")

with tabs[2]:
    st.subheader("Tabla de datos")
    st.dataframe(filtered, width="stretch", height=520)

with tabs[3]:
    st.subheader("Perfil del dataset")
    profile = build_profile(filtered)
    st.dataframe(profile, width="stretch", height=520)

with tabs[4]:
    st.subheader("Texto editorial")
    st.markdown(ARTICLE_TEXT)
    st.divider()
    st.markdown(NEWSLETTER_TEXT)

with tabs[5]:
    st.subheader("Descargas")
    csv_bytes = filtered.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar datos filtrados en CSV",
        data=csv_bytes,
        file_name="moma_filtrado.csv",
        mime="text/csv",
    )

    profile = build_profile(filtered)
    profile_csv = profile.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Descargar perfil del dataset en CSV",
        data=profile_csv,
        file_name="moma_profile.csv",
        mime="text/csv",
    )

st.sidebar.markdown("---")
st.sidebar.info(
    "Sugerencia: guarda tu CSV/XLSX dentro de la carpeta `data/` del repositorio (por ejemplo `data/3_MoMA_2025_Acquisitions_Clean.csv`) para que la app lo cargue automáticamente en Streamlit Cloud."
)
