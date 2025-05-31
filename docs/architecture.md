
# Architecture & Event-Flow

This document provides a deeper dive into how the multi-agent workflow is structured,
including a sequence diagram, event definitions, and notes on extending the system.

---

## 1. Sequence Diagram (Mermaid)

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant WebAPI as FastAPI
    participant BeeAI
    participant V as ZipValidator
    participant E as Extractor
    participant T as TreeBuilder
    participant R as FileTriage
    participant A as FileAnalysis
    participant S as SummarySynth
    participant C as Cleanup

    User ->> WebAPI: POST /analyse (ZIP)
    WebAPI ->> BeeAI: emit NewUpload
    BeeAI ->> V: NewUpload
    V -->> BeeAI: ZipValid / ZipInvalid
    alt ZipInvalid
      BeeAI ->> WebAPI: emit error event
      WebAPI -->> User: SSE "error:ZipInvalid"
    else ZipValid
      BeeAI ->> E: ZipValid
      loop For each file in ZIP
        E -->> BeeAI: FileDiscovered
      end
      E -->> BeeAI: ExtractionDone

      BeeAI ->> T: FileDiscovered*
      BeeAI ->> R: FileDiscovered*

      loop For each path from FileTriage
        R ->> A: FileForAnalysis
        A -->> BeeAI: FileAnalysed
      end
      A -->> BeeAI: AnalysisComplete

      BeeAI ->> S: TreeBuilt + FileAnalysed*
      S -->> BeeAI: ProjectDraft
      S -->> BeeAI: SummaryPolished

      BeeAI ->> C: SummaryPolished
      C -->> BeeAI: CleanupDone
      BeeAI -->> WebAPI: emit WORKFLOW_DONE
      WebAPI -->> User: SSE "event:WORKFLOW_DONE"
    end
````

**Legend**

* `FileDiscovered*`: multiple events, one per file in the extracted archive.
* `FileAnalysed*`: multiple events, one per file passed to the analysis agent.

---

## 2. Event Definitions

| Event Type         | Producer                | Payload Fields                               | Notes                                                                 |
| ------------------ | ----------------------- | -------------------------------------------- | --------------------------------------------------------------------- |
| `NewUpload`        | FastAPI (`app.py`)      | `{ zip_path: str }`                          | Trigger to start analysis                                             |
| `ZipValid`         | ZipValidatorAgent       | `{ zip_path: str }`                          | Archive passed validation                                             |
| `ZipInvalid`       | ZipValidatorAgent       | `{ zip_path: str, reason: str }`             | Archive rejected early                                                |
| `FileDiscovered`   | ExtractionAgent         | `{ path: str }`                              | One event per extracted file                                          |
| `ExtractionDone`   | ExtractionAgent         | `{ base_dir: str }`                          | All files have been emitted                                           |
| `FileForAnalysis`  | FileTriageAgent         | `{ path: str, score: int }`                  | Path selected for deep analysis (based on priority)                   |
| `TriageComplete`   | FileTriageAgent         | `{}`                                         | No more `FileForAnalysis` will be emitted                             |
| `FileAnalysed`     | FileAnalysisAgent       | `{ rel_path: str, kind: str, summary: str }` | Summary for a single file                                             |
| `AnalysisComplete` | FileAnalysisAgent       | `{}`                                         | All queued files have been analysed                                   |
| `TreeBuilt`        | TreeBuilderAgent        | `{ tree_path: str }`                         | Directory tree text stored at `tree_path` in BeeAI memory             |
| `ProjectDraft`     | SummarySynthesizerAgent | `{ draft: str }`                             | Initial project summary (unpolished)                                  |
| `SummaryPolished`  | SummarySynthesizerAgent | `{ summary_path: str }`                      | Final polished summary stored at `summary_path` in BeeAI memory       |
| `CleanupDone`      | CleanupAgent            | `{}`                                         | Temporary files removed                                               |
| `WORKFLOW_DONE`    | BeeAI (all agents)      | (no payload)                                 | Aggregate signal used by WebAPI to notify the client that job is done |

---

## 3. Directory Layout Recap

```text
.
├── .dockerignore
├── .gitignore
├── .env.sample
├── beeai.yaml
├── Dockerfile
├── docker-compose.yml
├── README.md
├── install.sh
├── start.sh
├── requirements.txt
├── requirements_dev.txt
├── app.py
├── static/
│   ├── style.css
│   └── app.js
├── templates/
│   ├── upload.html
│   └── result.html
├── src/
│   ├── __main__.py
│   ├── config.py
│   ├── main.py
│   ├── workflows.py
│   ├── agents/
│   │   ├── zip_validator_agent.py
│   │   ├── extraction_agent.py
│   │   ├── tree_builder_agent.py
│   │   ├── file_triage_agent.py
│   │   ├── file_analysis_agent.py
│   │   └── summary_synthesizer_agent.py
│   ├── tools/
│   │   ├── file_io_tool.py
│   │   └── rich_printer_tool.py
│   └── utils/
│       ├── encoding_helper.py
│       └── language_detector.py
├── docs/
│   ├── api.md
│   └── architecture.md
└── tests/
    ├── test_zip_validator.py
    ├── test_file_analysis.py
    └── test_workflow_e2e.py
```

---

## 4. Extending or Modifying Agents

1. **Add a new agent module** in `src/agents/your_new_agent.py`.
2. **Declare** it in `beeai.yaml` and/or in `src/workflows.py`, specifying any `depends_on` relationships.
3. **Write unit tests** under `tests/` to cover both valid and invalid event flows for your agent.
4. **Update the HTML/JS** front-end only if you need to expose new event types or adjust progress logic.

---

## 5. Deployment Notes

* **Production**:

  * Build and run with Docker:

    ```bash
    docker build -t ai-analyser .
    docker run -p 8000:8000 -e BEEAI_MODEL="openai/gpt-4o-mini" ai-analyser
    ```
  * Or use `docker-compose up --build` to bring up the analyser and a local Ollama sidecar.

* **Scaling**:

  * Replace the in-memory `jobs` and `event_queues` in `app.py` with Redis or a message broker.
  * Switch BeeAI’s default SQLite memory store to PostgreSQL by setting `BEEAI_MEMORY_DSN`.

* **Security**:

  * Ensure the upload folder is not world-writable.
  * Restrict ZIP size via `ZIP_SIZE_LIMIT_MB` to prevent accidental DoS.


