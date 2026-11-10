# The lab's machines: what public sources exist

**Question:** Daniel photographed three machines in Dr. Li's lab. What can be cited for each before
anything is built, and which should come first?

**Status:** first pass, from web sources only, accessed 2026-11-06. No lab photo has been opened
yet, so nothing here says what the lab's own units look like or carry. The machine names are as
Daniel reported them from the lab (worklog 2026-11-06).

## Update, 2026-11-09: what the lab's photos show
Daniel's 29 photos of 2026-11-05 (worklog 2026-11-09) settle some of what follows:
- **The arm is a REBEL-6DOF-02,** by the label on its base. The public ROS package has only
  versions `00`, `01` and `pre`, so its joint limits are **not confirmed** for this unit.
- **Its end effector is the Realhand L20 alone,** on the wrist flange. Neither the SCHUNK EGP
  gripper nor the CobotPump is on it. The full name comes from Dr. Li's website (Daniel).
- **The hand is part of the arm's twin,** and all three machines are to be built (Daniel,
  2026-11-09).
- **The TM-1 is open-framed,** with sheet-metal guards and an umbrella tool changer. It was made
  in 11/06.
- **The VF-3 is enclosed,** was made in 12/2014, and carries a Haas two-axis trunnion rotary table,
  photographed with the doors open. The trunnion's model is not read yet. Being a Haas rotary
  product, like the HA5C, it may reuse decision 0026's controller [INFERENCE]. The second update
  finds this unlikely: on a Haas mill, its axes are the mill's own.

## Second update, 2026-11-09: the plan chat
Read for [the lab's machines plan](../lab-machines-plan.md). All accessed 2026-11-09. Nothing was
filed in `data/` or installed; downloads went to the session's scratchpad.

### The arm
- **igus's technical documentation.** "Technical documentation ReBeL", igus GmbH, "MAT0075179.25
  Stand 08/2022", 8 pages, from
  https://uploads.unchainedrobotics.de/media/file_upload/Robolink%20ReBeL_DINA5_v11_a8b0f58f.pdf
  (linked from Unchained Robotics' 6DOF-01 page; SHA-256
  `735c2fbea8ab67d90090c3ae4659399c53e7e91af86d7dbf6b3ba9bb34b68fb3`). Text read with pypdf, page 6
  rendered with pypdfium2, both backend dev dependencies.
  - p. 2, 6 DOF: reach "664", payload "2" kg, mass "< 8" kg, "Max. speed 45 [°/s]", "Linear speed
    200 [mm/s]", "Footprint Ø 180 [mm]", accuracy "+-1 [mm]", "With and without integrated
    control".
  - p. 2: "J1: -179° bis to +179° J2: -80° bis to +140° J3: -80° bis to +140° J4: -179° bis to
    +179° J5: -95° bis to + 95° J6: -179° bis to +179°". These match Unchained Robotics' listing
    in the table above.
  - p. 6: a drawing of the arm in its "Nullstellung" (zero position), straight up, with the row
    "ReBeL-6DOF-00 660 252 237 297 126 180 160 6,5 43 M3 62 M4" for L1, X1-X4 and D1-D7. Read from
    the drawing: X1 runs from the foot to joint 2's axis, X2 to joint 3's, X3 to joint 5's, X4 to
    the flange; L1 from joint 2's axis to the flange; D1 is the foot's diameter.
- **The ROS model's versions.** `igus_rebel_6dof_01.description.xacro` includes
  `igus_rebel_6dof_00.description.xacro` and calls its macro, so 01 is 00 (read through the GitHub
  API, `CommonplaceRobotics/iRC_ROS`, default branch).
- **Why the limits seemed to disagree** [INFERENCE, by arithmetic from the 00 description]:
  - joints 2 and 3: `lower="${-pi*11/18}" upper="${pi*11/18}"` (±110°) about an origin of
    `rpy="0.0 ${pi/6} 0.0"` (+30°), so -80° to +140° from the straight-up zero: igus's range;
  - joint 5: `lower="${-pi*19/36 + pi/24}" upper="${pi*19/36 + pi/24}"` (-87.5° to +102.5°)
    about `rpy="0.0 ${-pi/24} 0.0"` (-7.5°), so ±95°: igus's range;
  - the file's own comment: "pi*2/3 are the physical limits, but to avoid any collisions we set
    the actual limits lower";
  - the sign convention is the URDF's (the joint's origin, then its rotation). That the offsets
    are measured from igus's zero is the inference.
