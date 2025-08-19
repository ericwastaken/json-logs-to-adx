import os, sys, json, requests
from typing import Optional
import click

from utils.adx_cli_auth import get_adx_token
from utils.stdin_utils import read_text_maybe_from_stdin

@click.command(help="ADX inline ingest (single JSON object). If --json is omitted or set to '-', reads the JSON from STDIN.")
@click.option("cluster_host", "--cluster-host", required=True, help="Engine host, e.g. kvc-xxxxx.region.kusto.windows.net")
@click.option("db", "--db", required=True, help="Database name, e.g. TestDB")
@click.option("table", "--table", required=True, help="Table name (quotes handled), e.g. docker-logs")
@click.option("mapping", "--mapping", required=True, help="JSON ingestion mapping name")
@click.option("json_str", "--json", required=False, help="Single JSON object as a string; if omitted or '-', read from STDIN")
def main(cluster_host: str, db: str, table: str, mapping: str, json_str: Optional[str]):
    # Resolve JSON source: CLI option or STDIN (reusable util)
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

    # Validate & compact the JSON line (ensures it's a single object)
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
