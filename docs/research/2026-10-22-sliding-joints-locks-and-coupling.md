# Sliding joints, limits, locks, springs and coupled joints for Isaac Sim 6.2 (2026-10-22)

**Question.** Phase 1 of `docs/drill-press-plan.md` proves the exporter on a box-and-cylinder
drill press. What must the exporter write so that Isaac Sim 6.2.0 simulates:
- the quill sliding 3-1/4 in, returned by a spring, and stopped at an adjustable depth;
- the table's chain of four motions, each of which can be locked;
- the downfeed handles turning as the quill slides?

And how does a person push a part during the check?

**Sources.** All read on 2026-10-22.
- **usd-core 26.8,** the backend's OpenUSD, inspected with pxr: which schemas it defines.
- **OpenUSD's API pages:**
  - https://openusd.org/release/api/class_usd_physics_prismatic_joint.html
  - https://openusd.org/release/api/class_usd_physics_drive_a_p_i.html
- **Isaac Sim 6.2.0's own files, on Daniel's machine** (`C:\isaacsim`, the build of the PoC's
  checks: Kit 110.4.0, omni.physx 110.4.4, decision 0010). These are the definitions that build
  reads, so they are the primary source for it:
  - the PhysX schema, `extscache/omni.usd.schema.physx-110.4.4+.../plugins/PhysxSchema/resources/schema.usda`
    and its `generatedSchema.usda`;
  - the Newton schema, `exts/omni.usd.schema.newton` (version 1.5.0),
    `usd/schema/newton/newton_usd_schemas/generatedSchema.usda`;
  - NVIDIA's demos, `extscache/omni.physx.demos-110.4.4+.../omni/physxdemos/scenes/MimicJointDemo.py`
    and `RackAndPinionJointDemo.py`;
  - the asset validator's `extscache/omni.physx.asset_validator-110.4.4+.../omni/physxassetvalidator/scripts/newtonMigrationChecker.py`;
  - the PhysX UI's `extscache/omni.physx.ui-110.4.4+.../omni/physxui/scripts/settings.py` and
    `physxViewportOverlays.py`.
- NVIDIA's physics settings page,
  https://docs.omniverse.nvidia.com/extensions/latest/ext_physics/simulation-control/physics-settings.html,
  answered HTTP 403, so the installed source code above was read instead.

## 1. What usd-core 26.8 can write
- **Defined:**
  - `UsdPhysics.PrismaticJoint`, with `physics:axis`, `physics:lowerLimit` and
    `physics:upperLimit`;
  - `DriveAPI` with a `linear` instance: `drive:linear:physics:type`, `maxForce`,
    `targetPosition`, `targetVelocity`, `damping` and `stiffness`;
  - `LimitAPI`;
  - on every joint: `physics:jointEnabled`, `physics:collisionEnabled` and
    `physics:excludeFromArticulation`.
- **Not defined:** none of the PhysX schemas. `import pxr.PhysxSchema` fails, and the schema
  registry does not know `PhysxMimicJointAPI`, `NewtonMimicAPI`, `PhysxPhysicsRackAndPinionJoint`
  or `PhysicsJointStateAPI`.
  - [INFERENCE] They can still be written by name: an applied-schema token such as
    `PhysxMimicJointAPI:rotX` in the prim's `apiSchemas`, plus attributes with the names and types
    in Isaac Sim's `generatedSchema.usda`. Whether our validators accept such a file is to be tested.

## 2. Prismatic joints, linear drives and limits
OpenUSD's pages:
- **The joint:** "Predefined prismatic joint type (translation along prismatic joint axis is
  permitted.)". Limits are "Units: distance. -inf means not limited in negative direction" and
  "... inf means not limited in positive direction". Our stages are in metres (decision 0010), so
  the contract's metres are written as they are.
- **The drive:** "Each drive is an implicit force-limited damped spring". For a linear drive:
  - `targetPosition` is in "distance", and `targetVelocity` in "distance/second";
  - `stiffness` is in "mass/second/second", and `damping` in "mass/second";
  - `maxForce` is in "mass*DIST_UNITS/second/second" ("inf means not limited").

  The type "acceleration" means the "Drive spring is for the acceleration at the joint (rather than
  the force)" (decision 0010 uses it).
- **[INFERENCE] The angular drive's tuning would let the quill sag.** With an "acceleration" drive,
  a stiffness of 100 balances gravity at 9.81 / 100 = 0.098 m from the target, more than the whole
  3-1/4 in (0.08255 m) stroke. So the quill's spring needs its own, stiffer values.

