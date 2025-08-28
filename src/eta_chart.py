import pandas as pd
import altair as alt
import streamlit as st

def _empty_chart():
    return alt.Chart(pd.DataFrame({"x": []})).mark_rule(), alt.Chart(pd.DataFrame({"x": []})).mark_text()

def _midnight_layers(events_df: pd.DataFrame):
    if events_df.empty or "created_at" not in events_df.columns:
        return (
            alt.Chart(pd.DataFrame({"x": []})).mark_rule(),
            alt.Chart(pd.DataFrame({"x": []})).mark_text(),
        )

    min_time = pd.to_datetime(events_df["created_at"]).min().normalize()
    max_time = pd.to_datetime(events_df["created_at"]).max().normalize() + pd.Timedelta(days=1)
    midnights = pd.date_range(start=min_time, end=max_time, freq="D")

    midnight_df = pd.DataFrame({
        "midnight": midnights,
        "day_label": midnights.strftime("%b %d"),
    })

    # Yellow dashed vertical rules
    rules = (
        alt.Chart(midnight_df)
        .mark_rule(strokeDash=[4, 2], color="yellow")
        .encode(x="midnight:T")
    )

    # Yellow text labels
    labels = (
        alt.Chart(midnight_df)
        .mark_text(
            align="left",
            baseline="bottom",
            dy=-4,
            dx=2,
            color="yellow",     # force yellow
            fontWeight="bold",
        )
        .encode(
            x="midnight:T",
            y=alt.value(1),     # pin to top of chart
            text="day_label"
        )
    )

    return rules, labels

def _telematics_layers(telematics_events_df: pd.DataFrame):
    """
    Expects a pre-filtered telematics DataFrame (e.g., one transport already).
    Returns (rules_layer, labels_layer) to overlay on the ETA chart.
    """
    if telematics_events_df is None or telematics_events_df.empty:
        return _empty_chart()

    required = {"type", "created_at"}
    if not required.issubset(set(telematics_events_df.columns)):
        return _empty_chart()

    df = telematics_events_df.copy()
    # Parse datetimes (handle 'Z'); keep tz-aware to avoid unintended shifts
    df["created_at"] = pd.to_datetime(df["created_at"], errors="coerce", utc=True)
    df = df.dropna(subset=["created_at"])

    # Parse coordinates to lat/lon if present (format "(lat,lon)")
    if "position_coordinates" in df.columns:
        coords = df["position_coordinates"].astype(str).str.strip("()").str.split(",", n=1, expand=True)
        if coords.shape[1] == 2:
            with pd.option_context("mode.chained_assignment", None):
                df["lat"] = pd.to_numeric(coords[0], errors="coerce")
                df["lon"] = pd.to_numeric(coords[1], errors="coerce")

    if df.empty:
        return _empty_chart()

    # Color per TYPE
    color_domain = sorted(df["type"].astype(str).unique())
    color_range = [
        "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
        "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"
    ][:len(color_domain)]

    # Vertical lines
    rules = (
        alt.Chart(df)
        .mark_rule(strokeWidth=2, opacity=0.85)
        .encode(
            x=alt.X("created_at:T", title=None),
            color=alt.Color("type:N", scale=alt.Scale(domain=color_domain, range=color_range), legend=None),
            tooltip=[
                alt.Tooltip("type:N", title="Event"),
                alt.Tooltip("created_at:T", title="When"),
                alt.Tooltip("lat:Q", format=".5f"),
                alt.Tooltip("lon:Q", format=".5f"),
            ],
        )
    )

    # Labels (small, rotated)
    labels = (
        alt.Chart(df)
        .mark_text(angle=270, dy=-6, dx=-4, fontSize=10, opacity=0.9)
        .encode(
            x="created_at:T",
            y=alt.value(1),
            text="type:N",
            color=alt.Color("type:N", scale=alt.Scale(domain=color_domain, range=color_range), legend=None),
        )
    )

    return rules, labels

import pandas as pd
import altair as alt

