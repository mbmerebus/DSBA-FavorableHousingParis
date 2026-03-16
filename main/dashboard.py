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
st.markdown("""
Paris is one of Europe's most expensive student cities, with reference rents ranging from
**under 20 €/m²** in outer arrondissements to **over 40 €/m²** in the most central neighborhoods.
High rent and varying commute times can put pressure on a student's life, which makes it all the more important
to find the right appartment for their studies.

The dashboard bellow lets you rank and find Paris neighborhoods that have existing appartment which satisfy a select number of criteria,
most notably average rent and commute time. But you could also search for other criteria.
""")

st.divider()

# ──────────────────────────────────────────────
# Sidebar filters
# ──────────────────────────────────────────────
st.sidebar.header("Filters")
st.sidebar.markdown("""
_Here you can select and modify specific criteria according to your appartment search interests._
""")

campus_names = [c["name"] for c in campuses]
selected_campus_name = st.sidebar.selectbox("Campus selected", options=campus_names)
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
    help="You can narrow or widden your acceptable rent range."
)

if sorted_durations:
    max_commute = st.sidebar.select_slider(
        "Max commute time (minutes)",
        options=sorted_durations,
        value=sorted_durations[-1],
        help="You can narrow or widden your acceptable commute time range."
    )
else:
    max_commute = None

commute_weight = st.sidebar.slider(
    "Commute time weight",
    min_value=0.5,
    max_value=1.5,
    value=1.0,
    step=0.1,
    help="1.0 = equal weight. Higher = slow commutes penalized more in the combined score."
)

room_types = sorted(paris_zones["piece"].dropna().unique().tolist())
selected_rooms = st.sidebar.multiselect(
    "Number of rooms",
    options=room_types,
    default=room_types,
    help="Add or delete a specific amount of rooms. A higher amount of rooms may increase the average rent."
)

furnished_options = sorted(paris_zones["meuble_txt"].dropna().unique().tolist())
selected_furnished = st.sidebar.multiselect(
    "Furnished / Unfurnished",
    options=furnished_options,
    default=furnished_options,
    help="Add or delete furnished/unfurnished appartments in the search.\ Furnished appartments have often higher rents.\ Meublé = Furnished, Non Meublé = Unfurnished."
)

if "epoque" in paris_zones.columns:
    epoque_options = sorted(paris_zones["epoque"].dropna().unique().tolist())
    selected_epoque = st.sidebar.multiselect(
        "Construction era",
        options=epoque_options,
        default=epoque_options,
        help="Add or delete specific building periods.\ Older appartments usually have worse heat insullation/energy efficiency, which may increase electricity bills.\ Après=After, Avant=Before."
    )
else:
    selected_epoque = None


# ──────────────────────────────────────────────
# Apply filters — keep ALL zones, flag matching ones
# Zones with no commute data (outside all isochrones) are NEVER matching
# ──────────────────────────────────────────────
filtered = paris_zones.copy()

mask = (
    (filtered["ref"] >= rent_range[0])
    & (filtered["ref"] <= rent_range[1])
    & (filtered["piece"].isin(selected_rooms))
    & (filtered["meuble_txt"].isin(selected_furnished))
    & (filtered["commute_minutes"].notna())  # zones outside all isochrones never match
)

if max_commute is not None:
    mask = mask & (filtered["commute_minutes"] <= max_commute)

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

# ── Scoring ────────────────────────────────────────────────────────────────
# Rent score: 0 (cheapest) → 1 (most expensive)
ref_min = map_data["ref"].min()
ref_max = map_data["ref"].max()
if ref_max > ref_min:
    map_data["rent_score"] = (map_data["ref"] - ref_min) / (ref_max - ref_min)
else:
    map_data["rent_score"] = 0.0

# Commute base score: 0 (fastest isochrone) → 1 (slowest isochrone) → 1.5 (outside)
if sorted_durations:
    dur_min = float(sorted_durations[0])
    dur_max = float(sorted_durations[-1])
    map_data["commute_score_base"] = map_data["commute_minutes"].apply(
        lambda m: 1.5 if pd.isna(m)
        else 0.0 if dur_max == dur_min
        else (float(m) - dur_min) / (dur_max - dur_min)
    )
else:
    map_data["commute_score_base"] = 1.5

# Apply commute weight as a power curve:
#   weight = 1.0  → linear (score^1 = score)
#   weight = 2.0  → quadratic (score^2, slow zones punished more)
#   weight = 3.0  → cubic (score^3, slow zones punished even more)
# For zones outside isochrones (base > 1): linear amplification by weight
def apply_commute_weight(base, weight):
    b = float(base)
    w = float(weight)
    if b <= 1.0:
        return b ** (1 / w)    # weight > 1 → score closer to 1 → more penalized
    else:
        return 1.0 + (b - 1.0) * w  # outside isochrones: linear amplification

map_data["commute_score"] = map_data["commute_score_base"].apply(
    lambda b: apply_commute_weight(b, commute_weight)
)

# Combined raw score — not normalized so commute_weight has a visible effect
map_data["combined_score_raw"] = (map_data["rent_score"] + map_data["commute_score"]) / 2
map_data["combined_score"] = map_data["combined_score_raw"].round(3)

map_data["ref"] = map_data["ref"].round(1)

# Dynamic colour domain based on actual score range of matching zones only
matching_scores = map_data.loc[map_data["matches"], "combined_score"]
score_domain_min = float(matching_scores.min()) if len(matching_scores) else 0.0
score_domain_max = float(matching_scores.max()) if len(matching_scores) else 1.0
# ── End scoring ────────────────────────────────────────────────────────────

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

# Colour encoding:
# - matching zones → full colour
# - all other zones (non-matching or outside isochrones) → grey
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
        alt.Color(
            "properties.commute_minutes:O",
            scale=alt.Scale(
                domain=sorted_durations,
                range=["#60e309", "#ecf312", "#ffd900", "#ff6518"][: len(sorted_durations)],
            ),
            legend=alt.Legend(title="Commute (min)"),
        ),
        alt.value("#d0d0d0")
    )
else:
    colour_enc = alt.condition(
        "datum.properties.matches",
        alt.Color(
            "properties.combined_score:Q",
            scale=alt.Scale(
                scheme="redyellowgreen",
                reverse=True,
                domain=[score_domain_min, score_domain_max]
            ),
            legend=alt.Legend(title="Score (0=best)"),
        ),
        alt.value("#d0d0d0")
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
st.subheader("📋 Top neighborhoods (by combined score)")

table_data = map_data[map_data["matches"]].sort_values("combined_score").head(15)[
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