# FactoryPulse quality gate (ticket 07): Great Expectations suites over the
# lake's Delta tables, read through factorypulse.lake with deltalake. A plain
# Python image, not the Spark one: the checks need no JVM.
#
# The factorypulse package is not baked in: compose mounts ./src at /opt/src,
# the way the Spark jobs see it, so a check edit needs no rebuild.
FROM python:3.12-slim

COPY requirements-quality.txt /tmp/requirements-quality.txt
RUN python -m pip install --no-cache-dir -r /tmp/requirements-quality.txt

# GX_ANALYTICS_ENABLED=false: Great Expectations would otherwise send usage
# events to its servers; this local pipeline sends nothing anywhere.
ENV PYTHONPATH=/opt/src \
    GX_ANALYTICS_ENABLED=false \
    PYTHONUNBUFFERED=1

WORKDIR /opt
ENTRYPOINT ["python", "-m", "factorypulse.quality"]
