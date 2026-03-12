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

# Campus info
CAMPUS_NAME = "Paris 1 Panthéon-Sorbonne"
CAMPUS_LON, CAMPUS_LAT = 2.3463, 48.8467


# ──────────────────────────────────────────────
# Data loading (cached so it's fast on re-runs)
# ──────────────────────────────────────────────
@st.cache_data
def load_data():
    """Load GeoJSON + isochrone data and compute commute times."""
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
        return None, None

    paris_zones = gpd.read_file(geodata_path)
    paris_zones["annee"] = pd.to_numeric(paris_zones["annee"], errors="coerce")
    paris_zones = paris_zones[paris_zones["annee"] >= 2024].copy()
    paris_zones["centroid"] = paris_zones.to_crs(epsg=3857).centroid.to_crs(epsg=4326)

    # Load isochrone polygons
    possible_iso_dirs = [
        os.path.join(os.path.dirname(__file__), "..", "isochrone"),
        "/mount/src/dsba-favorablehousingparis/isochrone",
    ]

    iso_dir = None
    for p in possible_iso_dirs:
        if os.path.exists(p):
            iso_dir = p
            break

    sorted_durations = []
    if iso_dir:
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
    else:
        paris_zones["commute_minutes"] = None

    return paris_zones, sorted_durations


with st.spinner("Loading map data... this may take a moment on first load."):
    paris_zones, sorted_durations = load_data()

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

rent_min_val = float(paris_zones["ref"].min())
rent_max_val = float(paris_zones["ref"].max())
rent_range = st.sidebar.slider(
    "Rent range (€/m²)",
    min_value=rent_min_val,
    max_value=rent_max_val,
    value=(rent_min_val, rent_max_val),
    step=0.5,
)

if sorted_durations:
    max_commute = st.sidebar.select_slider(
        "Max commute time (minutes)",
        options=sorted_durations,
        value=sorted_durations[-1],
    )
else:
    max_commute = None

room_types = sorted(paris_zones["piece"].dropna().unique().tolist())
selected_rooms = st.sidebar.multiselect(
    "Number of rooms",
    options=room_types,
    default=room_types,
)

furnished_options = sorted(paris_zones["meuble_txt"].dropna().unique().tolist())
selected_furnished = st.sidebar.multiselect(
    "Furnished / Unfurnished",
    options=furnished_options,
    default=furnished_options,
)

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

if max_commute is not None:
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
    f"{filtered['commute_minutes'].mean():.0f}" if len(filtered) and filtered['commute_minutes'].notna().any() else "—",
)

st.divider()

# ──────────────────────────────────────────────
# Map
# ──────────────────────────────────────────────
if len(filtered) == 0:
    st.warning("No zones match the current filters. Try adjusting the sidebar.")
    st.stop()

# --- Aggregate to one row per neighborhood ---
# This reduces ~5000 rows to ~80, making the map small enough for Altair/Vega-Lite
map_data = filtered.groupby("id_quartier", as_index=False).agg(
    nom_quartier=("nom_quartier", "first"),
    geometry=("geometry", "first"),
    commute_minutes=("commute_minutes", "first"),
    ref=("ref", "mean"),
)
map_data = gpd.GeoDataFrame(map_data, geometry="geometry", crs="EPSG:4326")

# Simplify geometry slightly for faster rendering
map_data["geometry"] = map_data["geometry"].simplify(tolerance=0.0001, preserve_topology=True)

# Let user pick what to colour the map by
map_colour = st.radio(
    "Colour map by:",
    ["Rent (€/m²)", "Commute time (min)", "Combined score"],
    horizontal=True,
)

# Compute combined score
ref_min = map_data["ref"].min()
ref_max = map_data["ref"].max()
if ref_max > ref_min:
    map_data["rent_score"] = (map_data["ref"] - ref_min) / (ref_max - ref_min)
else:
    map_data["rent_score"] = 0

