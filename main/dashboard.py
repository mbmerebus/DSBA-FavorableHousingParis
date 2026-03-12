"""
Dashboard – Favorable Housing in Paris for Students
By Team Rent o'Matic: Marta SHKRELI & Matteo COUCHOUD
Run:  streamlit run dashboard.py
"""

import streamlit as st
import geopandas as gpd
import pandas as pd
import altair as alt
import json
import os
from shapely.geometry import shape

# ──────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────
st.set_page_config(
    page_title="Paris Student Housing Dashboard",
    page_icon="🏠",
    layout="wide",
)

# ──────────────────────────────────────────────
# Paths (relative to main/ folder)
# ──────────────────────────────────────────────
GEODATA_PATH = os.path.join(os.path.dirname(__file__), "..", "geodata", "logement-encadrement-des-loyers.geojson")
ISOCHRONE_DIR = os.path.join(os.path.dirname(__file__), "..", "isochrone")

# Campus info
CAMPUS_NAME = "Paris 1 Panthéon-Sorbonne"
CAMPUS_LON, CAMPUS_LAT = 2.3463, 48.8467


# ──────────────────────────────────────────────
# Data loading (cached so it's fast on re-runs)
# ──────────────────────────────────────────────
@st.cache_data
def load_data():
    """Load GeoJSON + isochrone data and compute commute times."""
    # Try multiple possible paths for the GeoJSON
    possible_paths = [
        os.path.join(os.path.dirname(__file__), "..", "geodata", "logement-encadrement-des-loyers.geojson"),
        "/mount/src/dsba-favorablehousingparis/geodata/logement-encadrement-des-loyers.geojson",
    ]
    
    geodata_path = None
    for p in possible_paths:
        if os.path.exists(p):
            geodata_path = p
            break
    
    if geodata_path is None:
        return None, None, None

    paris_zones = gpd.read_file(geodata_path)
    paris_zones["annee"] = pd.to_numeric(paris_zones["annee"], errors="coerce")
    paris_zones = paris_zones[paris_zones["annee"] >= 2024].copy()
    paris_zones["centroid"] = paris_zones.to_crs(epsg=3857).centroid.to_crs(epsg=4326)

    # Try multiple possible paths for isochrone data
    possible_iso_dirs = [
        os.path.join(os.path.dirname(__file__), "..", "isochrone"),
        "/mount/src/dsba-favorablehousingparis/isochrone",
    ]
    
    iso_dir = None
    for p in possible_iso_dirs:
        if os.path.exists(p):
            iso_dir = p
            break
    
    if iso_dir is None:
        return paris_zones, [], {}

    # Load isochrone polygons
    isochrone_polygons = {}
    iso_files = [f for f in os.listdir(iso_dir) if f.endswith(".json")]
    for iso_file in iso_files:
        with open(os.path.join(iso_dir, iso_file)) as f:
            iso_data = json.load(f)
        iso = iso_data["isochrones"][0]
        dur = iso["max_duration"] // 60
        isochrone_polygons[dur] = shape(iso["geojson"])

    sorted_durations = sorted(isochrone_polygons.keys())

    # Assign commute time
    centroids = paris_zones.to_crs(epsg=3857).centroid.to_crs(epsg=4326)

    def get_commute(c):
        for d in sorted_durations:
            if isochrone_polygons[d].contains(c):
                return d
        return None

    paris_zones["commute_minutes"] = centroids.apply(get_commute)

    return paris_zones, sorted_durations, isochrone_polygons


with st.spinner("Loading map data... this may take a moment on first load."):
    paris_zones, sorted_durations, isochrone_polygons = load_data()

# ──────────────────────────────────────────────
# Handle missing GeoJSON gracefully
# ──────────────────────────────────────────────
if paris_zones is None:
    st.error(
        "⚠️ **GeoJSON file not found.** "
        "Please download *logement-encadrement-des-loyers.geojson* from "
        "[OpenData Paris](https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers) "
        "and place it in the `geodata/` folder of this repository."
    )
    st.stop()


