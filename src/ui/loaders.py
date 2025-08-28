# src/ui/loaders.py
import pandas as pd
import streamlit as st
from src.data import load_csv

def load_transports_ui() -> pd.DataFrame | None:
    df = None
    source = st.sidebar.radio("Data source", ["Local file", "Upload CSV"], index=0)

    if source == "Local file":
        try:
            df = load_csv("local_data/transports.csv")
            st.sidebar.success("Loaded transports.csv")
        except Exception as e:
            st.sidebar.error(f"Could not load transports.csv\n\n{e}")
    else:
        uploaded = st.sidebar.file_uploader("Upload transports CSV", type=["csv"], key="transports_uploader")
        if uploaded:
            df = load_csv(uploaded)
            st.sidebar.success("Uploaded transports CSV loaded")

    return df

def load_eta_ui() -> pd.DataFrame | None:
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
            st.session_state.events_all = events_all
            st.success(f"Loaded eta_events.csv from: {events_source}")
            st.caption(f"Rows: {len(events_all):,} | Cols: {events_all.shape[1]:,}")
            with st.expander("Preview ETA events (first 50 rows)"):
                st.dataframe(events_all.head(50), use_container_width=True, hide_index=True)
        else:
            st.warning("ETA events CSV not loaded. Charts will be unavailable until this loads.\n\n" + str(events_source))

        return events_all

def load_telematics_ui() -> pd.DataFrame | None:
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
            st.session_state.telematic_all = telem_all  # keep the same key used elsewhere
            st.success(f"Loaded telematic_events.csv from: {telem_source}")
            st.caption(f"Rows: {len(telem_all):,} | Cols: {telem_all.shape[1]:,}")
            with st.expander("Preview telematic_events (first 50 rows)"):
                st.dataframe(telem_all.head(50), use_container_width=True, hide_index=True)
        else:
            st.warning("Telematic events CSV not loaded. Related charts will be unavailable until this loads.\n\n" + str(telem_source))

        return telem_all