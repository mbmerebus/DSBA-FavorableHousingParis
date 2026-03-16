"""
Dashboard – Favorable Housing in Paris for Students
By Team Rent o'Matic: Marta SHKRELI & Matteo COUCHOUD
Run:  streamlit run dashboard.py
"""

import streamlit as st
import streamlit.components.v1 as components
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
    page_title="Favorable Housing for Student in Paris",
    page_icon="🏠",
    layout="wide",
)

# Campus info
possible_campus_paths = [
    os.path.join(os.path.dirname(__file__), "..", "geodata", "campus_data.json"),
    "/mount/src/dsba-favorablehousingparis/geodata/campus_data.json",
]

campuses = []
for p in possible_campus_paths:
    if os.path.exists(p):
        with open(p) as f:
            campuses = json.load(f)
        break


# ──────────────────────────────────────────────
# Data loading (cached so it's fast on re-runs)
# ──────────────────────────────────────────────
@st.cache_data
def load_data(campus_slug):
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
    possible_iso_dirs = []
    if campus_slug:
        possible_iso_dirs += [
            os.path.join(os.path.dirname(__file__), "..", "isochrone", campus_slug),
            f"/mount/src/dsba-favorablehousingparis/isochrone/{campus_slug}",
        ]
    possible_iso_dirs += [
        os.path.join(os.path.dirname(__file__), "..", "isochrone"),
        "/mount/src/dsba-favorablehousingparis/isochrone",
    ]

    iso_dir = None
    for p in possible_iso_dirs:
        if os.path.exists(p) and any(f.endswith(".json") for f in os.listdir(p)):
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

campus_names = [c["name"] for c in campuses]
selected_campus_name = st.sidebar.selectbox("🎓 Campus", options=campus_names)
selected_campus = next(c for c in campuses if c["name"] == selected_campus_name)
CAMPUS_NAME = selected_campus["name"]
CAMPUS_LON  = selected_campus["lon"]
CAMPUS_LAT  = selected_campus["lat"]

# Gets the campus slug and loads data according to the selected campus
CAMPUS_SLUG = selected_campus.get("slug")

with st.spinner("Loading map data..."):
    paris_zones, sorted_durations = load_data(CAMPUS_SLUG)

if paris_zones is None:
    st.error("⚠️ GeoJSON file not found.")
    st.stop()

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

outside_penalty = st.sidebar.slider(
    "Commute time weight",
    min_value=0.5,
    max_value=3.0,
    value=1.0,
    step=0.1,
    help="1.0 = linear. Higher = slow commutes penalized more in the combined score."
)

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
# Apply filters — keep ALL zones, flag matching ones
# ──────────────────────────────────────────────
filtered = paris_zones.copy()

mask = (
    (filtered["ref"] >= rent_range[0])
    & (filtered["ref"] <= rent_range[1])
    & (filtered["piece"].isin(selected_rooms))
    & (filtered["meuble_txt"].isin(selected_furnished))
)

if max_commute is not None:
    mask = mask & (
        filtered["commute_minutes"].isna()
        | (filtered["commute_minutes"] <= max_commute)
    )

if selected_epoque is not None:
    mask = mask & filtered["epoque"].isin(selected_epoque)

filtered["matches"] = mask


# ──────────────────────────────────────────────
# KPIs — based only on matching zones
# ──────────────────────────────────────────────
matching = filtered[filtered["matches"]]
col1, col2, col3, col4 = st.columns(4)
col1.metric("Matching zones", f"{matching['id_quartier'].nunique()}")
col2.metric("Neighborhoods", f"{matching['nom_quartier'].nunique()}")
col3.metric("Avg rent (€/m²)", f"{matching['ref'].mean():.1f}" if len(matching) else "—")
col4.metric(
    "Avg commute (min)",
    f"{matching['commute_minutes'].mean():.0f}" if len(matching) and matching['commute_minutes'].notna().any() else "—",
)

st.divider()

# ──────────────────────────────────────────────
# Map
# ──────────────────────────────────────────────
if len(filtered) == 0:
    st.warning("No zones found. Try adjusting the sidebar.")
    st.stop()

# Aggregate to one row per neighborhood — keep ALL zones, flag matching ones
map_data = filtered.groupby("id_quartier", as_index=False).agg(
    nom_quartier=("nom_quartier", "first"),
    geometry=("geometry", "first"),
    commute_minutes=("commute_minutes", "first"),
    ref=("ref", "mean"),
    matches=("matches", "any"),  # True if at least one row in the zone matches
)
map_data = gpd.GeoDataFrame(map_data, geometry="geometry", crs="EPSG:4326")
map_data["geometry"] = map_data["geometry"].simplify(tolerance=0.0001, preserve_topology=True)

