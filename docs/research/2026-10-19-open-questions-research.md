# Researching the PoC's open questions ourselves (2026-10-19)

**Question.** Before the PoC goes to the advisors, which open questions can we settle from trusted
sources ourselves, without a person at a real machine? Daniel asked for this: "The goal for this
platform will be to have the agentic agent be able to do research onto a machine/component's
function and motion as well from other trusted sources. So let's see if we can research this on our
own first."

**Dates.** Read on 2026-10-19 (local time, PDT). The files fetched are logged in their machine's
`SOURCES.md` with SHA-256 hashes:
- `data/machines/haas-ha5c/inputs/documents/haas-rotary-tailstock-operators-manual-2012.pdf`;
- `data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`.

PDF text was read with pypdf, and page numbers are the PDF's.

## Sources
- **The 2006 HA5C manual** (already in use): "HA5C Operators Manual 96-4039N RevN English June
  2006", `data/machines/haas-ha5c/inputs/documents/ha5c-operators-manual-2006.pdf`.
- **The 2012 rotary manual:** Haas's Rotary and Tailstock Operator's Manual, "96-0315 Rev P April
  2012", which covers the HA5C. It was fetched from
  https://www.haastooling.com/content/dam/haascnc/en/service/manual/operator/english---rotary---tailstock-operator's-manual---2012.pdf.
  Its archive cover page warns: "Publications are intended for use only with machines built at the
  time of original publication. As machine designs change the content of these publications can
  become obsolete."
- **The Haas UK HA5C page,** saved on 2026-10-18 (`haas-uk_HA5C_product-page_2026-10-18.html`).
- **The Grizzly T33901/T33902 manual,** https://cdn0.grizzly.com/manuals/t33901_m.pdf:
  "COPYRIGHT © SEPTEMBER, 2023 BY GRIZZLY INDUSTRIAL, INC., REVISED DECEMBER, 2023". Its data sheet
  "is deemed accurate as of 12/27/2023".
- **OpenAI's Codex documentation on MCP.** https://developers.openai.com/codex/mcp redirects (HTTP
  308) to https://learn.chatgpt.com/docs/extend/mcp?surface=cli, which shows no date or version.
- **Searches** (WebSearch, standard and extended) for HA5C service procedures and parameter
  tables. haascnc.com's own pages answered WebFetch with HTTP 403, as on 2026-10-18 (worklog), so
  only their search snippets were seen.

## 1. Does the six-screw disc turn with the spindle? Not settled
- **What the sources say:**
  - The 2006 manual says locking comes from "the large bearing area between spindle and body"
    (p. 2).
  - The 2006 parts list (p. 53) names a "SPINDLE COVER S5C", a "BEARING END CAP" and a "REAR OIL
    SHIELD 5CV". It also lists six "SHCS 1/4-20 X 1" and six "WASHER 1/4 COPPER" (decision 0012).
  - Seal labels: the 2006 manual has "Front Seal" and "Front Spindle Seal" (p. 50). The 2012
    manual has "Front Seal" and "Front Platter Seal" (p. 72).
- **What none of them says:** which part the six screws hold, or whether that part turns. No HA5C
  service procedure was found: the searches returned lathe and 5-axis procedures, which do not
  apply.
- **[INFERENCE]** Copper washers under screws are commonly used as seals. Six of them would fit a
  cover bolted to a lubricated housing, which would not turn. That agrees with Daniel's choice (the
  nose turns alone), but it is not confirmed.
- **What would settle it:** a look at a real HA5C, an exploded view of the spindle, or more photos
  of the front from other angles.

## 2. Which way the spindle turns, and which way it homes
- **Homing search: documented.**
  - "All Haas indexers home in the clockwise direction as viewed from the spindle" (2006, p. 9).
  - "All Haas indexers home in the clockwise direction as viewed from the platter/spindle" (2012,
    p. 18).
  - At power-up, "The motor then operates slowly in a clockwise direction (as viewed from the
    platter of a rotary table) until the proximity switch is magnetically tripped" (2006, p. 45).

  This is the search for the home switch at power-up, not a program's return home.
