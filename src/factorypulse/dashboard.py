"""Streamlit dashboard: machine health read from the lake.

Run with ``docker compose up -d streamlit`` and open http://localhost:8501.
It reads the lake through ``factorypulse.lake`` and computes through the pure
functions in ``factorypulse.analytics``; this module only renders, so no Spark
process takes part.
"""

from __future__ import annotations

from typing import Optional

import plotly.express as px
import streamlit as st

from factorypulse import analytics, lake

TREND_SENSORS = ("temperature", "vibration")


def render(root: Optional[str] = None) -> None:
    """Render the dashboard from the lake at ``root`` (default: MinIO)."""
    st.set_page_config(page_title="FactoryPulse", layout="wide")
    st.title("FactoryPulse machine health")
    try:
        machines = lake.read_table(analytics.DIM_MACHINE, root=root)
        hourly = lake.read_table(analytics.MRT_MACHINE_HOURLY, root=root)
        scores = lake.read_table(analytics.MRT_ANOMALY_SCORES, root=root)
    except (lake.LakeTableMissing, lake.LakeColumnsMissing) as unreadable:
        st.error(str(unreadable))
        return

    kpis = analytics.machine_health_kpis(machines, scores)
    for column, (label, count) in zip(st.columns(len(kpis)), kpis.items()):
        column.metric(label.title(), count)

    for sensor_type in TREND_SENSORS:
        st.subheader(f"{sensor_type.title()}, hourly average")
        trend = analytics.sensor_trend(hourly, sensor_type)
        figure = px.line(trend, x="hour_start", y=f"{sensor_type}_avg", color="machine_id")
        st.plotly_chart(figure)

    st.subheader("At-risk machines")
    st.dataframe(analytics.at_risk_machines(scores), hide_index=True)


if __name__ == "__main__":
    render()
