"""FactoryPulse shared Python components.

The sensor-event contract and its validator live here — the single seam
consumed by every stage of the pipeline (simulator, Spark ingestion, dbt
quality checks, anomaly scoring, dashboard).
"""

__version__ = "1.0.0"