- **Link lengths:** the URDF's offsets give 0.100 + 0.149 = 0.249 m to joint 2, 0.2384 m to joint
  3, 0.149 - 0.03 + 0.14 + 0.03 = 0.289 m to joint 5 and 0.1208 + 0.0012 = 0.122 m to the flange,
  against igus's 252, 237, 297 and 126 mm. Two of the URDF's offsets carry "TODO The 0.03m offset
  are most likely caused by the mesh file (Issue 15)".
- **Version 02.** DigiKey lists part "REBEL-6DOF-02" (search listing; its page answered 403), and
  Unchained Robotics' 6DOF-01 page captions its images "igus ReBeL-6DOF-02". No page describing
  what 02 changes was found. The lab's base has a connector panel and power button, on a base plate
  with its own label (photo `20261105_133326`), where igus's drawing shows a plain foot, so 02 may
  be the version with control in the base [INFERENCE].
- **The arm's photos:** the lab's arm is black and orange, as igus's standard colour ("Robot
  standard color black/orange", p. 2).

### The hand
- **The lab's hand reads "LINKERBOT"** on its back shell (photo `20261105_133438`, from above).
- **LinkerBot's models.** https://github.com/linkerbotai/linker_hand_sim (Apache-2.0, last pushed
  2025-08-29) holds `linker_hand_isaac_gym_urdf/l20/left/linkerhand_l20_left.urdf` and
  `.../right/linkerhand_l20_right.urdf`, and MuJoCo versions. The right URDF has 21 revolute
  joints, 5 with `<mimic>`. Its README: "This project has been moved to the new address, please
  visit https://github.com/linker-bot/linkerhand-sim", which the GitHub API answered 404.
- **Realhand's models** (`realhand-robotics/Realhand_description`, Apache-2.0, pushed 2026-10-05)
  hold left and right L20 URDFs in `l20/` and `L20v10/`, and Isaac Sim USD files in `l20/`. Its
  right URDF also has 21 revolute joints, 5 mimic.
- **The two models differ:** LinkerBot's joints are named `thumb_joint0`... with a first limit of
  -0.297 to 0.683 rad; Realhand's are named `pinky_mcp_roll`... with a first limit of ±0.17 rad.
  Which matches the lab's hand is not confirmed.
- **LinkerBot's other repositories** (`linkerbotai`): `linker_hand_python_sdk` and
  `linker_hand_cpp_sdk` have no licence on GitHub, so they can be read and cited, not reused;
  `linker_hand_ros2_sdk` is Apache-2.0.
- **Retailers** sell the "Linker Hand L20" by "Linkerbot" (for example
  https://rbtx.de/en-GB/components/end-effectors/linkerbot-dexterous-robotic-hand-linker-hand-l20,
  search listing) and an "L20 Lite". None found mentions Realhand.
