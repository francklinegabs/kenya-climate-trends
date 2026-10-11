"""Forty-five years of Kenyan weather: warming trends, the two rainy seasons, and extremes.

Reads data/daily_weather.csv (from fetch_data.py), writes charts to figures/ and
tables to output/.
Run:  python src/analysis.py
"""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import TwoSlopeNorm  # noqa: E402
from scipy import stats  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "daily_weather.csv"
FIG = ROOT / "figures"
OUT = ROOT / "output"

BASELINE = (1981, 2010)          # WMO-style 30-year reference period
LONG_RAINS = [3, 4, 5]           # March-May ("masika")
SHORT_RAINS = [10, 11, 12]       # October-December ("vuli")
CITY_COLORS = {"Nairobi": "#1f5c4b", "Mombasa": "#3d6fb4", "Kisumu": "#b5541c", "Eldoret": "#8a6bb8", "Garissa": "#c9a227"}
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})


# ---------------------------------------------------------------- data
def load() -> pd.DataFrame:
    df = pd.read_csv(DATA, parse_dates=["date"])
    df = df.dropna(subset=["tmean", "precip_mm"])
    df["year"] = df["date"].dt.year
    df["month"] = df["date"].dt.month
    return df


def complete_years(df: pd.DataFrame, min_days: int = 360) -> pd.DataFrame:
    """Drop city-years with missing days so that annual totals are comparable."""
    counts = df.groupby(["city", "year"]).size()
    keep = counts[counts >= min_days].index
    return df.set_index(["city", "year"]).loc[keep].reset_index()


# ---------------------------------------------------------------- statistics
def trend(series: pd.Series) -> dict:
    """OLS slope per decade plus a Mann-Kendall-style test (Kendall's tau of value vs time)."""
    s = series.dropna()
    x = s.index.values.astype(float)
    lr = stats.linregress(x, s.values)
    tau, p_mk = stats.kendalltau(x, s.values)
    return {"slope_per_decade": lr.slope * 10, "r2": lr.rvalue ** 2, "ols_p": lr.pvalue,
            "kendall_tau": tau, "mk_p": p_mk, "n_years": len(s)}


def annual_temperature(df: pd.DataFrame) -> pd.DataFrame:
    return df.groupby(["city", "year"])[["tmean", "tmax", "tmin"]].mean().unstack("city")


