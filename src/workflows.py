# src/workflows.py

"""
Assembles all BeeAI agents into a runnable Workflow (beeai-framework ≥ 0.1.14).

Fixes & improvements
--------------------
* Use `wf.run(state=…)` (since this Workflow class does not support `emit`).
* Add a robust `_find_mapping` helper: recursively inspects attributes,
  their return values (including zero-arg callables) and items inside
  `__dict__` until the first object satisfying `hasattr(x, "get")` is found.
* Skip calling coroutine functions / coroutine objects inside `_safe_call`.
* Keeps the public API exactly the same: `run_workflow(zip_path, …)` still
  returns a dict with **tree_text**, **file_summaries**, **project_summary**.
"""

from __future__ import annotations

import inspect
import json
import logging
import types
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Dict, List, Set

from beeai_framework.workflows.workflow import Workflow

from .config import settings


# --------------------------------------------------------------------------- #
# Logging
# --------------------------------------------------------------------------- #

LOG = logging.getLogger(__name__)
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format=(
        "%(asctime)s | %(levelname)s | %(name)s | "
        "%(module)s.%(funcName)s:%(lineno)d | ★ %(message)s"
    ),
    datefmt="%H:%M:%S",
    force=True,
)


# --------------------------------------------------------------------------- #
# Constants & helpers
# --------------------------------------------------------------------------- #

# Likely attribute / method names where the framework may hide its state
LIKELY_MEM_ATTRS: tuple[str, ...] = (
    "state",
    "_state",
    "outputs",
    "result",
    "data",
    "value",
    "payload",
    "memory",
    "_context",
    "context",
    "final_state",
    "state_data",
)

# Location of the `beeai.yaml` manifest
BEEAI_YAML = Path(__file__).parent.parent / "beeai.yaml"


def _safe_call(maybe_callable: Any) -> Any:
    """
    Call `obj()` **only** if it is a synchronous, zero-argument callable.
    Skip calling if:
      - it's a coroutine function (async def)
      - it returns a coroutine object (awaitable)
      - calling it raises any exception
    In those cases, return the object itself unmodified.
    """
    # 1) Not a callable at all? Return as is.
    if not callable(maybe_callable):
        return maybe_callable

    # 2) If it is a coroutine function (async def), do NOT call.
    if inspect.iscoroutinefunction(maybe_callable):
        LOG.debug("_safe_call: Skipping call to coroutine function %r", maybe_callable)
        return maybe_callable

    # 3) If it is a bound method or normal function, inspect its signature.
    sig = inspect.signature(maybe_callable)
    # Must have no required params to call
    for param in sig.parameters.values():
        if (
            param.kind not in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
            and param.default is inspect._empty
        ):
            # Found a required parameter; we cannot call it safely.
            LOG.debug("_safe_call: Function %r has required params; skipping call.", maybe_callable)
            return maybe_callable

    # 4) Attempt to call it, but guard against coroutine objects or exceptions
    try:
        result = maybe_callable()
    except Exception as e:
        LOG.warning("_safe_call: Calling %r raised %s; skipping.", maybe_callable, e, exc_info=False)
        return maybe_callable

    # 5) If the result is a coroutine object (awaitable), skip it.
    if inspect.iscoroutine(result) or isinstance(result, types.CoroutineType):
        LOG.debug("_safe_call: Result of calling %r is a coroutine; returning original.", maybe_callable)
        return maybe_callable

    # 6) Otherwise, return what we got
    return result


