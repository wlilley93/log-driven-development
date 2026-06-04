"""detect-secrets baseline management."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


BASELINE_FILE = ".secrets.baseline"


def get_baseline_path(target_dir: str) -> Path:
    return Path(target_dir) / BASELINE_FILE


def baseline_exists(target_dir: str) -> bool:
    return get_baseline_path(target_dir).exists()


def create_baseline(target_dir: str, detect_secrets_bin: str = "detect-secrets") -> tuple[bool, str]:
    """Create a new detect-secrets baseline.

    Returns (success, message).
    """
    baseline_path = get_baseline_path(target_dir)
    try:
        result = subprocess.run(
            [detect_secrets_bin, "scan", "--all-files"],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, f"detect-secrets scan failed: {result.stderr.strip()}"

        with open(baseline_path, "w") as f:
            f.write(result.stdout)

        # Count findings in baseline
        data = json.loads(result.stdout)
        count = sum(len(v) for v in data.get("results", {}).values())
        return True, f"Baseline created at {baseline_path} with {count} known secret(s)"

    except FileNotFoundError:
        return False, "detect-secrets not found. Run 'vibescan install' first."
    except subprocess.TimeoutExpired:
        return False, "detect-secrets scan timed out"
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Failed to create baseline: {e}"


def update_baseline(target_dir: str, detect_secrets_bin: str = "detect-secrets") -> tuple[bool, str]:
    """Update existing baseline after intentional changes.

    Returns (success, message).
    """
    baseline_path = get_baseline_path(target_dir)
    if not baseline_path.exists():
        return False, f"No baseline found at {baseline_path}. Run 'vibescan baseline --create' first."

    try:
        # Scan and produce new baseline
        result = subprocess.run(
            [detect_secrets_bin, "scan", "--all-files", "--baseline", str(baseline_path)],
            cwd=target_dir,
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            return False, f"detect-secrets scan failed: {result.stderr.strip()}"

        # Audit to mark false positives
        with open(baseline_path, "w") as f:
            f.write(result.stdout)

        data = json.loads(result.stdout)
        count = sum(len(v) for v in data.get("results", {}).values())
        return True, f"Baseline updated at {baseline_path} — {count} known secret(s)"

    except FileNotFoundError:
        return False, "detect-secrets not found. Run 'vibescan install' first."
    except subprocess.TimeoutExpired:
        return False, "detect-secrets scan timed out"
    except (json.JSONDecodeError, OSError) as e:
        return False, f"Failed to update baseline: {e}"
