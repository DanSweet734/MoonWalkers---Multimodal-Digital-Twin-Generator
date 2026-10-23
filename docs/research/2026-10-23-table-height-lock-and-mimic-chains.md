# The T33901's table height lock, and chains of mimic joints (2026-10-23)

**Why.** Daniel's review of decision 0020 (2026-10-23) asked for research on two of its
inferences:
1. **The table height.** The record called the height "locked" because "the crank's worm holds
   it" [INFERENCE]. Does the worm hold the table? What holds it in use?
2. **Chains of links.** The record refused a leader that itself follows another joint, because
   "whether PhysX takes a mimic of a mimic was not researched". Does it?

**Sources.** All read on 2026-10-23.
- **The T33901 manual:**
  - the file: `data/machines/grizzly-t33901/inputs/documents/grizzly-t33901-t33902-manual-2023.pdf`;
  - the download: https://cdn0.grizzly.com/manuals/t33901_m.pdf;
  - read with pypdf; page numbers are the PDF's.
- **A. V. Karvelis, "Self-locking worm gears: fact or fiction?",** *Machine Design*, 2000-03-01:
  https://www.machinedesign.com/motors-drives/article/21834661/selflocking-worm-gears-fact-or-fiction.
  Quotes checked against the downloaded page.
- **PhysX 5.6.1's documentation:**
  - "Articulations", section "Mimic Joints": https://nvidia-omniverse.github.io/PhysX/physx/5.6.1/docs/Articulations.html
    (page footer: "Last updated on Jul 22, 2025"). Quotes checked against the downloaded page;
  - the PhysX Team's "Mimic Joints" maths note, dated "September 25, 2024":
    https://nvidia-omniverse.github.io/PhysX/physx/5.6.1/_downloads/9489689e1019677308b6f6cbb82bc5db/mimicJoints.pdf.
- **Isaac Sim 6.2.0's own files** on Daniel's machine (`C:\isaacsim`), read only:
  - the PhysX schema, `extscache/omni.usd.schema.physx-110.4.4+.../plugins/PhysxSchema/resources/schema.usda`,
    class `PhysxMimicJointAPI`;
  - the SimReady validator, `exts/isaacsim.asset.validation/pip_prebundle/simready/foundation/tier_core/capabilities/physics_bodies/physics_driven_joints/validation.py`,
    class `MimicAPICheck`;
  - the URDF converter, `exts/isaacsim.asset.importer.urdf/urdf_prebundle/urdf_usd_converter/_impl/link.py`;
  - Newton's builder, `exts/isaacsim.pip.newton/pip_prebundle/newton/_src/sim/builder.py`,
    `add_constraint_mimic`.
