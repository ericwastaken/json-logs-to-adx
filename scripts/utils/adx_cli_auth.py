#!/usr/bin/env python3
"""
ADX Azure CLI authentication helper.

Provides a verbose, safe way to acquire an Azure AD access token suitable for
Azure Data Explorer (Kusto) REST APIs using the local Azure CLI session.

- Tries to reuse an existing Azure CLI login and cached token first.
- If not logged in, initiates 'az login --use-device-code', prints the URL and
  device code for the user to complete sign-in, waits for completion, and then
  retries token acquisition.
- Never prints the access token itself.

Functions:
- get_adx_token(verbose: bool = True, timeout: int = 600) -> str

Notes:
- Requires Azure CLI (az) installed and on PATH.
- The token audience used is Kusto resource: https://kusto.kusto.windows.net
- For newer Azure CLI versions supporting --scope, a fallback is attempted.
"""
from __future__ import annotations

import os
import sys
import json
import shutil
import subprocess
import time
from typing import Optional, Tuple

KUSTO_RESOURCE = "https://kusto.kusto.windows.net"
KUSTO_SCOPE = f"{KUSTO_RESOURCE}/.default"


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    sys.stderr.write(f"[{ts}] {msg}\n")
    sys.stderr.flush()


def _az_exists() -> bool:
    return shutil.which("az") is not None


def _run_az(args: list[str], capture_output: bool = True, text: bool = True) -> Tuple[int, str, str]:
    try:
        proc = subprocess.run(["az", *args], capture_output=capture_output, text=text, check=False)
        return proc.returncode, proc.stdout or "", proc.stderr or ""
    except FileNotFoundError:
        return 127, "", "az not found"
    except Exception as e:
        return 1, "", str(e)


def _get_access_token_once(verbose: bool = True) -> Tuple[Optional[str], Optional[str]]:
    """
    Attempt to get a token using Azure CLI without prompting login.
    Returns (token, error_message). Only one of them will be non-None.
    """
    # Prefer legacy --resource for broad CLI compatibility
    if verbose:
        _log("Attempting to get ADX token from Azure CLI cache (resource mode)...")
    code, out, err = _run_az(["account", "get-access-token", "--resource", KUSTO_RESOURCE, "-o", "json"])
    if code == 0:
        try:
            data = json.loads(out)
            token = data.get("accessToken") or data.get("access_token")
            if token:
                if verbose:
                    _log("Obtained ADX token from Azure CLI cache.")
                return token, None
            return None, "Azure CLI returned success but token field missing"
        except json.JSONDecodeError as e:
            return None, f"Failed to parse Azure CLI token JSON: {e}"
    # Try scope variant for newer CLIs
    if verbose:
        _log("Resource mode failed; retrying Azure CLI get-access-token using scope...")
    code, out, err = _run_az(["account", "get-access-token", "--scope", KUSTO_SCOPE, "-o", "json"])
    if code == 0:
        try:
            data = json.loads(out)
            token = data.get("accessToken") or data.get("access_token")
            if token:
                if verbose:
                    _log("Obtained ADX token from Azure CLI cache (scope mode).")
                return token, None
            return None, "Azure CLI returned success but token field missing (scope mode)"
        except json.JSONDecodeError as e:
            return None, f"Failed to parse Azure CLI token JSON (scope mode): {e}"
    # Error path
    msg = err.strip() or out.strip() or f"Azure CLI get-access-token failed with code {code}"
    return None, msg


def _print_login_instructions_from_output(output: str) -> None:
    # Try to extract and echo URL and device code lines clearly.
    # Typical lines include:
    # "To sign in, use a web browser to open the page https://microsoft.com/devicelogin and enter the code ABCD-1234 to authenticate."
    # We'll scan lines and surface those that contain 'http' and 'code'.
    for line in output.splitlines():
        l = line.strip()
        if not l:
            continue
        lower = l.lower()
        if ("http://" in lower or "https://" in lower) and ("code" in lower or "enter the code" in lower):
            # Redact potential token-like substrings (very defensive):
            safe = l.replace("\r", " ")
            _log(f"Azure login hint: {safe}")


def _interactive_login(verbose: bool = True, timeout: int = 600) -> bool:
    """
    Start device-code login flow and wait for completion (or timeout).
    Returns True on successful login, False otherwise.
    """
    if verbose:
        _log("Starting Azure CLI device login flow (az login --use-device-code)...")
    try:
        proc = subprocess.Popen(
            ["az", "login", "--use-device-code"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    except FileNotFoundError:
        _log("ERROR: Azure CLI (az) not found on PATH.")
        return False
    except Exception as e:
        _log(f"ERROR: Failed to start az login: {e}")
        return False

    start = time.time()
    aggregated = []
    try:
        while True:
            if proc.stdout is None:
                break
            line = proc.stdout.readline()
            if line:
                aggregated.append(line)
                _print_login_instructions_from_output(line)
            if proc.poll() is not None:
                break
            if time.time() - start > timeout:
                proc.kill()
                _log("ERROR: Azure CLI login timed out.")
                return False
        rc = proc.wait(timeout=5)
        if rc == 0:
            if verbose:
                _log("Azure CLI login completed successfully.")
            return True
        else:
            _log(f"ERROR: Azure CLI login failed with exit code {rc}.")
            # Print any accumulated hints
            if aggregated:
                _print_login_instructions_from_output("".join(aggregated))
            return False
    except Exception as e:
        _log(f"ERROR: Exception while waiting for az login: {e}")
        return False


def get_adx_token(verbose: bool = True, timeout: int = 600) -> str:
    """
    Obtain an ADX (Kusto) bearer token using Azure CLI.

    - Tries cached token via az account get-access-token.
    - If unavailable, performs az login --use-device-code and waits for completion.
    - Returns the access token string on success.
    - Raises RuntimeError on failure.

    The function prints verbose progress messages but never prints the token itself.
    """
    if not _az_exists():
        raise RuntimeError("Azure CLI (az) is required but was not found on PATH.")

    # 1) Try from cache
    token, err = _get_access_token_once(verbose=verbose)
    if token:
        return token
    if verbose:
        _log(f"No cached ADX token available from Azure CLI: {err}")

    # 2) Trigger interactive login
    if not _interactive_login(verbose=verbose, timeout=timeout):
        raise RuntimeError("Azure CLI login failed or timed out.")

    # 3) Retry token acquisition after login
    # Give CLI cache a brief moment to settle
    time.sleep(1.0)
    token, err = _get_access_token_once(verbose=verbose)
    if token:
        return token
    raise RuntimeError(f"Failed to obtain ADX token after login: {err}")


if __name__ == "__main__":
    # Simple manual test: try to fetch a token and print only metadata.
    try:
        t = get_adx_token(verbose=True)
        _log("Token acquired successfully (not printing the token).")
        # Show expiry info if available
        # Note: We avoid parsing JWT to prevent introducing deps and exposing data accidentally.
    except Exception as e:
        _log(f"ERROR: {e}")
        sys.exit(1)
