# The L20 hand: its two public models and LinkerBot's SDK commands

For the lab's machines plan, Phase 7 (the hand on `igus/rebel6dof02`). Accessed 2026-11-09
(the models) and 2026-11-17 (the SDK). Every file below is filed under
`data/machines/igus-rebel6dof02/inputs/documents/` with its SHA-256 in the twin's reference file
(`backend/src/moonwalkers/pipelines/b/igus_rebel6dof02.reference.json`) or the SDK folder's
`MANIFEST.sha256`. Earlier findings: `docs/research/2026-11-06-lab-machines.md`, sections on the
hand.

## 1. Which hand

- The lab's hand reads "LINKERBOT" on its back shell (photo `20261105_133438`). Dr. Li's website
  names it a "Realhand L20 Dexterous Robotic Hand" (Daniel, 2026-11-09).
- Whether Realhand and LinkerBot's Linker Hand are one product is **not confirmed**
  (2026-11-06 note). Left or right is **not confirmed** either: the visit list's item 14 (the
  hand's label or box) settles both.
- **Chosen: LinkerBot's right L20** [INFERENCE]. The shell's name, and the SDK's own angle table
  for a right L20 is this model's limits, slot by slot (section 3). Logged as an issue on the twin.

## 2. The two public models disagree

Both are Apache-2.0 and have 21 revolute joints, 5 of them mimic followers. Their names, limits
and joint order differ:

| | LinkerBot, `linkerbotai/linker_hand_sim@b21e9fa`, `l20/right/linkerhand_l20_right.urdf` | Realhand, `realhand-robotics/Realhand_description@7a64d07`, `l20/right/realhand_l20_right.urdf` |
|---|---|---|
| Fingers' spread | `index_joint0` ... -0.26 to 0.26 rad | `index_mcp_roll` ... -0.17 to 0.17 rad |
| Fingers' base | `index_joint1` ... 0 to 1.40 | `index_mcp_pitch` ... 0 to 1.40 |
| Fingers' middle | `index_joint2` ... 0 to 1.08 | `index_pip` ... 0 to 1.57 |
| Fingers' tip (follows) | `index_joint3` ... 0 to 1.15, mimic of joint2 | `index_dip` ... 0 to 1.40, mimic of pip |
| Thumb | `thumb_joint0` -0.297 to 0.683, `thumb_joint1` 0 to 1.78, `thumb_joint2` 0 to 0.87, `thumb_joint3` 0 to 1.29, `thumb_joint4` (follows joint3) 0 to 1.29 | `thumb_cmc_roll` 0 to 1.22, `thumb_cmc_yaw` 0 to 1.40, `thumb_cmc_pitch` 0 to 0.79, `thumb_mcp` 0 to 1.05, `thumb_dip` (follows mcp) 0 to 1.22 |
| Its joints' velocity | `velocity="1"` (rad/s) on every joint | (not used) |

Realhand's model is named here and not used: only its fingers' base joints (0 to 1.4) match
the SDK's slots for a right L20; its spread, middle and thumb joints match none (section 3). The twin (`igus/rebel6dof02@v5`) carries LinkerBot's names and limits.

**The meshes are not imported** (the plan's checklist; Daniel, 2026-11-09). They were read for
their sizes only: the hand's 22 parts are labelled boxes sized from each link mesh's bounds and
placed by the model's joint frames (decision 0037), because the generated hand contradicts the
photos (no shell, two thumbs, 155 mm long where the model is 260 mm; worklog 2026-11-17).

## 3. LinkerBot's SDK commands

**Which SDK:** LinkerBot's ROS 2 SDK, https://github.com/linker-bot/linkerhand-ros2-sdk at
commit `0035f236c98b644aba6d9e972359df3fa1af4342` (README "V3.0.1"), **Apache-2.0** (its
`LICENSE`). Six files are filed. The plan's note that "LinkerBot's Python SDK has no licence"
holds for `linkerbotai/linker_hand_python_sdk` (2026-11-06 note), which was not used; nothing
of either SDK is copied into this repository. Our code (`control/linkerhand.py`) is our own.

| What | Where | Quote or content |
|---|---|---|
| A position command | `linker_hand_api.py`, `LinkerHandApi.finger_move` | "@params: pose list L7 len(7) \| L10 len(10) \| L20 len(20) \| L25 len(25) 0~255"; values "less than 0 or greater than 255" are refused |
| The slots' names | `README.md`, the joint correspondence table | `L20: ["Thumb Base", "Index Base", "Middle Base", "Ring Base", "Little Base", "Thumb Abduction", ...` (slots 11 to 14 "Reserved") |
| The CAN frames | `linker_hand_l20_can.py`, `FrameProperty` and `pose_slice` | 0x01 "pitch angle - finger base flexion" (slots 0-4), 0x02 "yaw angle - finger abduction/adduction" (5-9), 0x03 "roll angle - only used for thumb" (10-14), 0x04 "fingertip angle control" (15-19), 0x05 "speed - motor running speed control" |
| Speed | `linker_hand_api.py`, `set_speed` | five values 0-255; with none given, `speed = [100] * 5` |
| Torque | `linker_hand_l20_can.py`, `set_torque` | "Set torque, not supported for L20" |
| Values to angles | `mapping.py`, `# L20 R OK` and `range_to_arc_right` | per slot a minimum, maximum and direction (`l20_r_min`, `l20_r_max`, `l20_r_derict`); direction -1 maps 0 to the maximum and 255 to the minimum, else 0 to the minimum; slots 11-14 skipped |
| Presets | `gui_control/.../constants.py`, `_HAND_CONFIGS["L20"]` | `init_pos` and `preset_actions`, among them "张开" (open) `[255, 255, 255, 255, 255, 255, 10, 100, 180, 240, 245, 255, ...]` and "握拳" (fist) `[40, 0, 0, 0, 0, 131, 10, 100, 180, 240, 19, 255, 255, 255, 255, 135, 0, 0, 0, 0]` |

**Each slot's joint.** Every one of the 16 driven slots' (minimum, maximum) is exactly one
LinkerBot joint's limits, and no two agree [INFERENCE: the match is the mapping, since no file
names the joints]:

