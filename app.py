# =============================================================================
# Dior Quarry Tonnage App – NTSF
# Q3.2025 RM
# -----------------------------------------------------------------------------
# Author:        Julio Cesar Solano A.
# Position:      Mineral Resource Superintendent
# Organization:  B
# Project:       Dior Quarry – NTSF
#
# Description:
# Interactive Streamlit dashboard for tabulation, validation, and reporting
# of construction material volumes and tonnages (Filter, Rockfill, Waste)
# within the current reserves pit. Includes geochemical classification
# (Carb-NPR, CO3 threshold), roll-up reconciliation, and audit trail export.
#
# Data Source:
# Q3.2025 Updated Block Model Tabulation (Excel)
#
# Key Features:
# - Destination normalization and roll-up reconciliation
# - CO3 sensitivity threshold analysis
# - Material classification (NPAG / PAG)
# - Sanity check vs official reporting totals
# - CSV and JSON export functionality
#
# Version:       1.0.0
# Last Update:   March 2026
# Environment:   Python 3.11+ | Streamlit
#
# =============================================================================


# -----------------------------
# Libraries
# -----------------------------
import json
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

# -----------------------------
# Dashboard config
# -----------------------------
st.set_page_config(
    page_title="Block Model Sensitivity"
st.title(TITLE)",
    layout="wide",
)

TITLE = "Block Model Sensitivity"
st.title(TITLE)

# Palette (RGB)
MYCOLORS = {
    "gold": "rgb(163,145,97)",
    "blue": "rgb(3,84,124)",
    "gray": "rgb(109,110,113)",
    "gray_light": "rgb(199,200,202)",
    "orange": "rgb(253,184,19)",
}

# -----------------------------
# Load data helper
# -----------------------------
@st.cache_data(show_spinner=False)
def load_data(path_or_buffer) -> pd.DataFrame:
    df = pd.read_excel(path_or_buffer)
    df.columns = [c.strip().upper() for c in df.columns]
    return df

# -----------------------------
# Professional table formatting (display only)
# -----------------------------
def format_professional_table(df_in: pd.DataFrame) -> pd.DataFrame:
    """
    Formats tables for display only (USA separators).
    Keeps original numeric df intact for calculations/exports.
    """
    df = df_in.copy()

    # Integer
    for col in ["VOLUME", "TONNES"]:
        if col in df.columns:
            df[col] = df[col].apply(lambda x: f"{x:,.0f}" if pd.notnull(x) else "")

    # Mt with 3 decimals
    if "TONNES_MT" in df.columns:
        df["TONNES_MT"] = df["TONNES_MT"].apply(lambda x: f"{x:,.3f}" if pd.notnull(x) else "")

    # Percent with 2 decimals
    if "PCT_OF_SUBTOTAL" in df.columns:
        df["PCT_OF_SUBTOTAL"] = df["PCT_OF_SUBTOTAL"].apply(lambda x: f"{x:.2f}%" if pd.notnull(x) else "")

    return df

# -----------------------------
# Data upload (upload-only)
# -----------------------------
uploaded = st.file_uploader("Upload Excel (.xlsx)", type=["xlsx"], key="main_file_upload")

if uploaded is None:
    st.warning("Please upload the Excel (.xlsx) file to proceed.")
    st.stop()

data = load_data(uploaded)

# -----------------------------
# Columns validations
# -----------------------------
REQUIRED_COLS = [
    "SOURCE", "PHASE", "BENCH", "DESTINATION", "CATEG", "LITHO", "WEATHERING",
    "C_PCT", "OC_PCT", "S_PCT", "S2_PCT", "NPR", "CO3_PCT", "VOLUME", "TONNES"
]

missing = [c for c in REQUIRED_COLS if c not in data.columns]
if missing:
    st.error("Missing required columns in uploaded file:")
    st.write(missing)
    st.stop()

# -----------------------------
# Data validation
# -----------------------------
with st.expander("Diagnostics (uploaded file)", expanded=False):
    st.write("Rows:", len(data))
    st.write("Columns:", list(data.columns))
    st.dataframe(data.head(50), use_container_width=True)
    if "DESTINATION" in data.columns:
        st.write("DESTINATION unique:", sorted(pd.Series(data["DESTINATION"]).dropna().unique().tolist())[:200])
    if "LITHO" in data.columns:
        st.write("LITHO unique:", sorted(pd.Series(data["LITHO"]).dropna().unique().tolist())[:200])
    if "WEATHERING" in data.columns:
        st.write("WEATHERING unique:", sorted(pd.Series(data["WEATHERING"]).dropna().unique().tolist())[:200])

