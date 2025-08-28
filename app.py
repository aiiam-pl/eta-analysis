# app.py
import pandas as pd
import streamlit as st
import altair as alt  # required by chart module

from src.data import load_csv, load_eta_events
from src.eta_chart import eta_timeline_chart
from src.events import load_eta_events_for_transport, load_telematics_events_for_transport,  find_unloading_time

st.set_page_config(page_title="Transports Viewer", layout="wide")
st.title("🚚 Transports.csv Viewer")

# --- Load Transports ---
df = None
source = st.sidebar.radio("Data source", ["Local file", "Upload CSV"], index=0)

# --- Load transports.csv ---
if source == "Local file":
    try:
        df = load_csv("local_data/transports.csv")  # adjust path if needed
        st.sidebar.success("Loaded transports.csv")
    except Exception as e:
        st.sidebar.error(f"Could not load transports.csv\n\n{e}")
else:
    uploaded = st.sidebar.file_uploader("Upload transports CSV", type=["csv"], key="transports_uploader")
    if uploaded:
        df = load_csv(uploaded)
        st.sidebar.success("Uploaded transports CSV loaded")

if df is None:
    st.info("Load a CSV to begin.")
    st.stop()

# Ensure ID exists
if "ID" not in df.columns:
    st.error("This feature requires an 'ID' column in transports.csv.")
    st.stop()

# --- Load ETA events (once) ---
with st.sidebar:
    st.header("ETA events source")

    eta_source_choice = st.radio(
        "Choose ETA events source:",
        ["Local file", "Upload"],
        horizontal=True,
        key="eta_source",
    )

    events_all, events_source = None, "No file selected"
    if eta_source_choice == "Local file":
        try:
            events_all = load_csv("local_data/eta_events.csv")
            events_source = "Local file"
        except Exception as e:
            events_all = None
            events_source = f"Error: {e}"
    else:
        uploaded_eta = st.file_uploader("Upload ETA events CSV", type=["csv"], key="eta_uploader")
        if uploaded_eta:
            try:
                events_all = load_csv(uploaded_eta)
                events_source = "Uploaded file"
            except Exception as e:
                events_all = None
                events_source = f"Error: {e}"

    if isinstance(events_all, pd.DataFrame):
        st.session_state.events_all = events_all  # cache in session
        st.success(f"Loaded eta_events.csv from: {events_source}")
        st.caption(f"Rows: {len(events_all):,} | Cols: {events_all.shape[1]:,}")
        with st.expander("Preview eta_events (first 50 rows)"):
            st.dataframe(events_all.head(50), use_container_width=True, hide_index=True)
    else:
        st.warning("ETA events CSV not loaded. Charts will be unavailable until this loads.\n\n" + str(events_source))

# --- Load Telematic events (once) ---
with st.sidebar:
    st.header("Telematic events source")

    telem_source_choice = st.radio(
        "Choose telematic events source:",
        ["Local file", "Upload"],
        horizontal=True,
        key="telem_source",
    )

    telem_all, telem_source = None, "No file selected"
    if telem_source_choice == "Local file":
        try:
            telem_all = load_csv("local_data/telematic_events.csv")
            telem_source = "Local file"
        except Exception as e:
            telem_all = None
            telem_source = f"Error: {e}"
    else:
        uploaded_telem = st.file_uploader("Upload telematic events CSV", type=["csv"], key="telem_uploader")
        if uploaded_telem:
            try:
                telem_all = load_csv(uploaded_telem)
                telem_source = "Uploaded file"
            except Exception as e:
                telem_all = None
                telem_source = f"Error: {e}"

    if isinstance(telem_all, pd.DataFrame):
        st.session_state.telematic_all = telem_all  # cache in session
        st.success(f"Loaded telematic_events.csv from: {telem_source}")
        st.caption(f"Rows: {len(telem_all):,} | Cols: {telem_all.shape[1]:,}")
        with st.expander("Preview telematic_events (first 50 rows)"):
            st.dataframe(telem_all.head(50), use_container_width=True, hide_index=True)
    else:
        st.warning("Telematic events CSV not loaded. Related charts will be unavailable until this loads.\n\n" + str(telem_source))

# --- Quick filters ---
fdf = df.copy()

# Create columns for horizontal layout
cols = st.columns([1, 1, 2, 2])  # adjust ratios for layout

# LOADING_COUNTRY filter
if "LOADING_COUNTRY" in df.columns:
    with cols[0]:
        sel = st.multiselect("LOADING_COUNTRY", sorted(df["LOADING_COUNTRY"].dropna().astype(str).unique()), [])
        if sel:
            fdf = fdf[fdf["LOADING_COUNTRY"].astype(str).isin(sel)]

# UNLOADING_COUNTRY filter
if "UNLOADING_COUNTRY" in df.columns:
    with cols[1]:
        sel = st.multiselect("UNLOADING_COUNTRY", sorted(df["UNLOADING_COUNTRY"].dropna().astype(str).unique()), [])
        if sel:
            fdf = fdf[fdf["UNLOADING_COUNTRY"].astype(str).isin(sel)]

# DISTANCE range filter
if "DISTANCE" in df.columns and pd.api.types.is_numeric_dtype(df["DISTANCE"]):
    with cols[2]:
        dmin, dmax = int(df["DISTANCE"].min()), int(df["DISTANCE"].max())
        fmin, fmax = st.slider("DISTANCE range", dmin, dmax, (dmin, dmax))
        fdf = fdf[(fdf["DISTANCE"] >= fmin) & (fdf["DISTANCE"] <= fmax)]

