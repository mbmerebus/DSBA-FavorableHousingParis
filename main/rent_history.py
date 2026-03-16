import pandas as pd
import altair as alt
import geopandas as gpd


def build_rent_history(paris_zones_all: gpd.GeoDataFrame) -> tuple:
    """
    Returns two Altair charts:
    - history_chart: ref/max/min rent over years for a selected neighborhood
    - top_increases_chart: neighborhoods with highest rent increase since first record
    """

    # Aggregate to one row per (quartier, annee) — average across room types
    df = (
        paris_zones_all
        .groupby(["nom_quartier", "id_quartier", "annee"], as_index=False)
        .agg(ref=("ref", "mean"), max=("max", "mean"), min=("min", "mean"))
    )
    df["annee"] = pd.to_numeric(df["annee"], errors="coerce")
    df = df.dropna(subset=["annee"])
    df["annee"] = df["annee"].astype(int)

    return df


def plot_rent_history(df: pd.DataFrame, quartier_name: str) -> alt.Chart:
    """Line chart: ref (solid), max and min (dashed) for a given neighborhood."""
    data = df[df["nom_quartier"] == quartier_name].sort_values("annee")

    if data.empty:
        return None

    # Melt to long format for Altair
    melted = data.melt(
        id_vars="annee",
        value_vars=["ref", "max", "min"],
        var_name="metric",
        value_name="rent"
    )

    line_styles = {
        "ref": "solid",
        "max": "dashed",
        "min": "dashed",
    }
    color_map = {
        "ref": "#2c2116",
        "max": "#c0392b",
        "min": "#27ae60",
    }
    label_map = {
        "ref": "Reference rent",
        "max": "Max rent",
        "min": "Min rent",
    }
    melted["label"] = melted["metric"].map(label_map)

    chart = alt.Chart(melted).mark_line(point=True).encode(
        x=alt.X("annee:O", title="Year"),
        y=alt.Y("rent:Q", title="Rent (€/m²)", scale=alt.Scale(zero=False)),
        color=alt.Color(
            "label:N",
            scale=alt.Scale(
                domain=list(label_map.values()),
                range=list(color_map.values())
            ),
            legend=alt.Legend(title="")
        ),
        strokeDash=alt.StrokeDash(
            "metric:N",
            scale=alt.Scale(
                domain=["ref", "max", "min"],
                range=[[0], [6, 4], [6, 4]]
            ),
            legend=None
        ),
        tooltip=[
            alt.Tooltip("annee:O", title="Year"),
            alt.Tooltip("label:N", title="Metric"),
            alt.Tooltip("rent:Q", title="€/m²", format=".1f"),
        ]
    ).properties(
        width="container",
        height=300,
        title=f"Rent history — {quartier_name}"
    )

    return chart


def plot_top_increases(df: pd.DataFrame, year_min: int, year_max: int, top_n: int = 5) -> tuple:
    """
    Returns two Altair charts side by side:
    - top_n neighborhoods with highest rent increase over the given year range
    - top_n neighborhoods with lowest rent increase (or biggest decrease)
    """
    # Filter to selected year range
    df_range = df[df["annee"].between(year_min, year_max)]

    # Get rent at start and end of range for each quartier
    first_rent = (
        df_range[df_range["annee"] == df_range.groupby("nom_quartier")["annee"].transform("min")]
        [["nom_quartier", "ref"]]
        .rename(columns={"ref": "ref_first"})
        .drop_duplicates("nom_quartier")
    )
    last_rent = (
        df_range[df_range["annee"] == df_range.groupby("nom_quartier")["annee"].transform("max")]
        [["nom_quartier", "ref"]]
        .rename(columns={"ref": "ref_last"})
        .drop_duplicates("nom_quartier")
    )

    merged = first_rent.merge(last_rent, on="nom_quartier")
    merged["increase_pct"] = ((merged["ref_last"] - merged["ref_first"]) / merged["ref_first"] * 100).round(1)

    # Top N highest increases
    top = merged.nlargest(top_n, "increase_pct").sort_values("increase_pct", ascending=True)
    # Top N lowest increases (could be negative)
    bottom = merged.nsmallest(top_n, "increase_pct").sort_values("increase_pct", ascending=False)

    def make_chart(data, title, color_scheme, reverse):
        return (
            alt.Chart(data).mark_bar().encode(
                x=alt.X("increase_pct:Q", title="Change (%)", axis=alt.Axis(format=".1f")),
                y=alt.Y(
                    "nom_quartier:N",
                    sort=alt.EncodingSortField(field="increase_pct", order="ascending"),
                    title="",
                    axis=alt.Axis(labelLimit=200, labelOverlap=False)
                ),
                color=alt.Color(
                    "increase_pct:Q",
                    scale=alt.Scale(scheme=color_scheme, reverse=reverse),
                    legend=None
                ),
                tooltip=[
                    alt.Tooltip("nom_quartier:N", title="Neighborhood"),
                    alt.Tooltip("ref_first:Q", title=f"Rent {year_min} (€/m²)", format=".1f"),
                    alt.Tooltip("ref_last:Q", title=f"Rent {year_max} (€/m²)", format=".1f"),
                    alt.Tooltip("increase_pct:Q", title="Change (%)", format=".1f"),
                ]
            ).properties(
                width="container",
                height=top_n * 50,
                title=title
            )
        )

    chart_top = make_chart(top, f"Top {top_n} highest increases", "reds", False)
    chart_bottom = make_chart(bottom, f"Top {top_n} lowest increases", "greens", True)

    return chart_top, chart_bottom