# ──────────────────────────────────────────────
# Header
# ──────────────────────────────────────────────
st.title("🏠 Paris Student Housing Dashboard")
st.markdown(
    "Find the best neighborhoods in Paris balancing **rent price** and **commute time**. "
    "Use the sidebar filters to narrow down your search."
)

# ──────────────────────────────────────────────
# Sidebar filters
# ──────────────────────────────────────────────
st.sidebar.header("🔍 Filters")

# Rent range
rent_min_val = float(paris_zones["ref"].min())
rent_max_val = float(paris_zones["ref"].max())
rent_range = st.sidebar.slider(
    "Rent range (€/m²)",
    min_value=rent_min_val,
    max_value=rent_max_val,
    value=(rent_min_val, rent_max_val),
    step=0.5,
)

# Commute time
commute_options = sorted_durations + ["60+ (unreachable)"]
max_commute = st.sidebar.select_slider(
    "Max commute time (minutes)",
    options=sorted_durations,
    value=sorted_durations[-1],
)

# Room type
room_types = sorted(paris_zones["piece"].dropna().unique().tolist())
selected_rooms = st.sidebar.multiselect(
    "Number of rooms",
    options=room_types,
    default=room_types,
)

# Furnished filter
furnished_options = sorted(paris_zones["meuble_txt"].dropna().unique().tolist())
selected_furnished = st.sidebar.multiselect(
    "Furnished / Unfurnished",
    options=furnished_options,
    default=furnished_options,
)

# Construction era (bonus filter from the dataset)
if "epoque" in paris_zones.columns:
    epoque_options = sorted(paris_zones["epoque"].dropna().unique().tolist())
    selected_epoque = st.sidebar.multiselect(
        "Construction era",
        options=epoque_options,
        default=epoque_options,
    )
else:
    selected_epoque = None


# ──────────────────────────────────────────────
# Apply filters
# ──────────────────────────────────────────────
filtered = paris_zones.copy()
filtered = filtered[
    (filtered["ref"] >= rent_range[0])
    & (filtered["ref"] <= rent_range[1])
]
filtered = filtered[filtered["piece"].isin(selected_rooms)]
filtered = filtered[filtered["meuble_txt"].isin(selected_furnished)]

# Commute filter: keep zones within selected max commute (drop NaN = unreachable)
filtered = filtered[
    filtered["commute_minutes"].notna()
    & (filtered["commute_minutes"] <= max_commute)
]

if selected_epoque is not None:
    filtered = filtered[filtered["epoque"].isin(selected_epoque)]


# ──────────────────────────────────────────────
# KPIs
# ──────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)
col1.metric("Matching zones", f"{len(filtered)}")
col2.metric("Neighborhoods", f"{filtered['nom_quartier'].nunique()}")
col3.metric("Avg rent (€/m²)", f"{filtered['ref'].mean():.1f}" if len(filtered) else "—")
col4.metric(
    "Avg commute (min)",
    f"{filtered['commute_minutes'].mean():.0f}" if len(filtered) else "—",
)

st.divider()

# ──────────────────────────────────────────────
# Map
# ──────────────────────────────────────────────
if len(filtered) == 0:
    st.warning("No zones match the current filters. Try adjusting the sidebar.")
    st.stop()

# Prepare display data — simplify geometry to reduce data size for Altair
alt.data_transformers.disable_max_rows()
display_df = filtered.drop(columns=["centroid"], errors="ignore").copy()
display_df["geometry"] = display_df["geometry"].simplify(tolerance=0.0005, preserve_topology=True)
geo_json = alt.InlineData(
    values=display_df.__geo_interface__,
    format=alt.DataFormat(property="features", type="json"),
)

# Let user pick what to colour the map by
map_colour = st.radio(
    "Colour map by:",
    ["Rent (€/m²)", "Commute time (min)", "Combined score"],
    horizontal=True,
)

if map_colour == "Rent (€/m²)":
    colour_enc = alt.Color(
        "properties.ref:Q",
        scale=alt.Scale(scheme="redyellowgreen", reverse=True),
        legend=alt.Legend(title="Rent (€/m²)"),
    )