# STARTED_AT day filter
if "STARTED_AT" in df.columns:
    with cols[3]:
        fdf["STARTED_AT"] = pd.to_datetime(fdf["STARTED_AT"], errors="coerce")

        # --- Day filter ---
        available_days = sorted(
            fdf["STARTED_AT"].dropna().dt.normalize().unique(),
            reverse=True
        )
        selected_days = st.multiselect(
            "STARTED_AT days",
            options=available_days,
            format_func=lambda x: x.strftime("%Y-%m-%d"),
        )
        if selected_days:
            fdf = fdf[fdf["STARTED_AT"].dt.normalize().isin(selected_days)]

        # --- Month filter ---
        available_months = sorted(
            fdf["STARTED_AT"].dropna().dt.to_period("M").unique(),
            reverse=True
        )
        selected_months = st.multiselect(
            "STARTED_AT months",
            options=available_months,
            format_func=lambda x: x.strftime("%Y-%m"),
        )
        if selected_months:
            fdf = fdf[fdf["STARTED_AT"].dt.to_period("M").isin(selected_months)]

st.subheader("Select a transport")

# Built-in single-row selection (Streamlit >= 1.35)
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
        if selected_id is not None:
            st.success(f"Selected transport ID: **{selected_id}**")

            # Filter events for this transport (using preloaded df)
            events_df = load_eta_events_for_transport(str(selected_id), events_all=st.session_state.get('events_all'))
            telematics_events_df = load_telematics_events_for_transport(str(selected_id), telem_all=st.session_state.get('telem_all'))
            if events_df is None:
                st.stop()

            if events_df.empty:
                st.info("No ETA events found for this transport.")
            else:
                reached_unloading_at = find_unloading_time(selected_row)
                st.subheader("ETA timeline")
                chart = eta_timeline_chart(events_df, telematics_events_df, reached_unloading_at, height=420)
                st.altair_chart(chart, use_container_width=True)

                # --- ETA events table ---
                try:
                    table_df = events_df.copy()
                    # Prefer a friendly ordering if these columns exist
                    preferred_cols = [
                        "created_at", "calculated_eta", "eta_relative_hr",
                        "event_type", "source", "message"
                    ]
                    cols = [c for c in preferred_cols if c in table_df.columns]
                    cols += [c for c in table_df.columns if c not in cols]
                    table_df = table_df[cols]
                    # Sort by created_at when available
                    if "created_at" in table_df.columns:
                        table_df = table_df.sort_values("created_at")

                    st.subheader("ETA events")
                    st.dataframe(table_df, use_container_width=True, hide_index=True)

                except Exception as e:
                    st.warning(f"Could not render ETA events table: {e}")
        else:
            st.info("Selected a row, but column 'ID' is missing.")
    except Exception as e:
        st.warning(f"Could not read selection: {e}")
else:
    st.subheader("Transports distribution by ETA difference")

    # Which metrics are available in the current (filtered) dataframe?
    eta_cols_all = [
        "AVERAGE_ETA_DIFF_V2", "AVERAGE_ETA_DIFF_9H_V2",
        "AVERAGE_ETA_DIFF_V3", "AVERAGE_ETA_DIFF_9H_V3",
        "RELATIVE_ETA_DIFF_V2", "RELATIVE_ETA_DIFF_9H_V2",
        "RELATIVE_ETA_DIFF_V3", "RELATIVE_ETA_DIFF_9H_V3",
    ]
    present_eta_cols = [c for c in eta_cols_all if c in fdf.columns]

    if not present_eta_cols:
        st.info("No ETA difference columns found in the dataset.")
        st.stop()

    # Switch (selectbox) to choose the metric
    selected_metric = st.selectbox("Metric", present_eta_cols, index=0)

    # Optional controls
    c1, c2 = st.columns([2, 1])
    with c1:
        # Bin width in hours (float). Adjust if your values are minutes.
        bin_width = st.slider("Bin width (hours)", min_value=60.0, max_value=1440.0, value=60.0, step=60.0)
    with c2:
        show_table = st.checkbox("Show binned table", value=False)

    # Prepare a numeric series (drop NaNs)
    plot_df = fdf.copy()
    plot_df[selected_metric] = pd.to_numeric(plot_df[selected_metric], errors="coerce")
    plot_df = plot_df.dropna(subset=[selected_metric])

    st.caption(f"Transports counted: {len(plot_df):,} (filtered). Metric: **{selected_metric}**")

    if plot_df.empty:
        st.info("No data points for the selected metric in the current filters.")
    else:
        # Altair makes a clean histogram with transform binning
        chart = (
            alt.Chart(plot_df)
            .mark_bar()
            .encode(
                x=alt.X(
                    f"{selected_metric}:Q",
                    bin=alt.Bin(step=bin_width),
                    title=f"{selected_metric} (hours)"
                ),
                y=alt.Y("count():Q", title="Number of transports"),
                tooltip=[
                    alt.Tooltip(f"{selected_metric}:Q", bin=alt.Bin(step=bin_width), title="ETA diff (bin)"),
                    alt.Tooltip("count():Q", title="# transports"),
                ],
            )
            .properties(height=380)
        )
        st.altair_chart(chart, use_container_width=True)

        # Optional: show the binned table
        if show_table:
            # Build a small grouped table using pandas cut
            s = plot_df[selected_metric]
            # Compute bins around the observed range with given width
            lo = float(s.min());
            hi = float(s.max())
            # protect against degenerate range
            if hi == lo: hi = lo + bin_width
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