def _find_mapping(obj: Any, *, max_depth: int = 3) -> Mapping[str, Any] | None:
    """
    Recursively search `obj` (and selected descendants) for the first dict-like
    object (anything with a `.get` attribute).

    Depth-first search; stops as soon as one mapping is found.

    Parameters
    ----------
    obj : Any
        Object to inspect.
    max_depth : int, default 3
        Prevents infinite loops & runaway recursion.

    Returns
    -------
    Mapping[str, Any] | None
        The mapping if found, else `None`.
    """
    visited: Set[int] = set()

    def _walk(current: Any, depth: int) -> Mapping[str, Any] | None:
        if depth < 0 or id(current) in visited:
            return None
        visited.add(id(current))

        # 1) If it's already a mapping, return it
        if hasattr(current, "get"):
            return current  # type: ignore[return-value]

        # 2) Look at likely attributes / callables
        for name in LIKELY_MEM_ATTRS:
            if hasattr(current, name):
                candidate = getattr(current, name)
                candidate = _safe_call(candidate)
                if hasattr(candidate, "get"):
                    LOG.debug("_find_mapping: Found mapping via attribute %r", name)
                    return candidate  # type: ignore[return-value]

        # 3) Inspect __dict__ values (recursively)
        if hasattr(current, "__dict__"):
            for val in current.__dict__.values():
                candidate = _safe_call(val)
                if hasattr(candidate, "get"):
                    LOG.debug("_find_mapping: Found mapping inside __dict__ value %r", val)
                    return candidate  # type: ignore[return-value]
                deeper = _walk(candidate, depth - 1)
                if deeper is not None:
                    return deeper

        # 4) Nothing found in this branch
        return None

    return _walk(obj, max_depth)


def create_workflow_engine(model: str | None = None) -> Workflow:
    """
    Load a Workflow from `beeai.yaml`.
    The *model* argument is only logged for completeness. beeai-framework ≥ 0.1.14
    reads model settings from env / YAML directly (including OLLAMA_URL).
    """
    LOG.info(">>> Creating BeeAI Workflow engine (schema=%s, model=%s) ...", BEEAI_YAML, model or "default")
    wf = Workflow(schema=str(BEEAI_YAML))
    LOG.info("✔ Workflow engine instantiated from %s", BEEAI_YAML)
    return wf


# Back-compatible alias
create_runtime = create_workflow_engine


