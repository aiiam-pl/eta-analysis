# src/ui/views.py
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

from src.events import (
    load_eta_events_for_transport,
    load_telematics_events_for_transport,
    find_unloading_time,
)
from src.eta_chart import eta_timeline_chart

def _first_df(*candidates):
    for c in candidates:
        if isinstance(c, pd.DataFrame):
            return c
    return None

def _pick_table_columns(table_df: pd.DataFrame) -> pd.DataFrame:
    preferred_cols = [
        "created_at", "calculated_eta", "eta_relative_hr",
        "event_type", "source", "message"
    ]
    cols = [c for c in preferred_cols if c in table_df.columns]
    cols += [c for c in table_df.columns if c not in cols]
    return table_df[cols]

def render_transport_view_or_distribution(fdf: pd.DataFrame, events_all: pd.DataFrame | None, telem_all: pd.DataFrame | None):
    st.subheader("Select a transport")
    st.caption("Click a row to select it. Selection persists across filters until the row disappears.")

    event = st.dataframe(
        fdf,
        use_container_width=True,
        hide_index=True,
        on_select="rerun",
        selection_mode="single-row",
    )
    selected_positions = getattr(event, "selection", None)
    selected_positions = selected_positions.rows if selected_positions else []

    if len(selected_positions) == 1:
        pos = selected_positions[0]
        try:
            selected_row = fdf.iloc[pos]
            selected_id = selected_row["ID"] if "ID" in fdf.columns else None
            if selected_id is None:
                st.info("Selected a row, but column 'ID' is missing.")
                return

            st.success(f"Selected transport ID: **{selected_id}**")

            # Filter events for this transport
            events_src = _first_df(events_all, st.session_state.get('events_all'))
            telem_src = _first_df(telem_all, st.session_state.get('telematic_all'))

            events_df = load_eta_events_for_transport(str(selected_id), events_all=events_src)
            telematics_events_df = load_telematics_events_for_transport(str(selected_id), telem_all=telem_src)
            if events_df is None:
                return

            if events_df.empty:
                st.info("No ETA events found for this transport.")
                return

            reached_unloading_at = find_unloading_time(selected_row)
            st.subheader("ETA timeline")
            chart = eta_timeline_chart(events_df, telematics_events_df, reached_unloading_at, height=420)
            st.altair_chart(chart, use_container_width=True)

            # ETA events table
            try:
                table_df = _pick_table_columns(events_df.copy())
                if "created_at" in table_df.columns:
                    table_df = table_df.sort_values("created_at")
                st.subheader("ETA events")
                st.dataframe(table_df, use_container_width=True, hide_index=True)
            except Exception as e:
                st.warning(f"Could not render ETA events table: {e}")

        except Exception as e:
            st.warning(f"Could not read selection: {e}")

    else:
        _render_distribution_view(fdf)

def _render_distribution_view(fdf: pd.DataFrame):
    st.subheader("Transports distribution by ETA difference")

    eta_cols_all = [
        "AVERAGE_ETA_DIFF_V2", "AVERAGE_ETA_DIFF_9H_V2",
        "AVERAGE_ETA_DIFF_V3", "AVERAGE_ETA_DIFF_9H_V3",
        "RELATIVE_ETA_DIFF_V2", "RELATIVE_ETA_DIFF_9H_V2",
        "RELATIVE_ETA_DIFF_V3", "RELATIVE_ETA_DIFF_9H_V3",
    ]
    present_eta_cols = [c for c in eta_cols_all if c in fdf.columns]

    if not present_eta_cols:
        st.info("No ETA difference columns found in the dataset.")
        return

    selected_metric = st.selectbox("Metric", present_eta_cols, index=0)

    c1, c2 = st.columns([2, 1])
    with c1:
        # NOTE: UI says "hours" but original slider used large values; keep consistent:
        bin_width = st.slider("Bin width (units of the selected metric)", min_value=60.0, max_value=1440.0, value=60.0, step=60.0)
    with c2:
        show_table = st.checkbox("Show binned table", value=False)

    plot_df = fdf.copy()
    plot_df[selected_metric] = pd.to_numeric(plot_df[selected_metric], errors="coerce")
    plot_df = plot_df.dropna(subset=[selected_metric])

    st.caption(f"Transports counted: {len(plot_df):,} (filtered). Metric: **{selected_metric}**")

    if plot_df.empty:
        st.info("No data points for the selected metric in the current filters.")
        return

    # Histogram
    chart = (
        alt.Chart(plot_df)
        .mark_bar()
        .encode(
            x=alt.X(
                f"{selected_metric}:Q",
                bin=alt.Bin(step=bin_width),
                title=f"{selected_metric}",
            ),
            y=alt.Y("count():Q", title="Number of transports"),
            tooltip=[
                alt.Tooltip(f"{selected_metric}:Q", bin=alt.Bin(step=bin_width), title="Metric (bin)"),
                alt.Tooltip("count():Q", title="# transports"),
            ],
        )
        .properties(height=380)
    )
    st.altair_chart(chart, use_container_width=True)

    if show_table:
        s = plot_df[selected_metric]
        lo = float(s.min()); hi = float(s.max())
        if hi == lo:
            hi = lo + bin_width
        edges = list(np.arange(lo, hi + bin_width, bin_width))
        cats = pd.cut(s, bins=edges, include_lowest=True)
        binned = (
            pd.DataFrame({selected_metric: cats})
            .value_counts()
            .reset_index(name="count")
            .rename(columns={0: "bin"})
            .sort_values("bin")
        )
        st.dataframe(binned, use_container_width=True, hide_index=True)