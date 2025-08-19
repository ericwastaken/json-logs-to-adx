import os, sys, json, requests
from typing import Optional, List
import click

from utils.adx_cli_auth import get_adx_token
from utils.stdin_utils import read_text_maybe_from_stdin

@click.command(help="ADX inline ingest. Supports a single JSON object or NDJSON (newline-delimited JSON). If --json is omitted or set to '-', reads from STDIN.")
@click.option("cluster_host", "--cluster-host", required=True, help="Engine host, e.g. kvc-xxxxx.region.kusto.windows.net")
@click.option("db", "--db", required=True, help="Database name, e.g. TestDB")
@click.option("table", "--table", required=True, help="Table name (quotes handled), e.g. docker-logs")
@click.option("mapping", "--mapping", required=True, help="JSON ingestion mapping name")
@click.option("json_str", "--json", required=False, help="Single JSON object or NDJSON as a string; if omitted or '-', read from STDIN")
@click.option("ndjson", "--ndjson/--no-ndjson", default=False, help="Treat input as NDJSON (one JSON object per line) and ingest in batches")
@click.option("batch_size", "--batch-size", default=100, show_default=True, type=int, help="Batch size (number of lines per ingest) when --ndjson is used")
def main(cluster_host: str, db: str, table: str, mapping: str, json_str: Optional[str], ndjson: bool, batch_size: int):
    # Resolve input source: CLI option or STDIN (reusable util)
    source = read_text_maybe_from_stdin(
        json_str,
        empty_stdin_error="ERROR: No --json provided and no data on STDIN. Provide --json or pipe JSON into this command.\n",
        dash_alias=True,
        timeout_sec=0.05,
    )
    if source is None:
        sys.stderr.write("ERROR: Empty input for JSON.\n")
        sys.exit(2)
    source = source.strip()
    if not source:
        sys.stderr.write("ERROR: Empty input for JSON.\n")
        sys.exit(2)

    # Acquire ADX token via Azure CLI helper (verbose, no secrets printed)
    try:
        token = get_adx_token(verbose=True)
    except Exception as e:
        sys.stderr.write(f"ERROR: Failed to acquire ADX token via Azure CLI: {e}\n")
        sys.exit(2)

    # Helper to send a batch of compacted JSON objects using multijson
    def send_batch(compacted_json_lines: List[str]) -> None:
        if not compacted_json_lines:
            return
        # Join with newlines (multijson supports concatenated objects; newlines are fine)
        data_blob = "\n".join(compacted_json_lines)
        csl = (
            f".ingest inline into table ['{table}'] "
            f"with (format='multijson', ingestionMappingReference='{mapping}') <| {data_blob}"
        )
        url = f"https://{cluster_host}/v1/rest/mgmt"
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        payload = {"db": db, "csl": csl}
        r = requests.post(url, headers=headers, json=payload, timeout=60)
        if r.status_code != 200:
            raise RuntimeError(f"INGEST FAILED {r.status_code}: {r.text}")

    if ndjson:
        # Process as NDJSON (one JSON object per line), batching
        lines = source.splitlines()
        compacted: List[str] = []
        bad_lines = 0
        total_sent = 0
        for idx, line in enumerate(lines, start=1):
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
                if not isinstance(obj, dict):
                    raise ValueError("Top-level must be a JSON object")
                compacted.append(json.dumps(obj, separators=(",", ":")))
            except Exception as e:
                bad_lines += 1
                sys.stderr.write(f"WARN: Skipping malformed JSON on line {idx}: {e}\n")
                continue
            if len(compacted) >= max(1, batch_size):
                try:
                    send_batch(compacted)
                    total_sent += len(compacted)
                finally:
                    compacted = []
        # Flush remaining
        if compacted:
            send_batch(compacted)
            total_sent += len(compacted)
        print(f"Ingest OK (NDJSON). Sent {total_sent} records. Skipped {bad_lines} malformed lines.")
        return

    # Otherwise, treat as a single JSON object
    try:
        obj = json.loads(source)
        if isinstance(obj, (list, str, int, float, bool)) or obj is None:
            raise ValueError("Top-level must be a JSON object")
        json_line = json.dumps(obj, separators=(",", ":"))
    except Exception as e:
        sys.stderr.write(f"ERROR: Invalid JSON input: {e}\n")
        sys.exit(2)

    # Kusto control command (quotes table in case it contains dashes)
    csl = (
        f".ingest inline into table ['{table}'] "
        f"with (format='multijson', ingestionMappingReference='{mapping}') <| {json_line}"
    )

    url = f"https://{cluster_host}/v1/rest/mgmt"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    payload = {"db": db, "csl": csl}

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        if r.status_code != 200:
            sys.stderr.write(f"INGEST FAILED {r.status_code}: {r.text}\n")
            sys.exit(1)
        print("Ingest OK")
    except requests.RequestException as e:
        sys.stderr.write(f"REQUEST ERROR: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