## 3. A chain of joints
Nothing new is needed in the schema: each joint joins two bodies, and the exporter already walks a
tree to one root (`_root_part`). The manual's photos and exploded view put a real part between
every two motions: the rack between the column and the bracket, and the mounting arm between the
bracket and the table (`docs/research/2026-10-22-t33901-handle-ratio-and-figures.md`). So no
invisible link is needed.

## 4. Coupled motion: the handles follow the quill
Three schema options exist in Isaac Sim 6.2, plus a fallback.

**(a) `PhysxMimicJointAPI`: works across joint types, but deprecated.**
- Its doc opens: "DEPRECATED: use NewtonMimicAPI (single-apply) from the Newton schema instead.
  PhysxMimicJointAPI is kept for backward compatibility with existing assets".
- "Applied to a Physics Joint that must be part of an articulation. Supported joint types are:
  PhysicsRevoluteJoint (with a limit set), PhysicsPrismaticJoint as well as the more generic
  PhysicsJoint if all linear degrees of freedom are locked."
- **The relationship:** "jointPosition + (gearing * referenceJointPosition) + offset = 0".
  - The instance name picks the follower's degree of freedom: "The allowed instance name tokens
    are "rotX", "rotY" and "rotZ"".
  - The gearing's units are "if linear to angular: degrees / distance".
  - "the two joints have to be part of the same articulation".
  - "the mimic joint relationship is interpreted as a two-way interaction and an impulse will get
    applied to the reference joint as well".
  - `naturalFrequency` and `dampingRatio` "<= 0 will behave as a hard constraint".
- **The attribute names** (generated schema): `physxMimicJoint:<instance>:referenceJoint` (a
  relationship), and `...:referenceJointAxis`, `...:gearing`, `...:offset`,
  `...:naturalFrequency` and `...:dampingRatio`.
- **NVIDIA's own demo does our case.** `MimicJointDemo.py` drives a revolute joint from a
  prismatic one: "mimic joint that should transfer the linear movement of joint1 to angular
  movement".
  - It applies `PhysxMimicJointAPI` with `rotZ` to the revolute joint, with `gearing =
    (180/pi) / gearRadius`.
  - It gives the revolute joint limits of ±1e10.
  - It sets a starting angle with `PhysicsJointStateAPI`.

**(b) `NewtonMimicAPI`: the replacement, but not for our case.**
- "A mimic constraint enforces that `joint0 = coef0 + coef1 * joint1`".
- "The leader and follower must be the same joint type. The coefficients are expressed in the
  follower's position units, so mimicking across types -- an angular follower tracking a linear
  leader, or the reverse -- has no well defined units and is not supported."
- The handles (turning) follow the quill (sliding), which is across types. So it cannot couple them.
- **A trap to note:** Isaac Sim's `NewtonMimicMigrationChecker` would still offer to migrate our
  mimic. It only checks that both joints are single revolute or prismatic joints. Type rules "are
  enforced by the NewtonMimicAPI runtime and are not specific to this" checker. A person accepting
  that migration would break the coupling [INFERENCE].

**(c) `PhysxPhysicsRackAndPinionJoint`: works across types, but outside the articulation.**
- It "connects an existing revolute/hinge joint to an existing prismatic joint, and constrains
  the angular and linear velocities of involved rigid bodies". The constraint is "abs(omega) =
  abs(V) * R": on the sizes of the speeds, not on positions.
- "If a rack-and-pinion joint is created between articulation joints, excludeFromArticulation must
  be set to true for the rack-and-pinion joint itself, otherwise an error occurs. To include the
  rack-and-pinion joint in the articulation itself, please use PhysxMimicJointAPI instead".
- `physics:ratio` is in "degrees / distance". The demo sets `body0` to the pinion's body, `body1`
  to the rack's, `physics:hinge` to the revolute joint and `physics:prismatic` to the prismatic
  joint.

**(d) Fallback: no coupling in the physics.** A runner script sets the handles' target from the
quill's position every step. Or both joints get time-sampled targets, as the HA5C's native program
file does (decision 0016). [INFERENCE] Neither makes a push on the quill turn the handles.

**For the box test:** (a) and (c) each get a check file, so Daniel can compare them in Isaac Sim.
(b) is ruled out by its own documentation.

