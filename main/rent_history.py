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
        "ref": "#b5956a",
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


def plot_top_increases(df: pd.DataFrame, top_n: int = 15) -> alt.Chart:
    """Bar chart: neighborhoods with highest ref rent increase since first record."""
    first = df.groupby("nom_quartier")["annee"].min().reset_index()
    first.columns = ["nom_quartier", "first_year"]
    last = df.groupby("nom_quartier")["annee"].max().reset_index()
    last.columns = ["nom_quartier", "last_year"]

    periods = first.merge(last, on="nom_quartier")
    periods = periods[periods["first_year"] < periods["last_year"]]

    first_rent = df.merge(periods[["nom_quartier", "first_year"]], on="nom_quartier")
    first_rent = first_rent[first_rent["annee"] == first_rent["first_year"]][["nom_quartier", "ref"]].rename(columns={"ref": "ref_first"})
    last_rent = df.merge(periods[["nom_quartier", "last_year"]], on="nom_quartier")
    last_rent = last_rent[last_rent["annee"] == last_rent["last_year"]][["nom_quartier", "ref"]].rename(columns={"ref": "ref_last"})

    merged = first_rent.merge(last_rent, on="nom_quartier").drop_duplicates("nom_quartier")
    merged["increase"] = (merged["ref_last"] - merged["ref_first"]).round(2)
    merged["increase_pct"] = ((merged["increase"] / merged["ref_first"]) * 100).round(1)

    top = merged.nlargest(top_n, "increase_pct").sort_values("increase_pct", ascending=True)

    chart = alt.Chart(top).mark_bar(color="#b5956a").encode(
        x=alt.X("increase_pct:Q", title="Increase (%)"),
        y=alt.Y("nom_quartier:N", sort="-x", title=""),
        tooltip=[
            alt.Tooltip("nom_quartier:N", title="Neighborhood"),
            alt.Tooltip("ref_first:Q", title="First recorded (€/m²)", format=".1f"),
            alt.Tooltip("ref_last:Q", title="Latest (€/m²)", format=".1f"),
            alt.Tooltip("increase_pct:Q", title="Increase (%)", format=".1f"),
        ]
    ).properties(
        width="container",
        height=400,
        title=f"Top {top_n} neighborhoods by rent increase"
    )

    return chart