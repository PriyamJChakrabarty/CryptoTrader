"""Atomic write + directory initialization utilities.

FR-013: atomic write (temp + os.rename) + threading.Lock in-process exclusive lock.
"""

from __future__ import annotations

import os
import tempfile
import threading
from pathlib import Path

# In-process global write lock (single-process single-writer model)
_write_lock = threading.Lock()


def atomic_write(path: Path, content: str) -> None:
    """Atomically write a file (temp file + os.rename).

    Exclusive within the same process via _write_lock, preventing concurrent
    write conflicts. Cross-process extension: could be upgraded to fcntl.flock
    in the future.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        fd, tmp_path = tempfile.mkstemp(dir=path.parent, prefix=".tmp_")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(content)
            os.rename(tmp_path, path)
        except Exception:
            # Clean up leftover temp file
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise


def ensure_skill_dirs(base: Path | None = None) -> None:
    """Automatically create the agent_skills/ directory skeleton (initial 5 skill directories)."""
    from cryptotrader.agents.skills._constants import _INITIAL_SKILL_DIRS, DEFAULT_AGENT_SKILLS_DIR

    skills_dir = base or DEFAULT_AGENT_SKILLS_DIR
    for name in _INITIAL_SKILL_DIRS:
        (skills_dir / name).mkdir(parents=True, exist_ok=True)


def atomic_rename(src: Path, dst: Path) -> None:
    """Atomic rename (used for archive operations)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock:
        os.rename(src, dst)
