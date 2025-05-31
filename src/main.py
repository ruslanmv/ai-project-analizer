"""
Programmatic façade so that *other Python code* can import and run the
analyser without shelling-out.  All heavy-lifting sits in
`workflows.run_workflow()`, which returns a dict of artefacts.

Example:

    from src.main import analyse_zip
    artefacts = analyse_zip("/tmp/foo.zip")
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from .config import settings
from .workflows import run_workflow


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
    return run_workflow(
        zip_path=Path(zip_path),
        model=kwargs.pop("model", settings.BEEAI_MODEL),
        **kwargs,
    )