elif map_colour == "Commute time (min)":
    colour_enc = alt.Color(
        "properties.commute_minutes:O",
        scale=alt.Scale(
            domain=sorted_durations,
            range=["#60e309", "#ecf312", "#ffd900", "#ff6518"][: len(sorted_durations)],
        ),
        legend=alt.Legend(title="Commute (min)"),
    )
else:
    # Combined score: compute on the fly for filtered data
    ref_min = filtered["ref"].min()
    ref_max = filtered["ref"].max()
    dur_min = sorted_durations[0]
    dur_max = sorted_durations[-1]

    filtered_scored = filtered.copy()
    if ref_max > ref_min:
        filtered_scored["rent_score"] = (filtered_scored["ref"] - ref_min) / (ref_max - ref_min)
    else:
        filtered_scored["rent_score"] = 0
    filtered_scored["commute_score"] = (filtered_scored["commute_minutes"] - dur_min) / (
        dur_max - dur_min
    )
    filtered_scored["combined_score"] = (
        filtered_scored["rent_score"] + filtered_scored["commute_score"]
    ) / 2

    display_df = filtered_scored.drop(columns=["centroid"], errors="ignore").copy()
    display_df["geometry"] = display_df["geometry"].simplify(tolerance=0.0005, preserve_topology=True)
    geo_json = alt.InlineData(
        values=display_df.__geo_interface__,
        format=alt.DataFormat(property="features", type="json"),
    )
    colour_enc = alt.Color(
        "properties.combined_score:Q",
        scale=alt.Scale(scheme="redyellowgreen", reverse=True, domain=[0, 1]),
        legend=alt.Legend(title="Score (0 = best)"),
    )

# Build chart
base_map = (
    alt.Chart(geo_json)
    .mark_geoshape(stroke="white", strokeWidth=0.5)
    .encode(
        color=colour_enc,
        tooltip=[
            alt.Tooltip("properties.nom_quartier:N", title="Neighborhood"),
            alt.Tooltip("properties.ref:Q", title="Rent (€/m²)"),
            alt.Tooltip("properties.commute_minutes:Q", title="Commute (min)"),
            alt.Tooltip("properties.piece:N", title="Rooms"),
            alt.Tooltip("properties.meuble_txt:N", title="Type"),
        ],
    )
)

campus_pt = (
    alt.Chart({"values": [{"lon": CAMPUS_LON, "lat": CAMPUS_LAT}]})
    .mark_point(color="red", size=120, shape="cross", filled=True)
    .encode(longitude="lon:Q", latitude="lat:Q", tooltip=alt.value(CAMPUS_NAME))
)

campus_lbl = (
    alt.Chart({"values": [{"lon": CAMPUS_LON, "lat": CAMPUS_LAT, "name": CAMPUS_NAME}]})
    .mark_text(dy=-12, fontSize=11, fontWeight="bold", color="black")
    .encode(longitude="lon:Q", latitude="lat:Q", text="name:N")
)

chart = (
    (base_map + campus_pt + campus_lbl)
    .properties(width=750, height=550)
    .project(type="mercator")
)

st.altair_chart(chart, use_container_width=True)


# ──────────────────────────────────────────────
# Top neighborhoods table
# ──────────────────────────────────────────────
st.subheader("📋 Top neighborhoods (by average rent)")

table_data = (
    filtered.groupby("nom_quartier", as_index=False)
    .agg(
        avg_rent=("ref", "mean"),
        commute_min=("commute_minutes", "first"),
        zones=("id_quartier", "nunique"),
    )
    .sort_values("avg_rent")
    .head(15)
)
table_data.columns = ["Neighborhood", "Avg Rent (€/m²)", "Commute (min)", "Zones"]
table_data["Avg Rent (€/m²)"] = table_data["Avg Rent (€/m²)"].round(1)
table_data = table_data.reset_index(drop=True)
table_data.index += 1  # 1-based ranking

st.dataframe(table_data, use_container_width=True)


# ──────────────────────────────────────────────
# Footer
# ──────────────────────────────────────────────
st.divider()
st.caption(
    "Data: [OpenData Paris](https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers) "
    "& [Île-de-France Mobilités Navitia API](https://prim.iledefrance-mobilites.fr/). "
    "Built by Team Rent o'Matic — Marta SHKRELI & Matteo COUCHOUD."
)