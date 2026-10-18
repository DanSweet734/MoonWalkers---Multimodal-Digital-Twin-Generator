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
        2026-10-17_run-003/   # one build per run folder (Pipeline B, decision 0012)
          request.json        # the JobRequest: the photo as a source
          generator/          # job.json, generator.log, result.json, mesh.glb; run.json records the run
          inspect_raw/        # renders of the generated mesh (also inspect_oriented/, preview/)
          geometry_spec.json  # how to orient, split and scale the mesh; cited by the twin
          meshes/             # body.glb, spindle.glb (twin frame, metres); assembly.json records them
          twin.usdc           # exported twin (binary USD)
          checks/             # spin.usdc, quarter_turn.usdc for the Isaac Sim check
          twin_record.json    # copies of what the knowledge base stored
          pipeline_result_b.json
          request.job_result.json  # what the request returned (one per request file)
          RUN.md              # versions, settings, time taken, success level, reviewer notes
  kb/                    # the proof-of-concept knowledge base (JSON files, decision 0008)
    results/<result_id>.json
    twins/<manufacturer>/<model>/v0001.json
  models/                # downloaded model weights, if not in the Hugging Face cache
```

The generator's environment and weights live outside the repository (`C:\mw-gen` on Daniel's
machine, `docs/setup/generators.md`). The HA5C's reference facts, short cited quotes, are committed
in `backend/src/moonwalkers/pipelines/b/haas_ha5c.reference.json`.

Rules:
- Every input file gets a line in its machine's `SOURCES.md`.
- Never edit an input in place; save processed versions under `runs/`.
- Machine folder names are the machine key with "/" replaced by "-": key `haas/ha5c` (the
  `TwinRecord.machine_key`) gives folder `haas-ha5c` (decision 0009).
- Never edit files under `kb/` by hand; only the orchestrator writes there.
- Never change a run folder's outputs: a stored twin points at them. To build again, start a new run
  folder (Pipeline B refuses to overwrite one).