def eta_timeline_chart(
    events_df: pd.DataFrame,
    telematics_events_df: pd.DataFrame,   # prefiltered to this transport (or empty)
    reached_unloading_at,
    height: int = 420
):
    # --- Copy & parse ---
    events_df = events_df.copy()
    events_df["created_at"] = pd.to_datetime(events_df["created_at"], errors="coerce", utc=True)
    events_df["calculated_eta"] = pd.to_datetime(events_df["calculated_eta"], errors="coerce", utc=True)
    unload_ts = pd.to_datetime(reached_unloading_at, errors="coerce", utc=True)

    # --- Derived fields ---
    events_df["eta_relative_hr"] = (events_df["calculated_eta"] - unload_ts) / pd.Timedelta(hours=1)

    def _derive_version(row):
        # Prefer explicit VERSION column if present
        if "VERSION" in events_df.columns and pd.notna(row.get("VERSION")):
            v = str(row["VERSION"]).lower()
            if "3" in v or "v3" in v:
                return "v3"
            if "2" in v or "v2" in v:
                return "v2"
        # Heuristic from 'source'
        s = str(row.get("source", "")).lower()
        if "v3" in s: return "v3"
        if "v2" in s: return "v2"
        return "unknown"

    if "version" not in events_df.columns:
        events_df["version"] = events_df.apply(_derive_version, axis=1)
    else:
        events_df["version"] = (
            events_df["version"].astype(str).str.lower()
            .replace({"2": "v2", "v2": "v2", "3": "v3", "v3": "v3"})
        )

    # --- Clean / sort ---
    events_df = events_df.dropna(subset=["created_at", "eta_relative_hr"]).sort_values("created_at")
    if events_df.empty:
        return alt.Chart(pd.DataFrame({"x": [], "y": []})).mark_point().properties(height=height)

    # --- Base chart (ETA line + points) ---
    base = alt.Chart(events_df).encode(
        x=alt.X("created_at:T", title="Event time", axis=alt.Axis(format="%H:%M")),
        y=alt.Y("eta_relative_hr:Q", title="ETA difference (hours)", axis=alt.Axis(format="+.1f")),
        color=alt.Color("version:N", title="ETA Version"),
        tooltip=[
            alt.Tooltip("created_at:T", title="Event time", format="%d.%m %H:%M"),
            alt.Tooltip("calculated_eta:T", title="Calculated ETA", format="%d.%m %H:%M"),
            alt.Tooltip("eta_relative_hr:Q", title="ETA - Unloading (h)", format=".2f"),
            alt.Tooltip("version:N", title="Version"),
        ],
    )
    line = base.mark_line(opacity=0.8)
    points = base.mark_circle(size=80, opacity=0.95, stroke='white', strokeWidth=1)

    # --- Zero line + label (unloading moment -> y=0) ---
    unload_rule = (
        alt.Chart(pd.DataFrame({"y": [0]}))
        .mark_rule(color="red", strokeDash=[6, 4])
        .encode(y="y:Q")
    )

    unload_label_df = pd.DataFrame({
        "x": [events_df["created_at"].min()],
        "y": [0],
        "label": [unload_ts.strftime("%Y-%m-%d %H:%M %Z") if pd.notna(unload_ts) else "unloading"],
    })
    unload_label = (
        alt.Chart(unload_label_df)
        .mark_text(align="left", baseline="bottom", dx=4, dy=-4, color="red", fontWeight="bold")
        .encode(x="x:T", y="y:Q", text="label")
    )

    # --- Midnight guides (assumes you have this helper) ---
    midnight_rules, midnight_labels = _midnight_layers(events_df)
    # Keep them subtle
    midnight_rules = midnight_rules.mark_rule(opacity=0.45, color="yellow")
    midnight_labels = midnight_labels.mark_text(color="yellow")

    # --- Telematics layers (assumes pre-filtered df + your helper) ---
    # If your _telematics_layers returns (rules, labels) that already have encodings,
    # just reuse them and pin labels outside the y-scale so they don’t alter y domain.
    tele_rules, tele_labels = _telematics_layers(telematics_events_df)
    tele_rules = tele_rules.mark_rule(opacity=0.45, strokeWidth=2)
    tele_labels = tele_labels.encode(y=alt.value(6)).mark_text(angle=270, dy=0, dx=-4, fontSize=10, opacity=0.9)

    # --- Layering order controls visibility: last layers are drawn on top ---
    final_chart = alt.layer(
        midnight_rules,      # bottom
        midnight_labels,
        tele_rules,
        tele_labels,
        unload_rule,
        unload_label,
        line,
        points               # top
    ).resolve_scale(
        color="independent"  # avoid color-scale collisions between ETA version vs telematics TYPE
    ).properties(height=height)

    return final_chart