| Slots | Range (rad) | Joints |
|---|---|---|
| 0 Thumb Base | 0 to 0.87 | `thumb_joint2` |
| 1-4 Index to Little Base | 0 to 1.4 | `index_joint1` ... `little_joint1` |
| 5 Thumb Abduction | -0.297 to 0.683 | `thumb_joint0` |
| 6-9 abductions | -0.26 to 0.26 (direction 0) | `index_joint0` ... `little_joint0` |
| 10 Thumb Roll | 0 to 1.78 | `thumb_joint1` |
| 15 Thumb Tip | 0 to 1.29 | `thumb_joint3` |
| 16-19 tips | 0 to 1.08 | `index_joint2` ... `little_joint2` |

The left L20's table differs (slot 10's minimum 0.122; directions -1 on 6-9), so the hand's side
matters to the mapping. Realhand's limits (±0.17, 0 to 1.57, 0 to 1.22 ...) match none of the
spread or middle slots.

**Not found** in the filed SDK files: what a speed value means in rad/s,
how the hand moves between commands (together or joint by joint), and its acceleration. The
plan's stand-ins are in decision 0038.

## 4. What the fist preset asks for

Posing LinkerBot's link meshes (read, not imported) at the fist preset, thumb_link3 and
thumb_link4 lie inside the ring and little fingers (up to 10.9 % of thumb_link3's surface inside
ring_link3; a winding-number test, scratch `fist_meshes.py`, 2026-11-17). At the open preset only
parts on their own joints touch. So the preset's targets pass contact; the real thumb would stop
against the fingers [INFERENCE]. The twin's hand parts pass through each other (decision 0037).

## Sources
- LinkerBot, linker_hand_sim, `linker_hand_isaac_gym_urdf/l20/right/linkerhand_l20_right.urdf`,
  https://github.com/linkerbotai/linker_hand_sim/blob/b21e9faa6078288a18311c351fc871371c784063/linker_hand_isaac_gym_urdf/l20/right/linkerhand_l20_right.urdf
  (Apache-2.0), accessed 2026-11-09.
- Realhand, Realhand_description, `l20/right/realhand_l20_right.urdf`,
  https://github.com/realhand-robotics/Realhand_description/blob/7a64d077ea8f1b81cd4df1f7b472ae3dece1b0ed/l20/right/realhand_l20_right.urdf
  (Apache-2.0), accessed 2026-11-09.
- LinkerBot, linkerhand-ros2-sdk at `0035f23` (Apache-2.0), accessed 2026-11-17:
  `README.md`, `linker_hand_ros2_sdk/linker_hand_ros2_sdk/LinkerHand/linker_hand_api.py`,
  `.../LinkerHand/utils/mapping.py`, `.../LinkerHand/core/can/linker_hand_l20_can.py`,
  `gui_control/gui_control/config/constants.py`, `LICENSE`; each at
  `https://github.com/linker-bot/linkerhand-ros2-sdk/blob/0035f236c98b644aba6d9e972359df3fa1af4342/<path>`.
- Photo `data/machines/igus-rebel6dof02/inputs/photos/20261105_133438.jpg` (Daniel Sweet,
  2026-11-05; shows serial numbers, kept out of commits).
