
# REST API Contract

> Base URL when running locally via `uvicorn app:app` is  
> `http://localhost:8000`

---

## 1 POST /analyse

Upload a ZIP archive to initiate the analysis job.

- **Endpoint**: `/analyse`
- **Method**: `POST`
- **Content-Type**: `multipart/form-data`
- **Form Field**:
  - `file` (required): the `.zip` archive to analyse.

### Request Example

```http
POST /analyse HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data; boundary=----WebKitFormBoundaryXYZ

------WebKitFormBoundaryXYZ
Content-Disposition: form-data; name="file"; filename="my_project.zip"
Content-Type: application/zip

(binary content here)
------WebKitFormBoundaryXYZ--
````

### Successful Response (200)

```json
{
  "job_id": "21f53260f0e14ee8871be74f0fb9e4a4"
}
```

* `job_id` is a UUID string you will use to poll progress and fetch results.
* If the file is not a `.zip` or is rejected due to size limits, the server will respond with HTTP 400.

### Error Responses

* **400 Bad Request**

  * Occurs if the uploaded file is missing, not a `.zip`, or exceeds configured size limits.
  * Example error body:

    ```json
    { "detail": "Only .zip files are accepted" }
    ```
* **500 Internal Server Error**

  * Unexpected server-side error during upload or job scheduling.

---

## 2 GET /events/{job\_id}

Subscribe to a Server-Sent Events (SSE) stream that emits progress updates as the multi-agent workflow proceeds.

* **Endpoint**: `/events/{job_id}`
* **Method**: `GET`
* **Response**:

  * **Content-Type**: `text/event-stream`
  * Streamed plain-text messages in SSE format.

### Messages

Each SSE “data” line is a simple string in one of these two forms:

1. **Progress Event**

   ```
   data: event:<BeeAI-event-type>
   ```

   * `<BeeAI-event-type>` might be one of:

     * `ZipValid`
     * `FileDiscovered`
     * `TreeBuilt`
     * `FileForAnalysis`
     * `FileAnalysed`
     * `ProjectDraft`
     * `SummaryPolished`
     * etc.
   * On each such event, the front-end can update a progress bar or log the agent name.

2. **Workflow Done**

   ```
   data: event:WORKFLOW_DONE
   ```

   * Indicates the entire analysis pipeline has finished. After this, you should close the SSE connection and fetch the final results from `/result/{job_id}`.

3. **Error**

   ```
   data: error:<error message>
   ```

   * If an unrecoverable error occurs in any agent, you will see `error:` followed by a brief description. The SSE stream may then terminate.

### Example SSE Stream

```
HTTP/1.1 200 OK
Content-Type: text/event-stream

data: event:ZipValid

data: event:FileDiscovered
data: event:FileDiscovered
data: event:FileDiscovered

data: event:ExtractionDone

data: event:TreeBuilt

data: event:FileForAnalysis
data: event:FileAnalysed
data: event:FileForAnalysis
data: event:FileAnalysed

data: event:ProjectDraft

data: event:SummaryPolished

