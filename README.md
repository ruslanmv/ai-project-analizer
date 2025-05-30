
# ai-project-analizer

`ai-project-analizer` is an end-to-end **multi-agent ZIP project explorer**.  
Upload a `.zip` (or point the CLI to one) and the system will:

* ✅ **Validate** the archive (size, CRC, Zip-Slip).  
* ✅ **Safely extract** it to a sandbox.  
* ✅ **Inventory** every file and render a colourised directory tree.  
* ✅ **Triage & parse** high-signal files (README, code, JSON/YAML …).  
* ✅ **Draft & polish** an executive summary with *IBM Watsonx .ai* (or an offline Ollama model).  
* ✅ **Stream events** in real time via SSE or the BeeAI CLI.  
* ✅ **Clean up** all temp artefacts under policy control.

---

## 1 · How it works ⚙️

```mermaid
flowchart TD
    U[User uploads ZIP & prompt] --> Plan[PlanningAgent<br/>watsonx.ai – drafts static BeeAI DAG]

    Plan --> PF1[[Policy Filter]]
    PF1 --> Py1[ExecutorAgent<br/>snippet #1 --> <br/>is_valid_zip]
    Py1 --> V{ZIP OK?}
    V -- no --> Err[ZipInvalid<br/>graceful JSON error] --> Z[Done]
    V -- yes --> Extract[ExtractionAgent<br/>“extract next”]

    Extract --> PF2[[Policy Filter]]
    PF2 --> Py2[ExecutorAgent<br/>snippet #2 --> safe_extract]
    Py2 --> FileEvents[/FileDiscovered* events/]

    FileEvents --> TreeBuilder[TreeBuilderAgent]
    TreeBuilder --> Out2[Tree text<br/>+ file list]
    Out2 --> L3[Context tokens<br/>BeeAI memory]

    L3 --> Pick[[FileTriageAgent<br/>selects next path]]
    Pick --> PFloop[[Policy Filter]]
    PFloop --> PyN[ExecutorAgent<br/>snippet #N --> summarise_path]
    PyN --> OutN[/FileAnalysed event/] --> L3

    L3 --> Synth[SummarySynthesizerAgent<br/>watsonx.ai draft]
    Synth --> PolishStep[[Policy Filter]]
    PolishStep --> Polish[ExecutorAgent<br/>snippet --> polish text]
    Polish --> SummaryPolished[/SummaryPolished event/]

    SummaryPolished --> PFclean[[Policy Filter]]
    PFclean --> Clean[ExecutorAgent<br/>snippet --> shutil.rmtree tmp]
    Clean --> CleanupDone[/CleanupDone event/]

    CleanupDone --> Z[Deliverables:<br/>• directory tree<br/>• per-file blurbs<br/>• polished summary]
````

Under the hood each **blue box** is a Python snippet executed by `ExecutorAgent` in a fresh namespace; every snippet passes through a **PolicyFilter** before it runs.

---

## 2 · Features ✨

| Pillar                    | What you get                                                                                 |
| ------------------------- | -------------------------------------------------------------------------------------------- |
| **BeeAI orchestration**   | Agents exchange typed events; you can plug/replace any stage.                                |
| **Watsonx / Ollama LLM**  | Choose cloud Watsonx models or a local Ollama model for full offline mode.                   |
| **Security by design**    | Zip-Slip guard, size quota, CRC check, per-snippet policy gate.                              |
| **Live streaming**        | FastAPI streams Server-Sent Events you can render in any browser.                            |
| **Artefact traceability** | `project_tree.txt`, `file_summaries.json`, `draft.txt`, `project_summary.txt` saved per run. |

---

## 3 · Repository layout 🗂️

```text
src/
├─ agents/              # all BeeAI agents (planner, validator, extractor, …)
├─ tools/               # reusable helpers (zip, Rich tree, snippet builder)
├─ utils/               # encoding + language heuristics
├─ workflows.py         # imperative BeeAI DAG
app.py                  # FastAPI front-end (POST /analyse, /health)
start.sh                # Unix entry-point
tests/                  # pytest suite incl. e2e run
```

---

## 4 · Configuration 🗝️

Copy `.env.sample` to `.env` and fill in credentials:

```ini
# Choose the LLM backend:  watsonx   |   ollama
LLM_BACKEND=watsonx

# Watsonx (needed if LLM_BACKEND=watsonx)
WATSONX_PROJECT_ID=***
WATSONX_API_KEY=***
WATSONX_API_URL=https://us-south.ml.cloud.ibm.com
WATSONX_MODEL_ID=ibm/granite-13b-instruct-v2

# Ollama (needed if LLM_BACKEND=ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL_ID=granite:8b-chat
OLLAMA_AUTO_PULL=1            # pull model automatically if missing
```

> **Tip:** set `LLM_BACKEND=ollama` for a completely air-gapped install—no external calls.

---

## 5 · Installation & quick start 🛠️

```bash
git clone https://github.com/ruslanmv/ai-project-analizer.git
cd ai-project-analizer
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### Local Ollama example

```bash
# 1 · Install & start daemon
curl -fsSL https://ollama.ai/install.sh | sh
ollama serve &

# 2 · Pull Granite 8-B model once
ollama pull granite:8b-chat
```

### Run the CLI

```bash
python -m src samples/toy.zip
```

### Run the FastAPI service

```bash
./start.sh               # starts uvicorn on :8000
```

Open [http://localhost:8000/docs](http://localhost:8000/docs) to test `POST /analyse`.

---

## 6 · Developer guide 👩‍💻

```bash
# lint, type-check, test
pip install -r requirements_dev.txt
ruff check .
mypy src
pytest -q
```

* **Add a new agent:** subclass `beeai.Agent`, emit/consume events, add it to `workflows.py` and `beeai.yaml`.
* **Swap LLM:** just edit `.env`. Any 🤗 transformers model running in Ollama works.

---

## 7 · Roadmap 🚦

* [ ] Tar/GZip support
* [ ] Front-end progress bar
* [ ] Language-specific skeleton analysis (package.json, pyproject)

---

## 8 · License 📄

MIT — see `LICENSE`.

---

## 9 · Acknowledgements 🤝

Built with [BeeAI](https://beeai.dev) and [IBM Watsonx.ai](https://www.ibm.com/watsonx).

