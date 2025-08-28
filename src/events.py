import pandas as pd
import streamlit as st

def _pick_first_existing_column(frame: pd.DataFrame, candidates):
    for c in candidates:
        if c in frame.columns:
            return c
    return None

def find_unloading_time(row: pd.Series):
    candidates = ["REACHED_UNLOADING_AT"]
    for c in candidates:
        if c in row.index and pd.notna(row[c]):
            return pd.to_datetime(row[c], errors="coerce")
    return None

def load_eta_events_for_transport(selected_id: str, events_all: pd.DataFrame | None = None):
    # Prefer preloaded df from session
    events = None
    if isinstance(selected_id, (int, float)):
        selected_id = str(selected_id)

    if 'events_all' in st.session_state and isinstance(st.session_state.events_all, pd.DataFrame):
        events = st.session_state.events_all.copy()
    if events_all is not None and isinstance(events_all, pd.DataFrame):
        events = events_all.copy()

    if events is None:
        return None  # caller will handle missing

    # Find the transport-id column
    col = _pick_first_existing_column(events, ["TRANSPORT_ID"])
    if col is None:
        st.warning("eta_events.csv does not contain a transport identifier column.")
        return None

    # Filter
    events = events[events[col].astype(str) == str(selected_id)].copy()
    if events.empty:
        return pd.DataFrame()

    # Normalize expected columns
    rename_map = {}
    if "created_at" not in events.columns:
        alt_created = _pick_first_existing_column(events, ["CREATED_AT"])
        if alt_created:
            rename_map[alt_created] = "created_at"
    if "calculated_eta" not in events.columns:
        alt_eta = _pick_first_existing_column(events, ["CALCULATED_ETA"])
        if alt_eta:
            rename_map[alt_eta] = "calculated_eta"

    for _col in ["created_at", "calculated_eta"]:
        if _col in events.columns:
            # Coerce to pandas datetime and set/convert to UTC (tz-aware)
            events[_col] = pd.to_datetime(events[_col], errors="coerce", utc=True)

    if rename_map:
        events = events.rename(columns=rename_map)

    return events


def load_telematics_events_for_transport(selected_id: str, telem_all: pd.DataFrame | None = None):
    """
    Returns a telematics events DataFrame filtered to a single transport.
    Prefers a preloaded df from st.session_state.telematic_all, but can accept an override via telem_all.
    Normalizes common column names and types:
      - created_at (datetime, UTC)  <- CREATEDAT / CREATED_AT
      - type (str)                  <- TYPE
      - position_coordinates (str)  <- POSITIONCOORDINATES
      - lat, lon (floats) extracted from position_coordinates "(lat,lon)" if present
    """
    # Normalize the selected_id
    if isinstance(selected_id, (int, float)):
        selected_id = str(selected_id)

    # Source selection (session first, then override if provided)
    events = None
    if "telematic_all" in st.session_state and isinstance(st.session_state.telematic_all, pd.DataFrame):
        events = st.session_state.telematic_all.copy()
    if telem_all is not None and isinstance(telem_all, pd.DataFrame):
        events = telem_all.copy()

    if events is None:
        return None  # caller handles missing

    # Find the transport-id column
    col = _pick_first_existing_column(events, ["TRANSPORTID", "TRANSPORT_ID"])
    if col is None:
        st.warning("telematic_events.csv does not contain a transport identifier column.")
        return None

    # Filter to this transport
    events = events[events[col].astype(str) == str(selected_id)].copy()
    if events.empty:
        return pd.DataFrame()

    # Normalize expected columns (names)
    rename_map = {}

    # created_at
    if "created_at" not in events.columns:
        alt_created = _pick_first_existing_column(events, ["CREATEDAT", "CREATED_AT"])
        if alt_created:
            rename_map[alt_created] = "created_at"

    # type
    if "type" not in events.columns:
        alt_type = _pick_first_existing_column(events, ["TYPE"])
        if alt_type:
            rename_map[alt_type] = "type"

    # position_coordinates
    if "position_coordinates" not in events.columns:
        alt_pos = _pick_first_existing_column(events, ["POSITIONCOORDINATES", "POSITION_COORDINATES"])
        if alt_pos:
            rename_map[alt_pos] = "position_coordinates"

    if rename_map:
        events = events.rename(columns=rename_map)

    # Coerce datetimes and set tz to UTC
    if "created_at" in events.columns:
        events["created_at"] = pd.to_datetime(events["created_at"], errors="coerce", utc=True)

    # Extract lat/lon from "(lat,lon)" if available
    if "position_coordinates" in events.columns:
        coords = events["position_coordinates"].astype(str).str.strip().str.strip("()").str.split(",", n=1, expand=True)
        if isinstance(coords, pd.DataFrame) and coords.shape[1] == 2:
            with pd.option_context("mode.chained_assignment", None):
                events["lat"] = pd.to_numeric(coords[0], errors="coerce")
                events["lon"] = pd.to_numeric(coords[1], errors="coerce")

    return events