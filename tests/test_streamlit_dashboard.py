"""Streamlit dashboard (ticket 09): machine health read from the lake.

The machine-health computations are pure functions over frames, tested
directly. The app itself runs under Streamlit's AppTest against a fixture
lake written to a local directory, so no MinIO and no Spark take part.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
from deltalake import write_deltalake
from streamlit.testing.v1 import AppTest

from factorypulse import analytics
from factorypulse.contract import STATUSES

ROOT = Path(__file__).resolve().parent.parent
NOMINAL, WARNING, CRITICAL = STATUSES
H0 = pd.Timestamp("2026-10-01T00:00:00Z")
H1 = pd.Timestamp("2026-10-01T01:00:00Z")


def _score(machine_id, window_start, sensor_type, z, machine_status, site_id="S-01"):
    return {
        "machine_id": machine_id,
        "site_id": site_id,
        "window_start": window_start,
        "window_end": window_start + pd.Timedelta(hours=1),
        "sensor_type": sensor_type,
        "value": 50.0,
        "baseline_mean": 40.0,
        "baseline_stddev": 5.0,
        "baseline_count": 6,
        "z_score": z,
        "sensor_status": machine_status,
        "machine_status": machine_status,
    }


def _scores(*rows):
    return pd.DataFrame(list(rows), columns=list(analytics.ANOMALY_SCORE_COLUMNS))


def _machines(*machine_ids):
    return pd.DataFrame(
        [
            {
                "machine_id": machine_id,
                "site_id": "S-01",
                "first_seen_at": H0,
                "last_seen_at": H1,
                "reading_count": 8,
                "sensor_type_count": 4,
            }
            for machine_id in machine_ids
        ],
        columns=list(analytics.MACHINE_DIM_COLUMNS),
    )


def _hourly(*rows):
    """``rows`` are (machine_id, hour_start, temperature_avg, vibration_avg)."""
    return pd.DataFrame(
        [
            {
                "machine_hour_key": f"{machine_id}|{hour.isoformat()}",
                "machine_id": machine_id,
                "site_id": "S-01",
                "hour_start": hour,
                "reading_count": 4,
                "nominal_count": 4,
                "warning_count": 0,
                "critical_count": 0,
                "temperature_avg": temperature,
                "temperature_max": temperature + 1.0,
                "vibration_avg": vibration,
                "vibration_max": vibration + 0.1,
                "pressure_avg": 30.0,
                "pressure_max": 31.0,
                "humidity_avg": 45.0,
                "humidity_max": 46.0,
            }
            for machine_id, hour, temperature, vibration in rows
        ],
        columns=list(analytics.MACHINE_HOURLY_COLUMNS),
    )


# --- pure machine-health functions ------------------------------------------


def test_latest_machine_status_takes_each_machines_latest_window():
    scores = _scores(
        _score("M-001", H0, "temperature", 4.0, CRITICAL),
        _score("M-001", H1, "temperature", 0.5, NOMINAL),
        _score("M-001", H1, "vibration", -0.8, NOMINAL),
        _score("M-002", H0, "temperature", 2.5, WARNING),
    )

    latest = analytics.latest_machine_status(scores)

    assert list(latest["machine_id"]) == ["M-001", "M-002"]
    assert list(latest["window_start"]) == [H1, H0]
    assert list(latest["machine_status"]) == [NOMINAL, WARNING]
    # The worst sensor's distance from its baseline, whatever its sign.
    assert list(latest["max_abs_z_score"]) == [0.8, 2.5]


def test_at_risk_machines_lists_non_nominal_latest_status_worst_first():
    scores = _scores(
        _score("M-001", H0, "temperature", 4.0, CRITICAL),  # recovered since
        _score("M-001", H1, "temperature", 0.1, NOMINAL),
        _score("M-002", H1, "vibration", 2.5, WARNING),
        _score("M-003", H1, "temperature", -4.0, CRITICAL),
        _score("M-004", H1, "vibration", 2.6, WARNING),
    )

    at_risk = analytics.at_risk_machines(scores)

    assert list(at_risk["machine_id"]) == ["M-003", "M-002", "M-004"]
    assert list(at_risk["machine_status"]) == [CRITICAL, WARNING, WARNING]


def test_machine_health_kpis_count_machines_by_latest_status():
    machines = _machines("M-001", "M-002", "M-003", "M-004")
    scores = _scores(
        _score("M-001", H1, "temperature", 0.1, NOMINAL),
        _score("M-002", H1, "vibration", 2.5, WARNING),
        _score("M-003", H0, "temperature", 0.2, NOMINAL),
        _score("M-003", H1, "temperature", 4.0, CRITICAL),
    )

    kpis = analytics.machine_health_kpis(machines, scores)

    assert kpis == {
        "machines": 4,
        NOMINAL: 1,
        WARNING: 1,
        CRITICAL: 1,
        "unscored": 1,
    }


def test_no_scores_means_no_machine_at_risk_and_every_machine_unscored():
    machines = _machines("M-001", "M-002")
    scores = _scores()

    assert analytics.at_risk_machines(scores).empty
    kpis = analytics.machine_health_kpis(machines, scores)
    assert kpis["unscored"] == 2
    assert [kpis[status] for status in STATUSES] == [0, 0, 0]


def test_a_machine_with_no_scored_window_is_unscored_not_nominal():
    # The anomaly job writes a null z_score, status nominal, for every window
    # without a usable baseline.
    machines = _machines("M-001", "M-002")
    scores = _scores(
        _score("M-001", H0, "temperature", None, NOMINAL),
        _score("M-001", H1, "temperature", None, NOMINAL),
        _score("M-002", H1, "temperature", 0.3, NOMINAL),
    )

    assert list(analytics.latest_machine_status(scores)["machine_id"]) == ["M-002"]
    assert analytics.machine_health_kpis(machines, scores) == {
        "machines": 2,
        NOMINAL: 1,
        WARNING: 0,
        CRITICAL: 0,
        "unscored": 1,
    }


def test_an_unscored_latest_window_keeps_the_last_scored_status():
    machines = _machines("M-002")
    scores = _scores(
        _score("M-002", H0, "temperature", 4.0, CRITICAL),
        _score("M-002", H1, "temperature", None, NOMINAL),
        _score("M-002", H1, "vibration", None, NOMINAL),
    )

    latest = analytics.latest_machine_status(scores)

    assert list(latest["window_start"]) == [H0]
    assert list(latest["machine_status"]) == [CRITICAL]
    assert list(analytics.at_risk_machines(scores)["machine_id"]) == ["M-002"]
    assert analytics.machine_health_kpis(machines, scores)["unscored"] == 0


def test_a_window_with_one_scored_sensor_is_a_scored_window():
    scores = _scores(
        _score("M-001", H0, "temperature", 0.1, NOMINAL),
        _score("M-001", H1, "temperature", None, WARNING),
        _score("M-001", H1, "vibration", -2.5, WARNING),
    )

    latest = analytics.latest_machine_status(scores)

    assert list(latest["window_start"]) == [H1]
    assert list(latest["machine_status"]) == [WARNING]
    assert list(latest["max_abs_z_score"]) == [2.5]


def test_a_status_outside_the_contract_vocabulary_is_rejected():
    scores = _scores(_score("M-001", H0, "temperature", 9.0, "on_fire"))

    with pytest.raises(ValueError, match="on_fire"):
        analytics.latest_machine_status(scores)


def test_sensor_trend_is_one_hourly_series_per_machine_in_time_order():
    hourly = _hourly(
        ("M-002", H0, 70.0, 0.3),
        ("M-001", H1, 61.0, 0.2),
        ("M-001", H0, 60.0, 0.1),
    )

    trend = analytics.sensor_trend(hourly, "vibration")

    assert list(trend.columns) == ["machine_id", "hour_start", "vibration_avg", "vibration_max"]
    assert list(trend["machine_id"]) == ["M-001", "M-001", "M-002"]
    assert list(trend["hour_start"]) == [H0, H1, H0]
    assert list(trend["vibration_avg"]) == [0.1, 0.2, 0.3]


def test_sensor_trend_rejects_a_sensor_type_outside_the_contract():
    with pytest.raises(ValueError, match="noise"):
        analytics.sensor_trend(_hourly(), "noise")


# --- the app, against a fixture lake ----------------------------------------


def _app(root):
    from factorypulse import dashboard

    dashboard.render(root)


def _fixture_lake(root, *, skip=()):
    tables = {
        analytics.DIM_MACHINE: _machines("M-001", "M-002"),
        analytics.MRT_MACHINE_HOURLY: _hourly(
            ("M-001", H0, 60.0, 0.1),
            ("M-001", H1, 61.0, 0.2),
            ("M-002", H0, 70.0, 0.3),
            ("M-002", H1, 95.0, 0.9),
        ),
        analytics.MRT_ANOMALY_SCORES: _scores(
            _score("M-001", H1, "temperature", 0.2, NOMINAL),
            _score("M-002", H1, "temperature", 4.2, CRITICAL),
        ),
    }
    for name, frame in tables.items():
        if name not in skip:
            write_deltalake(str(root / name), frame)


def _run(root):
    app = AppTest.from_function(_app, args=(str(root),), default_timeout=30)
    return app.run()


def test_app_shows_kpis_trends_and_at_risk_machines_from_the_lake(tmp_path):
    _fixture_lake(tmp_path)

    app = _run(tmp_path)

    assert not app.exception
    assert not app.error
    metrics = {metric.label: metric.value for metric in app.metric}
    assert metrics["Machines"] == "2"
    assert metrics[CRITICAL.title()] == "1"
    assert metrics[NOMINAL.title()] == "1"
    assert len(app.get("plotly_chart")) == 2
    (at_risk,) = app.dataframe
    assert list(at_risk.value["machine_id"]) == ["M-002"]
    assert list(at_risk.value["machine_status"]) == [CRITICAL]


@pytest.mark.parametrize(
    "missing",
    [analytics.DIM_MACHINE, analytics.MRT_MACHINE_HOURLY, analytics.MRT_ANOMALY_SCORES],
)
def test_app_names_a_table_that_has_not_been_built_instead_of_an_empty_chart(
    tmp_path, missing
):
    _fixture_lake(tmp_path, skip=(missing,))

    app = _run(tmp_path)

    assert not app.exception
    (error,) = app.error
    assert missing in error.value
    assert not app.get("plotly_chart")
    assert not app.dataframe


def test_app_names_a_built_table_that_lacks_a_declared_column(tmp_path):
    _fixture_lake(tmp_path, skip=(analytics.MRT_ANOMALY_SCORES,))
    stored = _scores(_score("M-001", H1, "temperature", 0.2, NOMINAL))
    write_deltalake(
        str(tmp_path / analytics.MRT_ANOMALY_SCORES), stored.drop(columns="z_score")
    )

    app = _run(tmp_path)

    assert not app.exception
    (error,) = app.error
    assert "z_score" in error.value


def test_dashboard_imports_no_spark():
    code = (
        "import sys, factorypulse.dashboard; "
        "sys.exit(any(m.split('.')[0] == 'pyspark' for m in sys.modules))"
    )
    assert subprocess.run([sys.executable, "-c", code]).returncode == 0


def test_dashboard_spells_no_status_string():
    source = (ROOT / "src" / "factorypulse" / "dashboard.py").read_text(encoding="utf-8")

    for status in STATUSES:
        assert not re.search(rf"\b{status}\b", source, re.IGNORECASE), status


# --- one command: the streamlit compose service -----------------------------


def _compose_service(name):
    text = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    match = re.search(rf"^  {name}:\n((?:    .*\n|\n)+)", text, re.MULTILINE)
    assert match, f"compose.yaml has no {name} service"
    return match.group(1)


def test_streamlit_service_serves_the_app_from_its_own_light_image():
    service = _compose_service("streamlit")

    assert "dockerfile: docker/dashboard.Dockerfile" in service
    assert "./src:/opt/src" in service
    assert "MINIO_ENDPOINT: minio:9000" in service
    assert "MINIO_BUCKET: factorypulse" in service
    assert "minio: { condition: service_healthy }" in service
    assert '"127.0.0.1:8501:8501"' in service
    # Brought up by a plain `docker compose up -d streamlit`: no profile.
    assert "profiles:" not in service


def test_dashboard_image_is_python_with_pinned_readers_not_spark():
    dockerfile = (ROOT / "docker" / "dashboard.Dockerfile").read_text(encoding="utf-8")
    requirements = (ROOT / "requirements-dashboard.txt").read_text(encoding="utf-8")

    assert re.search(r"^FROM python:3\.12", dockerfile, re.MULTILINE)
    assert "requirements-dashboard.txt" in dockerfile
    assert "factorypulse/dashboard.py" in dockerfile
    assert "--browser.gatherUsageStats=false" in dockerfile
    for package in ("streamlit", "plotly", "deltalake", "pyarrow"):
        assert re.search(rf"^{package}==\d", requirements, re.MULTILINE), package
    assert not re.search(r"spark", requirements, re.IGNORECASE)
