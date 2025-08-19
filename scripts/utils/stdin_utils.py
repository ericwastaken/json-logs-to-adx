"""
Reusable helpers for safely reading optional input from STDIN in CLI scripts.

Primary use case: when a CLI option can be provided via flag or via STDIN
(if the option is omitted or explicitly set to "-"). These helpers avoid
blocking reads by first checking whether STDIN has data available.
"""
from __future__ import annotations

import sys
import select
from typing import Optional


def stdin_has_data(timeout_sec: float = 0.05) -> bool:
    """
    Returns True if there is data ready to be read from sys.stdin within the
    given timeout window. Uses select.select to avoid blocking.
    """
    try:
        if sys.stdin.closed or not hasattr(sys.stdin, "fileno"):
            return False
        rlist, _, _ = select.select([sys.stdin], [], [], timeout_sec)
        return bool(rlist)
    except Exception:
        return False


essential_stdin_error = (
    "ERROR: No --json provided and no data on STDIN. Provide --json or pipe JSON into this command.\n"
)


def read_text_maybe_from_stdin(
    option_value: Optional[str],
    empty_stdin_error: str = essential_stdin_error,
    dash_alias: bool = True,
    timeout_sec: float = 0.05,
) -> str:
    """
    Resolve a text value from either an explicit CLI option value or from STDIN.

    Behavior:
    - If option_value is provided and (not '-' or dash_alias is False), return it as-is.
    - If option_value is None or '-', attempt to read from STDIN only if it's non-TTY
      and data is actually available within timeout. Otherwise, print error and exit(2).

    This function writes errors to stderr and terminates the process with exit code 2
    when input is required but not provided, mirroring typical CLI behavior.
    """
    source = option_value

    if source is None or (dash_alias and source == "-"):
        # Determine if stdin is a TTY; treat exceptions as TTY (i.e., no piped input)
        try:
            is_tty = sys.stdin.isatty()
        except Exception:
            is_tty = True

        if not is_tty:
            # Only read when data is ready to avoid blocking in CI/containers
            if stdin_has_data(timeout_sec=timeout_sec):
                try:
                    return sys.stdin.read()
                except Exception:
                    # If read fails, treat as no input provided
                    sys.stderr.write(empty_stdin_error)
                    sys.exit(2)
            else:
                sys.stderr.write(empty_stdin_error)
                sys.exit(2)
        else:
            sys.stderr.write(empty_stdin_error)
            sys.exit(2)

    return source  # type: ignore[return-value]