# -----------------------------
# Destination normalization
# -----------------------------
def normalize_destination(raw: str) -> str:
    if raw is None or (isinstance(raw, float) and np.isnan(raw)):
        return "Unknown"

    s = str(raw).strip().lower()

    # Filter bins
    if s in ["filter1", "filter_1", "filter 1", "f1", "filter material 1"]:
        return "Filter1"
    if s in ["filter2", "filter_2", "filter 2", "f2", "filter material 2"]:
        return "Filter2"
    if s in ["filter", "filter material"]:
        return "Filter"

    # Rockfill bins
    if s in ["rockfill1", "rockfill_1", "rockfill 1", "rf1", "rock fill 1", "rock fill1"]:
        return "Rockfill1"
    if s in ["rockfill2", "rockfill_2", "rockfill 2", "rf2", "rock fill 2", "rock fill2"]:
        return "Rockfill2"
    if s in ["rockfill", "rockfill material", "rock fill"]:
        return "Rockfill"

    # Waste bins
    if s in ["waste nag", "waste_nag", "wastenag", "nag", "waste non-acid", "waste npag"]:
        return "Waste Nag"
    if s in ["waste pag", "waste_pag", "wastepag", "pag", "waste acid"]:
        return "Waste Pag"
    if s in ["waste", "waste tonnes", "waste tonnage"]:
        return "Waste"

    return str(raw).strip()

def destination_rollup(norm: str) -> str:
    if norm in ["Filter1", "Filter2", "Filter"]:
        return "filter"
    if norm in ["Rockfill1", "Rockfill2", "Rockfill"]:
        return "rockfill"
    if norm in ["Waste Nag"]:
        return "waste_nag"
    if norm in ["Waste Pag"]:
        return "waste_pag"
    if norm in ["Unc_Rockfill", "Unc Rockfill", "Uncertain Rockfill"]:
        return "unc_rockfill"
    return "other"

# -----------------------------
# Derived fields
# -----------------------------
def add_derived_fields(df: pd.DataFrame, co3_threshold: float = 1.0) -> pd.DataFrame:
    out = df.copy()

    for col in ["VOLUME", "TONNES", "NPR", "CO3_PCT"]:
        if col in out.columns:
            out[col] = pd.to_numeric(out[col], errors="coerce")

    if "NPR" in out.columns:
        out["NPR_TYPE"] = np.where(out["NPR"] > 1.0, "NPAG", "PAG")

    if "CO3_PCT" in out.columns:
        out["CO3_BIN"] = np.where(
            out["CO3_PCT"] >= co3_threshold,
            f"CO3 ≥ {co3_threshold:.1f}%",
            f"CO3 < {co3_threshold:.1f}%",
        )

    if "DESTINATION" in out.columns:
        out["DESTINATION_NORM"] = out["DESTINATION"].apply(normalize_destination)
        out["DESTINATION_ROLLUP"] = out["DESTINATION_NORM"].apply(destination_rollup)
    else:
        out["DESTINATION_NORM"] = "Unknown"
        out["DESTINATION_ROLLUP"] = "other"

    if "TONNES" in out.columns:
        out["TONNES_MT"] = out["TONNES"] / 1e6
    else:
        out["TONNES_MT"] = np.nan

    return out

def safe_multiselect(label, series: pd.Series, default_all=True):
    opts = sorted([x for x in series.dropna().unique().tolist()])
    default = opts if default_all else (opts[:1] if opts else [])
    return st.multiselect(label, options=opts, default=default)

def build_filters_sidebar(df: pd.DataFrame):
    dff = df.copy()
    filters_used = {}

    with st.sidebar:
        st.header("Filters (Current Reserves Pit)")
        st.caption("All rows are assumed to be inside current reserves pit; filters are for sensitivity checks.")

        co3_thr = st.slider("CO3 threshold (%)", 0.0, 5.0, 1.0, 0.1)
        filters_used["CO3_threshold_pct"] = co3_thr

        if "DESTINATION_NORM" in dff.columns:
            dst = safe_multiselect("DESTINATION (normalized)", dff["DESTINATION_NORM"], default_all=True)
            filters_used["DESTINATION_NORM"] = dst
            dff = dff[dff["DESTINATION_NORM"].isin(dst)]

        for col in ["SOURCE", "PHASE", "CATEG", "LITHO", "WEATHERING", "NPR_TYPE"]:
            if col in dff.columns:
                sel = safe_multiselect(col, dff[col], default_all=True)
                filters_used[col] = sel
                dff = dff[dff[col].isin(sel)]

        if "BENCH" in dff.columns:
            dff["BENCH"] = pd.to_numeric(dff["BENCH"], errors="coerce")
            if dff["BENCH"].notna().any():
                bmin, bmax = int(dff["BENCH"].min()), int(dff["BENCH"].max())
                bench_rng = st.slider("BENCH range", bmin, bmax, (bmin, bmax), step=10)
                filters_used["BENCH_range"] = list(bench_rng)
                dff = dff[(dff["BENCH"] >= bench_rng[0]) & (dff["BENCH"] <= bench_rng[1])]

    dff = add_derived_fields(dff, co3_threshold=filters_used["CO3_threshold_pct"])
    return dff, filters_used, filters_used["CO3_threshold_pct"]