# Compute combined score on ALL zones (matching or not)
ref_min = map_data["ref"].min()
ref_max = map_data["ref"].max()
if ref_max > ref_min:
    map_data["rent_score"] = (map_data["ref"] - ref_min) / (ref_max - ref_min)
else:
    map_data["rent_score"] = 0.0

if sorted_durations:
    dur_min, dur_max = sorted_durations[0], sorted_durations[-1]
    # Base commute score: 0 (fastest) → 1 (slowest), NaN → 1 (outside all isochrones)
    map_data["commute_score_base"] = map_data["commute_minutes"].apply(
        lambda m: 1.0 if pd.isna(m) else (m - dur_min) / (dur_max - dur_min) if dur_max > dur_min else 0
    )
else:
    map_data["commute_score_base"] = 1.0

# Apply power curve: higher weight = slow zones punished more
map_data["commute_score"] = map_data["commute_score_base"] ** outside_penalty

# Raw combined score
map_data["combined_score_raw"] = (map_data["rent_score"] + map_data["commute_score"]) / 2

# Normalize to [0, 1] so the full color range is always used
score_min = map_data["combined_score_raw"].min()
score_max = map_data["combined_score_raw"].max()
if score_max > score_min:
    map_data["combined_score"] = ((map_data["combined_score_raw"] - score_min) / (score_max - score_min)).round(3)
else:
    map_data["combined_score"] = 0.0

map_data["ref"] = map_data["ref"].round(1)

# Colour selector
map_colour = st.radio(
    "Colour map by:",
    ["Rent (€/m²)", "Commute time (min)", "Combined score"],
    horizontal=True,
)

# Build Altair chart
display_df = map_data.drop(columns=["centroid"], errors="ignore")
geojson_data = alt.InlineData(
    values=display_df.__geo_interface__,
    format=alt.DataFormat(property="features", type="json"),
)

# Colour encoding: matching zones get full colour, non-matching zones are greyed out
if map_colour == "Rent (€/m²)":
    colour_enc = alt.condition(
        "datum.properties.matches",
        alt.Color(
            "properties.ref:Q",
            scale=alt.Scale(scheme="redyellowgreen", reverse=True),
            legend=alt.Legend(title="Rent (€/m²)"),
        ),
        alt.value("#d0d0d0")
    )
elif map_colour == "Commute time (min)":
    colour_enc = alt.condition(
        "datum.properties.matches",
        alt.condition(
            "datum.properties.commute_minutes !== null",
            alt.Color(
                "properties.commute_minutes:O",
                scale=alt.Scale(
                    domain=sorted_durations,
                    range=["#60e309", "#ecf312", "#ffd900", "#ff6518"][: len(sorted_durations)],
                ),
                legend=alt.Legend(title="Commute (min)"),
            ),
            alt.value("#8B0000")  # crimson for zones outside all isochrones
        ),
        alt.value("#d0d0d0")  # grey for non-matching zones
    )
else:
    colour_enc = alt.condition(
        "datum.properties.matches",
        alt.Color(
            "properties.combined_score:Q",
            scale=alt.Scale(scheme="redyellowgreen", reverse=True, domain=[0, 1]),
            legend=alt.Legend(title="Score (0=best)"),
        ),
        alt.value("#d0d0d0")  # grey for non-matching zones
    )

base_map = (
    alt.Chart(geojson_data)
    .mark_geoshape(stroke="white", strokeWidth=0.5)
    .encode(
        color=colour_enc,
        tooltip=[
            alt.Tooltip("properties.nom_quartier:N", title="Neighborhood"),
            alt.Tooltip("properties.ref:Q", title="Avg Rent (€/m²)"),
            alt.Tooltip("properties.commute_minutes:Q", title="Commute (min)"),
            alt.Tooltip("properties.combined_score:Q", title="Combined Score"),
            alt.Tooltip("properties.matches:N", title="Matches filters?"),
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
    .properties(width="container", height=550)
    .project(type="mercator")
)

# Render via chart.to_html() + st.components.v1.html
# This is necessary because st.altair_chart flattens GeoJSON data,
# destroying the nested geometry that geoshape needs.
components.html(chart.to_html(), height=620, scrolling=False)


# ──────────────────────────────────────────────
# Top neighborhoods table — matching zones only
# ──────────────────────────────────────────────
st.subheader("📋 Top neighborhoods (by average rent)")

table_data = map_data[map_data["matches"]].sort_values("ref").head(15)[
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
    "Data: [OpenData Paris](https://opendata.paris.fr/explore/dataset/logement-encadrement-des-loyers)\n"
    "& [Île-de-France Mobilités Navitia API](https://prim.iledefrance-mobilites.fr/). \n"
    "Built by Team PixelParty — Marta SHKRELI & Matteo COUCHOUD."
)