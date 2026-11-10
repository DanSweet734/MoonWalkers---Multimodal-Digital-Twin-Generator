# MoonWalkers tool guide

Every tool the platform uses, by the name you will hear it called: what it is, what it does for
us, what goes in and what comes out. The diagrams of how they fit together are in
[how-a-twin-is-built.md](how-a-twin-is-built.md).

Written on 2026-11-02. Versions are from `backend/uv.lock`, `dashboard/package.json` and the setup
guides named in each row.

**Contents**
1. [Outside software](#outside-software)
2. [Our own modules](#our-own-modules)
3. [The agent's 26 MCP tools](#the-agents-26-mcp-tools)
4. [Commands people run](#commands-people-run)
5. [Scripts that run inside Isaac Sim](#scripts-that-run-inside-isaac-sim)

## Outside software
| Tool | What it is | What it does for us | In | Out | Version and source |
|---|---|---|---|---|---|
| **Claude Code** | Anthropic's AI coding agent | It is the platform's agent. It reads the documents, records cited facts, inspects the mesh, writes the geometry spec, and builds the twin through our MCP tools (decision 0003; confirmed by the advisors on 2026-10-22) | A person's request, documents, photos, tool results | Calls to our MCP tools, and cited notes and specs in the run folder | `.mcp.json`; `docs/agent-procedure.md` |
| **MCP** (Model Context Protocol) **Python SDK** | A standard way for an AI agent to call a program's functions | Gives Claude Code our 26 tools | Tool calls with typed arguments | Typed results, or a readable error | `mcp` 2.3.0 (decision 0013) |
| **Hunyuan3D-2mv** and **Hunyuan3D-2** | Tencent's image-to-3D models | Turn the machine's photos into one 3D mesh. The multi-view model takes 2-4 photos with their views; the single-image model takes 1 | Photos, each in a slot (front, left, back, right) | `mesh.glb`, untextured, in its own axes and units | hy3dgen 2.0.2, commit f8db630, under the Tencent Hunyuan 3D 2.0 Community License; installed in `C:\mw-gen`, its own Python environment (`docs/setup/generators.md`) |
| **PyTorch** | A machine-learning framework that runs models on the GPU | Runs the Hunyuan3D models on the RTX 4090 | Model weights, prepared photos | The mesh, through the generator | torch 2.8.0 for CUDA 12.6, with diffusers 0.35.2 and transformers 4.57.1, in the generator's environment (`docs/setup/generators.md`, "Installed versions") |
| **Hugging Face Hub** (`hf`) | Hugging Face's model hosting and its download tool | Downloads the Hunyuan3D weights once, and checks their SHA-256 | A model name | The weight files in `C:\mw-gen\models\` | huggingface-hub 0.36.0 (`docs/setup/generators.md`) |
| **rembg** | A background remover | Cuts the machine out of each photo before the generator sees it | A photo | The photo with its background removed | rembg 2.0.68, in the generator's environment (`docs/setup/generators.md`) |
| **OpenUSD** (usd-core, `pxr`) | Pixar's scene format, with its physics schema UsdPhysics | Writes and reads the twin: parts, joints, drives, limits and couplings that Isaac Sim simulates | Our parts and joints in SI units | `twin.usdc` and check files (binary `.usdc` or text `.usda`) | `usd-core` 26.8 (decision 0010) |
| **NVIDIA Isaac Sim** (with PhysX) | NVIDIA's robotics simulator on Omniverse | Where a person checks that the twin moves and is controlled as the manual says | A `.usdc` file, plus our runner and recorder scripts | What the person sees, and recordings of every joint | Isaac Sim Full 6.2.0, Kit 110.4.0, build 386251 (`docs/setup/isaac-sim-check.md`) |
| **NVIDIA Omniverse Asset Validator** | NVIDIA's checker for USD files | A second check of every twin file, besides ours | A `.usd` file | Errors and warnings, or "No issues found." | `omniverse-asset-validator` 1.18.0 (`omni_asset_validate`) |
| **trimesh** and **NumPy** | Python mesh and maths libraries | Orient, measure, cut, patch and scale the generated mesh, and mesh the stand-ins | Meshes, cut shapes | Part meshes (GLB), measurements, PNG views | `trimesh` 5.1.1, `numpy` 2.5.4 |
| **pypdf** | A PDF text reader | Reads manuals and checks that every quote is on its cited page | A PDF | Each page's text | `pypdf` 6.21.1 |
| **pypdfium2** | A PDF renderer (Google's PDFium) | Renders manual pages and figures so they can be read, for example exploded views and speed charts | A PDF page | A PNG | `pypdfium2` 5.14.0 (installed on 2026-10-22) |
| **Pydantic** | Python data models with validation | The shared contract (`PipelineResult`) and every spec is a checked model, so bad input is refused with a reason | JSON | Checked objects, or a validation error | `pydantic` 2.14.1 |
| **FastAPI** and **uvicorn** | A Python web framework and server | The API behind the dashboard, on 127.0.0.1 only | HTTP requests | JSON, files, and the built dashboard | `fastapi` 0.146.0, `uvicorn` 0.54.0 (decision 0014) |
| **React**, **Vite**, **TypeScript**, **Oxlint** | Web UI library, build tool, typed JavaScript, linter | The dashboard: upload photos, see jobs and twins with their sources, approve or reject a version | What a person clicks and uploads | Pages, and requests to the API | React 19.2, Vite 8.3, TypeScript 6.0, Oxlint 1.81 (decision 0007) |
| **Node.js** and **npm** | JavaScript runtime and package manager | Install and build the dashboard, and run its tests | `package.json`, `package-lock.json` | `dashboard/dist/`, which the API serves | Node.js 24.20.0 with npm 11.19.0 (`docs/setup/windows-dev-setup.md`) |
| **pytest** and **Ruff** | Python test runner and linter/formatter | Run 696 quick tests and keep the code consistent | The code | Pass or fail; lint findings | `pytest` 9.1.1, `ruff` 0.17.1 |
| **uv** | A Python package and environment manager | Installs the backend's exact versions from `uv.lock` | `pyproject.toml`, `uv.lock` | `backend/.venv` (Python 3.12.15) | uv 0.13.1 (`docs/setup/windows-dev-setup.md`) |
| **Git**, **GitHub**, **GitHub CLI** | Version control, hosting, command line | Branches, pull requests and reviews of every phase | Commits | The repository's history and PRs | GitHub CLI 2.102.0 (`docs/setup/windows-dev-setup.md`) |

## Our own modules
All in `backend/src/moonwalkers/` (Python 3.12) except the dashboard.

### Shared platform
| Module | What it does | In | Out |
|---|---|---|---|
| `contracts` (`pipeline_result.py`, `json_schema.py`) | The contract every pipeline returns (`PipelineResult`, v0.2.0): sources, identity, facts, parts, joints, control behaviours and issues, all cited. `json_schema.py` writes it as a JSON Schema for the teammates | What a pipeline found | A checked result; `pipeline_result.schema.json` |
| `workspace` | The data folder as the shared workspace of the agent and the dashboard: run folders are jobs, and their files say how far each has got | Uploads, run folders | Job lists, saved inputs, status |
| `api` | The dashboard's API: jobs, twins, sources, reviews and files (decision 0014). `security.py` keeps it to this computer (it answers on 127.0.0.1 only and checks each request's host); `typescript.py` writes the dashboard's types from its schema, so they are never copied by hand | HTTP requests | JSON and files; `dashboard/src/api/types.gen.ts` |
| `dashboard/` (React) | The web pages people use | Clicks, uploads | Jobs started, reviews recorded |
| `mcp` (with `reports.py`) | The MCP server that gives Claude Code its 26 tools ([below](#the-agents-26-mcp-tools)); `reports.py` defines what each tool returns | Tool calls | Run folders, notes, specs, builds |
| `orchestrator` (with `router.py`, `photos.py`) | Sends each input to its pipeline, then reuses a stored twin or stores a new version and has it exported. It is the only writer to the knowledge base | A job's request | A twin version, or the reused one |
| `kb` (`json_store.py`, `keys.py`, `reviews.py`) | The knowledge base: one JSON file per record, behind an interface Neo4j can replace (decisions 0005, 0008). `keys.py` turns a maker and model into one key, aliases included; `reviews.py` keeps people's approvals and rejections as append-only records (decision 0015) | Results, twin versions, reviews | The same, by machine key (`grizzly/t33901`) |
| `pipelines` (A, C, D; `fixture_stub.py`, `cli.py`) | The teammates' pipelines: nameplates and data sheets (A, Ava), drawings and schematics (C, Kiran), catalogs and online resources (D, Sarkis). Until theirs are in, `fixture_stub.py` stands in for them in the tests only, and `cli.py` lets an owner run theirs alone (decision 0021) | Their input types | A `PipelineResult` each |

### Pipeline B: photos to a jointed twin (`pipelines/b/`)
| Module | What it does | In | Out |
|---|---|---|---|
| `photos.py` | Picks which photos feed the generator, in which slot, from their views (decision 0022) | The run's photos and views | Generator slots |
| `generators/` (`hunyuan3d.py`, `subprocess_job.py`, `scripts/hunyuan3d_shape_job.py`) | Runs the image-to-3D model in its own environment: a JSON job goes in to the generator's Python, a JSON result comes back, so its libraries never mix with ours. It first turns each photo upright and cuts the machine out (automatically, or by the photo's SAM box, crop box or drawn mask; decision 0029) | Photos, with any cut-outs | `generator/mesh.glb` and a record of versions |
| `inspection.py`, `mesh_tools.py` | Orient the mesh and measure it: extents, round parts, PNG views | `mesh.glb`, up/front axes | Measurements and views |
| `parts_spec.py` | The geometry spec of several parts: frame, cuts, parts, stand-ins, joints, scale, size checks, all cited (decisions 0023, 0027) | `geometry_spec.json` | A checked spec |
| `part_cuts.py` | Cuts the mesh into parts by the spec's ordered list of shapes | Mesh, cut list | One mesh per part |
| `stand_ins.py` | Builds labelled stand-in shapes where the mesh hides or gets a part wrong (a table with T-slots, a chuck, handles) | Cited sizes | Stand-in meshes |
| `photo_marks.py`, `part_views.py` | Place each photo on the mesh by its silhouette, and draw the parts over it, so a reviewer can compare | Photos, parts | PNG views |
| `assemble.py`, `pipeline.py` | Put it together: scale by a cited length, check sizes, cite every part and joint | Mesh, spec, reference facts | A `PipelineResult` |
| `quotes.py` | Checks every quote in a reference file against its cited PDF page | Reference and spec files | Found, elsewhere or not found, per quote |
| `build.py`, `cli.py` | Build a run folder through the orchestrator, with its check files, programs and `RUN.md` | A run folder | A stored twin version and its files |
| `part_spike.py`, `mesh_segments.py`, `synthetic_parts.py` | Phase 4's comparison of four ways to cut a mesh into parts, scored on a synthetic drill press whose right answer is known face by face (decision 0023) | A mesh, or the synthetic one | Scores and views (`docs/research/2026-10-24-part-cutting-spike.md`) |

### Export and validation (`usd/`)
| Module | What it does | In | Out |
|---|---|---|---|
| `exporter.py` | Writes the twin as OpenUSD. The contract says what the machine does; the exporter decides how to simulate it: drives, springs, locks, depth stops, couplings (decisions 0010, 0017-0020, 0025) | Results, twin record | `twin.usdc`, check files |
| `mesh_files.py`, `geometry.py`, `frames.py`, `units.py` | Helpers: read a part's GLB or OBJ, mesh boxes and cylinders, turn joint frames, and convert SI units to the stage's at the export boundary | Meshes, shapes, axes | Points and frames in stage units |
| `physx_schemas.py` | Writes NVIDIA's PhysX attributes that usd-core does not define: mimic couplings, start positions, the joint speed cap, staying awake | Joints | PhysX attributes |
| `validate.py` | Our checker: structure, units, joints, frames, drives | A `.usd` file | Errors, warnings, infos |
| `isaac_recorder.py` | The joint recorder, copied into run folders as `record_joints.py` | (runs in Isaac Sim) | CSV recordings |
| `primitive_twin.py`, `primitive_drill_press.py` | Box-and-cylinder test twins that proved the exporter before any generated mesh | Cited sizes | Test twins and check files |

### Control logic (`control/`)
| Module | What it does | In | Out |
|---|---|---|---|
| `program.py`, `interpreter.py` | The HA5C's step table (S, F, L, G) and its interpreter: moves with acceleration, the CNC relay, waits for cycle start (decisions 0016, 0026) | A program from the manual | A trajectory of targets over time |
| `export.py`, `isaac_runner.py` | Write a program folder, and the runner that drives the joint in Isaac Sim | Twin, program | `program.usdc`, `run_program.py`, `PROGRAM.md` |
| `manual.py`, `isaac_controls.py` | A manual machine's controls: a switch, a speed table and the operator's commands, run by one controller in the tests and in Isaac Sim (decision 0025) | Three control behaviours | Plans per scenario; live control |
| `controls_export.py` | Writes the controls folder, with the controls in Isaac Sim's Property panel | Twin, behaviours | `controls.usdc`, `run_controls.py`, `PROGRAM.md` |
| `compare.py` | Measures a recording against its plan | Recording CSV, trajectory JSON | A table of measured against planned |

## The agent's 26 MCP tools
Claude Code calls these through the MCP server (`moonwalkers.mcp`). "Run" is a run folder, the
job. Read-only tools change nothing.

| # | Tool | Purpose | In | Out |
|---|---|---|---|---|
| 1 | `check_knowledge_base` (read-only) | See which twins exist | Maker and model, or nothing | That machine's versions, or every machine; whether the generator is set up |
| 2 | `request_twin` | Get an existing twin without building | Maker and model | The reused version (newest approved, else newest not rejected), and why |
| 3 | `list_jobs` (read-only) | Find jobs waiting for the agent, such as a dashboard upload | A machine, whether to include finished jobs | Open jobs, newest first, with what each needs next |
| 4 | `start_run` | Start a job | Maker, model, whether to build a new version | A run id |
| 5 | `add_input` | Add a machine photo | Run, file, source id, title, date, view, use | The source recorded, with its SHA-256 |
| 6 | `set_photo` | Correct a photo before generation: its view, its use, or how the machine is cut out of it (decision 0029) | Run, source id, view, use, cut-out (SAM box and points, crop box, or a drawn mask) | The source, and which photos the generator will get |
| 7 | `preview_cutouts` | See how the generator will cut the machine out of each photo, in seconds, without generating | Run | A PNG sheet of the cut-outs, and the share of each photo kept |
| 8 | `add_reference_source` | Record a document the facts come from | Run, URL, file or "user", title, date | The source recorded |
| 9 | `identify_machine` | Record the maker and model | Run, maker, model, aliases, citations | The notes so far |
| 10 | `add_fact` | Record one specification value | Run, key, value, SI unit, original text, citations | The notes so far |
| 11 | `add_control` | Record how the machine is controlled: a program, a switch, a speed table, the operator's commands; checked at once | Run, kind, spec, joints driven, citations | The notes so far |
| 12 | `add_issue` | Record a doubt, assumption or disagreement for the reviewer | Run, severity, message, what it concerns | The notes so far |
| 13 | `generate_geometry` | Turn the photos into a mesh (about a minute on the GPU), or reuse this run's | Run | The mesh, six PNG views, the expected turn |
| 14 | `inspect_geometry` | Orient and measure the mesh | Run, up and front axes, turn | Sizes, a spindle's axis, warnings, PNG views |
| 15 | `fit_circles` (read-only) | Find a round part's axis (a column, a quill, a hub) | Run, axis, slice positions | Circle centres and radii, and how round each is |
| 16 | `add_joint` | One moving part: define the spindle joint | Run, axis, radius, start, method | The spec's status |
| 17 | `set_scale` | One moving part: scale from the cited centre height | Run, base plane | The spec's status |
| 18 | `set_spec_frame` | Several parts: the mesh's axes, the origin, the fixed part | Run, axes, origin, fixed part, method | The spec's status |
| 19 | `set_cut_list` | Several parts: the ordered cut shapes | Run, cuts with notes | The spec's status |
| 20 | `set_spec_part` | Add or replace a part: cut, removed or a labelled stand-in | Run, part | The spec's status |
| 21 | `set_spec_joint` | Add or replace a joint, with its behaviour (driven, spring return, locked, free, follows) | Run, joint | The spec's status |
| 22 | `remove_spec_entry` | Take a part or joint out of the spec | Run, which, id | The spec's status |
| 23 | `set_scale_length` | Scale by any cited length | Run, fact, measured length, how | The spec's status |
| 24 | `set_size_checks` | Compare more cited lengths with the model | Run, checks | The spec's status |
| 25 | `preview_twin` | Try the spec without storing anything | Run | Parts, sizes, holes and PNG views to look at |
| 26 | `submit_twin` | Build and store the twin, or reuse it | Run | The twin version, its files, and the validators' findings |

## Commands people run
From `backend/` with `uv run python -m ...`; CLAUDE.md lists them all.

| Command | What it does | In | Out |
|---|---|---|---|
| `moonwalkers.pipelines.b build` | Build a run folder | Run folder, reference facts | A twin version and its files |
| `moonwalkers.pipelines.b cutouts` | Cut the machine out of each fed photo as the generator will, without generating (decision 0029) | Run folder | `cutouts/sheet.png` and the cut-outs |
| `moonwalkers.pipelines.b inspect` | Inspect a mesh or try a spec | Run folder | Measurements, PNGs |
| `moonwalkers.pipelines.b.quotes` | Check quotes against their PDF pages | Reference and spec files | Found or not, per quote |
| `moonwalkers.usd.validate` | Our validator | A `.usd` file | Findings |
| `omni_asset_validate` | NVIDIA's validator | A `.usd` file | Findings |
| `moonwalkers.control list`, `show` | List the HA5C manual's example programs, or print what one does | A program's name | Its steps and timeline |
| `moonwalkers.control run` | Run an HA5C program on a stored twin | Program, twin, settings | A program folder |
| `moonwalkers.control controls` | Write a manual machine's controls for a stored twin | Twin | A controls folder |
| `moonwalkers.control compare` | Measure an Isaac Sim recording against its plan | Recording, trajectory | Measured against planned |
| `moonwalkers.pipelines run` | Run a teammate's pipeline outside the tests | Files or URLs | A checked result, nothing stored |
| `moonwalkers.pipelines.b.part_spike` | Re-run Phase 4's comparison of cutting methods | An output folder, the T33901's run | Scores and views |
| `moonwalkers.usd.primitive_twin`, `moonwalkers.usd.primitive_drill_press` | Write the box-and-cylinder test twins that check the exporter | A run folder | Test twins, check files, `RUN.md` |
| `moonwalkers.contracts.json_schema` | Write the contract's JSON Schema after a contract change | The contract | `pipeline_result.schema.json` |
| `moonwalkers.api.typescript` | Regenerate the dashboard's types after an API or contract change | The API's schema | `dashboard/src/api/types.gen.ts` |
| `moonwalkers.api` | Start the API and the dashboard | Data folder | http://127.0.0.1:8000/ |
| `moonwalkers.mcp` | Start the MCP server by hand (Claude Code normally starts it) | (stdio) | The 26 tools |

## Scripts that run inside Isaac Sim
Pasted into Isaac Sim's Script Editor (`docs/setup/isaac-sim-check.md`).

| Script | What it does | In | Out |
|---|---|---|---|
| `record_joints.py` | Records every joint after each physics step | The open twin | `recordings/*.csv`: time, then each joint's position and velocity |
| `run_program.py` | Drives the HA5C's spindle through its program, shows the CNC relay, and can hold for Cycle Start | `program.usdc` | The spindle following the program |
| `run_controls.py` | Runs the T33901's controls: scenarios, or live from the Property panel (plug, key, paddle, speed, pull) | `controls.usdc` | The spindle and quill as the operator commands them |