- **Left or right** [INFERENCE]: a right hand, from `20261105_133438` (the back of the hand up,
  fingers away from the base, thumb on the image's left).

### The VF-3's trunnion
- In `20261105_133959` and `20261105_133938` a cradle carries a round platter between two end
  housings, with "5th AXIS" on the vise. A small plate on the cradle's base, lower left, is not
  readable at the photos' resolution.
- Dealers' listings (search results, second-hand) say Haas's TRT160 and TRT210 need "a Haas mill
  with 4th & 5th axis drives and software version 18.00 or later", for example
  https://ecomm.productivity.com/itemdetail/HAA1%20TRT160 and
  https://ecomm.productivity.com/itemdetail/HAA1%20TR210 (not opened). So a Haas trunnion on a Haas
  mill is driven as the mill's own axes [INFERENCE], and its model is not confirmed.

### The TM-1
Dealers' listings (search results, second-hand; for example
https://surplusrecord.com/listing/haas-tm-1-cnc-toolroom-mill-47-5-x-10-5-table-30-x-12-y-16-z-7-5-hp-4000-rpm-10-automatic-tool-changer-cat-40-4th-axis-enabled-rigid-tapping-2007-1141865/,
a 2007 unit): travels 30 x 12 x 16 in, a 47.5 x 10.5 in table (others 47.75), 7.5 HP, 4000 RPM,
CAT-40, a 10-pocket tool changer. A TM-1P is listed at 6000 RPM
(https://www.exapro.com/haas-tm-1p-p260304053/). Haas's own pages were not tried again: they
refused scripts on 2026-11-06.

## Summary
| Machine | Moving parts | Public model | Its control | Scripts can read its sources? |
|---|---|---|---|---|
| ReBeL 6-DoF cobot | 6 revolute joints in series | Yes: URDF and meshes, Apache-2.0 | Joint moves; CRI or CAN | Yes for GitHub; two PDFs refused |
| Realhand L20 hand | 16 active + 5 follower joints | Yes: URDF and meshes, Apache-2.0 | Python SDK over CAN | Yes for GitHub and the SDK pages |
| Haas TM-1 | 3 sliding axes and a spindle, perhaps a tool changer | None found | G-code | No: haascnc.com answers 403 |
| Haas VF-3 | The same, in an enclosure, with a tool changer | None found | G-code | No: haascnc.com answers 403 |

## ReBeL 6-DoF cobot (igus)
- **Maker.** "ReBeL" is an igus product line. igus sells the SCHUNK EGP gripper set and the
  CobotPump gripper set as accessories for it (https://igus.com/robolink/cobot-accessories, search
  listing, page not opened). One listing names the pump as the Schmalz CobotPump ECBPMi.
- **Public model.** [CommonplaceRobotics/iRC_ROS](https://github.com/CommonplaceRobotics/iRC_ROS),
  Apache-2.0, last pushed 2025-05-21. Its README calls itself "an early beta version".
  - `irc_ros_description/urdf/robots/` holds `igus_rebel_6dof_00`, `_01` and `_pre` descriptions.
  - `irc_ros_description/meshes/igus_rebel_6dof_00/` holds one mesh and one collision mesh per
    joint.
  - `irc_ros_description/meshes/gripper_schmalz_ecbpmi/` holds the pump's meshes.
  - No SCHUNK EGP model was seen there. Not searched further.
- **Joint limits disagree between sources**, so the lab unit's version matters:

  | Joint | `igus_rebel_6dof_00` URDF | Unchained Robotics (search listing) | ManualsLib's igus manual (search listing) |
  |---|---|---|---|
  | 1 | ±179° | ±179° | not read |
  | 2 | ±110° (`pi*11/18`) | -80° to 140° | ±140° |
  | 3 | ±110° | -80° to 140° | ±115° |
  | 4 | ±179° | ±179° | not read |
  | 5 | -87.5° to +102.5° (`pi*19/36` with a `pi/24` offset) | ±95° | ±90° |

  Which is right for the lab's unit is **not confirmed**. The URDF's joints 2, 3 and 5 also carry
  zero-pose offsets (`pi/6`, `pi/6`, `-pi/24`), which may explain part of it [INFERENCE].
- **Size.** Listed at 664 mm reach, 2 kg payload, 8 kg weight
  (https://unchainedrobotics.de/en/products/robot/cobot/igus-rebel-6dof-os, search listing).
- **Refused to scripts.** The igus factsheet on the RobotShop CDN answered WebFetch with 403. The
  igus page https://www.igus.com/robolink/cobots loads, but holds no specifications.

## Realhand L20 hand
- **Maker.** The [realhand-robotics](https://github.com/realhand-robotics) organisation calls itself
  "an open robotics initiative focused on dexterous robotic hands, manipulation, and embodied AI."
- **Joints.** Its SDK page says "L20 has 16 degrees of freedom distributed across 5 fingers", and
  lists 16 joints by name
  (https://realhand-robotics.github.io/realbot-python-sdk-document/reference/l20/index.html).
- **Public model.** [Realhand_description](https://github.com/realhand-robotics/Realhand_description),
  Apache-2.0, last pushed 2026-10-05. `L20v10/left/realhand_l20_left.urdf` has 21 revolute joints,
  5 of them mimic joints, with STL meshes per finger segment. A right hand's files were not
  checked.
- **The count fits.** 16 driven + 5 mimic = 21, as retailers' "16 active + 5 passive" says. Mimic
  joints are what the T33901's handles use (decision 0019) [INFERENCE].
- **Name not settled.** Retailers sell an "L20" under the name Linker Hand (LinkerBot), also
  described as 16 + 5. Whether Realhand and Linker Hand are the same product is **not confirmed**;
  the Realhand pages do not mention it. The lab's nameplate or box should say.
- **Control.** The SDK page documents a Python SDK over CAN.

## Haas TM-1 and VF-3
All of this is from dealers' listings, so it is second-hand, and it varies by model year. Haas's
own pages must be saved by a person in a browser (`docs/agent-procedure.md`, step 2):
https://www.haascnc.com/service/online-operator-s-manuals/mill-operator-s-manual.html answered 403
on 2026-11-06.
- **TM-1 travels:** X 30 in, Y 12 in, Z 16 in, on many listings
  (for example https://www.machinio.com/models/haas/tm-1).
- **TM-1 enclosure:** a TM-1P is listed with a full enclosure. Whether the TM-1 has one is **not
  confirmed**; the lab's photos will show this unit.
- **TM-1 tool changer:** many listings show 10 stations, one says none. The photos will show.
- **VF-3 travels:** X 40 in, Y 20 in, Z 25 in, on many listings (for example
  https://www.equipt.com/listings/927541-used-2013-haas-vf-3-vertical-machining-centers-in-ohio).
- **VF-3 spindle and tool changer** differ by year and option. The lab's nameplate gives the unit's
  date of manufacture, which narrows this.
- **No public CAD or URDF** turned up for either. Searches were short, so this is not proof that
  none exists.
- **Control:** both are CNC mills, so their programs are G-code [INFERENCE]. `moonwalkers.control`
  has indexing programs for the HA5C and manual controls, and a search of it for "G-code" finds
  nothing, so a reader for mill programs would be new work.

## Which comes first [INFERENCE]
Provisional, until the photos are looked at and each machine's mesh has been generated.

**Recommended order: the ReBeL arm, then the TM-1, then the VF-3, then the L20 hand.**
1. **The arm first.** It is the one machine with an independent answer key. Its joints can be
   cited, and its published meshes can score the generated mesh in numbers, which is what a
   "real-world comparison" needs. It needs no new joint type or program reader.
2. **The TM-1 next.** Its sliding axes are what the drill press proved. Its open frame, if the
   photos confirm one, shows the moving parts. It starts the G-code work, the largest new piece.
3. **The VF-3 after it.** It should reuse the TM-1's axes and control. Its enclosure will hide the
   moving parts, so it will need interior photos or stand-ins.
4. **The hand last, or as its own step.** Twenty-one joints in small fingers are unlikely to come
   out of the generator as separate parts, so it may be mostly stand-ins, or its public model.

**A question for the plan.** The public models can play two roles. As cited sources of joint facts
they fit our rules. As the geometry of the twin they would skip the photo-to-mesh step that the
platform exists to prove. Using a file both as a source and as the score would also not be an
independent check.

## Sources
All accessed 2026-11-06.
- https://github.com/CommonplaceRobotics/iRC_ROS (README and `irc_ros_description`, read through
  the GitHub API)
- https://github.com/realhand-robotics and
  https://github.com/realhand-robotics/Realhand_description (read through the GitHub API)
- https://realhand-robotics.github.io/realbot-python-sdk-document/reference/l20/index.html
- https://www.igus.com/robolink/cobots
- Search listings not opened: https://igus.com/robolink/cobot-accessories,
  https://unchainedrobotics.de/en/products/robot/cobot/igus-rebel-6dof-os,
  https://www.manualslib.de/manual/949812/Igus-Rebel.html?page=9,
  https://www.machinio.com/models/haas/tm-1,
  https://www.equipt.com/listings/927541-used-2013-haas-vf-3-vertical-machining-centers-in-ohio