def tabulate(df: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()

    agg = (
        df.groupby(group_cols, dropna=False)[["VOLUME", "TONNES", "TONNES_MT"]]
        .sum()
        .reset_index()
    )
    total_mt = agg["TONNES_MT"].sum()
    agg["PCT_OF_SUBTOTAL"] = np.where(total_mt > 0, 100.0 * agg["TONNES_MT"] / total_mt, 0.0)
    return agg.sort_values("TONNES_MT", ascending=False)

def barplot(
    df_plot: pd.DataFrame,
    x: str,
    y: str,
    title: str,
    color: str | None = None,
    y_decimals: int = 3,      # default for Mt
    y_is_int: bool = False    # for TONNES/VOLUME
):
    if df_plot.empty:
        st.warning("No data to plot.")
        return

    fig = px.bar(df_plot, x=x, y=y, color=color, title=title)

    # Plotly tick/hover format
    # int -> ",.0f"  | float -> ",.3f" (or user-defined)
    yfmt = ",.0f" if y_is_int else f",.{y_decimals}f"

    fig.update_traces(
        hovertemplate=f"<b>%{{x}}</b><br>{y}: %{{y:{yfmt}}}<extra></extra>"
    )
    fig.update_yaxes(tickformat=yfmt)

    fig.update_layout(
        title_font_size=18,
        font=dict(size=14),
        plot_bgcolor="white",
        paper_bgcolor="white",
        legend_title_text=color if color else "",
        colorway=[MYCOLORS["gold"], MYCOLORS["blue"], MYCOLORS["orange"], MYCOLORS["gray"], MYCOLORS["gray_light"]],
    )

    if color is None:
        fig.update_traces(marker_color=MYCOLORS["blue"])

    st.plotly_chart(fig, use_container_width=True)

def download_csv(df_out: pd.DataFrame, filename: str, label: str = "Download CSV"):
    if df_out is None or df_out.empty:
        st.info("Nothing to export.")
        return
    csv = df_out.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=csv,
        file_name=filename,
        mime="text/csv",
        use_container_width=False,
    )

# -----------------------------
# Init derived fields + filters
# -----------------------------
data = add_derived_fields(data, co3_threshold=1.0)
df, filters_used, co3_thr = build_filters_sidebar(data)

# -----------------------------
# Filters used
# -----------------------------
with st.expander("Filters used (Audit trail)", expanded=False):
    st.json(filters_used)
    st.download_button(
        "Download filters (JSON)",
        data=json.dumps(filters_used, indent=2).encode("utf-8"),
        file_name="filters_used.json",
        mime="application/json",
    )

st.divider()

# -----------------------------
# Sanity check (official totals)
# -----------------------------
st.markdown("### Sanity Check — Destination Tonnes (Mt) [Official vs Calculated]")
st.caption("Sanity check is computed using DESTINATION_ROLLUP to match the official categories.")

official = pd.DataFrame({
    "DESTINATION_ROLLUP": ["filter", "rockfill", "waste_nag", "waste_pag", "TOTAL"],
    "OFFICIAL_TONNES_MT": [68.2335, 18.9846, 70.0908, 7.19745, 164.5064],
})

calc = (
    df.groupby("DESTINATION_ROLLUP", dropna=False)["TONNES_MT"].sum()
    .reset_index()
    .rename(columns={"TONNES_MT": "CALC_TONNES_MT"})
)

total_row = pd.DataFrame({
    "DESTINATION_ROLLUP": ["TOTAL"],
    "CALC_TONNES_MT": [df["TONNES_MT"].sum()]
})
calc = pd.concat([calc, total_row], ignore_index=True)

