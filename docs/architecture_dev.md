
# Architecture & Event-Flow

This document provides a deeper dive into how the multi-agent workflow is structured,
including a sequence diagram, event definitions, and notes on extending the system.

---

## 1  Sequence diagram

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
        BeeAI ->> WebAPI: emit error
        WebAPI -->> User: SSE error
    else ZipValid
        BeeAI ->> E: ZipValid
        loop each file
            E -->> BeeAI: FileDiscovered
        end
        E -->> BeeAI: ExtractionDone
        BeeAI ->> T: FileDiscovered*
        BeeAI ->> R: FileDiscovered*
        R ->> A: FileForAnalysis*
        A -->> BeeAI: FileAnalysed*
        A -->> BeeAI: AnalysisComplete
        BeeAI ->> S: TreeBuilt + FileAnalysed*
        S -->> BeeAI: ProjectDraft
        S -->> BeeAI: SummaryPolished
        BeeAI ->> C: SummaryPolished
        C -->> BeeAI: CleanupDone
        BeeAI -->> WebAPI: event WORKFLOW_DONE
        WebAPI -->> User: SSE WORKFLOW_DONE
    end
````

**Legend**

* `FileDiscovered*`: multiple events, one per file in the extracted archive.
* `FileAnalysed*`: multiple events, one per file passed to the analysis agent.

---

## 2  Event catalogue

| Event type         | Producer     | Payload                       |
| ------------------ | ------------ | ----------------------------- |
| `NewUpload`        | WebAPI       | `zip_path`                    |
| `ZipValid`         | ZipValidator | `zip_path`                    |
| `ZipInvalid`       | ZipValidator | `reason`                      |
| `FileDiscovered`   | Extractor    | `path`                        |
| `ExtractionDone`   | Extractor    | `base_dir`                    |
| `TreeBuilt`        | TreeBuilder  | `tree_path`                   |
| `FileForAnalysis`  | FileTriage   | `path`, `score`               |
| `TriageComplete`   | FileTriage   | —                             |
| `FileAnalysed`     | FileAnalysis | `rel_path`, `kind`, `summary` |
| `AnalysisComplete` | FileAnalysis | —                             |
| `ProjectDraft`     | SummarySynth | `draft`                       |
| `SummaryPolished`  | SummarySynth | `summary_path`                |
| `CleanupDone`      | Cleanup      | —                             |

---

## 3  Directory layout

```text
src/
  agents/  (zip_validator_agent.py … summary_synthesizer_agent.py)
  tools/   (file_io_tool.py, rich_printer_tool.py)
  utils/   (encoding_helper.py, language_detector.py, llm_router.py)
static/    (style.css, app.js)
templates/ (upload.html, result.html)
docs/      (architecture.md, api.md)
```

---

## 4  Extending the pipeline

1. Create a new agent in `src/agents/`.
2. Add it to `beeai.yaml` (and to `src/workflows.py`) with a proper `depends_on`.
3. Write unit tests under `tests/`.
4. Adjust front-end progress logic if you emit new event types.

*That’s it!*

