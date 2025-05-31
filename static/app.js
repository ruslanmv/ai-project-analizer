/* app.js – wizard logic */
document.addEventListener("DOMContentLoaded", () => {
  const dropzone = document.querySelector(".dropzone");
  const input    = document.querySelector("#fileInput");
  const progress = document.querySelector("progress");
  const results  = document.querySelector("#results");
  let file;       // currently selected File object
  let jobId;      // uuid from backend

  // ---------- Drag & Drop ----------
  ["dragenter", "dragover"].forEach(evt =>
    dropzone.addEventListener(evt, e => {
      e.preventDefault(); e.stopPropagation();
      dropzone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach(evt =>
    dropzone.addEventListener(evt, e => {
      e.preventDefault(); e.stopPropagation();
      dropzone.classList.remove("dragover");
    })
  );
  dropzone.addEventListener("drop", e => {
    file = e.dataTransfer.files[0];
    input.files = e.dataTransfer.files;   // keep <input> in sync
    dropzone.textContent = `📦  ${file.name}`;
  });

  // ---------- Browse click ----------
  dropzone.addEventListener("click", () => input.click());
  input.addEventListener("change", () => {
    file = input.files[0];
    dropzone.textContent = `📦  ${file.name}`;
  });

  // ---------- Submit ----------
  document.querySelector("button").addEventListener("click", async () => {
    if (!file) { alert("Choose a .zip first"); return; }

    const form = new FormData();
    form.append("file", file);

    const res = await fetch("/analyse", { method: "POST", body: form });
    const json = await res.json();
    jobId = json.job_id;

    // Start SSE stream
    const es = new EventSource(`/events/${jobId}`);
    es.onmessage = ev => {
      if (ev.data.startsWith("event:")) {
        progress.value += 10;             // naive progress
      }
      if (ev.data === "event:WORKFLOW_DONE") {
        progress.value = 100;
        es.close();
        fetch(`/result/${jobId}`)
          .then(r => r.json())
          .then(data => showResults(data));
      }
      if (ev.data.startsWith("error:")) {
        es.close();
        alert(ev.data);
      }
    };
  });

  function showResults(data) {
    document.querySelector(".wizard").style.display = "none";
    const { tree_text, file_summaries, project_summary } = data;

    const treePre = document.createElement("pre");
    treePre.textContent = tree_text;
    results.append(treePre);

    const list = document.createElement("ul");
    file_summaries.forEach(f => {
      const li = document.createElement("li");
      li.textContent = `${f.rel_path} (${f.kind}) – ${f.summary}`;
      list.append(li);
    });
    results.append(list);

    const p = document.createElement("p");
    p.textContent = project_summary;
    results.append(p);
  }
});
