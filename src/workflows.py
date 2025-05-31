"""
src/workflows.py
================

Assembles all BeeAI agents into a runnable Workflow, using beeai_framework.

In this fixed version:
  1. We no longer call wf.emit(...) or wf.subscribe(...) (these methods do not exist).
  2. We load the BeeAI manifest (beeai.yaml) via Workflow(schema=...).
  3. We drive the workflow by calling wf.run(initial_state_dict).
  4. We attempt to retrieve results from common attribute names of the 'Run' object.
     If these fail, DEBUG logs and updated error messages guide the user to find the correct attribute/method.
  5. Enhanced logging to help analyze the Workflow and Run object, and to guide debugging.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Union

# --------------------------------------------------------------------------- #
#  Import the Workflow engine from beeai_framework
# --------------------------------------------------------------------------- #
try:
    from beeai_framework.workflows.workflow import Workflow
    # from beeai_framework.context import Run # Uncomment if you need to reference Run by name
except ImportError as exc:
    raise RuntimeError(
        "Cannot import Workflow from beeai_framework. Make sure beeai-framework is installed."
    ) from exc

from .config import settings

LOG = logging.getLogger(__name__)  # Should be 'src.workflows' if file is src/workflows.py

# Basic logging config. This might be overridden by application-wide logging setup.
# Ensure your application's logging configuration allows DEBUG messages from this logger
# if you need to inspect dir(run_output).
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(module)s.%(funcName)s:%(lineno)d | ★ %(message)s",
    datefmt="%H:%M:%S",
    force=True,  # Override any root handlers if already configured by Uvicorn/FastAPI at module load
)

# List of common attribute names for accessing state from a Run object.
# If these do not match your installed version, inspect dir(run_output) in DEBUG mode
# and add the correct member. We have extended this list with some additional guesses.
POTENTIAL_RUN_STATE_ATTRIBUTES = [
    "state",
    "outputs",
    "result",
    "data",
    "value",
    "context",
    "payload",
    "state_data",    # Added: potential canonical name in some versions
    "memory",        # Added: if Run exposes 'memory'
    "final_state",   # Added: some versions call it 'final_state'
]

# --------------------------------------------------------------------------- #
#  Path to the BeeAI YAML manifest
# --------------------------------------------------------------------------- #
ROOT_DIR = Path(__file__).resolve().parent.parent  # Use resolve() for more robust path
BEEAI_YAML = ROOT_DIR / "beeai.yaml"
if not BEEAI_YAML.exists():
    LOG.error("BeeAI manifest not found at %s", BEEAI_YAML)
    raise RuntimeError(f"BeeAI manifest not found at {BEEAI_YAML!r}")

# --------------------------------------------------------------------------- #
#  Workflow builder
# --------------------------------------------------------------------------- #
def create_workflow_engine(model: str | None = None) -> Workflow:
    """
    Load a Workflow from the beeai.yaml manifest.
    The constructor is Workflow(schema: type, name: str = 'Workflow').
    We pass the YAML path as a string to the schema parameter.
    """
    model_id = model or settings.BEEAI_MODEL  # Ensure settings.BEEAI_MODEL is accessible
    LOG.debug(
        "Attempting to instantiate Workflow with schema: %s, model_id: %s",
        str(BEEAI_YAML),
        model_id,
    )

    wf = Workflow(schema=str(BEEAI_YAML))

    LOG.info("Workflow engine instantiated from %s using schema parameter", BEEAI_YAML)
    return wf


create_runtime = create_workflow_engine  # alias for backward compatibility

# --------------------------------------------------------------------------- #
#  High-level helper
# --------------------------------------------------------------------------- #
def run_workflow(
    zip_path: Path,
    *,
    model: str | None = None,
    print_events: bool = True,  # This flag can control more verbose run-specific logging
) -> Dict[str, Any]:
    """
    Run the multi-agent workflow to analyze a ZIP, returning:
      • tree_text       (str)
      • file_summaries  (List[dict])
      • project_summary (str)

    The workflow is driven by an initial_state dictionary.
    Results are retrieved from an attribute or method of the object returned by wf.run().
    """

    # 1) Configure logging for this specific run if print_events is True,
    #    or ensure module-level config is respected.
    #    The basicConfig at module level with force=True should handle most cases.
    #    This explicit call can be used if finer control per run is needed.
    if print_events:
        LOG.info(
            "`print_events` is True. Detailed logging for this run is expected "
            "based on configured levels."
        )

    LOG.info("Starting 'run_workflow' for zip_path: %s", zip_path)

    # Report current effective log level to help user debug visibility of DEBUG messages
    effective_level_name = logging.getLevelName(LOG.getEffectiveLevel())
    LOG.info(
        "Current effective log level for logger '%s': %s. "
        "If DEBUG messages (like 'dir(run_output)') are not visible, "
        "ensure LOG_LEVEL in your application settings (e.g., src.config.settings.LOG_LEVEL) "
        "is set to 'DEBUG' and that the logging configuration is applied correctly.",
        LOG.name,
        effective_level_name,
    )

    # 2) Enforce compressed ZIP size limit
    max_bytes = settings.ZIP_SIZE_LIMIT_MB * 1_048_576  # Ensure settings.ZIP_SIZE_LIMIT_MB is accessible
    actual_bytes = zip_path.stat().st_size
    LOG.debug(
        "Zip file size: %d bytes. Max allowed: %d bytes (%s MB)",
        actual_bytes,
        max_bytes,
        settings.ZIP_SIZE_LIMIT_MB,
    )
    if actual_bytes > max_bytes:
        error_msg = (
            f"Archive exceeds {settings.ZIP_SIZE_LIMIT_MB} MB "
            f"({actual_bytes / 1_048_576:.1f} MB)"
        )
        LOG.error(error_msg)
        raise ValueError(error_msg)

    # 3) Instantiate the Workflow engine
    LOG.debug("Creating workflow engine...")
    wf = create_workflow_engine(model)

    # 4) Build the "initial_state" dictionary
    initial_state: dict[str, Any] = {
        "NewUpload": {"zip_path": str(zip_path.resolve())}  # Use absolute path
    }
    LOG.info(
        "Workflow initial_state prepared: %s",
        json.dumps(initial_state, indent=2, default=str),
    )

    # 5) Invoke wf.run(initial_state=...)
    LOG.info("Invoking Workflow.run() …")
    # If your version of Workflow.run expects `initial_state=...` instead of `state=...`,
    # adjust the keyword accordingly.
    run_output = wf.run(state=initial_state)

    # 6) Analyze the run_output object
    LOG.info("Workflow run finished. Type of run_output: %s", type(run_output))
    LOG.debug("Attributes and methods of run_output object: %s", dir(run_output))

    # 7) Access the results dictionary from the Run object.
    mem: dict[str, Any] | None = None

    # <<< USER ACTION MAY BE REQUIRED HERE >>>
    # If the attributes in POTENTIAL_RUN_STATE_ATTRIBUTES don't work,
    # inspect the DEBUG log for "Attributes and methods of run_output object"
    # (it's printed just above this section if DEBUG level is active).
    # Then, update the POTENTIAL_RUN_STATE_ATTRIBUTES list with the correct name(s),
    # or directly assign the correct attribute/method call below.
    # Example: if dir() shows 'workflow_data', add 'workflow_data' to the list
    # or, if it's a method, try: mem = run_output.get_workflow_data()

    for attr_name in POTENTIAL_RUN_STATE_ATTRIBUTES:
        try:
            candidate_mem = getattr(run_output, attr_name)
            LOG.info(
                "Found attribute 'run_output.%s'. Checking if it's dictionary-like.", attr_name
            )
            LOG.debug("Type of 'run_output.%s': %s", attr_name, type(candidate_mem))

            if callable(candidate_mem):
                LOG.debug(
                    "'run_output.%s' is callable. Attempting to call it, assuming it might return the state dictionary.",
                    attr_name,
                )
                try:
                    candidate_mem = candidate_mem()
                    LOG.debug(
                        "Called 'run_output.%s()'. Type of result: %s", attr_name, type(candidate_mem)
                    )
                except Exception as call_exc:
                    LOG.warning(
                        "Failed to call 'run_output.%s()': %s. Skipping this as state.",
                        attr_name,
                        call_exc,
                    )
                    continue

            if isinstance(candidate_mem, dict) and hasattr(candidate_mem, "get"):
                mem = candidate_mem
                LOG.info(
                    "Successfully accessed dictionary-like results via 'run_output.%s' (type: %s).",
                    attr_name,
                    type(mem),
                )
                try:
                    mem_snippet_keys = list(mem.keys())[:5]
                    mem_snippet = {k: type(mem[k]) for k in mem_snippet_keys}
                    LOG.debug(
                        "Snippet of keys and value types in 'mem' (up to 5 keys): %s",
                        json.dumps(mem_snippet, default=str),
                    )
                    if len(mem.keys()) > 5:
                        LOG.debug("... and %d more keys.", len(mem.keys()) - 5)
                except Exception as e:
                    LOG.debug("Could not create detailed snippet for 'mem': %s", e)
                break
            else:
                LOG.warning(
                    "'run_output.%s' (type: %s) was accessed/called but is not a dictionary "
                    "with a 'get' method. Trying next attribute.",
                    attr_name,
                    type(candidate_mem),
                )
        except AttributeError:
            LOG.debug("Attribute '%s' not found on run_output object.", attr_name)
        except Exception as e:
            LOG.error(
                "An unexpected error occurred while trying to access or call 'run_output.%s': %s",
                attr_name,
                e,
                exc_info=True,
            )

    # 8) If none of the above worked, try run_output.__dict__ as a fallback
    if mem is None:
        LOG.debug("Attempting fallback: inspecting run_output.__dict__ ...")
        candidate_dict = getattr(run_output, "__dict__", None)
        if isinstance(candidate_dict, dict):
            # Check if any nested entry is dict-like
            for key, val in candidate_dict.items():
                if isinstance(val, dict) and hasattr(val, "get"):
                    mem = val
                    LOG.info(
                        "Fallback succeeded: using run_output.__dict__['%s'] as the memory dictionary.", key
                    )
                    break

    if mem is None:
        effective_level_name = logging.getLevelName(LOG.getEffectiveLevel())
        error_message = (
            f"'Run' object (type: {type(run_output)}, class confirmed as beeai_framework.context.Run) "
            f"did not yield a dictionary-like object from the tried attributes/callable results: "
            f"{POTENTIAL_RUN_STATE_ATTRIBUTES}. \n\n"
            "================================ USER ACTION REQUIRED ================================\n"
            "1. IMPORTANT: Ensure your application's LOG_LEVEL (e.g., in 'settings.py' or environment variables) "
            "is set to 'DEBUG'. The current effective level for logger "
            f"'{LOG.name}' is '{effective_level_name}'.\n"
            "2. Re-run the analysis.\n"
            "3. Find the DEBUG log message from logger "
            f"'{LOG.name}' that starts with: \n"
            "   'Attributes and methods of run_output object: ...'. This log contains the list of all "
            "available members of the 'run_output' object.\n"
            "4. From that list, identify the correct attribute name (e.g., 'final_state_data') or a method "
            "   that returns the state dictionary (e.g., 'get_results()').\n"
            "5. Update the 'POTENTIAL_RUN_STATE_ATTRIBUTES' list at the top of 'src/workflows.py' with the correct name. "
            "   If it's a method that needs to be called (like 'get_results()'), the code now attempts to call it if the attribute itself is callable.\n"
            "   Alternatively, you can directly assign it in the code, for example:\n"
            "   # mem = run_output.your_correct_attribute_name \n"
            "   # OR if it's a method that returns the dict: \n"
            "   # mem = run_output.your_method_name() \n"
            "If the identified member is callable and expected to return the dictionary, ensure it's called.\n"
            "======================================================================================"
        )
        LOG.error(error_message)
        raise AttributeError(error_message)

    # 9) After run completes, read from the workflow's final state dictionary
    LOG.info("Gathering artefacts from the workflow's final state dictionary (mem)...")

    tree_text = mem.get("project_tree.txt", "")
    summaries_json = mem.get("file_summaries.json", "[]")
    project_summary = mem.get("project_summary.txt", "")

    LOG.debug(
        "Retrieved tree_text (first 100 chars): '%.100s%s'",
        tree_text[:100],
        "..." if len(tree_text) > 100 else "",
    )
    LOG.debug(
        "Retrieved summaries_json (first 100 chars): '%.100s%s'",
        summaries_json[:100],
        "..." if len(summaries_json) > 100 else "",
    )
    LOG.debug(
        "Retrieved project_summary (first 100 chars): '%.100s%s'",
        project_summary[:100],
        "..." if len(project_summary) > 100 else "",
    )

    try:
        file_summaries: List[Dict[str, Any]] = json.loads(summaries_json)
    except json.JSONDecodeError as exc:
        LOG.error(
            "Failed to parse file_summaries.json from memory: %s. Content was: %s",
            exc,
            summaries_json,
        )
        file_summaries = []
    except TypeError as exc:
        LOG.error(
            "Failed to parse file_summaries.json due to TypeError: %s. Content was: %r",
            exc,
            summaries_json,
        )
        file_summaries = []

    LOG.info("Successfully processed artefacts from workflow memory.")
    return {
        "tree_text": tree_text,
        "file_summaries": file_summaries,
        "project_summary": project_summary,
    }
