# FactoryPulse dashboard (ticket 09): Streamlit over the lake's Delta tables,
# read through factorypulse.lake with deltalake. A plain Python image, not the
# Spark one: the dashboard needs no JVM.
#
# The factorypulse package is not baked in: compose mounts ./src at /opt/src,
# the way the Spark jobs see it, so a dashboard edit needs no rebuild.
FROM python:3.12-slim

COPY requirements-dashboard.txt /tmp/requirements-dashboard.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-dashboard.txt

ENV PYTHONPATH=/opt/src \
    PYTHONUNBUFFERED=1

WORKDIR /opt
EXPOSE 8501
# --browser.gatherUsageStats=false: Streamlit would otherwise send usage
# events to its servers; this local pipeline sends nothing anywhere.
ENTRYPOINT ["streamlit", "run", "/opt/src/factorypulse/dashboard.py", \
    "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", \
    "--browser.gatherUsageStats=false"]
