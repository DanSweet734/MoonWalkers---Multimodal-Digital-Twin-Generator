# Local data (not committed)

Everything in this folder except this README is gitignored: test photos, PDFs, model weights,
generated meshes, and `.usd` outputs. Keep it organized so every run can be repeated.

```
data/
  machines/
    haas-ha5c/
      inputs/
        photos/          # machine photos (input type 2)
        documents/       # manuals, drawings, brochures (PDF)
        SOURCES.md       # one line per file: filename, source URL, date retrieved, license note
      runs/
        2026-10-20_run-001/
          pipeline_result.json
          twin_record.json
          meshes/        # generator output (GLB/OBJ)
          twin.usda      # exported twin
          RUN.md         # versions, settings, time taken, success level, reviewer notes
  kb/                    # the proof-of-concept knowledge base store (JSON/SQLite)
  models/                # downloaded model weights, if not in the Hugging Face cache
```

Rules:
- Every input file gets a line in its machine's `SOURCES.md`.
- Never edit an input in place; save processed versions under `runs/`.
- Machine folder names are lowercase `manufacturer-model` (this matches `TwinRecord.machine_key`).
