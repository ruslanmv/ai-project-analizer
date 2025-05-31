
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

All five “Policy Filter” boxes in your architecture diagram are realized as inline conditional checks (using if statements) inside the existing agents:

PF1 in zip_validator_agent.py

PF2 in safe_extract() (called by extraction_agent.py)

PFloop in file_triage_agent.py

PolishStep in summary_synthesizer_agent.py (via generate_completion())

PFclean in extraction_agent.on_shutdown() (checking DELETE_TEMP_AFTER_RUN)

There is no separate “PolicyAgent” class or file. Instead, each agent contains its own local policy code. This approach keeps the workflow simple and avoids proliferating tiny “filter” agents—each policy is enforced right where it matters.
---

## 4  Extending the pipeline

1. Create a new agent in `src/agents/`.
2. Add it to `beeai.yaml` (and to `src/workflows.py`) with a proper `depends_on`.
3. Write unit tests under `tests/`.
4. Adjust front-end progress logic if you emit new event types.

*That’s it!*

