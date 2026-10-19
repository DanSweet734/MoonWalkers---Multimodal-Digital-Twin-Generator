# Research notes

- `project-context.md` - the full project context file (research topics 1-14, meeting notes, decisions,
  sources). Large: read the section you need rather than the whole file. Section 10b holds the Oct 16, 2026
  decisions and proof-of-concept research.
- Add one file per new research question, named `YYYY-MM-DD-topic.md`, with: the question, sources (URL +
  access date + short quote), findings, `[INFERENCE]`-labeled conclusions, and open questions.
- `2026-10-17-usd-physics-for-isaac-sim.md` - how to write a simulatable twin as OpenUSD for Isaac Sim 6.2
  (units, articulations, joints, drives, colliders, mass) and what each validator catches.
- `2026-10-17-ha5c-photo-to-twin.md` - Phase 3: the HA5C photo and documents, the facts read from them
  (with quotes and pages), which drawing dimension is which, what turns with the spindle, Hunyuan3D-2's
  requirements and license, measurements on the generated mesh, reproducibility, and export findings.
- `2026-10-18-mcp-server-for-claude-code.md` - Phase 4: the MCP Python SDK 2.3 (license, dependencies,
  API, how errors and results reach the client), how Claude Code loads and limits project MCP servers,
  and measurements on our server.
- `2026-10-18-api-and-dashboard.md` - Phase 5: FastAPI 0.146 (release, pinning, what the install
  added), generating TypeScript types (why not `openapi-typescript` or `json-schema-to-typescript`),
  Node's test runner for TypeScript, protecting a local API without a login (OWASP, the MCP
  specification on DNS rebinding, Starlette's host check), Vite's proxy, and measurements.

Note: `project-context.md` summarizes material shared by Dr. Li's lab. Daniel asked Dr. Li on 2026-10-17, and
Dr. Li said it is not protected and does not need to be kept private, so the repository may be public.
