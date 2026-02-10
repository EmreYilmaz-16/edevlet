"""Runtime safety tweaks for report rendering dependencies.

This module ensures reportlab can write its cache/config files in locked-down
containerized Odoo environments where $HOME is read-only.
"""

from pathlib import Path
import os
import tempfile


def _is_writable(path: Path) -> bool:
    return path.exists() and path.is_dir() and os.access(path, os.W_OK)


def configure_reportlab_environment() -> None:
    """Configure reportlab-related environment variables conservatively.

    reportlab writes runtime config/cache files under RL_HOME (or HOME). In
    some deployments this location is not writable and causes noisy warnings
    such as "couldn't write the config file" during PDF/report operations.
    """
    if os.environ.get('RL_HOME'):
        return

    candidates = [
        Path('/var/tmp'),
        Path(tempfile.gettempdir()),
        Path('/tmp'),
    ]

    for candidate in candidates:
        if _is_writable(candidate):
            os.environ['RL_HOME'] = str(candidate)
            break