if sorted_durations:
    dur_min = sorted_durations[0]
    dur_max = sorted_durations[-1]
    map_data["commute_score"] = map_data["commute_minutes"].apply(
        lambda m: 1.0 if pd.isna(m) else (m - dur_min) / (dur_max - dur_min) if dur_max > dur_min else 0
    )
else:
    map_data["commute_score"] = 0

map_data["combined_score"] = (map_data["rent_score"] + map_data["commute_score"]) / 2

# Round for cleaner tooltips
map_data["ref"] = map_data["ref"].round(1)
map_data["combined_score"] = map_data["combined_score"].round(3)

# Build GeoJSON for Altair — use features list directly
# alt.InlineData gets stripped by Streamlit's Vega-Lite theme processing
display_df = map_data.drop(columns=["centroid"], errors="ignore")
features = display_df.__geo_interface__["features"]

if map_colour == "Rent (€/m²)":
    color_field = "properties.ref"
    color_type = "quantitative"
    color_scale = {"scheme": "redyellowgreen", "reverse": True}
    legend_title = "Rent (€/m²)"
elif map_colour == "Commute time (min)":
    color_field = "properties.commute_minutes"
    color_type = "ordinal"
    color_scale = {
        "domain": sorted_durations,
        "range": ["#60e309", "#ecf312", "#ffd900", "#ff6518"][: len(sorted_durations)],
    }
    legend_title = "Commute (min)"
else:
    color_field = "properties.combined_score"
    color_type = "quantitative"
    color_scale = {"scheme": "redyellowgreen", "reverse": True, "domain": [0, 1]}
    legend_title = "Score (0=best)"

# Build Vega-Lite spec directly — avoids Streamlit stripping inline data
vega_spec = {
    "$schema": "https://vega.github.io/schema/vega-lite/v5.json",
    "width": 750,
    "height": 550,
    "projection": {"type": "mercator"},
    "layer": [
        {
            "data": {
                "values": features,
                "format": {"property": "geometry", "type": "json"},
            },
            "mark": {"type": "geoshape", "stroke": "white", "strokeWidth": 0.5},
            "encoding": {
                "color": {
                    "field": color_field,
                    "type": color_type,
                    "scale": color_scale,
                    "legend": {"title": legend_title},
                },
                "tooltip": [
                    {"field": "properties.nom_quartier", "type": "nominal", "title": "Neighborhood"},
                    {"field": "properties.ref", "type": "quantitative", "title": "Avg Rent (€/m²)"},
                    {"field": "properties.commute_minutes", "type": "quantitative", "title": "Commute (min)"},
                    {"field": "properties.combined_score", "type": "quantitative", "title": "Combined Score"},
                ],
            },
        },
        {
            "data": {"values": [{"lon": CAMPUS_LON, "lat": CAMPUS_LAT}]},
            "mark": {"type": "point", "color": "red", "size": 120, "shape": "cross", "filled": True},
            "encoding": {
                "longitude": {"field": "lon", "type": "quantitative"},
                "latitude": {"field": "lat", "type": "quantitative"},
            },
        },
        {
            "data": {"values": [{"lon": CAMPUS_LON, "lat": CAMPUS_LAT, "name": CAMPUS_NAME}]},
            "mark": {"type": "text", "dy": -12, "fontSize": 11, "fontWeight": "bold", "color": "black"},
            "encoding": {
                "longitude": {"field": "lon", "type": "quantitative"},
                "latitude": {"field": "lat", "type": "quantitative"},
                "text": {"field": "name", "type": "nominal"},
            },
        },
    ],
}

st.vega_lite_chart(vega_spec, use_container_width=True)


# ──────────────────────────────────────────────
# Top neighborhoods table
# ──────────────────────────────────────────────
st.subheader("📋 Top neighborhoods (by average rent)")

table_data = map_data.sort_values("ref").head(15)[
    ["nom_quartier", "ref", "commute_minutes", "combined_score"]
].copy()
table_data.columns = ["Neighborhood", "Avg Rent (€/m²)", "Commute (min)", "Score"]
table_data = table_data.reset_index(drop=True)
table_data.index += 1

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