## 5. Locks, springs and the depth stop
- **Locks: candidates to compare in Isaac Sim** [INFERENCE: no source names a "lock"]:
  - a stiff position drive at the setting. It holds until something pushes harder than the drive;
  - equal limits (lower = upper = the setting). This is a hard stop, and the limits are written
    from the start anyway;
  - `physxJoint:jointFriction` (`PhysxJointAPI`: "Only applies to joints that are part of an
    articulation"). Its units are not stated where it was read;
  - a fixed joint beside the moving one, switched by `physics:jointEnabled`. It closes a loop, so
    [INFERENCE] it would need `physics:excludeFromArticulation`, as the rack-and-pinion joint does.
- **Spring return** [INFERENCE: the spring's force is not in the manual]:
  - The manual's spring is a wound "FLAT COIL SPRING" whose tension is adjusted by notches (pp. 40,
    49), so it is preloaded.
  - One way to model that: a linear drive whose target lies above the top of the travel, with the
    top limit holding the quill there. Pulling the quill down works against the spring's force, and
    letting go returns it to the top.
  - The stiffness is a stand-in, chosen so the quill does not sag under gravity (section 2).
- **The depth stop.** NVIDIA: "Articulation joints without limits cannot be configured with limits
  after attaching the stage" (`docs/research/2026-10-17-usd-physics-for-isaac-sim.md`). So the
  quill always has limits, and the depth stop is the limit at the bottom of its travel, set to a
  depth within 3-1/4 in.
- **Starting positions.** `PhysicsJointStateAPI` (in the PhysX schema plugin) sets an articulation
  joint's position.
  - "When writing to the position attribute, the changes are immediately reflected on the next
    simulation step, instantaneously teleporting articulation links to the wanted position."
  - The instance names are "linear" for prismatic joints and "angular" for revolute joints, with
    units "if linear: distance" and "if angular: degrees".
  - "After a simulation step, the position value will reflect the actual last position of the
    joint". [INFERENCE] So it could also feed the joint recorder, if Isaac Sim writes the value back
    to USD. To check.

## 6. Pushing a part during a check
From the installed PhysX UI's source:
- a drag with Shift held, while the simulation runs, starts a physics interaction
  (`on_mouse_shift_dragged`, `physxViewportOverlays.py`);
- the Physics settings have a "Mouse Interaction" section (`settings.py`) with "Mouse Interaction
  Enabled", "Mouse Grab", "Mouse Grab With Force", "Mouse Grab Force Coeff" and "Mouse Push
  Acceleration".

[INFERENCE] With masses at the placeholder density, how hard a push feels says nothing about the
real machine.

## What this means for the exporter (decisions 0017-0019)
- Prismatic joints and linear drives come straight from usd-core, with limits in metres.
- Each joint gets its own drive: spin, hold, spring return, locked or free.
- The handles' coupling is written two ways for the check: `PhysxMimicJointAPI` with `rotX` on the
  handles' revolute joint (it needs limits), and a rack-and-pinion joint excluded from the
  articulation. Both are written by name, because usd-core does not know them.
- `PhysicsJointStateAPI` sets starting positions in the check files.
- Still to find out in Isaac Sim: which lock holds best, and whether either coupling works on our
  stage.

## Checked on the exported files (later on 2026-10-22)
The box-and-cylinder drill press's ten check files
(`data/machines/moonwalkers-testdrillpress/runs/2026-10-22_run-001/`) were run through both
validators:
- **Ours** (`moonwalkers.usd.validate`): 0 errors in every file.
  - The files with the mimic report one info line each: do not accept the Newton migration.
  - The locked table reports "joint is locked by equal limits".
- **NVIDIA's `omni_asset_validate`** (omniverse-asset-validator 1.18.0): "No issues found." in all
  ten. So it accepts the PhysX schemas written by name: `PhysxMimicJointAPI`, the rack-and-pinion
  joint, and `PhysicsJointStateAPI`.
- **One finding, fixed.** The first export drew all three handle bars from the hub's centre.
  NVIDIA's `WeldChecker` warned "Some points are co-located and may be able to be merged" on the
  hub's mesh, because the bars' end caps shared points. The bars now start 0.02 m out from the
  centre (a made-up thread depth), and the warning is gone.
- **usd-core detail:** `Usd.Prim.GetAppliedSchemas()` leaves out schemas it does not define. The
  prim type info's `GetAppliedAPISchemas()` keeps them, so `physx_schemas.applied_schemas` uses
  that.
