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
  product, like the HA5C, it may reuse decision 0026's controller [INFERENCE].

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
