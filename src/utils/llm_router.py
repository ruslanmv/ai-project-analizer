"""
llm_router.py
~~~~~~~~~~~~~

Single entry-point `generate_completion(prompt, model_id)` that hides the
differences between OpenAI, watsonx.ai and Ollama.

* OpenAI          – uses `openai` Python SDK
* IBM watsonx.ai  – uses plain `requests` (official SDK still private-beta)
* Ollama          – local REST API compatible with `/v1/chat/completions`

Returns **str** (assistant reply) or raises `RuntimeError`.

Environment variables
---------------------
OPENAI_API_KEY      – for OpenAI back-end
WATSONX_API_KEY     – for IBM watsonx.ai
WATSONX_URL         – watsonx base-URL (e.g. https://us-south.ml.cloud.ibm.com)
OLLAMA_URL          – host:port (default http://localhost:11434)
"""

from __future__ import annotations

import json
import os
import requests
from typing import Dict, List

# --------------------------------------------------------------------------- #
#  Public façade
# --------------------------------------------------------------------------- #
def generate_completion(
    messages: List[Dict[str, str]],
    model_id: str,
    temperature: float = 0.3,
) -> str:
    """
    Parameters
    ----------
    messages
        OpenAI-style chat array: [{"role": "system", "content": "…"}, …]
    model_id
        Either:
          • "openai/gpt-4o-mini"
          • "watsonx/meta-llama/llama-4-maverick-17b-128e-instruct-fp"
          • "ollama/llama3"
    temperature
        Sampling temperature (back-end permitting).

    Returns
    -------
    str
        Assistant reply text.
    """
    if model_id.startswith("openai/"):
        return _call_openai(messages, model_id.split("/", 1)[1], temperature)

    if model_id.startswith("watsonx/"):
        return _call_watsonx(messages, model_id.split("/", 1)[1], temperature)

    if model_id.startswith("ollama/") or os.getenv("OLLAMA_URL"):
        # Strip optional "ollama/" prefix
        if model_id.startswith("ollama/"):
            model_id = model_id.split("/", 1)[1]
        return _call_ollama(messages, model_id, temperature)

    raise RuntimeError(f"Unknown LLM back-end in model_id={model_id}")


# --------------------------------------------------------------------------- #
#  Back-end: OpenAI
# --------------------------------------------------------------------------- #
def _call_openai(
    messages, model, temperature
):  # noqa: D401  (helper, not part of public API)
    try:
        import openai
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("openai package not installed") from exc

    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY env var missing")

    resp = openai.ChatCompletion.create(
        model=model,
        messages=messages,
        temperature=temperature,
    )
    return resp.choices[0].message.content.strip()


# --------------------------------------------------------------------------- #
#  Back-end: IBM watsonx.ai
# --------------------------------------------------------------------------- #
def _call_watsonx(messages, model, temperature):  # noqa: D401
    api_key = os.getenv("WATSONX_API_KEY")
    base    = os.getenv("WATSONX_URL", "https://us-south.ml.cloud.ibm.com")

    if not api_key:
        raise RuntimeError("WATSONX_API_KEY env var missing")

    endpoint = f"{base}/v2/inference"
    headers  = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model_id": model,
        "parameters": {"temperature": temperature},
        "input": {
            "messages": messages,
        },
    }

    r = requests.post(endpoint, headers=headers, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"watsonx responded {r.status_code}: {r.text[:200]}")

    data = r.json()
    return data["results"][0]["generated_text"].strip()


# --------------------------------------------------------------------------- #
#  Back-end: Ollama
# --------------------------------------------------------------------------- #
def _call_ollama(messages, model, temperature):  # noqa: D401
    base = os.getenv("OLLAMA_URL", "http://localhost:11434")
    endpoint = f"{base}/v1/chat/completions"
    payload = {
        "model": model,
        "temperature": temperature,
        "messages": messages,
    }

    r = requests.post(endpoint, json=payload, timeout=60)
    if r.status_code != 200:
        raise RuntimeError(f"Ollama responded {r.status_code}: {r.text[:200]}")
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()
