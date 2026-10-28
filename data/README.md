# Local data (not committed)

Everything in this folder except this README is gitignored: test photos, PDFs, model weights,
generated meshes, and `.usd` outputs. Keep it organized so every run can be repeated.

```
data/
  machines/
    haas-ha5c/
      inputs/
        photos/          # machine photos (input type 2); dashboard uploads are <local date>_<name>
        documents/       # manuals, drawings, brochures (PDF), saved web pages (HTML)
        SOURCES.md       # one line per file: filename, source URL, date retrieved, license note
      runs/
        2026-10-17_run-003/   # one build per run folder (Pipeline B, decision 0012); a job
          request.json        # the JobRequest: the photos as sources, with their views (0022)
          reference_facts.json      # the agent's cited reading notes (MCP builds, decision 0013)
          geometry_spec.parts.json  # the spec as the agent sets it: a spindle's joint and scale,
                                    # or a several-part spec's pieces (decision 0028)
          generator/          # job.json, generator.log, result.json, mesh.glb; run.json records the run
          inspect_raw/        # renders of the generated mesh (also inspect_oriented/, preview/;
                              # preview_parts/ for a several-part spec)
          geometry_spec.json  # how to orient, split and scale the mesh; cited by the twin
          meshes/             # body.glb, spindle.glb (twin frame, metres); assembly.json records them;
                              # a several-part spec gives one GLB per part (decision 0027)
          twin.usdc           # exported twin (binary USD)
          checks/             # spin.usdc, quarter_turn.usdc for the Isaac Sim check; a twin whose
                              # joints state behaviour gets one file per behaviour (0027)
          views/              # several parts: coloured views, the parts over each fed photo (0023)
          record_joints.py    # several parts: the joint recorder for the Isaac Sim check; it
                              # writes recordings/ beside the file opened (checks/recordings/)
          twin_record.json    # copies of what the knowledge base stored
          pipeline_result_b.json
          request.job_result.json  # what the request returned (one per request file)
          programs/<behaviour>/    # when the control behaviour carries a program (decision 0016)
          RUN.md              # versions, settings, time taken, success level, reviewer notes
      pipeline_tries/
        2026-10-23_d.json     # one pipeline's result on some inputs, stored nowhere else
                              # (python -m moonwalkers.pipelines run ... --out, decision 0021)
      part_cutting/
        2026-10-24_spike/     # the drill-press plan's Phase 4 spike on cutting a mesh into parts
                              # (python -m moonwalkers.pipelines.b.part_spike): report.md,
                              # results.json, coloured views, the cuts drawn over the photos
        2026-10-27_spec/      # Phase 5: the script that writes the T33901's several-part spec,
                              # and the specs it wrote (README.md there)
      programs/
        2026-10-18_ha5c-manual-example-5-subroutine_v3/   # a program run on a stored twin:
          program.usdc, run_program.py, program_native.usdc,   # python -m moonwalkers.control run
          program.json, trajectory.json, PROGRAM.md
  kb/                    # the proof-of-concept knowledge base (JSON files, decision 0008)
    results/<result_id>.json
    twins/<manufacturer>/<model>/v0001.json
    reviews/<manufacturer>/<model>/v0001/r0001.json   # a person's review of a version (0015)
  models/                # downloaded model weights, if not in the Hugging Face cache
```

A run folder with `request.json` is a **job**. The dashboard and the agent's `list_jobs` tool
read its stage from the files above (decision 0014, `moonwalkers/workspace/status.py`). A photo
uploaded in the dashboard is saved under `inputs/photos/` with its `SOURCES.md` line, and starts a
new run folder.

The generator's environment and weights live outside the repository (`C:\mw-gen` on Daniel's
machine, `docs/setup/generators.md`). The HA5C's reference facts, short cited quotes, are committed
in `backend/src/moonwalkers/pipelines/b/haas_ha5c.reference.json`.

Rules:
- Every input file gets a line in its machine's `SOURCES.md` (the API adds one for each upload).
- Never edit an input in place; save processed versions under `runs/`.
- Machine folder names are the machine key with "/" replaced by "-": key `haas/ha5c` (the
  `TwinRecord.machine_key`) gives folder `haas-ha5c` (decision 0009).
- Never edit files under `kb/` by hand; only the orchestrator writes there, reviews included.
- The files here are copyrighted by their owners and kept for internal research only. The API
  serves them only on this computer (127.0.0.1); never expose it on a network.
- Never change a run folder's outputs: a stored twin points at them. To build again, start a new run
  folder (Pipeline B refuses to overwrite one).
