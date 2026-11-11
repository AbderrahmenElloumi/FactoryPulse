# FactoryPulse orchestrator (ticket 06): Airflow plus the Docker CLI and the
# compose plugin, and nothing else. Airflow holds no compute: every task runs
# `docker compose run --rm <service>` against the host daemon (socket mounted
# in compose.yaml), so the Spark, dbt and quality dependencies stay in their
# own images instead of being copied in here.
#
# The slim image carries the standard provider (BashOperator) and defaults to
# the LocalExecutor over SQLite, which is all this pipeline needs.
FROM apache/airflow:slim-3.4.0-python3.12

# Static binaries from the official CLI image: no apt layer, no repository key.
COPY --from=docker:29.9.3-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:29.9.3-cli /usr/local/libexec/docker/cli-plugins/docker-compose /usr/local/libexec/docker/cli-plugins/docker-compose
