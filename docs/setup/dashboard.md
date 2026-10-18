# Running the API and the dashboard (Phase 5)

The dashboard is a web page for people: upload a machine photo, follow the job, and look at a twin
with its sources and reviews. The API behind it (`moonwalkers.api`, decision 0014) works on the
same `data/` folder as the agent's MCP server. Both run only on this computer.

Prerequisites: the backend synced (`uv sync` in `backend/`) and the dashboard's packages installed
(`npm ci` in `dashboard/`), as in `docs/setup/windows-dev-setup.md`.

## 1. Start it
**One server, the usual way.** Build the dashboard once, then let the API serve it:
```
cd dashboard
npm run build
cd ../backend
uv run python -m moonwalkers.api
```
Open http://127.0.0.1:8000/. The API's own documentation is at http://127.0.0.1:8000/api/docs.
Stop it with Ctrl+C.

**While changing the dashboard's code,** run two terminals:
```
# terminal 1, in backend/
uv run python -m moonwalkers.api
# terminal 2, in dashboard/
npm run dev
```
Open http://localhost:5173/. Vite reloads the page on every change and forwards `/api` to port 8000.

Options for `python -m moonwalkers.api`:
- `--data <folder>`: another data folder, for example a scratch copy (section 3). The default is
  the one the MCP server uses: `MOONWALKERS_DATA_DIR`, else the repository's `data/`.
- `--port <n>`: another port. The development server always forwards to 8000.

The API never listens beyond 127.0.0.1 and has no login. Don't expose it on a network: the input
documents are copyrighted and kept for internal research only (`data/README.md`).

## 2. What to check (read-only, on the real data)
1. **The top bar** shows "3 twin versions · 0 open jobs" and the data folder.
2. **Jobs:** three jobs, `2026-10-18_run-001` (Built `haas/ha5c@v3`) and the two from 2026-10-17
   (v2 and v1). Open `2026-10-18_run-001`:
   - all six steps ticked, most with a detail, such as "hunyuan3d-2 2.0.2 in 46.8 s";
   - the photo, the agent's reading notes with quotes, the images (generator input, mesh views,
     previews) and the files.
3. **Twins:** `haas/ha5c` with v3, v2 and v1, each "Needs review", and "A request for this machine
   reuses v3". Open v3:
   - the facts, each with its source, page and quote;
   - the parts with their sizes, the joint (top speed "5.7596 rad/s (330 °/s)"), the scale, the
     control behaviours and the issues;
   - the sources table, where the two PDFs have a "saved copy" link that opens the local PDF;
   - the USD link downloads `twin.usdc`.
4. **Sources:** the drawing and the manual each listed once, cited by v1, v2 and v3.
5. **Narrow window:** the page stays readable at phone width, and tables scroll sideways.

## 3. Trying uploads and reviews on a scratch copy
Uploads and reviews are permanent records (run folders and the knowledge base are never edited,
`data/README.md`). To try them without adding records to the real data, use a copy. In PowerShell,
from the repository:
```
Copy-Item data "$env:TEMP\mw-data-try" -Recurse
cd backend
uv run python -m moonwalkers.api --data "$env:TEMP\mw-data-try"
```
Then, in the dashboard:
1. **Reuse.** Start a job: manufacturer `Haas`, model `HA5C`, the photo
   `data/machines/haas-ha5c/inputs/photos/haas-uk_HA5C_2011.original.jpg`, and where it came from.
   Leave "new version" unticked. The job opens as **Reused `haas/ha5c@v3`**, with the message
   "Found an existing twin (v3, needs review) for haas/ha5c; reused it.". This is the PoC's reuse
   criterion, from the dashboard.
2. **A job for the agent.** Do the same with "Build a new version" ticked. The job shows **Waiting
   for the agent** and a prompt to copy. (Building it would need Claude Code with its MCP server on
   the same copy, through `MOONWALKERS_DATA_DIR`; that is not needed for this check.)
3. **A review.** Open v3, choose Reject, give a name and a reason, and record it. The badge turns
   to "Rejected", and the twins page now says a request reuses v2. Start another job like step 1:
   it reuses v2 and says "Newer versions were rejected in review: v3."
4. **Refusals.** Try uploading a PDF (pick "All files" in the file dialog): "the photo must be a
   JPEG or PNG image".

Delete the copy afterwards: `Remove-Item "$env:TEMP\mw-data-try" -Recurse`.

## 4. Real reviews
A review on the real data is a real decision, kept with the twin version (decision 0015). For
example, Daniel's Isaac Sim check of v2 (worklog 2026-10-18: success level 2) could become an
approval of v2 with that reason. Reviews are added, never edited: a later review of the same version
decides from then on.

## 5. Report back
For the worklog: what you checked in section 2 and 3, the browser and its version, anything that
looked wrong (with a screenshot if you can), and whether the look fits the monochrome wireframe.