def run_workflow(
    zip_path: Path,
    *,
    model: str | None = None,
    print_events: bool = True,
) -> Dict[str, Any]:
    """
    Run the BeeAI multi-agent workflow on *zip_path* and return the artefacts.

    Returns
    -------
    Dict[str, Any] with keys
      • **tree_text**       – the directory tree as a string
      • **file_summaries**  – list[dict] of per-file summaries
      • **project_summary** – final overall summary
    """
    # -----------------------------
    # 0) Configure logging level
    # -----------------------------
    if print_events:
        LOG.setLevel(logging.DEBUG)
    else:
        LOG.setLevel(getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO))

    LOG.info(">>> Starting run_workflow for ZIP: %s", zip_path)

    # -----------------------------
    # 1) ZIP size guard-rail
    # -----------------------------
    max_bytes = settings.ZIP_SIZE_LIMIT_MB * 1_048_576
    size = zip_path.stat().st_size
    LOG.debug(
        "ZIP file size is %d bytes; max allowed is %d bytes (%d MB)",
        size,
        max_bytes,
        settings.ZIP_SIZE_LIMIT_MB,
    )
    if size > max_bytes:
        error_msg = f"ZIP is {size / 1_048_576:.1f} MB – exceeds limit of {settings.ZIP_SIZE_LIMIT_MB} MB"
        LOG.error(error_msg)
        raise ValueError(error_msg)
    LOG.info("ZIP size check passed (%0.1f MB ≤ %d MB)", size / 1_048_576, settings.ZIP_SIZE_LIMIT_MB)

    # -----------------------------
    # 2) Build workflow engine
    # -----------------------------
    wf = create_workflow_engine(model)

    # -----------------------------
    # 3) Prepare initial state (since emit is unavailable)
    # -----------------------------
    resolved_path = str(zip_path.resolve())
    initial_state: dict[str, Any] = {"NewUpload": {"zip_path": resolved_path}}
    LOG.info("Initial state for workflow prepared: %s", initial_state)

    # If the user wants to see every event, attempt to subscribe (may be no-op)
    if print_events:
        try:
            wf.subscribe("*", lambda e: LOG.info("Event fired: %s", e["type"]))
        except AttributeError:
            LOG.debug("Workflow.subscribe is not available; skipping event logging.")

    # -----------------------------
    # 4) Run the workflow with initial_state
    # -----------------------------
    try:
        LOG.info(">>> Invoking wf.run(state=…) …")
        run_output = wf.run(state=initial_state)
        LOG.info("✔ Workflow.run completed.")
    except Exception as e:
        LOG.exception("✖ Error while running workflow: %s", e)
        raise

    # (Optional) inspect run_output for debugging
    LOG.debug("Run object returned (class=%s)", run_output.__class__.__name__)
    LOG.debug("dir(run_output) = %s", dir(run_output))

    # -----------------------------
    # 5) Locate the memory / outputs mapping
    # -----------------------------
    LOG.info(">>> Looking for BeeAI memory in the Run object …")
    mem = _find_mapping(run_output)
    if mem is None:
        LOG.error(
            "✖ Could not locate a dictionary-like state in the Run object. "
            "Enable DEBUG logs, inspect dir(run_output), and update _find_mapping if needed."
        )
        raise AttributeError("No mapping attribute found in Run object.")
    LOG.info("✔ Found BeeAI memory mapping: %r", type(mem))

    # -----------------------------
    # 6) Extract artefacts
    # -----------------------------
    LOG.info(">>> Extracting 'project_tree.txt' from memory …")
    tree_text = mem.get("project_tree.txt", "")
    if tree_text:
        LOG.debug(
            "First 100 chars of tree_text: %r",
            tree_text[:100] + ("…" if len(tree_text) > 100 else ""),
        )
    else:
        LOG.warning("No 'project_tree.txt' found in memory.")

    LOG.info(">>> Extracting 'file_summaries.json' from memory …")
    summaries_json = mem.get("file_summaries.json", "[]")
    if isinstance(summaries_json, str):
        LOG.debug(
            "First 100 chars of summaries_json: %r",
            summaries_json[:100] + ("…" if len(summaries_json) > 100 else ""),
        )
    else:
        LOG.debug("'file_summaries.json' is not a string (type=%s)", type(summaries_json))

    LOG.info(">>> Extracting 'project_summary.txt' from memory …")
    project_summary = mem.get("project_summary.txt", "")
    if project_summary:
        LOG.debug(
            "First 100 chars of project_summary: %r",
            project_summary[:100] + ("…" if len(project_summary) > 100 else ""),
        )
    else:
        LOG.warning("No 'project_summary.txt' found in memory.")

    # -----------------------------
    # 7) Convert summaries to list[dict]
    # -----------------------------
    file_summaries: List[Dict[str, Any]]
    try:
        if isinstance(summaries_json, str):
            if summaries_json.strip():
                file_summaries = json.loads(summaries_json)
                LOG.info("✔ Parsed file_summaries.json into %d entries.", len(file_summaries))
            else:
                LOG.warning("file_summaries.json was empty or whitespace.")
                file_summaries = []
        else:
            # If the framework returned a native list/dict-like structure
            if isinstance(summaries_json, list):
                file_summaries = summaries_json  # type: ignore[assignment]
                LOG.info("✔ Retrieved file_summaries as list (length=%d).", len(file_summaries))
            else:
                # Fallback: try converting to list
                file_summaries = list(summaries_json)  # type: ignore[arg-type]
                LOG.info("✔ Converted file_summaries to list (length=%d).", len(file_summaries))
    except Exception as exc:
        LOG.warning("✖ Could not parse file_summaries.json: %s. Returning empty list.", exc)
        file_summaries = []

    LOG.info("✔ Successfully processed artefacts from workflow memory.")

    # -----------------------------
    # 8) Return final dict
    # -----------------------------
    return {
        "tree_text": tree_text,
        "file_summaries": file_summaries,
        "project_summary": project_summary,
    }