- **Could not be read:**
  - a Garage Journal thread about a drill press table that fell once its lock was loosened
    (https://www.garagejournal.com/forum/showthread.php?p=5082636): HTTP 403. A search summary
    described it, but it is not a primary source and its machine is not known;
  - Grizzly's product and parts pages: they refused scripts on 2026-10-22
    (`docs/research/2026-10-22-t33901-handle-ratio-and-figures.md`), so they were not retried.

## 1. What holds the table's height
**The manual: the lock handle holds the height in use.**
- p. 7: "T. Table Height Lock Handle: Loosens to allow adjustment of table position on column;
  tightens to lock table position."
- p. 32, "Raising/Lowering Table": "1. Loosen table height lock handle (see Figure 36). 2. Raise or
  lower table by rotating table height crank (see Figure 36), then tighten table height lock handle
  to secure."
- p. 38, troubleshooting, "Table hard to move": the causes are "1. Table locked. 2. Dirty or dry
  rack and pinion", and the fixes "1. Disengage table locks (Page 30)", and so on.

So "locked" is the height's mode because of the lock handle, which the manual names. The worm is
not needed for that.

**The same handle locks the table around the column.** p. 7's "table position on column" covers
both the height and the turn around the column. p. 32's "Rotating Table Around Column" says
"Loosen table lock handle (see Figure 36)", and Figure 36 labels only the "Table Height Lock
Handle" and the "Table Pivot Lock Handle". This supports what the plan listed as an inference to
check (`docs/drill-press-plan.md`, "What the manual gives"). [INFERENCE: "position on column" is
read as both motions; the manual does not list them.]

**The mechanism.** The crank turns a worm, which turns a 14-tooth gear that meshes with the column
rack [INFERENCE: the gear's mesh with the rack is read from the parts' names and from p. 9's
"Rack and Pinion"; the text does not say it]:
- p. 23: "Install table height crank over worm shaft shown in Figure 21";
- p. 50, the parts list: "107 ... GEAR SHAFT", "108 ... GEAR 14T", "109 ... WORM SHAFT", "113 ...
  RACK", "106 ... COLUMN BRACKET";
- p. 9: "Hand-Crank Enabled Rack and Pinion Table Elevation".

**Whether the worm holds the table when the lock is loose: not confirmed.**
- The engineering condition, Karvelis: "the load on the worm gear can't drive the worm if the
  coefficient of friction between worm gear and worm is larger than the tangent of the worm's lead
  angle. In other words, the friction angle must be larger than the lead angle to prevent
  backdriving."
- It is a static condition, and can fail: "All theoretical analyses of self-locking worm gears
  deal with static conditions." Under "shock and vibration, the friction coefficient between worm
  and gear may suddenly drop", and then "the gears are no longer self-locking and back-driving can
  occur."
- The article's rule: "If safety is a potential issue, always add an adequate braking device,
  whether or not vibration and shock are expected." It also quotes Machinery's Handbook: "It is
  usually impractical to design irreversible worm gearing with any security."
- The manual gives no lead angle, number of starts, or materials for the worm, so the condition
  cannot be checked. The lock handle the manual names would be the braking device the rule asks
  for [INFERENCE].

**What would settle it:** on a real T33901, loosen the height lock with nothing on the table and
see whether the table drifts down, with and without a tap. Or ask Grizzly. Both are for the lab or
Daniel.

**Daniel's own research (2026-10-23, reported in chat):**
- **The Garage Journal thread** is about a 1950s Craftsman drill press, model 103.23140, not the
  T33901. Its table's mechanism looks similar, and the thread says the table fell once a lock was
  loosened.
- **Grizzly's site:** he could reach it, but found no page for the T33901. He found listings at
  Home Depot and Lowe's [not read here; retailer listings are not primary sources].
- **His direction:** "Other drill presses seem to show that behavior so it might be a safe
  assumption to assume the T33901 does as well unless otherwise stated somewhere."

**For the twin:**
- **Contract (decision 0020):** the height is `locked`, citing p. 7 and p. 32. The record's example
  of "a crank that holds where it is left" is dropped.
- **The check file with the locks loosened** (`table_free`, decision 0018): following Daniel's
  direction, the height is free once its lock is loosened, so the table drops to the bottom of its
  travel. This is an assumption from a similar machine, not a fact about the T33901. It is logged
  as an inaccuracy until the test above, or a source, settles it.

## 2. Chains of mimic joints
**PhysX allows a joint in several mimic joints.** PhysX 5.6.1, "Mimic Joints":
- "Mimic joints attempt to enforce a linear relationship between the positions of two degrees of
  freedom (dofs) of the same articulation instance. Each dof may be in any sub-tree of the
  articulation and the dof pair may be any combination of linear and angular type."
- "An articulation may have multiple mimic joints applied and there is no restriction on the
  number of mimic joints referenced by any individual joint. The only restriction is that each dof
  of a mimic joint must be capable of motion".
- "PhysX mimic joints are implemented as two-way interactions". The constraint is "q_A + G*q_B +
  γ = 0" between two dofs. In PhysX, neither dof is the leader.
- "Combinations of mimic joints may be used to create more complex joint types such as
  differential joints."

A chain (C follows B, B follows A) is two mimic joints that share joint B. So PhysX allows it.

**How PhysX solves several of them.** The maths note: "a typical use case is multiple constraints
that compete with each other. The solution is to perform multiple passes over the list of all
constraints." The Articulations page warns that an articulation with a mimic joint "may require
many solver position iterations" [INFERENCE: a chain may need more of them].

**Nothing in Isaac Sim 6.2.0 refuses a chain:**
- `PhysxMimicJointAPI`'s schema text names only the joint types, "the same articulation", and "a
  two-way interaction". It says nothing about chains.
- SimReady's `MimicAPICheck` checks the reference joint ("expected: 1"), the gearing, the
  compliance values, the limits, and that neither joint is "excluded from articulation". It does
  not check whether the reference joint is itself a mimic.
- The URDF converter writes each URDF `<mimic>` against the joint it names, without resolving
  chains.
- Newton's `add_constraint_mimic` checks only that the joint indexes are valid and in the current
  world.

**Not tested:** no chain has been run in Isaac Sim, and no twin needs one yet [INFERENCE: Isaac
Sim's USD parser hands each `PhysxMimicJointAPI` to PhysX as one mimic joint].

**A loop is different.** If A follows B and B follows A, the two equations either say the same
thing twice or contradict each other [INFERENCE]. So decision 0020 refuses loops, not chains.

**For the contract:** links may chain, but they may not loop.

## A side finding: SimReady and mimic compliance
SimReady's `MimicAPICheck` fails a mimic joint with "has no natural frequency" or "natural
frequency == 0". PhysX's schema says "A mimic joint with naturalFrequency <= 0 will behave as a
hard constraint", and its default is 0.0. Our exporter writes neither value (`usd/physx_schemas.py`),
so the handles' mimic is a hard constraint. It worked in Isaac Sim (decision 0019), and NVIDIA's
`omni_asset_validate` found "No issues found." [INFERENCE] So under the SimReady profile our mimic
would fail that rule, although PhysX accepts it. Nothing is changed now. This matters only if the
project aims for SimReady.
