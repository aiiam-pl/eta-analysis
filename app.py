# app.py

import streamlit as st

from src.ui.loaders import load_transports_ui, load_eta_ui, load_telematics_ui
from src.ui.filters import apply_quick_filters
from src.ui.views import render_transport_view_or_distribution

st.set_page_config(page_title="Transports Viewer", layout="wide")
st.title("🚚 Transports.csv Viewer")

# --- Load Transports ---
df = load_transports_ui()
if df is None:
    st.info("Load a CSV to begin.")
    st.stop()

if "ID" not in df.columns:
    st.error("This feature requires an 'ID' column in transports.csv.")
    st.stop()

# --- Load ETA & Telematics (sidebar) ---
events_all = load_eta_ui()
telem_all = load_telematics_ui()

# --- Quick filters ---
fdf = apply_quick_filters(df)

# --- Main view (single transport vs distribution) ---
render_transport_view_or_distribution(fdf, events_all, telem_all)