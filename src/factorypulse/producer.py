"""Kafka producer + MinIO snapshot for simulator events (ticket 04).

Wires the ticket-02 simulator into the lake: publishes each event to the
``sensor-events`` Kafka topic (keyed by ``event_id``, so consumers can
partition/dedup on it) and, in the same run, drops a deterministic JSONL
snapshot into MinIO that the ticket-04 batch path reprocesses — so one
generator feeds both the streaming and the batch ingestion paths.

Determinism survives to the lake: the snapshot object name derives from the
seed and count, so re-running a producer produces a byte-identical source
file, and the batch MERGE (spark/batch_ingest.py) is then idempotent by
construction.

The Kafka/MinIO clients are imported lazily so this module (and its tests)
never need them on the host — they live in the producer image only.
"""

import argparse
import io
import json
import os
import sys
from typing import Iterable

from .simulator import SimulatorConfig, generate_events

DEFAULT_TOPIC = "sensor-events"
DEFAULT_BOOTSTRAP = "localhost:9092"  # on the host; compose overrides via KAFKA_BOOTSTRAP


def events_to_records(events: Iterable[dict]) -> list[tuple[bytes, bytes]]:
    """Frame events as Kafka (key, value) byte records.

    key   = ``event_id``      → partition/dedup handle for consumers
    value = canonical JSON    → decodes to the identical event dict
    """
    return [
        (
            event["event_id"].encode("utf-8"),
            json.dumps(event, ensure_ascii=False).encode("utf-8"),
        )
        for event in events
    ]


def snapshot_object_key(seed: int, records_per_day: int) -> str:
    """Deterministic MinIO object key for the backfill snapshot."""
    return f"backfill/events-seed-{seed}-n{records_per_day}.jsonl"


def publish_to_kafka(events: Iterable[dict], bootstrap: str, topic: str) -> int:
    """Publish framed events to the topic; returns the record count."""
    from kafka import KafkaProducer  # type: ignore[import-not-found]  # producer image only

    records = events_to_records(events)
    producer = KafkaProducer(bootstrap_servers=bootstrap, acks="all", retries=3)
    try:
        for key, value in records:
            producer.send(topic, key=key, value=value)
        producer.flush()
    finally:
        producer.close()
    return len(records)


def write_snapshot(
    events: Iterable[dict],
    bucket: str,
    object_key: str,
    *,
    endpoint: str,
    access_key: str,
    secret_key: str,
    secure: bool = False,
) -> str:
    """Write a JSONL snapshot of the events into MinIO; returns the object key."""
    from minio import Minio  # type: ignore[import-not-found]  # producer image only

    client = Minio(endpoint, access_key=access_key, secret_key=secret_key, secure=secure)
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
    payload = io.BytesIO(
        b"".join(
            json.dumps(event, ensure_ascii=False).encode("utf-8") + b"\n"
            for event in events
        )
    )
    client.put_object(bucket, object_key, payload, length=payload.getbuffer().nbytes)
    return object_key


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="FactoryPulse producer: simulator events → Kafka (and MinIO snapshot)"
    )
    parser.add_argument("--records-per-day", type=int, default=SimulatorConfig.records_per_day)
    parser.add_argument("--seed", type=int, default=SimulatorConfig.seed)
    parser.add_argument("--anomaly-rate", type=float, default=SimulatorConfig.anomaly_rate)
    parser.add_argument("--spike-fraction", type=float, default=SimulatorConfig.spike_fraction)
    parser.add_argument("--sites", nargs="+", default=list(SimulatorConfig.sites))
    parser.add_argument("--machines-per-site", type=int, default=SimulatorConfig.machines_per_site)
    parser.add_argument(
        "--bootstrap", default=os.environ.get("KAFKA_BOOTSTRAP", DEFAULT_BOOTSTRAP)
    )
    parser.add_argument("--topic", default=os.environ.get("KAFKA_TOPIC", DEFAULT_TOPIC))
    parser.add_argument(
        "--no-snapshot", action="store_true", help="skip the MinIO JSONL snapshot"
    )
    args = parser.parse_args(argv)

    config = SimulatorConfig(
        seed=args.seed,
        records_per_day=args.records_per_day,
        sites=tuple(args.sites),
        machines_per_site=args.machines_per_site,
        anomaly_rate=args.anomaly_rate,
        spike_fraction=args.spike_fraction,
    )
    events = list(generate_events(config))

    sent = publish_to_kafka(events, args.bootstrap, args.topic)
    print(f"producer: sent {sent} events -> kafka {args.bootstrap} topic={args.topic}")

    if not args.no_snapshot:
        bucket = os.environ.get("MINIO_BUCKET", "factorypulse")
        key = write_snapshot(
            events,
            bucket,
            snapshot_object_key(args.seed, args.records_per_day),
            endpoint=os.environ.get("MINIO_ENDPOINT", "localhost:9000"),
            access_key=os.environ.get("MINIO_ACCESS_KEY", ""),
            secret_key=os.environ.get("MINIO_SECRET_KEY", ""),
            secure=os.environ.get("MINIO_SECURE", "false").lower() == "true",
        )
        print(f"producer: snapshot {key} -> minio bucket={bucket}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())