data: event:WORKFLOW_DONE
```

---

## 3 GET /result/{job\_id}

Retrieve the final JSON artefacts once the workflow is complete.

* **Endpoint**: `/result/{job_id}`
* **Method**: `GET`
* **Response Content-Type**: `application/json`

### Success Response (200)

When the job is finished, you receive:

```json
{
  "tree_text": "ai-project-analizer/\n  Dockerfile\n  README.md\n  src/\n    agents/\n      zip_validator_agent.py\n      extraction_agent.py\n      …\n    tools/\n      file_io_tool.py\n      rich_printer_tool.py\n    utils/\n      encoding_helper.py\n      language_detector.py\n  static/\n    style.css\n    app.js\n  templates/\n    upload.html\n    result.html\n  docs/\n    api.md\n    architecture.md\n",
  "file_summaries": [
    {
      "rel_path": "README.md",
      "kind": "text",
      "summary": "AI Project-Analizer is a multi-agent system that turns a ZIP into summaries"
    },
    {
      "rel_path": "src/agents/zip_validator_agent.py",
      "kind": "python",
      "summary": "Python module with ZipValidatorAgent: checks MIME, CRC, size"
    },
    {
      "rel_path": "src/agents/extraction_agent.py",
      "kind": "python",
      "summary": "Python module with ExtractionAgent: safe_extract ZIP, emits FileDiscovered"
    },
    {
      "rel_path": "src/agents/tree_builder_agent.py",
      "kind": "python",
      "summary": "Python module with TreeBuilderAgent: builds Rich tree, emits TreeBuilt"
    },
    {
      "rel_path": "src/agents/file_triage_agent.py",
      "kind": "python",
      "summary": "Python module with FileTriageAgent: priority_score, skip binary assets"
    },
    {
      "rel_path": "src/agents/file_analysis_agent.py",
      "kind": "python",
      "summary": "Python module with FileAnalysisAgent: parse JSON/YAML/AST, summarise"
    },
    {
      "rel_path": "src/agents/summary_synthesizer_agent.py",
      "kind": "python",
      "summary": "Python module with SummarySynthesizerAgent: synthesise project overview"
    },
    {
      "rel_path": "src/tools/file_io_tool.py",
      "kind": "python",
      "summary": "Helpers: safe_extract, looks_binary, priority_score"
    },
    {
      "rel_path": "src/tools/rich_printer_tool.py",
      "kind": "python",
      "summary": "Helpers: render_tree with Rich (or ASCII fallback)"
    },
    {
      "rel_path": "src/utils/encoding_helper.py",
      "kind": "python",
      "summary": "Helpers: read_text_safe with chardet fallback"
    },
    {
      "rel_path": "src/utils/language_detector.py",
      "kind": "python",
      "summary": "Helpers: guess_stack, detect_dominant_language, synthesise_project"
    },
    {
      "rel_path": "app.py",
      "kind": "python",
      "summary": "FastAPI service with /analyse, /events/{id}, /result/{id}, /health"
    },
    {
      "rel_path": "static/style.css",
      "kind": "text",
      "summary": "CSS for drag-drop wizard, progress bar, preformatted tree"
    },
    {
      "rel_path": "static/app.js",
      "kind": "javascript",
      "summary": "Front-end logic: drag-drop, SSE, fetch /result, render output"
    },
    {
      "rel_path": "templates/upload.html",
      "kind": "html",
      "summary": "Jinja2 template: upload wizard + placeholders for progress/results"
    },
    {
      "rel_path": "templates/result.html",
      "kind": "html",
      "summary": "Jinja2 template: standalone results viewer"
    }
  ],
  "project_summary": "AI Project-Analizer is a multi-agent BeeAI application. The dominant file type is python (count: 12). Inferred tech stack: Python package. Presence of a Dockerfile suggests containerized deployment."
}
```

* `tree_text`: A newline-encoded ASCII (or Rich-exported) tree of the entire project.
* `file_summaries`: Array of `{ rel_path, kind, summary }` for each analysed file.
* `project_summary`: A short human-readable paragraph describing the repository.

### Running State Response

If the workflow has not yet finished, you receive:

```json
{ "status": "running" }
```

---

## 4 GET /health

A simple health check endpoint.

* **Endpoint**: `/health`
* **Method**: `GET`
* **Response (200)**:

```json
{ "status": "ok" }
```

---

### Error Codes Summary

| Status | Description                                                 |
| ------ | ----------------------------------------------------------- |
| 400    | Bad request (e.g., non-ZIP upload or size limit exceeded)   |
| 404    | Unknown `job_id` for `/events/{id}` or `/result/{id}` calls |
| 500    | Internal server error                                       |

---

## How to Explore

FastAPI auto-generates OpenAPI docs. Once the server is running, visit:

* **Swagger UI**:
  [http://localhost:8000/docs](http://localhost:8000/docs)

* **ReDoc UI**:
  [http://localhost:8000/redoc](http://localhost:8000/redoc)

* **Raw OpenAPI JSON**:
  [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

