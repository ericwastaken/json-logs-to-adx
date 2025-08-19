# JSON Logs to ADX Ingester

This repository contains a lightweight setup to ingest JSON logs into Azure Data Explorer (ADX) using Python scripts. It 
also includes a Docker Compose setup to execute the scripts fully from inside a container.

Important: The README documents both native (Python venv) usage and Docker-based usage.

**In a rush?** Jump to [Ingestion Patterns](#ingestion-patterns).

## What’s here

- Dockerfile based on `ericwastakenondocker/network-multitool` that pre-installs Python deps from `scripts/requirements.txt`.
- docker-compose.yml that mounts `./scripts` into the container at `/scripts` and exposes a tiny HTTP server (from the base image) to keep the container running.
- Python scripts under `./scripts` (e.g., `ingest_inline.py`) that talk to ADX. Scripts can be run natively or via Docker.
- Convenience shell wrappers (`x-*.sh`) for common Docker workflows.

### Script wrappers

These wrappers simplify common docker compose operations.
- Service name in compose: `adx-ingester`
- Container name: `adx-ingester`

Docker Wrappers:
- x-up.sh — Start the compose stack in the background (build if needed).
- x-force-build-and-up.sh — Force a rebuild and start in the background.
- x-shell.sh — Open an interactive bash shell inside the running container.
- x-exec.sh — Execute a command inside the running container (stdin supported). Example: `./x-exec.sh python3 ingest_inline.py --help`.
- x-build.sh — Build the Docker image (supports multi-platform via buildx; reads docker-build-manifest.env).
- x-deploy-dockerhub.sh — Tag and push the image to Docker Hub (multi-platform or single platform; reads docker-build-manifest.env).
- x-export.sh — Save the local image to ./exported/adx-ingester.docker.
- x-import.sh — Load the image from ./exported/adx-ingester.docker.

Note: Some wrappers expect docker, compose, and optionally buildx. Ensure you’re logged into Docker for push operations.

## Prepare ADX and your database and table

Please refer to the [ADX Preparation README](adx-helpers/README.md).

## Running scripts via docker compose
This is the recommended approach for a consistent environment. The container remains alive via the base image’s web 
server and mounts `./scripts` at `/scripts`.

1) Build and start the container
- Using wrappers: `./x-up.sh` start (build if needed) or `./x-force-build-and-up.sh` force rebuild and start
- Or directly: `docker compose up -d --build`

Optional: Verify it’s up: `curl -f http://localhost:8080/ && echo OK`

2) Execute adx-ingester inside the running container
- Show help:
  ```bash
  docker compose exec -i adx-ingester python3 ingest_inline.py --help
  ```

- Example:
  ```bash
  docker compose exec adx-ingester \
    python3 ingest_inline.py \
    --cluster-host "<your-cluster-host>.kusto.windows.net" \
    --db "<DB>" \
    --table "<Table>" \
    --mapping "<MappingName>" \
    --json '{"hello":"world"}'
  ```

- Using wrappers:
  `./x-exec.sh python3 ingest_inline.py --help`
  `./x-shell.sh` to get an interactive bash shell in the container

  ```bash
  ./x-exec.sh python3 ingest_inline.py \
  --cluster-host <your-cluster-host>.kusto.windows.net \
  --db <DB> \
  --table <Table> \
  --mapping <MappingName> \
  --json '{"timestamp":"2025-08-16T15:00:00Z","ping":"inline-ok-from-script"}'
  ```

3) Environment variables
- Option A: Put them under `environment:` in docker-compose.yml.
- Option B: Pass at runtime:
  ```bash
  AZURE_TENANT_ID=... AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=... \
  docker compose exec scripts python3 ingest_inline.py --help
  ```

4) Notes about Azure CLI in container
- The Python scripts use the Azure CLI token flow, which is provided by the base image.
- For quick tests, get a shell inside the container and run `az login` or other Azure CLI commands.

5) Optional: Docker socket
- If any script needs to interact with Docker, uncomment the `/var/run/docker.sock` volume mapping in docker-compose.yml.

## Running scripts natively inside a Python venv

Use this if you prefer not to use Docker. Note, this requires Python 3.12+ and the Azure CLI.

1) Create and activate a venv

- macOS/Linux:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

2) Install requirements

- Upgrade pip and install:
  ```bash
  pip install --upgrade pip
  pip install -r scripts/requirements.txt
  ```

3) Ensure Azure CLI is available (for ingest_inline.py)

- This repo’s `scripts/utils/adx_cli_auth.py` acquires tokens via the Azure CLI (`az`).
- Azure sign in: `az login`

4) Run a helper script

