# How to write a simulatable twin as OpenUSD for Isaac Sim 6.2

**Question.** What must a `.usda` file contain so that Isaac Sim 6.2.0 opens it at the right size and
simulates a fixed machine base with one driven revolute joint? And how can we check a file before
opening Isaac Sim? (Phase 2 of `docs/poc-plan.md`.)

All sources were read on **2026-10-17**. Quotes are verbatim. Facts marked "observed" were checked
on Daniel's machine with usd-core 26.8 and omniverse-asset-validator 1.18.0; the commands are in
`docs/worklog/2026-10-17.md`.

## Sources and what they say

**OpenUSD, UsdPhysics overview** (https://openusd.org/release/api/usd_physics_page_front.html)
- Units: UsdPhysics "adopts degrees as the standard angular unit", "continues to respect arbitrary
  units for distance" (the stage's `metersPerUnit`), and adds a `kilogramsPerUnit`.
- Fixed-base articulations: the articulation root API "can be on a direct or indirect parent of the
  root joint which is connected to the world", "or on the joint itself".
- Joint frames: "The joint space relative to each body is a translation and orientation only,
  scaling is not supported."
- Mass: "Density is assumed to be 1000.0 kg/m3 (approximately the density of water)", and "Mass is
  assumed to be 1.0 in the mass units used when none is provided explicitly" "and there are no
  collision volumes to derive from."
- Gravity: a scene uses a "default direction (which is opposite the stage up axis)" and a "default
  magnitude (earth gravity)".

**OpenUSD, UsdPhysicsDriveAPI** (https://openusd.org/release/api/class_usd_physics_drive_a_p_i.html)
- "Each drive is an implicit force-limited damped spring".
- `physics:type` "acceleration": "Drive spring is for the acceleration at the joint (rather than the
  force)." The default is "force".
- Angular units: `targetPosition` in "degrees", `targetVelocity` in "degrees/second"; `maxForce`
  defaults to `inf` ("inf means not limited").

**NVIDIA Omni Physics, Articulations**
(https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/articulations.html)
- Fixed base: the root API goes on the fixed joint that connects the base to the world, or on an
  ancestor of that joint; the fixed joint's own frames are ignored. For connecting the root to the
  world, "it is recommended that you use a fixed joint, because it best expresses the intention."
- "The joint position of a revolute joint that does not have limits applied will wrap on a 360°
  boundary." Also: "Articulation joints without limits cannot be configured with limits after
  attaching the stage."
- Maximum joint velocity is `maxJointVelocity` on PhysxJointAxisAPI, in degrees per second for
  angular axes. (A PhysX schema attribute, not part of usd-core; see open questions.)

**NVIDIA Omni Physics, Rigid bodies**
(https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/rigid_bodies.html)
- "The default density used for automatically inferring mass properties is 1000 kg per cubic meter".

**NVIDIA Omni Physics, Colliders**
(https://docs.omniverse.nvidia.com/kit/docs/omni_physics/latest/dev_guide/rigid_bodies_articulations/collision.html)
- "Triangle meshes offer an efficient way to model large, complex objects that are either static or
  kinematic."
- SDF colliders "are a requirement for dynamic rigid bodies with non-convex colliders without
  resorting to convex decomposition."
- GPU convex meshes: "the largest dimension of a convex mesh should not exceed 100 times the radius
  of its insphere."

**Isaac Sim 6.2.0, Conventions**
(https://docs.isaacsim.omniverse.nvidia.com/6.2.0/reference_material/reference_conventions.html)
- Default units: metre, kilogram, second. World axes: +Z up, +X forward.
- Angles: degrees in USD, radians in Isaac Sim Core and PhysX. "UI elements that show attributes
  from USD should always display angles in Degrees, even if the value comes from Physics."
- Quaternion order in USD: (QW, QX, QY, QZ).

**Isaac Sim 6.2.0, GUI tutorial "simple robot"**
(https://docs.isaacsim.omniverse.nvidia.com/6.2.0/robot_setup_tutorials/tutorial_gui_simple_robot.html)
- The articulation root is added to the robot's top-level prim (Property > Add > Physics >
  Articulation Root).
- Drive tuning: position control uses "a high stiffness and relatively low or zero damping";
  velocity control uses "a high damping and zero stiffness". The articulation controllers use
  radians, while the Drive API properties in USD are degrees.

**Isaac Sim 6.2.0, Requirements and Download**
(https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/requirements.html,
https://docs.isaacsim.omniverse.nvidia.com/6.2.0/installation/download.html)
- Windows minimum: "Windows 11", "32GB" RAM, "50GB SSD", "GeForce RTX 4080" with "16GB" VRAM,
  driver "595.97".
- Windows package: `isaac-sim-standalone-6.2.0-windows-x86_64.zip`, MD5
  `86dabd127e9e8c225c239b41a8e3909b` (download page). Observed: the official link
  (https://downloads.isaacsim.nvidia.com/isaac-sim-standalone-6.2.0-windows-x86_64.zip) answers with
  `Content-Length: 10528731217` (10.53 GB) and `Last-Modified: Tue, 13 Oct 2026`.

**usd-core 26.8** (https://pypi.org/project/usd-core/; license text:
https://raw.githubusercontent.com/PixarAnimationStudios/OpenUSD/release/LICENSE.txt)
- License: Tomorrow Open Source Technology License 1.0, which "differs from the original Apache
  License 2.0" only in "Section 6 ("Trademarks")". Wheel for Python 3.12 on Windows: 13.89 MB, no
  dependencies, released 2026-07-20.
- Observed schema fallbacks: `PhysicsRevoluteJoint` `lowerLimit` = -inf and `upperLimit` = inf (not
  limited), `axis` = "X", `collisionEnabled` = false (jointed bodies do not collide); DriveAPI
  `type` = "force", `maxForce` = inf, other drive values 0; MeshCollisionAPI approximations: none,
  convexDecomposition, convexHull, boundingSphere, boundingCube, meshSimplification (default none).
- Observed API: `UsdPhysics.LoadUsdPhysicsFromRange` warns "is deprecated, use
  UsdPhysicsLoadStageFromPrimRange instead"; `UsdPhysics.UsdPhysicsLoadStageFromPrimRange(stage,
  [path])` returns the parsed scene, bodies, shapes, joints and articulations. `UsdUtils` does not
  expose `ComplianceChecker` in this wheel.
- Observed: on a stage where body0 is the world, the parser reports the fixed joint as the
  articulation root and gravity as (0, 0, -1) at 9.81 when the scene leaves gravity unauthored.

**omniverse-asset-validator 1.18.0** (https://pypi.org/project/omniverse-asset-validator/)
- Apache-2.0, pure Python, 0.26 MB. Its help text: validation "is based on the USD
  ComplianceChecker (i.e. the same backend as the usdchecker commandline tool)".
- Observed rules include `RigidBodyChecker`, `ColliderChecker`, `PhysicsJointChecker`,
  `ArticulationChecker` and `MassChecker` (category "Physics"), and `NormalsExistChecker`: "Either
  normals should be authored or subdivision should be set to Catmull-Clark or Loop".

## Experiment: what each validator catches (observed)
Copies of the test twin were broken one way at a time:

| Breakage | Our validator | omni_asset_validate (Physics) |
|---|---|---|
| Joint body1 points to a missing prim | error (after adding direct joint checks) | error ("points to a non existent prim, joint will not be parsed") |
| Moving body with a triangle-mesh collider | error | nothing reported |
| Joint body1 is not a rigid body | error (after adding direct joint checks) | nothing reported |
| No normals on non-subdivided meshes | (not checked) | error (NormalsExistChecker) |

The UsdPhysics parser alone hid the first and third problems, because it drops or re-points such
joints. So our validator now also reads the joint prims directly.

## Conclusions
- [INFERENCE] With metres, kilograms, +Z up, degrees, a fixed joint from the base to the world, the
  articulation root on the top prim and convex colliders on moving parts, the file follows every
  source above. Isaac Sim itself is the final check (Phase 2's manual step).
- [INFERENCE] An acceleration drive suits the PoC: its response does not depend on mass, and our
  masses are only the 1000 kg/m^3 default.
- [INFERENCE] Run both validators: each catches problems the other misses.

## Isaac Sim 6.2.0 check (2026-10-17, by Daniel)
Versions from the Kit log (`kit_20261017_111353.log`):
- `App Name: 'Isaac-Sim Full', App Version: '6.2.0', Kit Version: '110.4.0+feature.386251.187cf21b.gl'`
- omni.physx, omni.physics and omni.usdphysics 110.4.4; isaacsim.core.api 5.3.2
- NVIDIA driver 617.42; Windows 11 Pro build 26200

Seen:
- Both test files opened with nothing else needed and behaved as `docs/setup/isaac-sim-check.md`
  describes. `spin.usda` turned steadily; in `quarter_turn.usda` the spindle turned 90 deg and settled
  in about two seconds (Daniel's estimate).
- The viewport was lit by a directional light that is not in the file, so Isaac Sim lights a stage
  that has none.
- The log has 0 errors and 14 warnings. The one relevant to us comes from
  `isaacsim.core.throttling.extension`: "The current USD stage has no usable time-code range.
  Timeline playback will loop over a single frame, which prevents time-accumulating sensors and
  controllers from producing output. Author distinct startTimeCode and endTimeCode values in the
  root layer before playing."
- The other warnings are not about our files [INFERENCE: the "Unexpected reference count" warning
  also appears for Isaac Sim's own startup stage, and the rest come from Isaac Sim extensions]:
  skipping the non-NVIDIA Intel GPU, no material configuration file, `pxr.Semantics` deprecated, an
  `omni.anim.graph.core` node registration, an omniclient empty URL, and "Unexpected reference
  count" on stage close.

## Open questions (not confirmed)
- Whether Isaac Sim needs a PhysicsScene in the file. Our files include one and work; a file without
  one was not tried, which the PoC does not need.
- How PhysX scales stiffness and damping for an acceleration drive with degree-based USD values. The
  observed settle time (about 2 s, judged by eye) is slower than my estimate of under a second for
  w = 10 rad/s. The gap may come from how PhysX scales the values, or from where "settled" was judged
  by eye; not confirmed. Phase 6 should measure settle times in a scripted run before indexing speed
  matters.
- The exact attribute name and units for `maxJointVelocity` on PhysxJointAxisAPI, if we want to
  write the HA5C's cited 410 deg/s. Deferred to Phase 6.
- Which collider to use for the real HA5C meshes (convex decomposition or SDF). **Answered in
  Phase 3:** the convex hulls of decision 0010 were kept for both HA5C parts (a single-hull spindle
  nose and a single-hull body). The body's hull overlaps the back of the spindle; jointed bodies do not
  collide by default (decision 0010, Phase 3 update). The Isaac Sim check will show whether that is
  enough.
- Which start and end time codes to author (the warning above needs only distinct values).
  **Answered in Phase 3** (commit `a37f5e7`): 0 to 1,000,000 at 60 time codes per second, the values
  in NVIDIA's own example stage `isaacsim.examples.interactive/data/SurfaceGripper_gantry.usda`
  (Isaac Sim 6.2.0). The HA5C Isaac Sim check should confirm the warning is gone.
