"""
Module:  audit_logger.py
Agent:   Shared (all agents)
Purpose: Shared JSONL audit logger — the single execution timeline across all 5 agents.
         Every agent appends structured entries at the start and end of every major phase.
Inputs:  audit_log_path (pathlib.Path), agent name, module name, status, summary.
Outputs: Appends JSON-lines to the audit log file.
"""

import json
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator

# Global dictionary to track start times for automatic duration calculation
_phase_start_times: dict[str, float] = {}


# Valid status values for audit log entries
_VALID_STATUSES = frozenset({"STARTED", "COMPLETED", "FAILED"})


def log_audit_event(
    audit_log_path: Path,
    agent: str,
    module: str,
    status: str,
    summary: str,
    duration_seconds: float | None = None,
) -> None:
    """Append a single structured audit event to the JSONL log file.

    Args:
        audit_log_path: Path to the audit JSONL file (from config/paths.py).
        agent: Name of the agent logging this event (e.g. "IngestionAgent").
        module: Name of the module/phase (e.g. "Phase1_TickerResolution").
        status: One of "STARTED", "COMPLETED", or "FAILED".
        summary: Human-readable summary of what happened.
        duration_seconds: Elapsed time in seconds (typically set on
                          COMPLETED/FAILED, None on STARTED).

    Raises:
        ValueError: If status is not one of the three valid values.
    """
    if status not in _VALID_STATUSES:
        raise ValueError(
            f"Invalid audit status '{status}'. Must be one of: {_VALID_STATUSES}"
        )

    # Automatically calculate duration_seconds if it's not provided
    track_key = f"{agent}_{module}"
    if status == "STARTED":
        _phase_start_times[track_key] = time.monotonic()
    elif status in ("COMPLETED", "FAILED") and duration_seconds is None:
        if track_key in _phase_start_times:
            duration_seconds = round(time.monotonic() - _phase_start_times[track_key], 2)
            del _phase_start_times[track_key] # Clean up

    entry = {
        "agent": agent,
        "module": module,
        "status": status,
        # Bug Fix: Use local time instead of UTC so it matches user's timezone
        "timestamp": datetime.now().astimezone().isoformat(),
        "duration_seconds": duration_seconds,
        "summary": summary,
    }

    # Ensure the parent directory exists
    audit_log_path.parent.mkdir(parents=True, exist_ok=True)

    # Append one JSON line with immediate flush — no buffered writes that
    # could be lost on crash.
    with open(audit_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        f.flush()


@contextmanager
def audit_phase(
    audit_log_path: Path,
    agent: str,
    module: str,
) -> Generator[None, None, None]:
    """Context manager that logs STARTED/COMPLETED/FAILED for a phase.

    Usage:
        with audit_phase(paths["AUDIT_LOG_PATH"], "IngestionAgent", "Phase1_TickerResolution"):
            # ... all Phase 1 work ...

    On entry:  logs STARTED.
    On clean exit: logs COMPLETED with duration_seconds.
    On exception:  logs FAILED with duration_seconds and exception summary,
                   then re-raises the exception.

    Args:
        audit_log_path: Path to the audit JSONL file.
        agent: Name of the agent.
        module: Name of the module/phase.
    """
    log_audit_event(
        audit_log_path=audit_log_path,
        agent=agent,
        module=module,
        status="STARTED",
        summary=f"{module} started.",
    )

    start_time = time.monotonic()

    try:
        yield
    except Exception as exc:
        elapsed = time.monotonic() - start_time
        log_audit_event(
            audit_log_path=audit_log_path,
            agent=agent,
            module=module,
            status="FAILED",
            summary=f"{module} failed: {type(exc).__name__}: {exc}",
            duration_seconds=round(elapsed, 3),
        )
        raise
    else:
        elapsed = time.monotonic() - start_time
        log_audit_event(
            audit_log_path=audit_log_path,
            agent=agent,
            module=module,
            status="COMPLETED",
            summary=f"{module} completed successfully.",
            duration_seconds=round(elapsed, 3),
        )
