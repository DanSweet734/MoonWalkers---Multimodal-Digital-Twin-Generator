# How MoonWalkers builds a digital twin

From a machine's photos and documents to a twin that moves and is controlled in NVIDIA Isaac Sim.
Each step names the tools it uses, with what goes into and comes out of them. The
[tool guide](tool-guide.md) explains every tool by name: what it is, why we use it, and its inputs
and outputs.

The diagrams are Mermaid, which GitHub draws on this page. Written on 2026-11-02, as built at the
end of the drill-press plan's Phase 6 (`docs/drill-press-plan.md`). The Grizzly T33901 drill press
and the Haas HA5C indexer are the worked examples.

## 1. The whole path
```mermaid
flowchart LR
    subgraph IN["Inputs"]
        P["Machine photos"]
        D["Manuals, data sheets,<br/>drawings, catalogs"]
    end
    subgraph START["Who starts a job"]
        DASH["Dashboard<br/>React + Vite"]
        AG["AI agent<br/>Claude Code"]
    end
    subgraph PLATFORM["MoonWalkers backend (Python)"]
        API["API<br/>FastAPI"]
        MCP["MCP server<br/>24 tools"]
        RUN[("Run folder<br/>request.json, notes, spec")]
        ROUTER["Input Router"]
        PB["Pipeline B<br/>photos"]
        PACD["Pipelines A, C, D<br/>teammates' pipelines"]
        ORCH["Orchestrator"]
        KB[("Knowledge base<br/>results, twin versions, reviews")]
        EXP["USD exporter<br/>usd-core"]
        VAL["Validators<br/>ours + NVIDIA's"]
    end
    GEN["Image-to-3D generator<br/>Hunyuan3D-2mv"]
    OUT["Twin files<br/>twin.usdc, check files,<br/>programs and controls"]
    SIM["NVIDIA Isaac Sim 6.2<br/>runner + recorder scripts"]
    REV["People review<br/>approve or reject"]

    P --> DASH
    P --> AG
    D --> AG
    DASH --> API --> RUN
    AG --> MCP --> RUN
    RUN --> ROUTER
    ROUTER --> PB
    ROUTER --> PACD
    PB <--> GEN
    PB --> ORCH
    PACD --> ORCH
    ORCH --> KB
    ORCH --> EXP --> OUT
    OUT --> VAL
    OUT --> SIM
    KB --> DASH
    DASH --> REV --> KB
```

- **A twin is reused when it exists.** Before building, the orchestrator looks the machine up by its
  key (`grizzly/t33901`). It returns the newest approved version, else the newest that nobody
  rejected (decision 0015).
- **Every fact cites its source,** from the photo or page it came from to the twin file that uses it
  (rule 1).
- **Only the orchestrator writes to the knowledge base.** Pipelines return a `PipelineResult`, the
  shared contract (decision 0004; v0.2.0, decision 0020).

## 2. Starting a job
```mermaid
flowchart LR
    U["A person uploads photos<br/>in the dashboard"] -->|"photos, machine name"| API["API<br/>POST a job"]
    API -->|"saves photos under inputs/,<br/>writes request.json"| RUN[("Run folder<br/>data/machines/&lt;machine&gt;/runs/&lt;run&gt;/")]
    A["Claude Code"] -->|"start_run, add_input"| MCP["MCP server"]
    MCP -->|"request.json"| RUN
    A -->|"list_jobs"| MCP
    MCP -->|"open jobs, and what each needs next"| A
    API -->|"stored twin? reuse it at once"| KB[("Knowledge base")]
```
- **In:** photos, each with the side it shows in the operator's words (decision 0022), and the
  machine's maker and model.
- **Out:** a run folder, the job. The API never runs the generator; the agent continues the job
  (decision 0014).

## 3. Reading the documents: cited notes
```mermaid
flowchart LR
    DOC["Manual PDF, web page,<br/>or what a person said"] -->|"add_reference_source"| SRC["Sources<br/>with SHA-256 and access date"]
    SRC --> NOTES["Reading notes<br/>reference.json"]
    A["Claude Code reads the pages"] -->|"identify_machine, add_fact,<br/>add_control, add_issue"| NOTES
    NOTES -->|"every quote"| QC["Quote checker<br/>pypdf"]
    QC -->|"found on its cited page or not"| A
    PDF["PDF pages and figures"] -->|"pypdfium2"| PNG["Rendered pages<br/>for reading figures"]
```
- **In:** documents and photos of documents.
- **Out:** the machine's identity, its facts in SI units (sizes, speeds, travels), its control
  behaviours, and issues for a reviewer. Each one carries a citation: a source, a page or locator,
  and a short quote.
- **Example:** the T33901's reference file holds 36 facts and 3 control behaviours. Its 59 quotes
  were all found on their pages on 2026-10-30.

## 4. Photos to a mesh, and the mesh to parts (Pipeline B)
```mermaid
flowchart TB
    PH["Machine photos<br/>1 to 4, with their views"] -->|"photos.py: which photo<br/>feeds which slot"| GEN["Hunyuan3D-2mv<br/>own Python environment, GPU"]
    GEN -->|"mesh.glb, about 1 min"| MESH["Generated mesh"]
    MESH -->|"inspect_geometry,<br/>fit_circles"| INS["Orientation, sizes,<br/>round parts' axes, PNG views"]
    INS --> SPEC["geometry_spec.json<br/>cited cuts, parts, stand-ins,<br/>joints, scale"]
    A["Claude Code"] -->|"set_spec_frame, set_cut_list,<br/>set_spec_part, set_spec_joint,<br/>set_scale_length, set_size_checks"| SPEC
    SPEC -->|"preview_twin"| PREV["Parts drawn in colour<br/>and over each photo"]
    PREV -->|"look, then fix the spec"| A
    SPEC --> CUT["part_cuts + stand_ins<br/>trimesh, numpy"]
    MESH --> CUT
    CUT -->|"one GLB per part, scaled<br/>by a cited length"| PARTS["Parts and joints<br/>in a PipelineResult"]
```
- **In:** photos, and the cited notes.
- **Out:** the twin's parts (cut from the mesh, or labelled stand-ins where the mesh hides or gets a
  part wrong), its joints with their behaviour (spring return, locked, free, driven, follows
  another), and size checks against every cited length.
