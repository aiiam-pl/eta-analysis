import os
import pandas as pd
import streamlit as st

@st.cache_data(show_spinner=False)
def load_csv(path_or_buffer):
    return pd.read_csv(path_or_buffer)

@st.cache_data(show_spinner=False)
def load_eta_events():
    """Load eta_events.csv from working dir or /mnt/data. Returns (df or None, source_path or error_details)."""
    tried = []
    for p in ["eta_events.csv", os.path.join("/mnt/data", "eta_events.csv")]:
        try:
            df = pd.read_csv(p)
            return df, p
        except Exception as e:
            tried.append(f"{p} -> {e}")
    return None, "\n".join(tried)