# MoonWalkers Digital Twin Project — Context File

**Purpose of this file:** This is a reference document for Daniel Sweet's contribution to the MoonWalkers collaborative (hosted by CSUN's Autonomy Research Center for STEAHM, ARCS). It consolidates every fact, source, and work product from research and drafting conversations to date, so a new conversation can pick up without re-deriving prior work. Paste or attach this file at the start of a new session for continuity.

**How to use it:** Everything under "Verified findings" traces back to a specific source that was read (directly or via fetch) during research; citations are given so claims can be re-checked. Items marked **[UNCONFIRMED]** or **[INFERENCE]** are flagged as such and should not be presented as fact without further verification. Numeric figures that conflict between sources are flagged explicitly — do not silently pick one.

**Last updated:** October 16, 2026 (adds Section 10b: answers from the team's meetings with Dr. Li and Dr. Lu, team decisions, and proof-of-concept research; earlier updates through Oct 6 cover the Oct 1 multimodal expansion, Topics 9-14, the SRS reviews, and the GitHub README).

---

## 0. Sept 29, 2026 — Scope Pivot (Meeting with Dr. Li)

**This section overrides parts of Section 1 below where they conflict.** After a team meeting, Dr. Li generalized the project's scope. His own words (as relayed by Daniel): *"Ideally I could take a video walking through my lab and if given to your platform it could recreate the environment and make digital twins of all my equipment. Identifying and filtering relevant objects, looking up information and manuals if their model number is captured on the video and recreate digital twins of everything with enough time."*

**What changed:**
- **Input:** single 2D image → a **video walkthrough** (multi-frame; needs frame sampling and cross-frame object tracking, not just per-frame detection).
- **Scope:** lunar rover/terrain-specific → **general-purpose**, any equipment in any space (his example: his own lab).
- **New module:** **model-number recognition + lookup** — OCR a visible model number, resolve it to a manufacturer/product, and fetch its manual/spec sheet, attaching that metadata to the digital twin. Nothing in the original Topic 1–4 research covers this; it is a new capability, not a variant of anything already researched.
- **Asset generation:** a fixed catalog (like the lunar-mission Isaac Sim asset taxonomy behind CAST, Section 6) no longer applies — arbitrary lab equipment likely needs **generative 3D reconstruction** (SAM-3D / TRELLIS-style, from Topic 2 research) as the primary path, with catalog matching as a fallback at most.
- **Time budget:** "with enough time" — explicitly not real-time, which supports (rather than requires changing) the agentic revise-loop already designed. **Update, Oct 5, 2026 (confirmed by Daniel):** the wording has since changed slightly to a "reasonable amount of time" — still not real-time, but processing should not take an exorbitant amount of time.

**What did NOT change:** the agent-loop architecture (observe→plan→act→render→inspect→revise→submit) and its three accountability gates (Section 6.3) are still the right shape for this — Dr. Li's own framing is exactly the tradeoff that design already handles. The dashboard/API/orchestrator separation also still holds.

**Open questions raised by this pivot (not yet answered):**
1. Does "looking up information and manuals" mean OCR + general web search, or is there a specific manuals database Dr. Li expects the team to use?
2. Is generative reconstruction (no catalog) now the primary path, given his equipment won't be in the lunar-mission asset library?
3. Is video support required for v1, or can the team start from multi-image input and add video later?
4. Is the Spatial Web / ARCS interoperability goal (originally Part 1, Goal 5 of the Project Design doc) still in scope for a generalized platform, or does it become optional/drop?

**Work products updated for this pivot:**
- The team's "Project Design" living doc (Claude Docs) — Part 1 (Goals) has an appended "Update — Sept 29, 2026" section; Part 2 (Visualize Your Design) has an appended note on two new modules (Video Ingestion; Model-Number Recognition & Lookup); a third tab, "New Research Topics," was added Sept 30 with the four topics in Section 7 below.
- The companion architecture whiteboard (published HTML artifact, https://claude.ai/artifact/MkBM21ko3GiJQNGipAUxTT) — all four original diagrams updated with the new nodes (video ingestion, OCR/lookup) outlined for visibility, plus a new fifth diagram contrasting the lunar-specific pipeline against the generalized one, and two new rows in the diagram-ownership table.
- This context file (this section).

---

## 1. Project identity and goals

**Note:** the scope described below (2D image input, lunar/rover-specific) is what the project WAS before the Sept 29 pivot in Section 0 above. Kept here for history; Section 0 is the current scope.

- **Person:** Daniel Sweet, senior in Computer Science at CSUN (Cal State Northridge), expected graduation Spring 2027.
- **Team project:** Contribution to the **MoonWalkers collaborative platform**, hosted under CSUN's **ARCS** (Autonomy Research Center for STEAHM). Note: the user initially referred to this as "AARCS" — confirmed to mean ARCS.
- **Team's contribution goal:** Streamline the creation of digital twins by building an application that hosts an AI agent. The agent takes 2D images and produces digital twins ready for simulation.
- **Daniel's own role in the team:** In earlier work (per team's own project, referenced in memory), Daniel is designing the dashboard screen wireframe in Figma under a monochrome (white/gray/black) design constraint. The core product concept is a platform where an AI agent (Claude, ChatGPT, or another VLM) connects as an automation proxy, doing on the user's behalf what a human would do through the UI.
- **Faculty contact:** Dr. Bingbing Li, Associate Director of ARCS and Associate Professor, Manufacturing Systems Engineering & Management, CSUN. Email: bingbing.li@csun.edu. Daniel had prior in-person contact with Dr. Li before this research phase began.
- **Team meeting cadence:** Weekly, on Thursdays.

### The team's four research topics
The team split background research into four topics, one per person. Daniel was assigned **Topic 4**.
1. Dr. Fei-Fei Li's Stanford lab work on digital twins.
2. AI models' capacity to create digital twins (Anthropic, OpenAI's ChatGPT/GPT-6, etc.).
3. Hermes and other AI agents and their advantages.
4. **[Daniel's topic]** Previous work on the MoonWalkers Collaborative, specifically the work of a student, Yizhan Huang.

---

## 2. Topic 1 — Dr. Fei-Fei Li's Stanford lab work on digital twins

**Key finding:** No dedicated "digital twin" program was found under Li's Stanford lab specifically. Digital twins appear as a thread inside broader robot-learning/simulation research, mostly from the Stanford Vision and Learning Lab (SVL).

### Digital Cousins / ACDC (October 2024)
- **Paper:** "Automated Creation of Digital Cousins for Robust Policy Learning." Authors: Tianyuan Dai, Josiah Wong, Yunfan Jiang, Chen Wang, Cem Gokmen, Ruohan Zhang, Jiajun Wu, Li Fei-Fei (Stanford). arXiv:2410.07408.
- **Core claim:** Exact digital twins are expensive and don't generalize. A "digital cousin" is "a virtual asset or scene that, unlike a digital twin, does not explicitly model a real-world counterpart but still exhibits similar geometric and semantic affordances."
- **Pipeline:** single calibrated RGB image + camera intrinsics → GPT-4 captions objects → GroundedSAM-v2 masks them → Depth-Anything-v2 estimates depth → CLIP + DINOv2 match objects to assets in the BEHAVIOR-1K library → scene assembled and stabilized.
- **Result:** cousin-trained policies achieved "90% vs. 25% success rates under zero-shot sim-to-real transfer" vs. twin-trained policies.
- **Stated limitations:** bounded by asset-library diversity; inherits foundation-model failure modes; policy learning itself has room to improve.
- Project page: https://digital-cousins.github.io/ (links code).

### SimFoundry (2026)
- **Paper:** "SimFoundry: Modular and Automated Scene Generation for Policy Learning and Evaluation." arXiv:2606.28276. v1 June 26, 2026 → v4 (current) August 5, 2026.
- **Authors:** multi-institution — NVIDIA, Georgia Tech, UT Austin, University of Toronto, Stanford (Li Fei-Fei is a co-author, not lead).
- **Difference from ACDC:** takes **video**, not a single image. Per summary, lifts 2D crops to 3D meshes via TRELLIS/Hunyuan, builds a digital twin, then generates "digital cousin" variations of it (object, scene, and task level).
- **Reported results:** 0.911 mean correlation between simulated and real-world policy performance; real-world success-rate gains of 17% (object variants), 21% (scene variants), 40% (task variants).
- **Caveat:** I could only access a paraphrased abstract/summary for this paper, not the full text — method details are less firmly sourced than ACDC's.

### BEHAVIOR-1K / OmniGibson (the underlying asset/sim infrastructure)
- **Paper:** "BEHAVIOR-1K: A Human-Centered, Embodied AI Benchmark with 1,000 Everyday Activities and Realistic Simulation." arXiv:2403.09227 (submitted March 14, 2024). Many authors incl. Jiajun Wu and Li Fei-Fei.
- **Abstract figures:** "1,000 everyday activities, grounded in 50 scenes... with more than 9,000 objects."
- **Note on discrepancy:** the BEHAVIOR project's own site (behavior.stanford.edu) states "10,000+ objects" — a different figure from the arXiv abstract's "9,000." Cite whichever source you're quoting, don't blend them.
- Runs on **OmniGibson**, which per the BEHAVIOR site uses NVIDIA Isaac Sim as its underlying engine. Project run by the Stanford Vision and Learning Lab (SVL).
- Relevance flag for later: this Isaac Sim connection is the same simulation stack referenced in the CAST/agentic materials received from Dr. Li (Section 6) and in NVIDIA's own agent-based scene-prep workflow (Section 3). **[INFERENCE]** These ecosystems may or may not be directly interoperable — this is an open question, not confirmed.

### Li's "spatial intelligence" direction (World Labs — separate from her Stanford lab)
- Li is co-founder/CEO of **World Labs**, a company, distinct from her Stanford academic lab.
- Essay: "Spatial Intelligence Is AI's Next Frontier" (Time, https://time.com/7339693/fei-fei-li-ai/). Key quote: a world model needs "understanding, reasoning, generation and interaction with the semantically, physically, geometrically and dynamically complex worlds." She calls robotics "an ambitious mid-term horizon."
- **Marble** (World Labs product): launched November 12, 2025. Takes single images, text, multi-image, video, or coarse 3D layouts (via a tool called "Chisel") as input. Outputs Gaussian splats and meshes, including "low-fidelity meshes intended for coarse physics simulation" — note this is explicitly *coarse*, not simulation-grade.
- **World API**: launched January 21, 2026, exposing Marble's world-generation capability programmatically; lists robotics simulation as a named use case.
- No source calls Marble's output a "digital twin" — avoid using that term for it.

### Adjacent but NOT Li-authored
- **Gibson Env** (2018), arXiv:1808.10654 — Fei Xia, Amir Zamir, et al. Earlier Stanford paper building simulation environments from 1,400+ real building scans. Predates and is unrelated to Li's specific authorship, included only as useful background on Stanford's simulation lineage.

### Reading list (Topic 1)
1. ACDC / Digital Cousins: https://arxiv.org/abs/2410.07408 and https://digital-cousins.github.io/
2. SimFoundry: https://arxiv.org/abs/2606.28276
3. BEHAVIOR-1K: https://arxiv.org/abs/2403.09227 and https://behavior.stanford.edu/
4. Li's Time essay: https://time.com/7339693/fei-fei-li-ai/
5. Marble announcement: https://www.worldlabs.ai/blog/marble-world-model
6. Gibson Env: https://arxiv.org/abs/1808.10654

---

## 3. Topic 2 — AI models' capacity to create digital twins

**Key finding:** no general-purpose model was found that autonomously turns a 2D image into a simulation-ready digital twin end-to-end. Every documented example splits the job across three layers: an **orchestrating model** (reasons and calls tools), a **specialist image-to-3D model** (generates geometry), and **simulation tooling** (makes the result physics-ready, with human review at ambiguous steps). This three-layer split is **[INFERENCE]** drawn from the sources, not a claim any single source makes outright.

### Layer 1 — Orchestrating / agentic models
- **Anthropic (Claude):** Current models (per Claude Platform Docs) are Claude Fable 5.1, Opus 5, Sonnet 5, and Haiku 4.5. Fable 5.1, Opus 5, and Sonnet 5 have 1M-token context windows; Haiku 4.5 has 200K. All support image input and tool use. Vision docs explicitly warn: "Claude's coordinate and localization outputs are approximate... verify outputs before relying on them," and counting is only approximate.
  - **Claude for Creative Work** (announced April 28, 2026): added Blender and Autodesk Fusion connectors via MCP. Anthropic's own framing: artists can "analyze and debug entire Blender scenes, or build custom scripts to batch-apply changes." A trade-press report (Manufactur3D) said early CAD results were mixed — "complex geometries, extrusions, and multi-step assemblies" still produced errors.
- **OpenAI (GPT-6 Astra):** launched September 3, 2026 (confirmed exact name is **"GPT-6 Astra,"** not "Astral" or "ChatGPT 6 Astral" as originally guessed). Headline strength is computer use, coding, and cybersecurity — "the best model for software engineering to date," per OpenAI. Its own page claims (unverified beyond the demo claim itself): "GPT-6 Astra models a house in Blender and turns it into a walkable scene in Unreal Engine 5." No supporting benchmark for that specific claim was found. TechCrunch flagged controversy over Astra's "opaque recurrence" reasoning technique, which makes chain-of-thought auditing harder.
- **Google (Gemini Robotics-ER 1.6):** released April 14, 2026. Targets spatial reasoning: points, 2D bounding boxes, and trajectories (format: `[y, x]` normalized 0–1000). No 3D bounding-box output was found documented.

### Layer 2 — Specialist image-to-3D generation models
- **SAM 3D (Meta):** arXiv:2511.16624, "SAM 3D: 3Dfy Anything in Images." Reconstructs objects from a single image (geometry, texture, layout). Meta reports "at least a 5:1 win rate in human preference tests" vs. prior methods.
- **TRELLIS.2 (Microsoft):** 4B-parameter model, MIT-licensed, outputs textured GLB meshes with PBR materials. Needs an NVIDIA GPU with ≥24GB memory; on an H100, ~3 seconds at 512³ resolution, ~17 seconds at 1024³. GitHub: https://github.com/microsoft/TRELLIS.2
- **Hunyuan3D 2.0 (Tencent):** arXiv:2501.12202. Diffusion-based shape generator (Hunyuan3D-DiT) + texture generator (Hunyuan3D-Paint), open weights.
- None of these three were confirmed to output physical properties (mass, collision geometry, articulation) — that gap was not resolved either way. **Update, Oct 5, 2026:** checked against each tool's own abstract/README in Topic 13 (Section 7): none lists articulation, physics, or control behavior among its stated outputs, though that rests on what the sources state, not on testing.

### Layer 3 — Making a scene simulation-ready
- **NVIDIA's agent-based workflow** (developer.nvidia.com blog, "How to Use AI Agents to Prepare 3D Scenes for Simulation"): Codex (running GPT-6 Astra) or Claude orchestrates; specialized subagents are "built with the **Hermes** agent harness and deployed through NVIDIA **NemoClaw**" (this is the direct bridge to Topic 3). Uses a Blender MCP server for scene inspection, `ovphysx` for physics authoring, `ovrtx` for render preflight, and a **SimReady** validation gate before Isaac Sim/Lab handoff. Ambiguous decisions (uncertain semantic labels, task-dependent physical behavior) are explicitly escalated to a human.
- This NVIDIA workflow is structurally very close to the "agentic pipeline deck" Dr. Li later shared (Section 6) — both use an agent calling defined tools against an Isaac Sim / Omniverse backend with a validation gate before completion.

### Reading list (Topic 2)
1. NVIDIA agent workflow: https://developer.nvidia.com/blog/how-to-use-ai-agents-to-prepare-3d-scenes-for-simulation/
2. SAM 3D: https://arxiv.org/abs/2511.16624
3. TRELLIS.2: https://github.com/microsoft/TRELLIS.2
4. Hunyuan3D 2.0: https://arxiv.org/abs/2501.12202
5. Claude for Creative Work: https://www.anthropic.com/news/claude-for-creative-work
6. Claude vision docs: https://platform.claude.com/docs/en/build-with-claude/vision
7. GPT-6 Astra: https://openai.com/index/gpt-6-astra/ and system card: https://deploymentsafety.openai.com/gpt-6-astra

---

## 4. Topic 3 — Hermes and other AI agents and their advantages

**Scope note:** "Hermes" = **Hermes Agent** by Nous Research (MIT-licensed, ~240k GitHub stars). This is the same "Hermes" NVIDIA's Topic 2 workflow uses as an agent harness alongside NemoClaw.

### Hermes Agent
- **Core pitch:** "the only agent with a built-in learning loop" — agent-curated memory, autonomous skill creation, skill self-improvement during use, using the open **agentskills.io** skill format.
- **Portability:** works with Nous Portal, OpenRouter, OpenAI, or "any endpoint" — model-agnostic.
- **Where it runs:** several terminal backends (local, Docker, SSH, Singularity, Modal, Daytona, Vercel Sandbox — count varies 5–7 depending on which doc page you read) and 20+ messaging platforms (Telegram, Discord, Slack, WhatsApp, Signal, etc.).
- **MCP support:** yes, can connect to any MCP server.
- **NVIDIA + Hermes:** per NVIDIA's blog, after user feedback "Hermes writes a SKILL.md to the filesystem," and NVIDIA's OpenShell sandbox keeps credentials from the agent entirely ("the Hermes agent never sees the Slack or Outlook tokens") and blocks unlisted network hosts with a 403.
- **Latest release referenced:** v0.19.0, "The Quicksilver Release," July 20, 2026.

### Security caveats on Hermes — important if recommending it
- Three CVEs (via a Cloud Security Alliance research note):
  - **CVE-2026-7396** (medium) — path traversal in the WeChat Work platform adapter, v0.8.0, patch pending at time of research.
  - **CVE-2026-7397** (medium) — symlink-following vulnerability in file tools, fixed in v0.9.0.
  - **CVE-2026-6829** (medium) — path traversal in the separate `hermes-webui` package, fixed in v0.50.34.
- An independent GitHub security audit (issue #7826, filed April 11, 2026 against v0.8.0 by a third party) claimed 4 critical and 9 high-severity findings, saying the "default security posture is ALLOW-ALL." At the time of research, **no maintainer response was documented** on that issue.
- Current Hermes docs describe a "Smart" approval mode as the default (an auxiliary LLM assesses command risk) and recommend a Docker backend for production, where "the container itself is the security boundary."
- **Takeaway for the project:** if Hermes (or any similar harness) is ever proposed as the runtime for the MoonWalkers agent, sandboxing and credential isolation are non-negotiable design requirements, not optional hardening.

### Other agents/harnesses surveyed
| Agent/Harness | Key facts |
|---|---|
| **Claude Agent SDK** | Python/TypeScript library exposing Claude Code's own agent loop: built-in tools, hooks, subagents, MCP, permissions, sessions, skills, plugins. Governed by Anthropic's Commercial Terms of Service. |
| **OpenAI Agents SDK** | Updated April 15, 2026 — added native sandboxed execution (Blaxel, Cloudflare, Daytona, E2B, Modal, Runloop, Vercel), MCP support. Python-only at that time; TypeScript and subagents were listed as "coming." |
| **LangChain Deep Agents** | Open-source, model-neutral harness. Planning tool, virtual filesystem, subagents with isolated context. |
| **OpenClaw** | MIT-licensed, created by Peter Steinberger (later joined OpenAI; project now run by the OpenClaw Foundation). Messaging-first, skills-based. Security history includes a Cisco-reported data-exfiltration finding (Jan 2026) via a third-party skill, unencrypted stored credentials, and a March 2026 restriction on use by Chinese state enterprises. |

### Underlying protocol: MCP
- **Model Context Protocol** — described by its own docs as "a USB-C port for AI applications." Open standard for connecting AI apps to data sources, tools, and workflows. Supported by both Claude and ChatGPT, plus many IDEs.

### Framework for thinking about agents (Anthropic's own guidance)
From "Building Effective Agents" (Anthropic engineering blog):
- **Workflows** = "LLMs and tools orchestrated through predefined code paths." **Agents** = "systems where LLMs dynamically direct their own processes and tool usage."
- Agents suit "open-ended problems where it's difficult or impossible to predict the required number of steps," but "trade latency and cost for better task performance" and carry "the potential for compounding errors." Add agentic complexity "only when it demonstrably improves outcomes."
- Five named patterns: prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer.
- **[INFERENCE] for the project:** the MoonWalkers image-to-twin pipeline has fairly predictable steps (upload → segment → generate geometry → author physics → validate), which this guidance suggests should be a mostly-fixed **workflow**, with agentic judgment reserved for genuinely ambiguous steps (unclear labels, uncertain collision geometry) — this is exactly the shape of both NVIDIA's workflow (Topic 2) and the "agentic pipeline deck" from Dr. Li (Section 6).

### Important caveat on the harness comparisons
No independent, unbiased benchmark comparing Hermes / OpenClaw / Claude Code / Codex was found. The comparison articles read (Composio, Reinventing.AI) both have commercial ties to the products they're comparing — treat their conclusions as informed opinion, not neutral measurement.

### Reading list (Topic 3)
1. Hermes Agent docs: https://hermes-agent.nousresearch.com/docs/
2. NVIDIA + Hermes/NemoClaw: https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/
3. CSA note on Hermes CVEs: https://labs.cloudsecurityalliance.org/research/csa-research-note-hermes-agent-cves-20260504-csa-styled/
4. Building Effective Agents: https://www.anthropic.com/engineering/building-effective-agents
5. Claude Agent SDK overview: https://code.claude.com/docs/en/agent-sdk/overview
6. MCP introduction: https://modelcontextprotocol.io/docs/getting-started/intro

---

## 5. Topic 4 — Prior MoonWalkers work (Daniel's assigned topic)

### 5.1 Timeline of confirmed prior work

| Date | Event | Source confidence |
|---|---|---|
| Summer 2023 | Origin: JPL summer internship building "a 3D virtual test environment for collaborative robotic exploration in lunar south pole" | High — JPL profile of Thomas Lu |
| Oct 2023 | VIRCLE talk given at LSIC Fall Meeting by E. Chow (cited in the 2024 paper's references) | Title only, not accessed |
| **Mar 2024** | **"Collaborative Moonwalkers,"** 2024 IEEE Aerospace Conference (Big Sky, MT). DOI 10.1109/AERO58975.2024.10521103. **Read in full** (uploaded PDF) — see §5.2 | Full text read |
| Aug 22, 2024 | VERSES AI + JPL + CSUN + Spatial Web Foundation press release: real-time joint testing, lander model at CSUN, rover digital twin at JPL, over distributed NVIDIA Omniverse | Read |
| Oct 2024 | NSF NAIRR co-PI award to Bingbing Li: "Development of a Large World Model (LWM) for Enhancing Safe Human-Robot Collaboration in Lunar Missions" | Title/one-line news item only — **not accessed in detail**; possible link to Yizhan's work window, unconfirmed |
| 2024 (undated, "in press") | "Digital Twin and Physics Informed Machine Learning for Rover Motion Simulation" (Bardi de Fourtou, Lu, Chow), International Astronautical Congress 2024 | Listing only (proceedings.com, $30 paywall) — not read |
| **Mar 2025** | **"Enabling Interoperable Digital Twins for Collaborative Lunar Exploration,"** 2025 IEEE Aerospace Conference. DOI 10.1109/AERO63441.2025.11068549. **Read in full** (uploaded PDF) — see §5.2 | Full text read |
| Apr–May 2025 | "Utilizing V-JEPA for Action Recognition on the Lunar Surface: Advancing Human-Robot Collaboration" (Gold, Cortez, Carrillo, Li, Chow, Lu), SPIE DCS25, Proc. SPIE 13464. DOI 10.1117/12.3052411 | Metadata only |
| Nov 19, 2025 | Invited NVIDIA GTC talk, Bingbing Li: **"Digital Twin Generation and Interoperability for Moon Exploration through NVIDIA Omniverse and Cosmos Physical AI models"** | Title only — **this is the closest prior-art title match to Daniel's own project** |
| Mar 7–14, 2026 | "Demonstrating Digital Twin Interoperability Between Heterogeneous Platforms via Spatial Web" (Sanjurjo Barrio, Li, Chow, Lu — adds International Space University as a new partner institution). DOI 10.1109/AERO66936.2026.11519858. 2026 IEEE Aerospace Conference | Metadata only |
| Aug 6, 2026 | Invited talk, DigiTwin 2026 (6th Digital Twin International Conference), University of Oxford, Bingbing Li: "Moonwalkers: Interoperable Digital Twins for Collaborative Lunar Exploration" | Title only |

**Numeric discrepancy to flag before citing:** the 2024 paper's physics-informed ML module runs in "~400ms" per prediction (vs. ~90 min for the full Chrono simulation); the 2025 paper describes what appears to be the same or a closely related module running in "under 150ms" (reduced from 1.5h). **Do not cite one number as if the other doesn't exist** — clarify which paper/module you mean, or ask Dr. Li which figure is current.

### 5.2 What the two uploaded IEEE papers actually say (read in full)

**"Collaborative Moonwalkers" (2024)** — Authors: Edward Chow, Thomas Lu (JPL/Caltech); Kevin Payumo (USC); Gautier Bardi de Fourou (Mines Paris); Elliott Sadler, Neville Elieh Janvisloo, Jared Carrillo, Bingbing Li (CSUN); Benjamin Hubler (U. Chicago); Olin Littlejohn (Purdue); Vanessa Hernandez-Cruz, Sophia Torrellas (MIT).
- Describes itself as an "advanced concept study."
- **Architecture:** "System 1 / System 2" neuro-symbolic rover design. System 1 = fast, uses a pre-trained multimodal model (LLaVA) to turn rover camera images into text descriptions. System 2 = slower LLM-based reasoning using a graph neural network (trained via GraphSAGE) over a knowledge graph of game states/actions.
- **Reasoning experiments:** used the Game-of-24 puzzle (not a lunar task) as a testbed for Tree-of-Thoughts sampling strategies, using gpt-3.5-turbo-0613. Plain ToT scored 27% average; ToT + PPO-based sampling scored 40% (Table 1).
- **Virtual environment:** built by summer interns in 8 weeks using NVIDIA Omniverse (Isaac Sim + USD Composer). CADRE and VIPER rover models built via Fusion 360 → 3ds Max → Adobe Substance Painter. Lunar terrain built from real LRO (Lunar Reconnaissance Orbiter) elevation data, ~30m/pixel resolution, focused on the Shackleton Crater rim.
- **Path planning:** A* algorithm using elevation + slope-based heuristics.
- **Digital twin section (Section 4):** physics-informed machine learning — an ODE (physics equation) model corrected by a neural network trained against Chrono Engine ground truth (Chrono simulates rover-on-regolith motion). Reduced rover position error from **66m (ODE-only) to 23cm**, running in **~400ms vs. ~90 minutes** for the full Chrono simulation. A mass/torque-robustness test also showed the ML correction generalizing well to an unseen, heavier rover configuration.
- Bingbing Li's bio (in the paper) already names him "Associate Director of NASA funded Autonomy Research Center for STEAHM (ARCS)."

**"Enabling Interoperable Digital Twins for Collaborative Lunar Exploration" (2025)** — Authors: Jared Carrillo, Subhobrata Chakraborty, Rayyan Mridha, Neville Elieh Janvisloo, Elliott Sadler, Bingbing Li, Nhut Ho (CSUN); Gautier Bardi de Fourtou, Thomas Lu, Edward Chow (JPL); Capm Petersen, Aidin Eslami, Alessandro Muzzi (VERSES AI); George Percivall, Jacqueline Hynes (Spatial Web Foundation).
- **Goal:** VIRCLE ("Virtual Environment for Collaborative Lunar Explorations") — a shared, standards-based framework so different organizations' digital twins can interoperate.
- **Standard adopted:** the (at-the-time forthcoming) **IEEE P2874 Spatial Web standard**, using its Hyperspatial Modeling Language (HSML) and Hyperspatial Transaction Protocol (HSTP).
- **Demo 1:** real-time collaboration between an Omniverse-based system at JPL and an Omniverse system at CSUN, exchanging messages via HSML.
- **Demo 2:** cross-platform collaboration between Omniverse (right-handed coordinates) and Unity (left-handed coordinates) — required matrix transforms to reconcile coordinate systems.
- **Demo 3 (IP protection):** a proprietary Physics-Informed Neural Network (PINN) rover-motion model was hosted remotely and queried via HSML, so its code never left the owning organization's machine, while still returning real-time results.
- **Performance targets:** latency typically kept below 50ms; frame rate minimum of 30fps (industry standard is 24fps).
- Physical prototype validation: a scale lunar terrain model built from polyurethane foam (12 lb/ft³) used to cross-check the virtual terrain.
- States (Conclusions): "To our knowledge, this project marks the first demonstration of interoperability between distributed and disparate DT systems using the spatial web standard."

### 5.3 The Yizhan Huang investigation — status as of Sept 22

**Bottom line reached before Dr. Li responded:** no public record of Yizhan Huang's specific MoonWalkers contribution was found anywhere online.

What *was* found:
- **ARCS 2026 Fellows/Associates page** (arcs.center/2026-arcs-fellows-associates/): Yizhan Huang listed as a **2026 Associate**, with exactly one linked project: "Collaborative Moonwalker." No degree, mentor, or description given on that page.
- **Dr. Li's lab (LSAM) People page** (ecs.csun.edu/~bingbing/people.html), under **Alumni**: *"Yizhan (Ethan) Huang [linked to a LinkedIn profile that could not be opened] worked as Research Assistant at LSAM (09.2025-05.2026), obtained his M.S. degree in Artificial Intelligence from University of Southern California in May 2026 and B.S. degree in Computer Science from University of Nottingham, United Kingdom in June 2024. He is working at Baidu Inc."* No thesis/project topic specified. Immediately adjacent alumni entries: Mingtao Ding (listed just before Yizhan, same RA window and USC MS AI program) and Troy Israel (listed just after).
- **Where he does NOT appear:** the Moonwalker project page's own current-team or alumni lists; the 2025 ARCS project list (Associates on that project were blank that year); any author list on any Moonwalker/digital-twin paper found; the ARCS Publications page; the LSAM lab's own publications and news pages.
- **Other "Yizhan Huang" identities found online** (a University of Washington economics PhD candidate; a Chinese University of Hong Kong CS PhD student working on adversarial ML) — neither connects to CSUN and both were **excluded** as false matches.

**This gap is what prompted the email to Dr. Li (Section 7).**

### Reading list (Topic 4)
1. Both uploaded IEEE papers (Collaborative_Moonwalkers.pdf; Enabling_Interoperable_Digital_Twins_for_Collaborative_Lunar_Exploration_1.pdf) — full text already read, kept as local reference.
2. ARCS Moonwalker project page: https://arcs.center/metaverse-for-moon-exploration/
3. LSAM (Bingbing Li's lab) people page: https://www.ecs.csun.edu/~bingbing/people.html
4. LSAM publications page: https://www.ecs.csun.edu/~bingbing/publication.html
5. LSAM news page: https://www.ecs.csun.edu/~bingbing/news.html
6. VERSES/JPL press release: https://www.verses.ai/news/verses-completes-first-phase-of-digital-twins-interoperability-project-with-jpl

---

## 6. New materials from Dr. Li (received ~Sept 22–23, 2026)

Dr. Li responded to the outreach email with **two presentation decks** and a **GitHub link**. All three are directly relevant to the team's project and may represent Yizhan Huang's actual work, though this is not yet confirmed.

### 6.1 GitHub organization: Digital-Twin-Interoperability
- The link given pointed to one repo, `isaac-sim-reconstruction-benchmark`, but that repo lives inside a larger GitHub organization, **Digital-Twin-Interoperability**, which has **30 repositories** total.
- **Strong lead:** the given repo's file listing includes a config file named **`yizhan_A100.yaml`** — almost certainly Yizhan's own GPU (A100) training configuration. **[UNCONFIRMED]** — GitHub's contributor API and raw README fetch both returned 403 errors during research, so this could not be independently verified via commit history.
- **Pattern evidence supporting per-intern folder organization:** a sibling repo, `2025_fall_digital_twin_generation`, contains a folder literally named **`Mingtao_Ding`** — the LSAM alumnus listed immediately next to Yizhan on Dr. Li's own lab page, with the identical RA window (Sept 2025–May 2026) and the same USC MS in AI program. This strongly suggests the org may have (or once had) a parallel folder for Yizhan that simply wasn't found yet, or that his work is organized under a different, not-yet-checked repo.
- Other sibling repos noted but **not yet explored in depth**: `Automated-Digital-Twin-Generation-Pipeline`, `2025-Fall-Intern-Report` (rover collision/interaction across Unity and Omniverse Isaac Sim via HSML API), `hsml_api`, `hsml_schema`, `omniBL`, `unityBL`, `2025-summer-intern-reports`, `2025-Fall-HSML-Beta-Test`. **Follow-up idea:** these are worth searching directly for Yizhan's name/folder if this thread continues.
- **`isaac-sim-reconstruction-benchmark` repo itself:** Apache 2.0 licensed. It's a **benchmark framework** (not yet a working reconstruction pipeline) for evaluating scene-reconstruction methods in NVIDIA Isaac Sim. Evaluates: asset retrieval from a 6,321-variant catalog (85 categories, 18 families), scene template/component inference, spatial relation recovery, and 6-DOF pose placement accuracy. Ground-truth ex tractor tested on a warehouse scene with 3,139 components. Retrieval uses OpenCLIP ViT-B-32. Per its own README, **the actual reconstruction pipeline ("the player") is explicitly not yet built** — only the schemas, taxonomy, extractor, retrieval, evaluator, validator, and CLI scaffolding are complete.

### 6.2 CAST deck — "Component-Aligned 3D Scene Reconstruction" (15 slides, read in full)
A **working, fixed six-stage pipeline** that takes one 2D photo and outputs positioned 3D objects:
1. **Detection** — RAM (Recognize Anything Model: open-vocabulary image tagging, no fixed category list) + Grounding DINO (turns RAM's text tags into bounding boxes with confidence scores).
2. **Filtering** — GPT-5.2 acts as a VLM verifier: confirms each box is a real, distinct object, removes false positives/duplicates, and classifies occlusion as none/partial/heavy. Demo: a beach photo with 5 raw detections (guitar, surfboard, "camper," "sand," "sea") was filtered down to 2 kept objects (guitar, surfboard) — the van was dropped for partial occlusion, sand/sea dropped as background misdetections.
3. **Segmentation** — SAM produces a pixel-perfect binary mask per object (zero-shot, no task-specific training), generating four mask variants (cropped_mask, cropped_occ_mask, mask, occ_mask) and an RGBA crop.
4. **Depth Estimation** — MoGe v2 produces, in a single forward pass: a dense per-pixel depth map, an unprojected 3D point cloud, and estimated camera intrinsics (focal length, principal point).
5. **3D Mesh Generation** — SAM-3D / Gaussian Splatting converts each RGBA crop into a 3D point cloud/splat (demo shown for guitar and surfboard).
6. **Pose Estimation** — OrientAnything predicts an initial 6D rotation from the object crop (to avoid bad local minima), then a Chamfer-loss optimizer (PyTorch Adam, optimizing translation and rotation jointly, with occlusion-aware weighting) aligns the object's point cloud to the scene point cloud.
- **Output:** per-object JSON with translation (x,y,z), 3×3 rotation matrix, scale, confidence, fitness score, and Euler angles, plus aggregate fitness statistics across all objects in a scene.
- **Why this matters:** this is a complete, working answer to "how do you go from a photo to a positioned 3D object" — directly comparable to (and built from different, more recent tools than) the Stanford ACDC pipeline from Topic 1.

### 6.3 Agentic pipeline deck — "From Image to Executable Scene" (14 slides, read in full)
Proposes wrapping a CAST-style pipeline in an **agent loop** instead of running it as one fixed pass. **This maps almost exactly onto the team's own stated project goal.**
- **Framing:** input = one reference image; output is explicitly **not** a caption or a static mesh, but a loadable/renderable/scorable **Isaac Sim scene** (an Isaac Sim scene + PredictionJSON + scene.usd + a renderable result). Their own words: "image-to-simulation-scene reconstruction, not generic image understanding."
- **Why a fixed pipeline isn't enough** (their own stated reasons): images carry occlusion/scale/viewpoint ambiguity; catalog assets don't map one-to-one onto real objects; a single object may have several substitutable assets that can only be settled by render feedback; position/scale/orientation/camera typically need multiple adjustment rounds; a one-shot prediction is hard to explain or fix when wrong.
- **The closed loop:** Observe (input image + current scene state) → Plan (next scene change) → Act (call Isaac Sim tools) → Render (current scene) → Inspect (visual + structured feedback) → Revise → Submit final PredictionJSON.
- **Tool taxonomy (6 groups, explicitly designed to make every action auditable):**
  - *Inventory:* `set_inventory`, `mark_matched`, `update_inventory_item`
  - *Catalog:* `get_catalog_hits`, `list_families`, `list_assets_in_family`, `get_asset_info`
  - *Scene edit:* `add_component`, `modify_component`, `remove_component`, `align_components`
  - *Inspection:* `list_components`, `plot_top_down`, `view_reference`
  - *Render:* front / top-down / chosen views
  - *Submit:* `submit_prediction` (only once gates pass)
- **Three accountability gates:**
  1. **Inventory-lock gate** — no component edits allowed until the agent has explicitly declared every distinct object it sees.
  2. **Render-after-edit gate** — every edit must be followed by a render before continuing; no blind, chained edits.
  3. **Submit gate** — before submission: every inventory item must be matched or explicitly acknowledged as unmatched, no unaccounted extras, and the scene must have been rendered since the last edit.
  - Their own framing: this makes it "a debuggable system, not a black-box demo."
- **Case study — Packing Table Reconstruction:** one real photo, full agent trace shown: (1) Perceive 8 objects with positions/relations; (2) Research candidate asset families via `get_asset_info`; (3) Place all 8 via `add_component`; (4) Verify via render + `plot_top_down` + `list_components`; (5) Self-revise — re-queries table variants and removes a poorly-matched table; (6) Submit, with `acknowledge_unmatched=["work_table"]` and explanatory notes. Their framing: "the value is that the process is visible... [it] honestly admitted an object was unmatched rather than ship a wrong assignment."
- **Evaluation dimensions (7):** asset retrieval correctness, component coverage, count accuracy, spatial-relation plausibility, placement quality (6-DOF error vs. target), render-vs-input visual match, and trace quality (can the failure path be explained).
- **"What We Have Built" (their own delivered/not-delivered breakdown):**
  - *Delivered:* the Isaac Sim asset taxonomy + benchmark infrastructure (85 categories / 6,321 variants / a curated 59-asset retrieval pool), the full evaluation pipeline, a scene-generation/inspection framework, the agentic reconstructor with tools + gates, and a trace format that replays every tool call and gate decision.
  - *Still open (their own roadmap):* **short term** — more stable object detection/cropping, stronger per-object retrieval, finer pose/scale/camera correction, fuller render-based comparison, more case studies; **mid term** — more scene types beyond the current warehouse/packing-table setting, auto-generated benchmark scenes/splits, fused trace-and-evaluation; **long term** — moving from static reconstruction to fully interactive, simulatable, robotics-ready environments.
- This "long term" goal is essentially identical to the team's own stated project goal.

### 6.4 Open questions raised for Dr. Li / the team meeting (not yet answered)
1. Is CAST, or the agentic-pipeline concept, specifically Yizhan Huang's own work, or a broader lab effort he contributed one piece of?
2. Does the Digital-Twin-Interoperability org have a Yizhan-specific folder or repo (parallel to `Mingtao_Ding`) that simply wasn't surfaced yet?
3. Is the agentic pipeline actually implemented/running code, or still a design proposal? (This changes how directly the team can build on it vs. treat it as inspiration.)
4. How does this Isaac Sim asset taxonomy relate to Stanford's BEHAVIOR-1K catalog from Topic 1 — are they compatible, overlapping, or unrelated?

---

## 7. New research topics for the generalized scope (Sept 30, 2026)

The Sept 29 pivot (Section 0) opened four gaps that Topics 1-4 don't cover: video input, open-ended object identification, reading a model number off equipment, and looking up a manual from it. These four topics fill those gaps, each with a source. (Also written up as a "New Research Topics" tab in the team's Project Design doc.)

**Topic 5 - Identifying & filtering relevant objects (SAM 3 / SAM 2).** The CAST pipeline (Section 6) uses RAM + Grounding DINO + SAM, all single-image tools. Meta's **SAM 2** added video to the original SAM via a memory module: click an object once on one frame and it tracks that object across the rest of the video, surviving brief occlusion. **SAM 3** (released Nov 19, 2025) goes further with "Promptable Concept Segmentation" - prompt with a plain-language phrase (e.g. "oscilloscope") or an example image, and it segments *every* matching instance in a frame; for video it inherits SAM 2's memory system and tracks each as a "masklet," re-identifying it after occlusion or re-entry. This is a close match for "identifying and filtering relevant objects" in Dr. Li's request. Sources: [Meta AI, SAM 2](https://ai.meta.com/research/sam2/); [Meta AI, SAM 3](https://ai.meta.com/research/sam3/); [Roboflow, "SAM 3: Segment Anything with Concepts"](https://blog.roboflow.com/what-is-sam3/).

**Topic 6 - Multi-view / video-based 3D reconstruction (VGGT).** Our Topic 2 research covered single-image depth estimation (MoGe v2). A walkthrough video gives many views of the same object, which VGGT (Visual Geometry Grounded Transformer) is built to use: it takes "one, a few, or even hundreds of images of a scene" and in one forward pass outputs, per image, camera pose, a depth map, a dense point cloud, and 3D point tracks across images - reconstructing a scene in under a second, and outperforming optimization-based pipelines like COLMAP without their iterative post-processing. Source: [VGGT paper, arXiv](https://arxiv.org/html/2503.11651v1).

**Topic 7 - Reading model numbers off equipment (Ocean-OCR).** Dr. Li's request depends on reading a model number visible in the video. **Ocean-OCR** is a vision-language model trained end-to-end for dense documents, handwriting, and - most relevant here - **scene text** (signage, packaging, labels on physical objects). On combined OCR benchmarks it averaged 84.7% and outperformed dedicated OCR products (PaddleOCR, TextIn) on real-world scenes specifically, not just documents. Source: [Ocean-OCR paper, arXiv](https://arxiv.org/pdf/2501.15558).

**Topic 8 - From model number to manual (Octopart + general web search).** **Octopart**, via Altium's documentation, exposes a GraphQL API returning "part specifications, pricing, inventory levels, datasheets, and distributor offers" for a given electronic part - a real, working example of model-number-to-datasheet lookup. Source: [Altium, Octopart API docs](https://www.altium.com/documentation/altium-developer-center/octopart). **Gap [INFERENCE]:** Octopart only covers electronic components, not lab equipment generally (an oscilloscope chassis, an optical mount, a mechanical fixture) - no equivalent general-purpose database was found. For non-electronic equipment, the realistic path is a general web-search tool call rather than a structured API, which fits the agent tool-calling design already in Topic 3. **Open question for Dr. Li:** does he expect datasheet-grade lookups (Octopart-style) or is "found a manual online" sufficient for other equipment types?

**How this maps onto the pipeline:** SAM 3/SAM 2 → Detection & Segmentation + Video Ingestion modules (replacing RAM + Grounding DINO + single-image SAM); VGGT → Depth Estimation + 3D Mesh Generation modules (extending MoGe v2 to use every frame); Ocean-OCR and Octopart/web search → the new Model-Number OCR + Manual Lookup module.

### Oct 1, 2026 update: multimodal expansion (meeting with Dr. Li and Dr. Lu)

The scope changed again, substantially. The platform must be **multimodal with up to 8 possible inputs**: (1) video of a facility walkthrough, (2) photos of machines/components, (3) photos of equipment nameplates, (4) PDF product brochures/datasheets, (5) facility layout drawings, (6) schematic illustrations of machines from brochures, (7) PDF product catalogs, (8) online product-catalog/technical-spec resources. Each team member picks **two inputs** and builds a pipeline for them, after the team first builds the shared platform together. Output must be **NVIDIA Omniverse-compatible .usd**. The platform needs a **shared database/knowledge base** storing all source material (user-provided or found online) so a machine's digital twin, once built, doesn't need to be rebuilt - Dr. Li described this as a **multimodal RAG**. Other tools may be used as long as sourced; the stated novelty is that twins must be **functional, not just visual** - e.g., a CNC machine's twin needs correct internals and must behave like one in Omniverse, not just look like a hollow shell. The team separately discussed building the knowledge base as a **knowledge graph in Neo4j**.

**Dr. Lu's role (Oct 6, 2026, from Daniel):** an advisor to the team and a project stakeholder (Daniel believes also a technical stakeholder; not confirmed).

**Who is Dr. Lu:** per Daniel (Oct 5, 2026), Dr. Thomas Lu, a researcher at NASA JPL. His [JPL research profile](https://www.jpl.nasa.gov/site/research/thomaslu/) lists him as Dr. Thomas T Lu, Senior Researcher in the Bio-Inspired Technologies & Systems Group (in that position since 2004; Ph.D. in Electrical Engineering, Pennsylvania State University). A Thomas Lu (JPL/Caltech) is also listed as co-author of both IEEE papers in Section 5.2; it is likely the same person but this was not independently verified.

**[INFERENCE/gap]** This is the single biggest gap versus our research to date: every image-to-3D model we've researched (SAM-3D, CAST, TRELLIS, VGGT) produces visual geometry only, not functional internals. This directly echoes the "digital twin vs. digital cousin" distinction from Topic 1 (Section 2) - Dr. Li is now explicitly asking for the twin, not the cousin.

**Oct 2, 2026 follow-up:** the team will start smaller and more standardized - Dr. Li offered his own lab as a controlled place to capture video/photos, and gave the team "a few websites" to pull product data from for testing. Topics 9 and 10 below were researched in direct response to this meeting.

**Oct 2, 2026 follow-up (continued) - data sources and input pairing.** Daniel shared Dr. Li's 6 websites and the first pipeline assignment. Each site was checked directly (fetched Oct 2, 2026) rather than assumed:

- **BHS, Inc.** ([na.bhs1.com](https://na.bhs1.com/)) - a US manufacturer and direct seller of custom material handling equipment (battery handling, conveyors/lift tables/carts, electrical handling gear), in business 45+ years. Site offers specs, videos, and maintenance/safety documentation per product. Good fit as a single-manufacturer source with consistent product data.
- **Made-in-China.com** ([made-in-china.com](https://www.made-in-china.com/)) - a B2B marketplace/aggregator, not a manufacturer itself; it indexes listings from many Chinese suppliers, manufacturers, and exporters. Useful for breadth and for seeing how varied real-world listings are, but per-listing data quality and reliability will vary by seller - treat it as a lower-trust source and spot-check anything pulled from it.
- **Wheeler Machinery Sales** ([wheelermachinery.com](https://www.wheelermachinery.com/)) - a 75+-year-old used-industrial-machinery dealer/broker (Pomona, CA) carrying Bridgeport, Cincinnati, Haas, GMC, and Dreis & Krump equipment (lathes, mills, grinders, presses, saws, press brakes). Good for real-world used-equipment listings across several brands in one place.
- **Grizzly Industrial** ([grizzly.com](https://www.grizzly.com/)) - a direct-to-consumer manufacturer/retailer (est. 1983) of woodworking and metalworking machinery, with an in-house technical documentation department recognized industry-wide for manual quality. Strong candidate for detailed, consistent spec sheets and manuals. (Confirmed via [grizzly.com/inside-grizzly](https://grizzly.com/inside-grizzly); the main product catalog pages returned a 403 to automated fetch, so direct scraping may need a different approach than a simple fetch.)
- **MASCO** ([mascosocal.com](https://www.mascosocal.com/)) - a Southern California CNC machine tool distributor/dealer (est. 1938) representing manufacturers including Kitamura, Hurco, Takumi, and Sisma, specializing in 5-axis machining centers for aerospace/medical-grade precision work. Good fit for higher-end CNC equipment data, though as a dealer site its product pages are secondary to the manufacturers' own.
- **Haas Automation model guide PDF** ([haascnc.com, 2024 Model Guide](https://www.haascnc.com/content/dam/haascnc/assets/hfos/2024/model-guide/24_08_ModelGuide_EN.pdf)) - **[UNCONFIRMED]** the specific PDF returned a 403 to automated fetch and couldn't be read directly. However, Haas is a well-known, major CNC machine manufacturer, and a separate Haas technical-publications document that *was* fetched (a UK-site dimensions sheet) confirms Haas publishes precision dimensional drawings and specs (tolerances to ten-thousandths of an inch, multiple orthographic views). The linked model guide is very likely the same caliber of primary-source spec document, but that specific file's contents are not independently confirmed here - worth opening it manually once to verify. **Update Oct 5, 2026:** the Haas image Daniel supplied is the HA5C Layout Drawing (Rev B, Sept 17, 2013), the same document as the UK-site dimensions sheet above, not the Model Guide; the Model Guide remains unverified (see Topic 13 for what the drawing shows).

**Overall:** these are a reasonable, usable mix for a standardized test set - one clean single-manufacturer source (BHS), one broad marketplace to stress-test variability (Made-in-China), two regional CNC dealer/distributor sites (Wheeler, MASCO), one manufacturer with strong documentation (Grizzly), and one manufacturer-direct spec PDF (Haas, pending manual confirmation of that exact file).

**Input-pipeline pairing (finalized Oct 2, 2026):** of the 8 inputs from the Oct 1 meeting, only one pairing is assigned to a named person so far - **Ava** is building the pipeline for (3) photos of equipment nameplates + (4) PDF product brochures/datasheets (both are document/text-extraction-heavy: OCR off a nameplate, then structured parsing of a brochure/datasheet). Daniel asked the remaining 6 inputs to be grouped into 3 logical pairs with placeholder names for the rest of the team. **Owners finalized Oct 6, 2026 (from Daniel):** Pair B = Daniel Sweet, Pair C = Shankar Kiran Ragavender, Pair D = Sarkis Nazaryan; the pairs below are the ones he listed:

| Pair | Inputs | Shared processing approach | Assigned to |
|---|---|---|---|
| A (confirmed) | (3) Nameplate photos + (4) PDF brochures/datasheets | OCR + document/text parsing | **Ava** |
| B | (1) Video of facility walkthrough + (2) Photos of machines/components | Raw visual capture of physical machines → feeds detection/segmentation + 3D reconstruction (Topics 5-6: SAM 3, VGGT) | **Daniel Sweet** (Oct 6) |
| C | (5) Facility layout drawings + (6) Schematic illustrations of machines/products | 2D engineering-drawing/schematic interpretation → structured geometry & kinematics (ties into Topic 10's control-logic/kinematic knowledge graph) | **Shankar Kiran Ragavender** (Oct 6) |
| D | (7) PDF product catalogs + (8) Online product-catalog/technical-spec resources | External catalog/spec retrieval & matching → populates the shared knowledge base against what Pair A's OCR identifies (ties into Topic 9's GraphRAG design and the 6 websites above) | **Sarkis Nazaryan** (Oct 6) |

**Update Oct 6, 2026:** Daniel confirmed the pairings and owners (listed in the table). The grouping itself was originally our inference from shared technique; the team's assignment follows it.

**Topic 9 - Knowledge graph (Neo4j) vs. vector RAG for the shared knowledge base.** Vector RAG embeds content and retrieves by semantic similarity ("find the thing that looks like this"). GraphRAG (Neo4j's term) traverses explicit relationships in a knowledge graph instead - better for multi-hop questions like "which manufacturer makes this model, and what else shares its component family?" A 2026 benchmark Neo4j cites found GraphRAG scored ~80% higher on truthfulness than vector-only RAG, answering 65.3% of complex questions correctly versus 28.9% for vector-only retrieval. The two aren't either/or: Neo4j's recommended pattern uses vector search to find a starting point, then graph traversal to expand along real relationships. Source: [Neo4j, "Vector RAG vs. GraphRAG"](https://neo4j.com/blog/agentic-ai/vector-rag-vs-graphrag/). Graphs are already used for industrial digital twins - Neo4j cites CSX Transportation tracking hundreds of thousands of assets and their interrelationships. Source: [Neo4j digital twin press release](https://neo4j.com/press-releases/digital_twin_momentum/).

**Topic 10 - Knowledge graphs for functional (not just visual) digital twins.** Directly addresses the "not a hollow box" gap above. "Multi-Agent Framework Leveraging Knowledge Graphs for Virtual Commissioning Models" ([arXiv:2606.03255](https://arxiv.org/pdf/2606.03255)) builds a knowledge graph connecting a machine's control logic (PLC programs) to its kinematic simulation model (components, joints, sensors, actuators), then uses a three-tier agent system (supervisor, graph-query agent, specialist agents) with GraphRAG to answer structural questions, generate simulation components, and map control signals to simulation objects. Evaluated on a real lab manufacturing system (Festo CP Factory, 52,268 automation elements, 3,404 kinematic components): 90.7% accuracy on system-understanding questions, 100% success generating working simulation scripts, 100% hit@1 on signal mapping, 94.8% overall - versus 0% for an LLM-only baseline and 49% for a single-agent baseline. Human validation was still required throughout (semi-automated, not fully autonomous). **[INFERENCE]** This is close to a working blueprint for our functional-fidelity gap: it suggests the knowledge base needs structured relationships between a machine's logical/control behavior and its physical structure, not just images and PDFs, and that GraphRAG is better suited to querying that than plain vector search.

**Topic 14 - Which technology stack suits this project? (Oct 6, 2026).** Kiran's SRS draft assumed React, Python, and Docker; the team has not decided. Options and tradeoffs only; no decision. Pages were read through an automated fetch that summarizes, so re-check any page the SRS cites. **Similar projects (all Python):** Dr. Li's lab isaac-sim-reconstruction-benchmark (Python 3.10+, uv, Pydantic, OpenCLIP, pxr USD parsing, Click CLI, Isaac Sim 5.1, no web UI or database), the lab's Automated-Digital-Twin-Generation-Pipeline (Python plus .bat scripts, fine-tuned LLaVA, CadQuery, PyTorch/CUDA, Gradio web interface), AHa-3D (Python 3.11, Blender, NVIDIA GPU 24 GB class, Ubuntu/WSL2), and NVlabs SAGE (Python server/client, Isaac Lab/Isaac Sim, TRELLIS, GPT and Qwen, USD). None has a React dashboard, but these are research repos. **Platform findings:** Isaac Sim offers GUI, extension, and standalone Python workflows, and standalone Python "can be run in headless mode"; its container needs Docker and the NVIDIA Container Toolkit, supports Python apps "in headless mode only," and is "recommended for deployment on remote headless servers or the Cloud." Docker Compose can reserve a GPU. FastAPI (Python; async, built-in WebSockets, automatic docs) and Celery (Python task queue; RabbitMQ or Redis brokers) are available for a Python backend. Neo4j has official guides for Python, JavaScript/TypeScript, Java, .NET, Go, and Node.js. NVIDIA's Omniverse Web Viewer sample is React + TypeScript + Vite. **Hardware finding:** Isaac Sim's requirements page lists minimum GeForce RTX 4080 (16 GB), ideal RTX PRO 6000 Blackwell (48 GB), Ubuntu 22.04/24.04 or Windows 11, and states "GPUs without RT Cores (A100, H100) are not supported." TRELLIS.2 (Topic 2) needs an NVIDIA GPU of at least 24 GB. **[INFERENCE]** One machine running both the models and Isaac Sim needs an RT-core GPU with 24 GB or more; the TRELLIS.2 README says its code was verified on A100 and H100 (Linux only), but the A100 is not supported for Isaac Sim. **Options [INFERENCE]:** A = Python (FastAPI) + task queue + React/TypeScript + Docker + Neo4j via Python driver; B = all Python with a Gradio UI; C = Node/TypeScript backend with Python workers. A is most consistent with the sources and B is lowest effort if the dashboard stays simple; none tested. **Live 3D view (added Oct 6):** the team wants one. NVIDIA's Omniverse Web Viewer sample is a React + TypeScript + Vite client that shows a streamed Kit application (USD Viewer Template, Kit 107.3.1+, Node.js 18+, Chromium) over WebRTC with custom messaging; so Option A can support it in principle, backed by a GPU server. Isaac Sim's own headless livestream (browser client via Docker Compose) needs an NVENC GPU, TCP 49100 and UDP 47998, supports one client per instance, is not supported on the A100, and has no authentication or encryption. Concurrency/scaling limits and in-browser viewers for GLB files were not researched. **Team updates (Oct 6, Daniel):** everyone is comfortable with Python and Docker, React is the only new technology to learn; Daniel has a personal GeForce RTX 4090 (NVIDIA lists 24 GB GDDR6X, RT cores) for development, while TRELLIS.2 was verified on A100/H100 only and tested on Linux only. **[INFERENCE]** a 4090 meets the stated criteria for both TRELLIS.2 and Isaac Sim, but running both at once on one 24 GB card would likely be tight. **Open, queued for the Thursday meeting with Dr. Li and Dr. Lu:** which GPUs are available beyond the team's own, and which Isaac Sim version to target. (Also written up as Topic 14 in the Project Design doc's "New Research Topics" tab.)

**Topic 13 - Do our candidate 3D tools produce functional output? (Oct 5, 2026).** Daniel asked that the SRS's claim ("the image-to-3D tools we reviewed produce visual geometry rather than working internals") be checked. Findings, each from the tool's own abstract or README: **SAM 3D** states geometry, texture, and layout from a single image ([arXiv:2511.16624](https://arxiv.org/abs/2511.16624); articulation/physics not mentioned in the abstract, and the Appendix F Limitations text could not be retrieved). **TRELLIS.2** outputs GLB meshes with PBR materials (base color, roughness, metallic, opacity); its README mentions no articulation, physics, mass, or joints, but does list "Internal Enclosed Structures" among the topologies it handles ([GitHub](https://github.com/microsoft/TRELLIS.2)). **Hunyuan3D 2.0** produces a textured 3D shape ([arXiv:2501.12202](https://arxiv.org/abs/2501.12202)). **VGGT** outputs camera parameters, point maps, depth maps, and 3D point tracks - not even meshes or textures ([arXiv:2503.11651](https://arxiv.org/abs/2503.11651)). **CAST** (Dr. Li's deck, Section 6.2) reconstructs static scenes; the agentic deck's own roadmap lists moving from static reconstruction to fully interactive, simulatable environments as a long-term goal (Section 6.3). **Verdict: partly confirmed.** None claims working internals, but absence from an abstract is not proof of absence, and TRELLIS.2 can represent enclosed interior surfaces (nothing says those are accurate or functional for a real machine). **Tools that do target articulation:** Articulate-Anything takes text, images, or videos and generates code compiled into an interactable digital twin, raising success on PartNet-Mobility from 8.7-11.6% to 75% ([arXiv:2410.13882](https://arxiv.org/abs/2410.13882)); URDF-Anything takes a point cloud plus text and outputs URDF files, reporting 17% better segmentation, 29% lower kinematic-parameter error, and 50% better physical executability than baselines ([arXiv:2511.00940](https://arxiv.org/abs/2511.00940)). **[INFERENCE]** Articulation is one piece of function; a CNC machine's behavior also depends on control logic (Topic 10). Neither abstract read names industrial machinery as a test domain, so transfer is unverified. **Decision (Oct 5, 2026, from Daniel):** the team's definition of "functional" is both moving parts and control logic. It is not yet known whether the semester allows time for all of it, but it is set as the goal regardless and the SRS is written as if the time is available. Still open: whether to confirm this definition with Dr. Li, and which approach delivers each half (none tested). **Sample input check (Oct 5, 2026):** Daniel supplied an image of a Haas document, the HA5C Layout Drawing, Revision B, September 17, 2013, (c) Haas Automation, Inc. It is one page with isometric, top, front, side, bottom, and back views giving external dimensions with tolerances, locating-pin positions, and a spindle nose specification (2 3/16-10 NS-2A), and a note pointing to the Rotary Operator's Manual and haascnc.com for further specifications. It shows no internal components, motor specifications, or control information. **[INFERENCE]** From this one document, a drawing-type input supplies dimensions and interfaces useful for geometry and scale, while the functional half of the goal would have to come from other inputs. (Also written up as Topic 13 in the Project Design doc's "New Research Topics" tab.)

---

## 8. Correspondence log with Dr. Bingbing Li

- **~Sept 19–20, 2026:** Daniel sent an initial email (drafted collaboratively, then personalized by Daniel) reintroducing the project — "streamlining how digital twins are made using VLMs in an AI agent-oriented workspace" — noting it continues Yizhan Huang's prior work, and requesting anything Yizhan produced (reports, code, slides, datasets), a pointer to where it lives, or an introduction to Yizhan. Mentioned the team's Thursday meeting deadline. Subject line used: *"MoonWalkers Digital Twin Project: Request for Guidance on Prior Work."*
- **~Sept 21–22, 2026:** No response after ~2 days; Daniel sent a short, low-pressure follow-up email acknowledging Dr. Li was likely busy, restating the Thursday deadline, and offering to proceed without a reply if needed.
- **~Sept 22–23, 2026:** **Dr. Li responded**, sharing two presentation decks (CAST.pptx.pdf, agentic_pipeline_deck.pdf) and the GitHub org link (`Digital-Twin-Interoperability/isaac-sim-reconstruction-benchmark`). See Section 6 for full analysis of what was shared.

---

## 9. Presentation prepared for the Thursday, Sept 24 team meeting

Daniel's assigned speaking slot covers **Topic 4 (prior MoonWalkers work)**, reframed from "Yizhan's specific work" (undeliverable — see §5.3) to the fuller timeline, since his individual contribution couldn't be sourced directly before the meeting. Target: originally 10 minutes, later extended to up to 20 minutes after Dr. Li's materials arrived; final prepared deck runs ~20–22 minutes across 14 content slides plus one separate visual timeline slide.

**Slide sequence (bullets + full speaker talking points already drafted for each):**
1. Title/framing — sets expectation that Yizhan's specific work is still pending, pivots to broader prior-work review.
2. Origins (Summer 2023) — JPL internship beginnings.
3. "Collaborative Moonwalkers" (March 2024) — System 1/System 2 architecture, Omniverse virtual env, digital-twin physics-ML results (66m→23cm error, 400ms vs 90min).
4. Interoperability push (2024–2025) — VERSES/JPL/CSUN demo, IEEE P2874 Spatial Web standard, remote PINN/IP-protection demo.
5. Parallel 2025 threads — V-JEPA action recognition (85% accuracy), NSF NAIRR Large World Model award, November 2025 NVIDIA GTC talk.
6. Most recent work (2026) — March 2026 paper (adds International Space University), August 2026 Oxford DigiTwin talk.
7. What this means for the team's project — every prior twin was built by hand (CAD/texturing), no prior image-to-twin automation found; GTC talk title is closest prior art.
8. Dr. Li's response — transition slide introducing the new materials.
9. The GitHub organization — Mingtao_Ding parallel, `yizhan_A100.yaml` lead.
10. CAST pipeline breakdown (all 6 stages).
11. Agentic pipeline deck breakdown (closed loop, tools, 3 gates).
12. Packing Table case study walkthrough.
13. What's built vs. still open (their own roadmap).
14. Open questions for Dr. Li (the four questions listed in §6.4).

A separate **8-card visual timeline slide** was also drafted (matching the user's existing black-background/neon-green-accent card template), condensing the 2023–2026 timeline into 8 short title+snippet cards for a single graphic slide. Note: as of last discussion, one candidate event (August 2026 Oxford talk) was left off that 8-card version to keep the count at 8; swap-in guidance was given if recency should be prioritized over a middle-timeline item.

**Status as of last update:** slides drafted as bullet points/talking points in chat (user is building the actual deck in their own tool); user was about to send their built deck back for a final review/touch-up pass. **That review has not yet happened as of this file's writing — check whether it occurred in a later conversation.**

---

## 10. Open items / follow-ups to track in future conversations

**Course context (Oct 6, 2026, from Daniel):** the project is a capstone course project. Professor Xunfei Jiang leads the course, reviews the team's work, and guides the team. The SRS follows the course template (Template: Software Requirements Specification, F2026 version, Jira epic CNP-7).

1. **Yizhan Huang's specific work** — ✅ closed Oct 16, 2026 (no longer needed, per Daniel). Previously: still not confirmed. Possible next leads: ask Dr. Li directly at/after the meeting; check for a Yizhan-specific folder in the Digital-Twin-Interoperability org; check the unexplored sibling repos listed in §6.1.
2. **Authorship of CAST / the agentic pipeline** — ✅ closed Oct 16, 2026 (no longer needed).
3. **Whether the agentic pipeline is implemented or conceptual** — ✅ closed Oct 16, 2026: the team builds its own platform, taking inspiration; no lab code will be provided.
4. **Relationship between this project's Isaac Sim asset taxonomy and Stanford's BEHAVIOR-1K** — ✅ closed Oct 16, 2026 (no longer needed).
5. **The 400ms vs. <150ms discrepancy** between the 2024 and 2025 papers' physics-ML modules — ✅ closed Oct 16, 2026 (no longer needed); still do not cite either figure without naming its paper.
6. ✅ Closed Oct 16, 2026 (no longer needed). **GitHub API access was blocked (403)** during this research for both the contributors endpoint and raw README fetch — if continuing this thread, try again later or ask Dr. Li for direct repo access.
7. **Final slide-deck review (Sept 24 deck)** — ✅ closed Oct 16, 2026 (obsolete).
8. **The "few websites" Dr. Li gave for pulling product data** — ✅ resolved Oct 2, 2026. Six sites shared and assessed (see Section 7's "Oct 2, 2026 follow-up (continued)"): BHS Inc., Made-in-China.com, Wheeler Machinery Sales, Grizzly Industrial, MASCO, and a Haas Automation model-guide PDF. One item still open: the specific Haas PDF returned a 403 on automated fetch. On Oct 5 Daniel attached an image of a Haas document. It is the HA5C Layout Drawing (Revision B, September 17, 2013), which matches the HA5C dimensions sheet already fetched from haas.co.uk (same title, revision, date, and dimension values); it is not the 2024 Model Guide. The Model Guide's contents therefore remain unverified. Oct 16, 2026: Daniel confirmed the link given to the team is the 2024 Model Guide PDF and nothing else is known about it; an automated fetch on Oct 16 still failed, so its contents remain unverified. To resolve: open it manually.
9. **Which two inputs each team member is building a pipeline for** — partially resolved Oct 2, 2026. Ava is confirmed on nameplate photos + brochures/datasheets. The other 6 inputs were grouped into 3 pairs (by shared technical approach) — see the pairing table in Section 7. Team roster confirmed Oct 6, 2026: four members - Daniel Sweet, Ava Harken, Sarkis Nazaryan, and Shankar Kiran Ragavender (goes by Kiran). ✅ Resolved Oct 6, 2026: B = Daniel Sweet, C = Shankar Kiran Ragavender, D = Sarkis Nazaryan.
10. **Functional (not just visual) digital twin fidelity** — the biggest open technical gap. Topic 10 (knowledge-graph-based virtual commissioning) is the closest blueprint found so far. Topic 13 (Oct 5) found that none of SAM 3D, TRELLIS.2, Hunyuan3D 2.0, VGGT, or CAST lists articulation, physics, or control behavior as an output, and that Articulate-Anything and URDF-Anything target articulation; whether either transfers to industrial machines is unverified. Decided Oct 5, 2026 (Daniel): "functional" means both moving parts and control logic, set as the goal even though the semester may not allow time for all of it; documents are written as if the time is available. ✅ Confirmed by Dr. Li and Dr. Lu (recorded Oct 16, 2026). Still to decide: which approach delivers each half.
11. **AHa-3D related-work analysis (Oct 1, 2026)** — was written up in the Project Design doc's "Related Work" tab but has not yet been mirrored into this context file; worth doing in a future pass if this file needs to stand fully on its own.
12a. **Technology stack** - ✅ decided Oct 16, 2026: Option A (FastAPI + Celery + React/TypeScript + Docker + Neo4j via its Python driver); the advisors left it to the team. Previously undecided (Oct 6, 2026). Kiran's draft assumed React, Python, and Docker; Daniel asked for research on similar projects and options. Researched Oct 6 as Topic 14 (options only); the team still has to decide, and GPU availability (RT-core requirement for Isaac Sim) is a dependency.
12b. **Neo4j** - ✅ chosen Oct 16, 2026 (unless the team later finds a reason to change); the proof of concept uses a simple store behind an interface. Earlier: confirmed Oct 6, 2026 (Daniel) to be a team suggestion, not a requirement from Dr. Li; Kiran's draft says otherwise and Daniel wants it changed.
12c. **Digital cousin fallback** - ✅ accepted by the advisors as a later fallback (Oct 16, 2026); not part of the proof of concept.
12e. **Sarkis Nazaryan's Section 4 (Nonfunctional Requirements) reviewed Oct 6, 2026** against the template and our Section 1 / Kiran's Section 2. Main findings: GPT-6 Astra and Neo4j named as decided (same issue as Kiran's draft); 4.2.1 depends on the undecided digital cousin; "no hard time limit (per Dr. Li)" for spec lookup is not in our record (we have only "reasonable amount of time"); 4.1.1 is functional rather than performance and overstates what each input type can produce alone; 4.2.3 and 4.3.1 disagree on who may delete shared twins; 4.4.4 "never rebuild" is absolute; the time targets in 4.1.3 and Kiran's 2.5 refer to each other without stating a position; no requirement yet covers functional fidelity (moving parts and control logic), relative attribute preferences (a template ask), or security of a live 3D stream (Isaac Sim's livestream endpoints have no authentication or encryption). Sarkis's section still contains the template's instruction text.
12d. **Product name** - ✅ decided Oct 16, 2026: "MoonWalkers Multimodal Agentic Digital Twin Generation Platform".
12. **SRS Section 1 (revised Oct 5, 2026)** — rewritten for the multimodal scope in the Project Design doc's "SRS - Section 1" tab. Next step planned: review a classmate's SRS section against it for consistency. **Done Oct 6, 2026 for Kiran's Section 2 (Overall Description)** against the instructor's template (Template_Software-Requirements-Specification, F2026) and Section 1; findings were: Neo4j and GPT-6 Astra/Codex stated as decided when they are not; functional-twin goal missing from the function list; digital cousin fallback undefined and relied on elsewhere; stakeholder statements (open-source reuse "as much as needed", footage and layout drawings "will be supplied") stronger than our record; Spatial Web scope unanswered; plus template gaps (user class framing, operating environment detail, documentation formats). Section 1 was updated Oct 6 to add Kiran and Professor Xunfei Jiang to 1.2 and definitions for Digital cousin, Spatial Web, GPU, Articulation, and Control logic in 1.4, with two new references in 1.6. Also added later on Oct 6 for Sarkis's Section 4: TLS, Role-based access control, Salted hash, and Encryption/encryption at rest in 1.4 (sources: Wikipedia, NIST glossary, OWASP; OWASP recommends Argon2id and lists bcrypt for legacy systems), with five references in 1.6.
13. **Project Design doc Parts 1 and 2** — ✅ updated Oct 5, 2026 for the multimodal, functional-twin scope; the Sept 29 content is kept in each tab as labeled history. Meeting Prep and Related Work tabs carry a history note only.
14. **GitHub repository and README (Oct 6, 2026)** — recommended name `moonwalkers-twin-generator` (alternates `multimodal-twin-agent`, `arcs-twin-builder`); private first, hosted under a school account Daniel already has; all teammates and advisors may be named in the README (Daniel will inform them and edit while the repo is private); license to be chosen later (GitHub's docs say that without one, default copyright applies). README written at `README.md` (planning-status honest, 8 Mermaid diagrams validated by rendering); scope-history section removed at Daniel's request (history, not essential). Pipeline owners confirmed Oct 6: A = Ava Harken, B = Daniel Sweet, C = Shankar Kiran Ragavender, D = Sarkis Nazaryan. Instructor's full name: Professor Xunfei Jiang. Next: slides for the Thursday meeting with Dr. Li and Dr. Lu; SRS Section 3 review when Daniel sends it.

---

## 10b. Oct 16, 2026 — Meeting answers, team decisions, and proof-of-concept research

All questions found in a full sweep of the documentation were answered by Daniel on Oct 16, 2026 (advisor answers from the team's meetings with Dr. Li and Dr. Lu, plus team decisions). The full Question / Answer / Date table is the **"Decisions Log (Oct 16)"** tab of the Project Design doc (SRS Section 6 format).

**Advisor answers:** use a locally hosted instance on the team's own GPU for now (an RTX 4090); target the most recent Isaac Sim and Omniverse versions; "functional" = moving parts + control logic is confirmed; digital cousin acceptable later, proof of concept first; no target build time for now (target result; metrics after testing); stack is the team's choice; lookups should be near datasheet-grade if possible, but the user must always see where information came from; generative reconstruction, using catalog matching where available; the PoC may start from multiple photos, video required in the final product; Spatial Web is a stretch goal; build something new, no lab code provided; Dr. Li will provide test inputs (photos expected the week after Oct 16); human review acceptable and necessary in v1, with user-adjustable human input in the final version; novelty is functional twins (AHa-3D usable as much or as little as wanted); no new direction.

**Team decisions:** stack Option A; Neo4j (PoC: simple store behind an interface); AI model and agent runtime to be researched while developing; product name "MoonWalkers Multimodal Agentic Digital Twin Generation Platform"; data flow pipelines → agent orchestrator → knowledge base; PoC is single-user, twins re-versioned on user request, results must say when a twin was found in the knowledge base; non-pipeline owners deferred; evaluation = Dr. Li's deck metrics where they fit + a functional-check measure; research gaps belong to pipeline owners; include a scale-calibration input; an AI assistant/agent should drive the platform (create, edit, submit twins); milestones done so far: architecture design, surveys, sketches/Figma, next PoC then integration; no license for now; historical questions (Yizhan, CAST authorship, BEHAVIOR-1K, 400 vs 150 ms) closed; SRS Section 3 reviewed with fixes applied; course rubric not a constraint (project extends beyond the course).

**Proof of concept (agreed):** prove that an AI agent can create a digital twin in some capacity from one input type (whichever is easiest); a well-known, relatively easy machine with joints and control logic, using photos sourced online until lab photos arrive; a 3D model at minimum, aiming higher; pass criteria = the .usd opens in the target Isaac Sim version, a joint moves, a second request reuses the stored twin; dev machine Windows 11 + RTX 4090 (Linux VMs possible); cost as low as possible (Daniel has Claude Pro); simple store behind an interface; barebones dashboard first; industry-standard conventions; Claude Code may run tests, commit and open PRs but must ask before installing; API keys held by Daniel locally; test data stored locally in the project folder.

**Research findings, Oct 16, 2026 (sources below):**
- Isaac Sim **6.2.0** is the latest release (download page: "Latest Release", October 2026; PyPI `isaacsim 6.2.0.0` released Oct 13, 2026). Requirements: Ubuntu 22.04/24.04 or **Windows 11** (Windows 10 not supported); minimum GeForce RTX 4080 16 GB; 32 GB RAM minimum; Windows driver 595.97; "GPUs without RT Cores (A100, H100) are not supported"; Python 3.12 for the pip install. The RTX 4090 is not named on the page [INFERENCE: it exceeds the 16 GB minimum tier]. Windows install: workstation zip (`post_install.bat`, `isaac-sim.bat`) or `pip install isaacsim[all,extscache]==6.2.0.0 --extra-index-url https://pypi.nvidia.com`. Omniverse Launcher is deprecated. Kit SDK latest is 110.4 (October 2026), bundling OpenUSD 25.11; the USD Viewer is a template built from kit-app-template, not a download.
- Isaac Sim/Omniverse physics parse standard UsdPhysics schemas: `ArticulationRootAPI`, `PhysicsRevoluteJoint`/`PrismaticJoint`, `PhysicsDriveAPI` ("analogous to a PD controller"); drive values in degrees in the GUI tutorial; the Newton backend requires all joints in an articulation with body0 = parent, body1 = child.
- `usd-core` 26.8 (PyPI, Jul 20, 2026; Windows wheels; Python ≥3.9,<3.15) includes `pxr.UsdPhysics` (tested) but no command-line tools. `omniverse-asset-validator` 1.18.0 (pip) provides `omni_asset_validate` with physics joint/articulation checkers. GLB→USD official conversion is `omni.kit.asset_converter` (needs Kit/Isaac Sim).
- Image-to-3D on Windows + 24 GB (none outputs joints): Stable Fast 3D (~6 GB, Windows experimental, Stability Community License, gated weights), SPAR3D (~10.5 GB), Hunyuan3D-2 / 2mv (6 GB shape, 16 GB with texture; Windows listed; multiview input; Tencent community license excludes EU/UK/South Korea), Hunyuan3D-2.1 (29 GB for shape + texture), TRELLIS.2 (≥24 GB, Linux only tested, MIT but nvdiffrast is non-commercial), SAM 3D Objects (≥32 GB, Linux).
- Claude Pro includes Claude Code; usage limits are shared with claude.ai and reset every five hours; per the support article, Pro can use Sonnet but not Opus in Claude Code (may be dated). Claude Code runs natively on Windows (Git for Windows recommended). Project `CLAUDE.md` (target under 200 lines), `CLAUDE.local.md` for personal notes, `.claude/settings.json` permission rules (deny, then ask, then allow), project MCP servers via `.mcp.json` / `claude mcp add --scope project`. Whether headless `claude -p` on a subscription avoids API billing is not confirmed.
- PoC machine candidates: **Haas HA5C** (one servo-driven revolute spindle; control via stand-alone programming with G90/G91 steps, loops, remote cycle start; specs on haas.co.uk; 2006 operator's manual on haascnc.com loads; no public CAD); **Grizzly T33901** benchtop drill press (about five joints; minimal control logic: keyed on/off switch and belt-to-RPM table; full parts breakdown in the public manual); Prusa CORE One+ (published CAD, GPL firmware; more complex). Max-speed figures for the HA5C differ by source (410 °/s on haas.co.uk vs. 330/320 °/s in the 2006 manual).

**Sources (Oct 16, 2026):**
- https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/download.html ; https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html ; https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_workstation.html ; https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/install_python.html ; https://pypi.org/project/isaacsim/
- https://docs.omniverse.nvidia.com/dev-guide/latest/release-notes.html ; https://github.com/NVIDIA-Omniverse/kit-app-template
- https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/articulations.html ; https://docs.isaacsim.omniverse.nvidia.com/latest/physics/newton_physics.html ; https://docs.isaacsim.omniverse.nvidia.com/latest/robot_setup_tutorials/tutorial_gui_simple_robot.html
- https://pypi.org/project/usd-core/ ; https://pypi.org/project/omniverse-asset-validator/ ; https://docs.omniverse.nvidia.com/extensions/latest/ext_asset-converter.html
- https://github.com/Stability-AI/stable-fast-3d ; https://github.com/Stability-AI/stable-point-aware-3d ; https://github.com/Tencent-Hunyuan/Hunyuan3D-2 ; https://github.com/Tencent-Hunyuan/Hunyuan3D-2.1 ; https://github.com/microsoft/TRELLIS.2 ; https://github.com/facebookresearch/sam-3d-objects
- https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan ; https://code.claude.com/docs/en/setup ; https://code.claude.com/docs/en/memory ; https://code.claude.com/docs/en/settings ; https://code.claude.com/docs/en/permissions ; https://code.claude.com/docs/en/mcp
- https://haas.co.uk/?p=2253 ; https://www.haascnc.com/content/dam/haascnc/en/service/manual/operator/english---ha5c-indexer-operator's-manual---2006.pdf ; https://www.grizzly.com/products/T33901 ; https://cdn0.grizzly.com/manuals/t33901_m.pdf ; https://www.prusa3d.com/product/prusa-core-one/

**Work products from Oct 16:** Decisions Log tab; Parts 1/2, SRS Section 1, New Research Topics, and Related Work tabs updated; README updated; a draft shared pipeline output contract (`poc/contracts/pipeline_result.py`, Pydantic, with a JSON Schema export and an illustrative HA5C example) delivered for review.

---

## 11. Master source list (all topics)

**Topic 1 (Fei-Fei Li):**
- https://arxiv.org/abs/2410.07408 (ACDC/Digital Cousins)
- https://digital-cousins.github.io/
- https://arxiv.org/abs/2606.28276 (SimFoundry)
- https://arxiv.org/abs/2403.09227 (BEHAVIOR-1K)
- https://behavior.stanford.edu/
- https://arxiv.org/abs/1808.10654 (Gibson Env)
- https://profiles.stanford.edu/fei-fei-li
- https://time.com/7339693/fei-fei-li-ai/
- https://time.com/7339513/ai-fei-fei-li-virtual-worlds/
- https://www.worldlabs.ai/blog/marble-world-model
- https://www.worldlabs.ai/blog/announcing-the-world-api

**Topic 2 (AI models & digital twins):**
- https://openai.com/index/gpt-6-astra/
- https://deploymentsafety.openai.com/gpt-6-astra
- https://techcrunch.com/2026/09/03/openai-launches-astra-its-powerful-and-controversial-new-model/
- https://platform.claude.com/docs/en/about-claude/models/overview
- https://platform.claude.com/docs/en/build-with-claude/vision
- https://www.anthropic.com/news/claude-for-creative-work
- https://manufactur3dmag.com/anthropic-claude-for-cad-fusion-blender/
- https://deepmind.google/blog/gemini-robotics-er-1-6/
- https://ai.google.dev/gemini-api/docs/robotics-spatial
- https://arxiv.org/abs/2511.16624 (SAM 3D)
- https://github.com/microsoft/TRELLIS.2
- https://arxiv.org/abs/2501.12202 (Hunyuan3D 2.0)
- https://developer.nvidia.com/blog/how-to-use-ai-agents-to-prepare-3d-scenes-for-simulation/

**Topic 3 (Hermes & AI agents):**
- https://hermes-agent.nousresearch.com/docs/
- https://hermes-agent.nousresearch.com/docs/user-guide/security
- https://github.com/NousResearch/hermes-agent
- https://github.com/NousResearch/hermes-agent/issues/7826
- https://labs.cloudsecurityalliance.org/research/csa-research-note-hermes-agent-cves-20260504-csa-styled/
- https://developer.nvidia.com/blog/deploy-self-evolving-agents-for-faster-more-secure-research-with-a-hermes-agent-and-nvidia-nemoclaw/
- https://github.com/NVIDIA/NemoClaw
- https://en.wikipedia.org/wiki/OpenClaw
- https://www.anthropic.com/engineering/building-effective-agents
- https://code.claude.com/docs/en/agent-sdk/overview
- https://openai.com/index/the-next-evolution-of-the-agents-sdk/
- https://www.langchain.com/deep-agents
- https://modelcontextprotocol.io/docs/getting-started/intro

**Topic 4 (Prior MoonWalkers work & Yizhan Huang):**
- Uploaded PDFs: "Collaborative_Moonwalkers.pdf" (IEEE Aerospace 2024); "Enabling_Interoperable_Digital_Twins_for_Collaborative_Lunar_Exploration_1.pdf" (IEEE Aerospace 2025) — read in full
- https://arcs.center/2026-arcs-fellows-associates/
- https://arcs.center/metaverse-for-moon-exploration/
- https://arcs.center/2025-fellow-associate-project-list/
- https://arcs.center/publications/
- https://arcs.center/seminars/
- https://arcs.center/faculty/
- https://www.ecs.csun.edu/~bingbing/people.html
- https://www.ecs.csun.edu/~bingbing/publication.html
- https://www.ecs.csun.edu/~bingbing/news.html
- https://www.jpl.nasa.gov/site/research/thomaslu/
- https://www.verses.ai/news/verses-completes-first-phase-of-digital-twins-interoperability-project-with-jpl
- DOI 10.1109/AERO58975.2024.10521103 (2024 paper)
- DOI 10.1109/AERO63441.2025.11068549 (2025 paper)
- DOI 10.1117/12.3052411 (V-JEPA SPIE paper)
- DOI 10.1109/AERO66936.2026.11519858 (2026 paper)

**New materials from Dr. Li:**
- https://github.com/Digital-Twin-Interoperability/isaac-sim-reconstruction-benchmark
- GitHub org: Digital-Twin-Interoperability (30 repos)
- Uploaded decks: "CAST.pptx.pdf" (Component-Aligned 3D Scene Reconstruction); "agentic_pipeline_deck.pdf" ("From Image to Executable Scene") — both read in full

**New research topics (Sept 30, 2026 — post-pivot, Section 7):**
- SAM 2: https://ai.meta.com/research/sam2/
- SAM 3: https://ai.meta.com/research/sam3/
- Roboflow, "SAM 3: Segment Anything with Concepts": https://blog.roboflow.com/what-is-sam3/
- VGGT (Visual Geometry Grounded Transformer): https://arxiv.org/html/2503.11651v1
- Ocean-OCR: https://arxiv.org/pdf/2501.15558
- Altium, Octopart API documentation: https://www.altium.com/documentation/altium-developer-center/octopart

**Knowledge graph / GraphRAG research (Oct 2, 2026 — post multimodal-expansion meeting, Section 7):**
- Neo4j, "Vector RAG vs. GraphRAG": https://neo4j.com/blog/agentic-ai/vector-rag-vs-graphrag/
- Neo4j digital twin press release: https://neo4j.com/press-releases/digital_twin_momentum/
- "Multi-Agent Framework Leveraging Knowledge Graphs for Virtual Commissioning Models," arXiv:2606.03255: https://arxiv.org/pdf/2606.03255

**Related work (Oct 1, 2026, in the Project Design doc's "Related Work" tab, not yet mirrored here in full):**
- AHa-3D GitHub repo: https://github.com/KevinXu02/aha-3d
- AHa-3D project site: https://kevinxu02.github.io/real2sim-indoor-site/
- REAL2SIM_PIPELINE.md: https://raw.githubusercontent.com/KevinXu02/aha-3d/main/docs/REAL2SIM_PIPELINE.md
- RESULTS.md: https://raw.githubusercontent.com/KevinXu02/aha-3d/main/docs/RESULTS.md

**Oct 5, 2026 additions (Section 7):**
- Thomas Lu, NASA JPL research profile: https://www.jpl.nasa.gov/site/research/thomaslu/
- NVIDIA, Omniverse Developer Overview: https://docs.omniverse.nvidia.com/dev-overview/latest/introduction.html
- SAM 3D (arXiv abstract): https://arxiv.org/abs/2511.16624
- TRELLIS.2 README: https://github.com/microsoft/TRELLIS.2
- Hunyuan3D 2.0 (arXiv abstract): https://arxiv.org/abs/2501.12202
- VGGT (arXiv abstract): https://arxiv.org/abs/2503.11651
- Articulate-Anything (arXiv abstract): https://arxiv.org/abs/2410.13882
- URDF-Anything (arXiv abstract): https://arxiv.org/abs/2511.00940

**Dr. Li's product-data sources (Oct 2, 2026, Section 7):**
- BHS, Inc.: https://na.bhs1.com/
- Made-in-China.com: https://www.made-in-china.com/
- Wheeler Machinery Sales: https://www.wheelermachinery.com/
- Grizzly Industrial: https://www.grizzly.com/ (company confirmation via https://grizzly.com/inside-grizzly)
- MASCO: https://www.mascosocal.com/
- Haas Automation 2024 Model Guide (PDF, [UNCONFIRMED] - fetch blocked, see Section 7): https://www.haascnc.com/content/dam/haascnc/assets/hfos/2024/model-guide/24_08_ModelGuide_EN.pdf
- Corroborating Haas technical-publication sample (fetched successfully): https://www.haas.co.uk/wp-content/uploads/2019/10/HA5C_Dimensions.pdf


**Topic 14 sources (Oct 6, 2026):**
- https://github.com/Digital-Twin-Interoperability/isaac-sim-reconstruction-benchmark
- https://github.com/Digital-Twin-Interoperability/Automated-Digital-Twin-Generation-Pipeline
- https://github.com/KevinXu02/aha-3d
- https://github.com/NVlabs/sage
- https://github.com/NVIDIA-Omniverse/web-viewer-sample
- https://docs.isaacsim.omniverse.nvidia.com/latest/introduction/workflows.html
- https://docs.isaacsim.omniverse.nvidia.com/latest/python_scripting/manual_standalone_python.html
- https://docs.isaacsim.omniverse.nvidia.com/latest/installation/install_container.html
- https://docs.isaacsim.omniverse.nvidia.com/latest/installation/requirements.html
- https://docs.isaacsim.omniverse.nvidia.com/latest/development_tools/agent_skills.html
- https://docs.isaacsim.omniverse.nvidia.com/latest/installation/manual_livestream_clients.html
- https://docs.omniverse.nvidia.com/embedded-web-viewer/latest/workflow/streaming-and-messaging.html
- https://www.nvidia.com/en-us/geforce/graphics-cards/40-series/rtx-4090/
- https://github.com/microsoft/TRELLIS.2 (hardware requirements section)
- https://docs.docker.com/compose/how-tos/gpu-support/
- https://fastapi.tiangolo.com/ and https://fastapi.tiangolo.com/advanced/websockets/
- https://docs.celeryq.dev/en/stable/getting-started/introduction.html
- https://neo4j.com/docs/getting-started/languages-guides/
- https://neo4j.com/deployment-center/
- https://www.haas.co.uk/wp-content/uploads/2019/10/HA5C_Dimensions.pdf (HA5C Layout Drawing, Oct 5 sample check)

---

*End of context file. When resuming this project in a new conversation, share this file first, then state what's changed since October 5, 2026 (e.g., which teammate takes pair B/C/D, outcome of further Neo4j/knowledge-graph planning, confirmation of the Haas Model Guide's contents, whether Dr. Li confirms the definition of "functional" as moving parts plus control logic).*
