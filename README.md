# ADX Docker Logs Ingestor

This repository contains a lightweight setup to run Python scripts that ingest data into Azure Data Explorer (ADX). It 
also includes Docker tooling to keep a ready-to-run container alive while you execute scripts via docker compose exec, 
plus convenience wrappers (x-*.sh) for common tasks.

Important: The README documents both native (Python venv) usage and Docker-based usage, and calls out all available x-*.sh 
wrappers.

## What’s here
- Dockerfile based on `ericwastakenondocker/network-multitool` that pre-installs Python deps from `scripts/requirements.txt`.
- docker-compose.yml that mounts `./scripts` into the container at `/scripts` and exposes a tiny HTTP server (from the base image) to keep the container running.
- Python scripts under `./scripts` (e.g., `ingest_inline.py`) that talk to ADX.
- Convenience shell wrappers in the repo root (`x-*.sh`) for common Docker workflows.

## Script wrappers (x-*.sh)
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

---

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
    --cluster-host "<your-engine-host>.kusto.windows.net" \
    --db "<DB>" \
    --table "<Table>" \
    --mapping "<MappingName>" \
    --json '{"hello":"world"}'
  ```
  
---

## Running scripts via docker compose exec
This is the recommended approach for a consistent environment. The container remains alive via the base image’s web server and mounts `./scripts` at `/scripts`.

1) Build and start the container
- Using wrappers: `./x-up.sh` start (build if needed) or `./x-force-build-and-up.sh` force rebuild and start
- Or directly: `docker compose up -d --build`

Optional: Verify it’s up: `curl -f http://localhost:8080/ && echo OK`

2) Execute adx-ingester inside the running container
- Show help:
  ```bash
  docker compose exec -i adx-ingester python3 ingest_inline.py --help
  ```

- Example (replace placeholders):
  ```bash
  docker compose exec adx-ingester \
    python3 ingest_inline.py \
    --cluster-host "<your-engine-host>.kusto.windows.net" \
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
  --cluster-host kvc-j2p78vw7fzrdt1jcw9.southcentralus.kusto.windows.net \
  --db TestDB \
  --table docker-logs \
  --mapping adocker_logs_json_mapping \
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

---

## Additional context (for log ingestion scenarios)
If you’re adapting these helpers for a full Docker logs ingestion pipeline to ADX:
- Normalize log lines (parse JSON if possible, otherwise wrap as {"message": "..."}).
- Extract a timestamp into a top-level `timestamp` field when present; otherwise the scripts will use current UTC.
- Batch by records/bytes/time and send NDJSON to ADX streaming ingestion endpoints, or use control commands like shown in `ingest_inline.py` for small inline tests.
- Ensure your ADX table and JSON ingestion mapping exist (or are created) and that your identity has the appropriate roles (e.g., Ingestor).

Refer to the directory ./adx-helpers in this repo for more information.

