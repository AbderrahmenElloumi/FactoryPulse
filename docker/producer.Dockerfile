# FactoryPulse producer — the ticket-02 simulator wired into Kafka + MinIO.
FROM python:3.11-slim
WORKDIR /opt/app

COPY requirements-producer.txt ./
RUN python -m pip install --no-cache-dir -r requirements-producer.txt

COPY pyproject.toml ./
COPY src ./src
RUN python -m pip install --no-cache-dir -e .

ENTRYPOINT ["python", "-m", "factorypulse.producer"]