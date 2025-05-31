"""
Programmatic façade so that *other Python code* can import and run the
analyser without shelling-out.  All heavy-lifting sits in
`workflows.run_workflow()`, which returns a dict of artefacts.

Example:

    from src.main import analyse_zip
    artefacts = analyse_zip("/tmp/foo.zip")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from .config import settings
from .workflows import run_workflow

# --------------------------------------------------------------------------- #
# Configure logger for this module
# --------------------------------------------------------------------------- #
LOG = logging.getLogger(__name__)


def analyse_zip(zip_path: str | Path, **kwargs) -> Dict[str, Any]:  # noqa: D401
    """
    High-level helper around `run_workflow()`.

    Parameters
    ----------
    zip_path : Union[str, Path]
        Absolute or relative path to the .zip archive.
    **kwargs  :
        Any keyword override forwarded verbatim to `run_workflow`.

    Returns
    -------
    Dict[str, Any]
        A mapping with keys:
          • tree_text         (str)
          • file_summaries    (List[dict])
          • project_summary   (str)
    """
    LOG.info(">>> [main] analyse_zip() called with zip_path=%r, kwargs=%r", zip_path, kwargs)

    # Resolve Path
    resolved_path = Path(zip_path)
    LOG.debug("[main] Resolved zip_path to %r", resolved_path)

    # Determine model parameter
    model = kwargs.pop("model", settings.BEEAI_MODEL)
    LOG.info("[main] Using model=%r for analysis", model)

    try:
        LOG.info("[main] Invoking run_workflow() …")
        artefacts = run_workflow(
            zip_path=resolved_path,
            model=model,
            **kwargs,
        )
        LOG.info("[main] run_workflow() completed successfully")
        LOG.debug(
            "[main] Retrieved artefacts keys: %r",
            list(artefacts.keys()),
        )
        return artefacts
    except Exception as exc:
        LOG.exception("[main] Exception in analyse_zip(): %s", exc)
        raise
