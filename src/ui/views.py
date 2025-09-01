# src/ui/views.py
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt
import pydeck as pdk

from src.events import (
    load_eta_events_for_transport,
    load_telematics_events_for_transport,
    find_unloading_time,
)
from src.eta_chart import eta_timeline_chart
from src.helpers import _wkb_point_to_lonlat


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
def _telematics_points_df_single(telematics_events_df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects the per-transport telematics DF returned by load_telematics_events_for_transport,
    which already normalizes to columns: created_at (UTC), type, lat, lon (optional).
    Returns rows with valid lat/lon only.
    """
    if not isinstance(telematics_events_df, pd.DataFrame) or telematics_events_df.empty:
        return pd.DataFrame(columns=["lat", "lon", "type", "created_at"])

    gdf = telematics_events_df.copy()

    # If lat/lon are not present but position_coordinates is, try to parse (safety net)
    if ("lat" not in gdf.columns or "lon" not in gdf.columns) and "position_coordinates" in gdf.columns:
        coords = gdf["position_coordinates"].astype(str).str.strip().str.strip("()").str.split(",", n=1, expand=True)
        if isinstance(coords, pd.DataFrame) and coords.shape[1] == 2:
            gdf["lat"] = pd.to_numeric(coords[0], errors="coerce")
            gdf["lon"] = pd.to_numeric(coords[1], errors="coerce")

    gdf = gdf.dropna(subset=["lat", "lon"]).copy()

    # Ensure expected columns exist
    if "type" not in gdf.columns:
        gdf["type"] = "event"
    if "created_at" in gdf.columns:
        gdf["created_at"] = pd.to_datetime(gdf["created_at"], errors="coerce", utc=True)

    return gdf

def summary_panel(trow) -> None:
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        c1.subheader(f"Loading: {trow['LOADING_LOCALITY']}, {trow['LOADING_COUNTRY']}")
        c2.subheader(f"Unloading: {trow['UNLOADING_LOCALITY']}, {trow['UNLOADING_COUNTRY']}")
        c1.metric("Distance (km)", int(trow["DISTANCE"]))
        c2.metric("Duration (min)", int(trow["DURATION"]))
        c3.metric("Avg diff v2 (min)", trow["AVERAGE_ETA_DIFF_V2"])
        c4.metric("Avg diff v3 (min)", trow["AVERAGE_ETA_DIFF_V3"])

def _render_single_transport_telematics_map(trow: pd.DataFrame, telematics_events_df: pd.DataFrame, title: str):
    gdf = _telematics_points_df_single(telematics_events_df)
    if gdf.empty:
        st.info("No telematic events with coordinates for this transport.")
        return

    if "created_at" in gdf.columns:
        gdf = gdf.sort_values("created_at")

    # Colors per 'type'
    types = sorted(gdf["type"].astype(str).fillna("unknown").unique())
    palette = [[31,119,180],[255,127,14],[44,160,44],[214,39,40],
               [148,103,189],[140,86,75],[227,119,194],[127,127,127],
               [188,189,34],[23,190,207]]
    cmap = {t: palette[i % len(palette)] for i, t in enumerate(types)}
    colors = gdf["type"].map(cmap).tolist()
    gdf[["color_r","color_g","color_b"]] = pd.DataFrame(colors, index=gdf.index)

    # Decode loading/unloading WKB
    load_lonlat = _wkb_point_to_lonlat(trow.get("LOADING_COORDINATES"))
    unload_lonlat = _wkb_point_to_lonlat(trow.get("UNLOADING_COORDINATES"))

    # Build concentric ring features: 5 km and 20 km
    rings = []
    if load_lonlat is not None:
        rings.append({
            "label": "Loading 5km",
            "lon": float(load_lonlat[0]),
            "lat": float(load_lonlat[1]),
            "radius_m": 5_000,
            "line_color": [34, 139, 34, 220],  # green-ish
        })
        rings.append({
            "label": "Loading 20km",
            "lon": float(load_lonlat[0]),
            "lat": float(load_lonlat[1]),
            "radius_m": 20_000,
            "line_color": [34, 139, 34, 160],
        })

    if unload_lonlat is not None:
        rings.append({
            "label": "Unloading 5km",
            "lon": float(unload_lonlat[0]),
            "lat": float(unload_lonlat[1]),
            "radius_m": 5_000,
            "line_color": [220, 20, 60, 220],  # crimson
        })
        rings.append({
            "label": "Unloading 20km",
            "lon": float(unload_lonlat[0]),
            "lat": float(unload_lonlat[1]),
            "radius_m": 20_000,
            "line_color": [220, 20, 60, 160],
        })

    rings_df = pd.DataFrame(rings) if rings else pd.DataFrame(columns=["label", "lon", "lat", "radius_m", "line_color"])

    # Circle outlines (stroked only, bold, empty fill)
    lu_rings_layer = pdk.Layer(
        "ScatterplotLayer",
        data=rings_df,
        get_position="[lon, lat]",
        get_radius="radius_m",  # meters
        stroked=True,
        filled=False,  # empty circles
        get_line_color="line_color",
        get_line_width=8,  # bold outline (pixels)
        line_width_min_pixels=4,
        line_width_max_pixels=12,
        pickable=True,
    )

    # View
    center_lat = float(gdf["lat"].median())
    center_lon = float(gdf["lon"].median())
    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lon, zoom=6, pitch=0, bearing=0)

    # Layers
    tile_layer = pdk.Layer(
        "TileLayer",
        data="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
        minZoom=0, maxZoom=19, tileSize=256,
    )

    points_layer = pdk.Layer(
        "ScatterplotLayer",
        data=gdf,
        get_position="[lon, lat]",
        get_fill_color="[color_r, color_g, color_b, 190]",
        get_radius=120,
        radius_min_pixels=2,
        radius_max_pixels=24,
        pickable=True,
        stroked=True,
        get_line_color=[0, 0, 0],
        line_width_min_pixels=0.5,
    )

    path_data = [{"path": gdf[["lon", "lat"]].values.tolist()}]
    path_layer = pdk.Layer(
        "PathLayer",
        data=path_data,
        get_path="path",
        get_width=4,
        get_color=[50, 50, 200, 160],
        width_min_pixels=2,
    )

    tooltip = {
        "html": "<b>{type}</b><br/>lat: {lat}<br/>lon: {lon}<br/>{created_at}",
        "style": {"backgroundColor":"rgba(0,0,0,0.85)","color":"white"}
    }
    # A separate tooltip for loading/unloading (label)
    lu_tooltip = {
        "html": "<b>{label}</b><br/>lat: {lat}<br/>lon: {lon}",
        "style": {"backgroundColor":"rgba(0,0,0,0.85)","color":"white"}
    }

    st.subheader(title)
    st.pydeck_chart(
        pdk.Deck(
            layers=[tile_layer, path_layer, points_layer, lu_rings_layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_provider=None,
            map_style=None,
        ),
        use_container_width=True,
    )
    st.caption("Basemap © OpenStreetMap contributors")

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

            summary_panel(selected_row)

            st.subheader("ETA timeline")
            chart = eta_timeline_chart(events_df, telematics_events_df, reached_unloading_at, height=420)
            st.altair_chart(chart, use_container_width=True)

            if isinstance(telematics_events_df, pd.DataFrame) and not telematics_events_df.empty:
                _render_single_transport_telematics_map(
                    selected_row,
                    telematics_events_df,
                    title=f"Telematics events for transport {selected_id}"
                )

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