- **Example:** `grizzly/t33901@v8` has 17 parts (11 stand-ins) and 16 joints (9 fixed). It is
  scaled by the cited 39 in height, and checked against 6 more cited lengths.

## 5. Building, exporting and validating
```mermaid
flowchart LR
    A["Claude Code"] -->|"submit_twin"| ORCH["Orchestrator"]
    ORCH -->|"run the pipeline"| PB["Pipeline B"]
    PB -->|"PipelineResult"| ORCH
    ORCH -->|"result, twin version<br/>status: needs review"| KB[("Knowledge base")]
    ORCH --> EXP["USD exporter<br/>usd-core, UsdPhysics"]
    EXP --> TW["twin.usdc"]
    EXP --> CH["checks/*.usdc<br/>one per behaviour"]
    EXP --> PR["programs/<br/>HA5C programs,<br/>drill-press controls"]
    TW --> V1["moonwalkers.usd.validate"]
    TW --> V2["NVIDIA omni_asset_validate"]
    V1 -->|"errors stop the build"| ORCH
    TW --> RUNMD["RUN.md<br/>what to check, room for results"]
```
- **In:** a run folder with its photos, notes and spec.
- **Out:**
  - the twin as OpenUSD (`.usdc`), with articulation joints, drives, limits and couplings that
    Isaac Sim simulates;
  - a check file per behaviour;
  - program or control folders;
  - `RUN.md`;
  - a new twin version in the knowledge base.
- **A version is stored for good,** so a dry run in a scratch copy of the data folder comes first.

## 6. Control logic (success level 3)
```mermaid
flowchart LR
    subgraph HA5C["Haas HA5C: a program the controller runs"]
        STEPS["Step table from the manual<br/>S, F, L, G codes"] --> INT["Interpreter<br/>acceleration, relay, waits"]
        INT --> PF["program.usdc, run_program.py,<br/>trajectory.json, PROGRAM.md"]
    end
    subgraph T33901["Grizzly T33901: an operator at the controls"]
        BEH["Switch, speed table,<br/>operator's commands"] --> CTL["Controller<br/>same code in Isaac Sim and tests"]
        CTL --> CF["controls.usdc, run_controls.py,<br/>trajectory per scenario, PROGRAM.md"]
    end
    PF --> SIM["Isaac Sim<br/>Script Editor"]
    CF --> SIM
    SIM -->|"Property panel:<br/>key, paddle, speed, pull,<br/>Cycle Start"| SIM
```
- **In:** control behaviours cited from the manual (decisions 0016, 0025, 0026).
- **Out:** a twin that the machine's own control drives on every physics step: the HA5C's indexing
  programs, and the T33901's keyed switch, twelve speeds and drilling stroke. The T33901's controls
  can be operated live in the Property panel.

## 7. Checking in Isaac Sim, measuring, and reviewing
```mermaid
flowchart LR
    F["twin, check or<br/>controls file"] --> SIM["Isaac Sim 6.2"]
    REC["record_joints.py"] --> SIM
    SIM -->|"joint positions and<br/>velocities at 60 Hz"| CSV["recordings/*.csv"]
    CSV --> CMP["moonwalkers.control compare"]
    PLAN["trajectory_*.json"] --> CMP
    CMP -->|"measured against planned"| NOTES["RUN.md, PROGRAM.md,<br/>decision records"]
    NOTES --> R["Daniel reviews"]
    R -->|"approve or reject<br/>in the dashboard"| KB[("Knowledge base<br/>reviews")]
    R -->|"what to fix"| NEXT["Next version"]
```
- **In:** a person opens the file and runs the recorder.
- **Out:** measured numbers against the plan. For example, on 2026-11-02 the T33901's stroke
  reached its depth stop at 12.12 s against 12.13 s planned, and its spring returned the quill in
  0.28 s.
- **The agent never reviews:** approving or rejecting a version is a person's decision (decision
  0015).

## 8. The agent's tools, in the order it uses them
```mermaid
flowchart TB
    S0["check_knowledge_base"] --> S1{"stored twin<br/>and no rebuild?"}
    S1 -->|"yes"| RT["request_twin"]
    S1 -->|"no"| SR["start_run, or list_jobs<br/>for a dashboard job"]
    SR --> AI["add_input<br/>each photo with its view"]
    AI --> RS["add_reference_source"]
    RS --> ID["identify_machine, add_fact,<br/>add_control, add_issue"]
    ID --> GG["generate_geometry"]
    GG --> IG["inspect_geometry, fit_circles"]
    IG --> ONE{"one moving part<br/>or several?"}
    ONE -->|"one"| J1["add_joint, set_scale"]
    ONE -->|"several"| JN["set_spec_frame, set_cut_list,<br/>set_spec_part, set_spec_joint,<br/>remove_spec_entry,<br/>set_scale_length, set_size_checks"]
    J1 --> PV["preview_twin"]
    JN --> PV
    PV --> ST["submit_twin"]
```
The procedure the agent follows is `docs/agent-procedure.md`. Each tool's inputs and outputs are
in the [tool guide](tool-guide.md#the-agents-24-mcp-tools).