check = official.merge(calc, on="DESTINATION_ROLLUP", how="left")
check["CALC_TONNES_MT"] = check["CALC_TONNES_MT"].fillna(0.0)

check["DELTA_MT"] = check["CALC_TONNES_MT"] - check["OFFICIAL_TONNES_MT"]
check["DELTA_%"] = np.where(
    check["OFFICIAL_TONNES_MT"] > 0,
    100.0 * check["DELTA_MT"] / check["OFFICIAL_TONNES_MT"],
    0.0,
)

# Keep sanity check
check_display = check.copy()
numeric_cols = ["OFFICIAL_TONNES_MT", "CALC_TONNES_MT", "DELTA_MT", "DELTA_%"]
check_display[numeric_cols] = check_display[numeric_cols].round(3)

c1, c2 = st.columns([1.35, 1.0])

with c1:
    st.dataframe(check_display, use_container_width=True, hide_index=True)
    download_csv(check_display, "sanity_check_official_vs_calc.csv", "Download sanity check CSV")

with c2:
    calc_plot = calc.copy()
    calc_plot["CALC_TONNES_MT"] = calc_plot["CALC_TONNES_MT"].round(3)

    barplot(
        calc_plot[calc_plot["DESTINATION_ROLLUP"].isin(["filter", "rockfill", "waste_nag", "waste_pag"])],
        x="DESTINATION_ROLLUP",
        y="CALC_TONNES_MT",
        title="Calculated Tonnes (Mt) by Official Rollup",
        color=None,
    )

st.divider()

# -----------------------------
# Tabs: Case Base + Q1..Q10
# -----------------------------
tabs = st.tabs(["Base Case Q3.2025", "Q1", "Q2", "Q3", "Q4", "Q5", "Q6", "Q7", "Q8", "Q9", "Q10"])

# ---- Case Base ----
with tabs[0]:
    st.markdown("## Base Case")
    st.caption("Volume & tonnes by normalized DESTINATION bins (inside current reserves pit).")

    base = tabulate(df, ["DESTINATION_NORM"])
    st.dataframe(format_professional_table(base), use_container_width=True, hide_index=True)
    download_csv(base, "case_base_destination_norm.csv", "Download Case Base (CSV)")
    barplot(base, x="DESTINATION_NORM", y="TONNES_MT", title="Base Case — Tonnes (Mt) by DESTINATION_NORM")

# ---- Q1 ----
with tabs[1]:
    st.markdown("## Q1 — LITHO (mdi, gbdi, mf, cv)")
    q1 = df[df["LITHO"].isin(["mdi", "gbdi", "mf", "cv"])] if "LITHO" in df.columns else df
    t1 = tabulate(q1, ["LITHO"])
    st.dataframe(format_professional_table(t1), use_container_width=True, hide_index=True)
    download_csv(t1, "q1_litho.csv", "Download Q1 (CSV)")
    barplot(t1, x="LITHO", y="TONNES_MT", title="Q1 — Tonnes (Mt) by LITHO")

# ---- Q2 ----
with tabs[2]:
    st.markdown("## Q2 — mdi by WEATHERING")
    q2 = df[df["LITHO"].eq("mdi")]
    t2 = tabulate(q2, ["LITHO", "WEATHERING"])
    st.dataframe(format_professional_table(t2), use_container_width=True, hide_index=True)
    download_csv(t2, "q2_mdi_weathering.csv", "Download Q2 (CSV)")
    barplot(t2, x="WEATHERING", y="TONNES_MT", title="Q2 — mdi Tonnes (Mt) by WEATHERING")

# ---- Q3 ----
with tabs[3]:
    st.markdown("## Q3 — gbdi by WEATHERING")
    q3 = df[df["LITHO"].eq("gbdi")]
    t3 = tabulate(q3, ["LITHO", "WEATHERING"])
    st.dataframe(format_professional_table(t3), use_container_width=True, hide_index=True)
    download_csv(t3, "q3_gbdi_weathering.csv", "Download Q3 (CSV)")
    barplot(t3, x="WEATHERING", y="TONNES_MT", title="Q3 — gbdi Tonnes (Mt) by WEATHERING")

# ---- Q4 ----
with tabs[4]:
    st.markdown("## Q4 — (cv, mf)")
    q4 = df[df["LITHO"].isin(["cv", "mf"])]
    t4 = tabulate(q4, ["LITHO"])
    st.dataframe(format_professional_table(t4), use_container_width=True, hide_index=True)
    download_csv(t4, "q4_cv_mf.csv", "Download Q4 (CSV)")
    barplot(t4, x="LITHO", y="TONNES_MT", title="Q4 — Tonnes (Mt) by LITHO")