- Show help: `python scripts/ingest_inline.py --help`

- Example (replace placeholders):
  ```bash
  python scripts/ingest_inline.py \
    --cluster-host "<your-cluster-host>.kusto.windows.net" \
    --db "<DB>" \
    --table "<Table>" \
    --mapping "<MappingName>" \
    --json '{"hello":"world"}'
  ```
## Ingestion Patterns

Below are common ways to use scripts/ingest_inline.py to send data to ADX. Replace placeholders like `<your-cluster-host>`, 
`<DB>`, `<Table>`, and `<MappingName>` with your values.

**Note:** The examples below use the Docker Compose setup. However, just remove `./x-exec.sh` to run the scripts natively.

Before ingesting, ensure your ADX table and JSON ingestion mapping exist (or are created) and that your identity has the 
appropriate roles (e.g., Ingestor). Refer to the [ADX Preparation README](adx-helpers/README.md) 
for more information.

1) Single JSON object (inline)
- Sends exactly one JSON object via `--json`.
- Useful for quick connectivity tests or inserting one record.

```bash
./x-exec.sh python3 ingest_inline.py \
  --cluster-host <your-cluster-host>.kusto.windows.net \
  --db <DB> \
  --table <Table> \
  --mapping <MappingName> \
  --json '{"timestamp":"2025-08-16T15:00:00Z","ping":"inline-ok-from-script"}'
```

2) NDJSON from a file (pipe via STDIN)
- Reads newline-delimited JSON (one object per line) from STDIN.
- Use `--ndjson` so the tool batches and ingests multiple lines.

```bash
cat ./samples/sample.ndjson | ./x-exec.sh python3 ingest_inline.py \
  --cluster-host <your-cluster-host>.kusto.windows.net \
  --db <DB> \
  --table <Table> \
  --mapping <MappingName> \
  --ndjson
```

3) Stream Docker logs -> JSON -> NDJSON ingest (useful for scenarios where your docker logs are not in JSON format).
- Streams recent container logs, converts lines to JSON with jq, and ingests as NDJSON.
- Adjust docker logs options as needed (e.g., `--since`, container name).

```bash
docker logs --since 5m --timestamps adx-ingester \
  | jq -R -c 'split(" ") as $f | {timestamp: ($f[0] | sub("\\..*Z$"; "Z")), log: ($f[1:] | join(" "))}' \
  | ./x-exec.sh python3 ingest_inline.py \
  --cluster-host <your-cluster-host>.kusto.windows.net \
  --db <DB> \
  --table <Table> \
  --mapping <MappingName> \
  --ndjson
```

Arguments used in the examples
- --cluster-host: Your ADX engine host, e.g., `<your-cluster-host>.kusto.windows.net`
- --db: Target ADX database name.
- --table: Target ADX table name. Brackets/quoting are handled in the script for names with dashes.
- --mapping: Name of an existing JSON ingestion mapping in ADX for the target table.
- --json: The JSON payload to ingest. If omitted or set to '-', the script reads from STDIN instead.
- --ndjson: Treats the input as newline-delimited JSON (one JSON object per line) and ingests in batches.
- --batch-size: When `--ndjson` is used, controls how many lines are sent per batch (default: 100).

**Notes**

- The tool compacts JSON (removes whitespace) and uses a Kusto control command with `format='multijson'` and the provided ingestionMappingReference.
- For `--ndjson`, malformed lines are skipped with warnings; a summary of sent and skipped records is printed.
- Normalize log lines (parse JSON if already in that format or otherwise wrap as `{"message": "..."}`).
- Extract a timestamp into a top-level `timestamp` field; otherwise the scripts will use current UTC.
- Ensure your ADX table and JSON ingestion mapping exist (or are created) and that your identity has the appropriate 
  roles (e.g., Ingestor). Refer to the directory ./adx-helpers in this repo for more information.

## Azure Login

The full Azure CLI is installed in the container.

[TESTED AND CONFIRMED] The scripts use the Azure CLI token flow, which is supported by the Azure ADX Free Cluster, but it generally valid for a
short term of a few hours.
- The ingest script will try to get a token from the environment and will attempt a login if needed. Watch the command 
  line output for instructions to an interactive login. The interactive login will last only a few hours.
- For quick tests, get a shell inside the container and run `az login` or other Azure CLI commands.

[UNTESTED] If you have a paid cluster, you can also setup a service principal and other methods. This flow is more suitable 
for a longer term. In this case, you pass `AZURE_TENANT_ID=...`, `AZURE_CLIENT_ID=...`, `AZURE_CLIENT_SECRET=` to the 
scripts via the environment variable `AZURE_ACCESS_TOKEN`.