# src/ui/filters.py
import pandas as pd
import streamlit as st

def apply_quick_filters(df: pd.DataFrame) -> pd.DataFrame:
    fdf = df.copy()
    cols = st.columns([1, 1, 2, 2])

    # LOADING_COUNTRY
    if "LOADING_COUNTRY" in fdf.columns:
        with cols[0]:
            sel = st.multiselect("LOADING_COUNTRY", sorted(fdf["LOADING_COUNTRY"].dropna().astype(str).unique()), [])
            if sel:
                fdf = fdf[fdf["LOADING_COUNTRY"].astype(str).isin(sel)]

    # UNLOADING_COUNTRY
    if "UNLOADING_COUNTRY" in fdf.columns:
        with cols[1]:
            sel = st.multiselect("UNLOADING_COUNTRY", sorted(fdf["UNLOADING_COUNTRY"].dropna().astype(str).unique()), [])
            if sel:
                fdf = fdf[fdf["UNLOADING_COUNTRY"].astype(str).isin(sel)]

    # DISTANCE
    if "DISTANCE" in fdf.columns and pd.api.types.is_numeric_dtype(fdf["DISTANCE"]):
        with cols[2]:
            dmin, dmax = int(fdf["DISTANCE"].min()), int(fdf["DISTANCE"].max())
            fmin, fmax = st.slider("DISTANCE range", dmin, dmax, (dmin, dmax))
            fdf = fdf[(fdf["DISTANCE"] >= fmin) & (fdf["DISTANCE"] <= fmax)]

    # STARTED_AT day & month
    if "STARTED_AT" in fdf.columns:
        with cols[3]:
            fdf["STARTED_AT"] = pd.to_datetime(fdf["STARTED_AT"], errors="coerce")

            # Day filter
            available_days = sorted(fdf["STARTED_AT"].dropna().dt.normalize().unique(), reverse=True)
            selected_days = st.multiselect(
                "STARTED_AT days",
                options=available_days,
                format_func=lambda x: x.strftime("%Y-%m-%d"),
            )
            if selected_days:
                fdf = fdf[fdf["STARTED_AT"].dt.normalize().isin(selected_days)]

            # Month filter
            available_months = sorted(fdf["STARTED_AT"].dropna().dt.to_period("M").unique(), reverse=True)
            selected_months = st.multiselect(
                "STARTED_AT months",
                options=available_months,
                format_func=lambda x: x.strftime("%Y-%m"),
            )
            if selected_months:
                fdf = fdf[fdf["STARTED_AT"].dt.to_period("M").isin(selected_months)]

    return fdf