# ---- Q5 ----
with tabs[5]:
    st.markdown("## Q5 — mdi by NPR_TYPE (PAG vs NPAG) [CO3 ignored]")
    q5 = df[df["LITHO"].eq("mdi")]
    t5 = tabulate(q5, ["LITHO", "NPR_TYPE"])
    st.dataframe(format_professional_table(t5), use_container_width=True, hide_index=True)
    download_csv(t5, "q5_mdi_npr_type.csv", "Download Q5 (CSV)")
    barplot(t5, x="NPR_TYPE", y="TONNES_MT", title="Q5 — mdi Tonnes (Mt) by NPR_TYPE")

# ---- Q6 ----
with tabs[6]:
    st.markdown("## Q6 — gbdi by NPR_TYPE (PAG vs NPAG) [CO3 ignored]")
    q6 = df[df["LITHO"].eq("gbdi")]
    t6 = tabulate(q6, ["LITHO", "NPR_TYPE"])
    st.dataframe(format_professional_table(t6), use_container_width=True, hide_index=True)
    download_csv(t6, "q6_gbdi_npr_type.csv", "Download Q6 (CSV)")
    barplot(t6, x="NPR_TYPE", y="TONNES_MT", title="Q6 — gbdi Tonnes (Mt) by NPR_TYPE")

# ---- Q7 ----
with tabs[7]:
    st.markdown("## Q7 — mdi NPAG split by CO3")
    q7 = df[(df["LITHO"].eq("mdi")) & (df["NPR_TYPE"].eq("NPAG"))]
    t7 = tabulate(q7, ["LITHO", "NPR_TYPE", "CO3_BIN"])
    st.dataframe(format_professional_table(t7), use_container_width=True, hide_index=True)
    download_csv(t7, "q7_mdi_npag_co3.csv", "Download Q7 (CSV)")
    barplot(t7, x="CO3_BIN", y="TONNES_MT", title="Q7 — mdi NPAG Tonnes (Mt) by CO3 bin")

# ---- Q8 ----
with tabs[8]:
    st.markdown("## Q8 — gbdi NPAG split by CO3")
    q8 = df[(df["LITHO"].eq("gbdi")) & (df["NPR_TYPE"].eq("NPAG"))]
    t8 = tabulate(q8, ["LITHO", "NPR_TYPE", "CO3_BIN"])
    st.dataframe(format_professional_table(t8), use_container_width=True, hide_index=True)
    download_csv(t8, "q8_gbdi_npag_co3.csv", "Download Q8 (CSV)")
    barplot(t8, x="CO3_BIN", y="TONNES_MT", title="Q8 — gbdi NPAG Tonnes (Mt) by CO3 bin")

# ---- Q9 ----
with tabs[9]:
    st.markdown("## Q9 — mdi NPAG (aw_1, aw_2) split by CO3")
    q9 = df[
        (df["LITHO"].eq("mdi")) &
        (df["NPR_TYPE"].eq("NPAG")) &
        (df["WEATHERING"].isin(["aw_1", "aw_2"]))
    ]
    t9 = tabulate(q9, ["LITHO", "NPR_TYPE", "WEATHERING", "CO3_BIN"])
    st.dataframe(format_professional_table(t9), use_container_width=True, hide_index=True)
    download_csv(t9, "q9_mdi_npag_aw12_co3.csv", "Download Q9 (CSV)")
    barplot(t9, x="WEATHERING", y="TONNES_MT", title="Q9 — mdi NPAG Tonnes (Mt) by WEATHERING", color="CO3_BIN")

# ---- Q10 ----
with tabs[10]:
    st.markdown("## Q10 — gbdi NPAG (aw_1, aw_2) split by CO3")
    q10 = df[
        (df["LITHO"].eq("gbdi")) &
        (df["NPR_TYPE"].eq("NPAG")) &
        (df["WEATHERING"].isin(["aw_1", "aw_2"]))
    ]
    t10 = tabulate(q10, ["LITHO", "NPR_TYPE", "WEATHERING", "CO3_BIN"])
    st.dataframe(format_professional_table(t10), use_container_width=True, hide_index=True)
    download_csv(t10, "q10_gbdi_npag_aw12_co3.csv", "Download Q10 (CSV)")
    barplot(t10, x="WEATHERING", y="TONNES_MT", title="Q10 — gbdi NPAG Tonnes (Mt) by WEATHERING", color="CO3_BIN")