- **A positive step: the sources point both ways.**
  - The 2012 manual: "The direction of G33 motion is clockwise when the step size is set to 1.000
    and counter-clockwise when it is set to -1.000" (p. 47). It does not say from where it is
    viewed.
  - Parameter 27 has "+256: search for home in positive direction", added "to reverse direction
    when seeking a home switch" (2012, p. 63; 2006, p. 45). [INFERENCE] So the default search,
    clockwise from the spindle, is the negative direction. If G33's "clockwise" is also seen from
    the spindle, the two statements disagree.
  - "Different table movements are possible, for positive directions, depending on the equipment,
    parameter settings, or five-axis programming software being used" (2012, p. 38). Parameter 11
    holds "two flags used to reverse the direction of the motor drive and encoder" (2012, p. 60).
- **Our twin.** A positive step turns the spindle counter-clockwise as seen from in front of the
  nose [INFERENCE: the right-hand rule about +X, which points out of the nose towards the viewer;
  decisions 0012 and 0016]. That matches Parameter 27's reading and is the opposite of G33's,
  if G33's is seen from the spindle. **Still not confirmed.** A real machine, or Haas, would settle
  it. The direction could be a program setting, like `--absolute`, once it is known.
- **A program's return home** (Parameter 27's "+8", "+16" or "+24: home to zero position in
  shortest direction"): neither manual gives the HA5C's setting. **Not confirmed.**

## 3. Acceleration and the pause between steps
- **Parameter 18 (acceleration).** Both manuals give only its range, and their scale factors
  differ:
  - 2006: "The value used is (Par 18)*100 in encoder steps/second/second" (research note
    2026-10-18);
  - 2012: "The value used is (Par 18)*10 in encoder steps/second/second. The highest acceleration
    is thus 655350 steps per second per s[econd]" (p. 61).
- **Parameter 44** is an "Exponential acceleration time constant. Units are 1/10000 seconds"
  (2012, p. 65), with no value.
- **Parameter 16** ("Auto Continue Dwell, range 0 to 99") has no HA5C value.

Neither manual gives HA5C values for any of these. Some parameters do carry HA5C notes, such as
"(Not used in HA5C, and defaulted to 0.)" (2012, p. 62). The values above stay **not confirmed**.
The 2012 manual's parameter list on p. 27 holds "Initial settings" for a FANUC serial interface,
not HA5C defaults.

## 4. Does today's controller work as the 2006 manual says? Partly answered
The 2012 manual keeps the same programming model:
- "Each one of the possible 99 steps in a program must contain a G code (G)" (p. 45);
- G95 to G99 with the same meanings, for example "G97 Delay by L count/10 seconds (down to 0.1
  second)" (p. 47);
- "programming a G97 and setting L = 10 will produce a 1 second dwell" (p. 48).

It adds G33 (continuous motion). So the model held from 2006 to at least April 2012. Whether an
HA5C sold in 2026 uses the same controller is **not confirmed**.

## 5. The HA5C's weight: found
The Haas UK page's specification table gives "Weight ... Rotary Head 48 lb 21.8 kg" and
"Brushless Control – 1-Axis 14.2 lb 6.4 kg". A twin could use the head's 21.8 kg instead of the
placeholder density (decision 0010). Splitting it between the body and the spindle would still be
our choice [INFERENCE].

## 6. The backup machine: what the Grizzly T33901 has
From the manual's "Controls & Components" (PDF pp. 6-7), its data sheet (p. 8) and "Positioning
Table" (p. 32):
- **The spindle** turns, driven by the motor through V-belts. "The spindle has twelve speeds that
  operate between 340–2860 RPM. Spindle speed is controlled by the configuration of V-belts and
  pulleys" (p. 30).
- **The quill** slides: "Spindle Travel ... 3-1/4 in." (p. 8).
  - The "Downfeed Handle (1 of 3): Moves spindle down when pulled down. Spindle automatically
    returns to top position when released" (p. 7).
  - The "Spindle Return Spring: Automatically returns quill into headstock" (p. 7).
  - The "Depth Stop: Stops spindle travel at predetermined drilling depth" (p. 7).
