#!/usr/bin/env bash
# =============================================================================
# Docker Service Logs Ingestion Script
# =============================================================================
# This script fetches logs from Docker Swarm services and ingests them into 
# Azure Data Explorer (ADX). It processes logs with timestamps and JSON content,
# normalizing them into a structured NDJSON format before ingestion.
#
# Note: The pattern here is suitable for logs in the thousands of entries, maybe
# tens of thousands. Once you start getting into more logs (longer time periods on
# a very busy service) the `docker service logs` command seems to hang especially
# on the jq parsing!
#
# Features:
# - Fetches logs from all Docker Swarm services
# - Supports Docker-style duration formats (e.g., 5m, 2h, 1d, 1w)
# - Parses and normalizes log timestamps
# - Extracts container and host information
# - Handles JSON and non-JSON log content
# - Ingests data into ADX using specified mappings
#
# Usage:
#   ./z-docker-ingest-service-logs.sh <since-duration> <cluster-host>
#   Example: ./z-docker-ingest-service-logs.sh 4h kvc-some-cluster.kusto.windows.net
#
# Parameters:
#   since-duration: Time range for log collection (e.g., 5m, 2h, 1d, 1w)
#   cluster-host: ADX cluster hostname
#
# Dependencies:
#   - Docker with Swarm mode enabled
#   - jq for JSON processing
#   - json-logs-to-adx container environment with ADX ingestion capabilities
# =============================================================================
set -euo pipefail

if [[ $# -ne 2 ]]; then
    echo "Usage: $0 <since-duration> (e.g., 5m, 2h, 1d) <cluster-host> (e.g., kvc-xxxxxx.kusto.windows.net) " >&2
    exit 2
fi
SINCE="$1"
CLUSTER_HOST="$2"

# Optional sanity check (simple duration like 5m/2h/1d/1w). Remove if you pass RFC3339 times.
if ! [[ "$SINCE" =~ ^[0-9]+[smhdw]$ ]]; then
    echo "Error: since-duration must look like 5m, 2h, 1d, or 1w (simple form)." >&2
    exit 2
fi

# Remove https:// prefix if present
CLUSTER_HOST="${CLUSTER_HOST#https://}"

# Ensure the ingestion container is up
./x-force-build-and-up.sh

# Ensure output dir and truncate the NDJSON file
mkdir -p ./out
: > ./out/docker-logs.ndjson

# Build service list from Swarm
readarray -t SERVICES < <(docker service ls --format '{{.Name}}')

# jq program to parse lines like:
# 2025-08-19T21:20:04.777164448Z service.1.id@host | { ...json... }
# - trims fractional seconds to whole seconds ("...Z") for ADX friendliness
JQ_FILTER='
    select(test("^\\d{4}-\\d{2}-\\d{2}T") and test("\\|"))
    | capture("^(?<timestamp>\\S+)\\s+(?<pre>[^|]+)\\|\\s*(?<log>.*)$")
    | .pre |= gsub("\\s+$"; "")
    | .pre as $pre
    | ($pre | capture("^(?<container>[^@]+)@(?<host>\\S+)$")?) as $m
    | {
        timestamp: (.timestamp | sub("\\..*Z$"; "Z")),
        docker_container: ($m.container // $pre),
        host: ($m.host // null),
        log: (.log | fromjson? // .)
      }
'

# Fetch logs for each service and append to the NDJSON file
for svc in "${SERVICES[@]}"; do
    echo "Fetching logs for ${svc} (since ${SINCE})..." >&2
    docker service logs "$svc" --since "$SINCE" --timestamps 2>&1 \
        | jq -R -c "$JQ_FILTER" >> ./out/docker-logs.ndjson || true
done

# Ingest if we have any lines
if [[ -s ./out/docker-logs.ndjson ]]; then
    echo "Ingesting $(wc -l < ./out/docker-logs.ndjson) lines to '${CLUSTER_HOST}'..." >&2
    cat ./out/docker-logs.ndjson \
        | ./x-exec.sh python3 ingest_inline.py \
            --cluster-host $CLUSTER_HOST \
            --db DevLogs \
            --table docker-logs-json \
            --mapping docker_logs_json_mapping \
            --ndjson \
            --batch-size 1000
    echo "Done." >&2
else
    echo "No logs matched; nothing to ingest." >&2
fi
