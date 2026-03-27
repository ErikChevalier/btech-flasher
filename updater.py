"""
Auto-updater for flintwave-kdh-flasher.
Checks GitHub for newer commits and pulls them if available.
"""

import os
import subprocess

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_URL = "https://github.com/FlintWave/flintwave-kdh-flasher"


def get_local_commit():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None


def get_remote_commit():
    try:
        result = subprocess.run(
            ["git", "ls-remote", "origin", "HEAD"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.split()[0]
    except Exception:
        pass
    return None


def check_for_update():
    """Returns (has_update, local_sha, remote_sha) or (False, None, None) on error."""
    local = get_local_commit()
    remote = get_remote_commit()
    if not local or not remote:
        return False, local, remote
    return local != remote, local, remote


def apply_update():
    """Pull latest from origin. Returns (success, message)."""
    try:
        result = subprocess.run(
            ["git", "pull", "--ff-only", "origin", "master"],
            cwd=REPO_DIR, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            return True, result.stdout.strip()
        return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)