- **The table:** "The table moves vertically, rotates 360° around its center, rotates 360° around
  the column, and tilts 45° left or right" (p. 32). Each motion has a lock: the table height crank
  and its lock handle, the table pivot lock handle, and a tilt lock hex bolt.
- **Controls:**
  - "ON/OFF Switch w/Disabling Key: Turns motor ON when moved up; turns motor OFF when moved
    down. Removal of yellow key disables switch so motor cannot start" (p. 6);
  - LED and laser switches.
- **Sizes and weight:**
  - "Weight ... 108 lbs.";
  - "Width (side-to-side) x Depth (front-to-back) x Height ... 15 x 25-1/2 x 39 in.";
  - "Max. Distance From Spindle to Column ... 7 in.";
  - "Max. Distance From Spindle to Table ... 15-7/8 in." (p. 8).

**[INFERENCE] What a twin of it would need**, which is more than Pipeline B and the exporter do
today (one revolute joint about +X; "prismatic joints are not exported yet", `usd/exporter.py`).
Our contract already allows a `prismatic` joint type.
- several moving parts cut from one mesh;
- vertical axes;
- a chain of joints: column, then table arm, then table;
- sliding joints;
- a handle coupled to the quill;
- a spring return and an adjustable stop;
- adjustments that are locked rather than driven.

The decisions this needs are listed in `docs/poc-report.md`, section 8.

**Leads for coupling the handle to the quill,** found by search and not yet read or tried:
- the Omniverse USD physics schema has a `PhysxSchemaPhysxPhysicsRackAndPinionJoint`, "a
  predefined rack & pinion joint type" (search snippet of
  https://docs.omniverse.nvidia.com/kit/docs/omni_usd_schema_physics/106.1/physx_physics_rack_and_pinion_joint_8h.html);
- NVIDIA's SimReady guide describes mimic joints, `PhysxMimicJointAPI`, in which a joint follows
  another by a gear ratio (search snippet of
  https://nvidia.github.io/simready-foundation/latest/guides/benchmark/tests/fet022/mimic-joint.html).

Neither is in usd-core's `UsdPhysics`, and neither has been checked for Isaac Sim 6.2.

## 7. Can Codex use our MCP server? Yes, with a longer tool timeout
From OpenAI's MCP page:
- **Our kind of server is supported:** "STDIO servers: Servers that run as a local process (started
  by a command)."
- **Where the configuration goes:**
  - "Configure each MCP server with a `[mcp_servers.<server-name>]` table in the configuration
    file", which is `~/.codex/config.toml` by default;
  - for a stdio server, `command` is required, and `args`, `env` and `cwd` are optional;
  - servers can be scoped "to a project with `.codex/config.toml` (trusted projects only)";
  - "The ChatGPT desktop app, Codex CLI, and IDE extension share this configuration."
- **Timeouts:** `startup_timeout_sec` defaults to 10, and `tool_timeout_sec` is the "Timeout
  (seconds) for the server to run a tool. Default: `60`."

[INFERENCE] Our `.mcp.json` gives Claude Code 600,000 ms per call (decision 0013), and
`generate_geometry` took 46.8-57.1 s on the four real runs. So a Codex setup needs
`tool_timeout_sec` raised, to 600 to match. The agent procedure also names Claude Code's own tools
(its Read tool, `/mcp`), which a Codex version would word for Codex. Not yet tried with Codex.

## Still open after this research
1. Whether the six-screw disc turns.
2. Which way a positive step turns the real spindle.
3. The HA5C's program-home direction, acceleration (Parameters 18 and 44) and dwell (Parameter
   16).
4. Whether a 2026 HA5C controller matches the 2012 manual.
5. What the drawing's 7.80 in spans. It is printed right of the Side View, level with that view's
   spindle centreline mark (pypdf text position (713.8, 694.5) on a 792 × 1224 pt page). Daniel
   read 7.93 in as the depth from the spindle nose to the back of the unit (2026-10-19).
6. Whether PhysX's rack-and-pinion or mimic joints work in Isaac Sim 6.2.
7. A Codex run of the agent procedure.