def temperature_trends(annual: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for var in ["tmean", "tmax", "tmin"]:
        for city in annual[var].columns:
            s = annual[var][city]
            base = s.loc[BASELINE[0]:BASELINE[1]].mean()
            recent = s.loc[s.index.max() - 9:].mean()
            rows.append({"city": city, "variable": var, **trend(s),
                         "baseline_mean": base, "last_10y_mean": recent, "change_vs_baseline": recent - base})
    return pd.DataFrame(rows).round(4)


def seasonal_rain(df: pd.DataFrame) -> pd.DataFrame:
    def season_total(months):
        return df[df["month"].isin(months)].groupby(["city", "year"])["precip_mm"].sum()

    out = pd.DataFrame({"long_rains_mm": season_total(LONG_RAINS),
                        "short_rains_mm": season_total(SHORT_RAINS),
                        "annual_mm": df.groupby(["city", "year"])["precip_mm"].sum()})
    return out


def rain_summary(seasons: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for city, g in seasons.groupby(level="city"):
        g = g.droplevel("city")
        for col in seasons.columns:
            s = g[col]
            base = s.loc[BASELINE[0]:BASELINE[1]]
            anomaly_pct = (s / base.mean() - 1) * 100
            rows.append({
                "city": city, "season": col,
                "baseline_mean_mm": base.mean(),
                "cv_pct": s.std() / s.mean() * 100,
                "driest_year": int(s.idxmin()), "driest_mm": s.min(),
                "wettest_year": int(s.idxmax()), "wettest_mm": s.max(),
                "failed_seasons_lt_60pct": int((anomaly_pct < -40).sum()),
                **{f"trend_{k}": v for k, v in trend(s).items() if k in ("slope_per_decade", "mk_p")},
            })
    return pd.DataFrame(rows).round(2)


def hot_days(df: pd.DataFrame) -> pd.DataFrame:
    """Days per year above each city's own baseline 90th percentile of daily maximum temperature."""
    base = df[df["year"].between(*BASELINE)].groupby("city")["tmax"].quantile(0.9)
    flagged = df.assign(hot=df["tmax"] > df["city"].map(base))
    return flagged.groupby(["year", "city"])["hot"].sum().unstack("city")


def heavy_rain_days(df: pd.DataFrame, threshold_mm: float = 20.0) -> pd.DataFrame:
    return df.assign(heavy=df["precip_mm"] >= threshold_mm).groupby(["year", "city"])["heavy"].sum().unstack("city")


# ---------------------------------------------------------------- charts
def chart_climatology(df):
    clim = df.groupby(["city", "month"])["precip_mm"].sum().unstack("city") / df["year"].nunique()
    temp = df.groupby(["city", "month"])["tmean"].mean().unstack("city")
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    months = list("JFMAMJJASOND")
    for c in clim.columns:
        axes[0].plot(clim.index, clim[c], marker="o", ms=3.5, color=CITY_COLORS[c], label=c)
        axes[1].plot(temp.index, temp[c], marker="o", ms=3.5, color=CITY_COLORS[c], label=c)
    for ax in axes:
        ax.set_xticks(range(1, 13), months)
        ax.axvspan(2.5, 5.5, color="#3d6fb4", alpha=0.06)
        ax.axvspan(9.5, 12.5, color="#3d6fb4", alpha=0.06)
    axes[0].set_ylabel("Average monthly rainfall (mm)")
    axes[0].set_title("Two rainy seasons: long rains (MAM) and short rains (OND)")
    axes[1].set_ylabel("Mean temperature (°C)")
    axes[1].set_title("Altitude, not latitude, sets the temperature")
    axes[1].legend(frameon=False, fontsize=8.5)
    fig.tight_layout(); fig.savefig(FIG / "climatology.png"); plt.close(fig)


def chart_temperature_trends(annual, trends):
    tm = annual["tmean"]
    anom = tm - tm.loc[BASELINE[0]:BASELINE[1]].mean()
    fig, ax = plt.subplots(figsize=(10, 4.4))
    for c in anom.columns:
        t = trends[(trends.city == c) & (trends.variable == "tmean")].iloc[0]
        ax.plot(anom.index, anom[c].rolling(5, center=True, min_periods=3).mean(), color=CITY_COLORS[c], lw=2,
                label=f"{c}: {t.slope_per_decade:+.2f} °C/decade")
        ax.plot(anom.index, anom[c], color=CITY_COLORS[c], lw=0.6, alpha=0.35)
    ax.axhline(0, color="#555", lw=0.8)
    ax.set_ylabel(f"Anomaly vs {BASELINE[0]}-{BASELINE[1]} (°C)")
    ax.set_title("Every city is warming (annual mean temperature, 5-year smoothing)")
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    fig.tight_layout(); fig.savefig(FIG / "temperature_trends.png"); plt.close(fig)


def chart_stripes(annual, city="Nairobi"):
    s = annual["tmean"][city]
    anom = (s - s.loc[BASELINE[0]:BASELINE[1]].mean()).values.reshape(1, -1)
    lim = np.nanmax(np.abs(anom))
    fig, ax = plt.subplots(figsize=(10, 1.9))
    ax.imshow(anom, aspect="auto", cmap="RdBu_r", norm=TwoSlopeNorm(0, -lim, lim),
              extent=[s.index.min() - 0.5, s.index.max() + 0.5, 0, 1])
    ax.set_yticks([]); ax.grid(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.set_title(f"{city} warming stripes, {s.index.min()}-{s.index.max()} (each stripe is one year)")
    fig.tight_layout(); fig.savefig(FIG / f"{city.lower()}_stripes.png"); plt.close(fig)


def chart_seasons(seasons, city="Nairobi"):
    g = seasons.xs(city, level="city")
    base = g.loc[BASELINE[0]:BASELINE[1]].mean()
    fig, axes = plt.subplots(2, 1, figsize=(10, 5.6), sharex=True)
    for ax, col, title in [(axes[0], "long_rains_mm", "Long rains (Mar-May)"),
                           (axes[1], "short_rains_mm", "Short rains (Oct-Dec)")]:
        a = (g[col] / base[col] - 1) * 100
        ax.bar(a.index, a.values, color=np.where(a.values < 0, "#b5541c", "#3d6fb4"), width=0.8)
        ax.axhline(0, color="#555", lw=0.8)
        ax.axhline(-40, color="#b5541c", lw=0.8, ls="--")
        ax.set_ylabel("% vs baseline")
        ax.set_title(f"{city}: {title} rainfall anomaly")
        for yr in a.nsmallest(3).index.tolist() + a.nlargest(2).index.tolist():
            ax.annotate(str(yr), (yr, a[yr]), xytext=(0, 3 if a[yr] > 0 else -11), textcoords="offset points",
                        ha="center", fontsize=8)
    axes[1].text(seasons.index.get_level_values("year").min(), -46, "failed season (< 60% of normal)",
                 fontsize=8, color="#b5541c", va="top")
    fig.tight_layout(); fig.savefig(FIG / f"{city.lower()}_seasonal_rain.png"); plt.close(fig)


def chart_hot_days(hd):
    fig, ax = plt.subplots(figsize=(10, 4))
    for c in hd.columns:
        ax.plot(hd.index, hd[c].rolling(5, center=True, min_periods=3).mean(), color=CITY_COLORS[c], lw=2, label=c)
    ax.axhline(36.5, color="#555", lw=0.8, ls="--")
    ax.text(hd.index.min(), 39, "expected ~36.5 days/yr by construction in the baseline", fontsize=8, color="#555")
    ax.set_ylabel("Days per year (5-year smoothing)")
    ax.set_title("Hot days: daily max above each city's 1981-2010 90th percentile")
    ax.legend(frameon=False, ncol=5, fontsize=8.5)
    fig.tight_layout(); fig.savefig(FIG / "hot_days.png"); plt.close(fig)


def main() -> None:
    FIG.mkdir(exist_ok=True)
    OUT.mkdir(exist_ok=True)
    df = complete_years(load())
    print(f"{len(df):,} city-days, {df['city'].nunique()} cities, {df['year'].min()}-{df['year'].max()}")

    annual = annual_temperature(df)
    trends = temperature_trends(annual)
    seasons = seasonal_rain(df)
    rain = rain_summary(seasons)
    hd = hot_days(df)
    heavy = heavy_rain_days(df)

    trends.to_csv(OUT / "temperature_trends.csv", index=False)
    rain.to_csv(OUT / "rain_summary.csv", index=False)
    seasons.round(1).to_csv(OUT / "seasonal_rain_by_year.csv")
    hd.to_csv(OUT / "hot_days_by_year.csv")
    heavy.to_csv(OUT / "heavy_rain_days_by_year.csv")

    chart_climatology(df)
    chart_temperature_trends(annual, trends)
    chart_stripes(annual)
    chart_seasons(seasons)
    chart_hot_days(hd)

    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(trends[trends.variable == "tmean"])
    print(trends[trends.variable != "tmean"][["city", "variable", "slope_per_decade", "mk_p", "change_vs_baseline"]])
    print(rain)
    print("Hot days, first 10y vs last 10y mean:\n", pd.DataFrame({"first": hd.iloc[:10].mean(), "last": hd.iloc[-10:].mean()}).round(1))
    print("Heavy-rain days trend:", {c: round(trend(heavy[c])["slope_per_decade"], 2) for c in heavy.columns},
          {c: round(trend(heavy[c])["mk_p"], 3) for c in heavy.columns})
    print("Nairobi wettest single days:\n", df[df.city == "Nairobi"].nlargest(5, "precip_mm")[["date", "precip_mm"]])
    print("Warmest years Nairobi:", annual["tmean"]["Nairobi"].nlargest(5).round(2).to_dict())


if __name__ == "__main__":
    main()
