# The ReBeL's control: what an iRC program holds, and CRI (2026-11-10)

**Question.** Phase 3 of `docs/lab-machines-plan.md` (the arm's level 3) needs, before any code:
- what a program for igus Robot Control (iRC), the ReBeL's control software, holds: its file,
  its joint and linear moves, and how their speeds and accelerations are given;
- how a joint move of several joints is timed, and what "100 %" is on the ReBeL;
- CRI, the Ethernet interface through which other programs drive the arm;
- how iRC's joint angles relate to the URDF's and to the twin's (decision 0031).

**Dates.** Read on 2026-11-10. Files fetched are in
`data/machines/igus-rebel6dof02/inputs/documents/irc/`, logged with SHA-256 in that machine's
`inputs/SOURCES.md`. PDF text was read with pypdfium2. Page numbers are the PDF's, with the
printed page where it differs.

## Sources
- **igus, "Robot Control Command reference"**, "igus® Robot Control – V902-11-005",
  "MAT0074869.20 Issue 06/2020", 9 pages (two printed pages per PDF page):
  https://www.igus.com.br/contentData/wpck/pdf/global/igus_Robot_Control_iRC_RZ_screen.pdf.
  File `igus-irc-command-reference-2020-06.pdf`.
- **Commonplace Robotics, the iRC user guide**, "Version 14.5 January 15, 2025", "©2025 igus®
  GmbH", 99 pages: https://a.storyblok.com/f/298593/x/c429ad6e9d/userguide_irc_v14.pdf (found by a
  search). File `commonplace-irc-user-guide-v14.5-2025-01.pdf`. The printed page is the PDF's
  minus 2.
- **The CPR wiki** (Commonplace Robotics, who write iRC):
  - "Transferring Robot Programs via CRI",
    https://wiki.cpr-robots.com/index.php/Transferring_Robot_Programs_via_CRI ("last edited on 11
    August 2025"), saved as `cpr-wiki-transferring-robot-programs-via-cri.html`;
  - "CRI Ethernet Interface", https://wiki.cpr-robots.com/index.php/CRI_Ethernet_Interface ("last
    edited on 13 April 2026"), read with WebFetch, not saved. It links the CRI documents as PDFs;
    they were not opened.
- **Commonplace Robotics' CRI Python library**, https://github.com/CommonplaceRobotics/CRI-Python-Lib
  at commit `eae13201bbd97ef3aef2eb26833554c805f0135d` (2026-11-10), MIT licence ("Copyright (c)
  2024 Commonplace Robotics GmbH"): `cri_lib/cri_controller.py` and `LICENSE`, saved as `.txt`.
  Read, not run or installed.
- **iRC_ROS** (Commonplace Robotics, Apache-2.0) at commit `41701e6`, the commit the arm's URDF was
  filed from in Phase 1: `irc_ros_description/urdf/robots/igus_rebel_6dof_00.ros2_control.xacro`,
  `irc_ros_moveit_config/config/joint_limits.yaml` and `irc_ros_hardware/src/irc_ros_cri.cpp`.
- **RoboDK's post-processor for CPR robots**, `CPR.py` in
  https://github.com/ros-industrial-attic/robodk_postprocessors at commit `d7e6c1c`
  ("Copyright 2017 - RoboDK Software S.L.", Apache-2.0). It writes CPRog programs, iRC's
  predecessor, so it is a second-hand source of the XML's tags.
- **Searches** (WebSearch, standard) for iRC's program format and for CRI. Two more user guides
  the search listed answered with HTML instead of a PDF (RobotShop's "userguide rebel irc-eng"
  and Mouser's "iRC R13 UserGuide"); ManualsLib's ReBeL manual was not opened.

## What an iRC program is
- **A file of XML:** "Robot programs are .xml files in the /Data/Programs/ folder" (command
  reference, p. 2, section 2.2).
- **Its form,** from the wiki's example of a program sent to a gantry (quoted as printed, one
  line each):

  ```xml
  <?xml version="1.0" encoding="utf-8"?>
  <Program>
  <Header RobotName="igus Gantry" RobotType="DLE-RG-0001" GripperType="" Software="iRC V902-13-022-DEV" VelocitySetting="0" />
  <Loop Nr="1" Mode="DIn" Condition="False" Descr="" />
  <Joint AbortCondition="False" Nr="2" Source="Numerical" velPercent="100" acc="40" smooth="0" a1="10" a2="0" a3="0" a4="0" a5="0" a6="0" e1="0" e2="0" e3="0" Descr="" />
  <Joint AbortCondition="False" Nr="3" Source="Numerical" velPercent="100" acc="40" smooth="0" a1="210" a2="0" a3="0" a4="0" a5="0" a6="0" e1="0" e2="0" e3="0" Descr="" />
  <EndLoop Nr="4" Descr="" />
  </Program>
  ```

  RoboDK's post-processor writes the same `Joint` element (`velPercent`, `acc`, `smooth`,
  `a1`... `a8`), and a wait as `<Wait Nr="%i" Seconds="%.3f" Descr="" />` (`CPR.py`, lines 209
  and 241), and outputs as `<Output Nr="%i" Local="True" DIO="%s" State="%s" Descr="" />` (line
  279). Those are CPRog's tags; that iRC reads them the same is **not confirmed**.
- **The Header** is not a command: "The program editor inserts the pseudo command Start at the
  beginning of each program. It does not represent a real command, but displays information about
  the current hardware, software and kinematics ... When loading a program, this information is
  compared to avoid executing an incompatible program" (user guide, PDF p. 44, printed p. 42).
- **The commands** (command reference, p. 2): Joint, JointByVariable, Linear, LinearByVariable,
  RelativeBase, RelativeTool, RelativeJoint; DigitalOut and the gripper; LoopCounting,
  LoopConditional, If-Then-Else, Wait, WaitConditional, Sub; variables and a plugin target. The
  user guide adds circular motion, a joint move to a Cartesian position, "Set Velocity" for an
  external axis, and Path, from a `.csv` or `.dxf` file (PDF pp. 45-50).

## Joint moves
- **Joint** (command reference, PDF p. 4, printed p. 7, section 6.1): "Moves to a target position in
  joint coordinates. The joint velocities during the motion are constant. The resulting motion of
  the TCP is normally not a straight line, but curved." Its fields:
  - "A1 to A6: Joint values of the target position in degree";
  - "Vel: Velocity in percent of the max joint velocities";
  - "Acc: Acceleration in % of the max joint acceleration";
  - "Smooth: Interpolation at the edge points";
  - "Condition: Abort condition, if this is true the motion will be aborted".
- **The user guide** (PDF p. 46, printed p. 44): "The movement speed is indicated by "speed". It is
  measured in percent of the maximum allowed motion speed for the respective robot axes."
- **RelativeJoint** (command reference, PDF p. 5, section 6.7): "A1 to A6: relative joint
  motions in degrees", "Vel: Velocity in %". Its XML element is **not confirmed**: neither the
  wiki nor RoboDK writes one.
- **How several joints share one move.** No source says outright. Two passages point one way:
  "The joint velocities during the motion are constant" (above), and, for a joint move to a
  Cartesian position, "The robot moves as fast as the slowest joint allows" (user guide, PDF p. 47,
  printed p. 45). **[INFERENCE]** iRC times a joint move by the joint with the farthest to go,
  which runs at Vel % of its top speed, and slows the others so that all start and stop together
  (a synchronised point-to-point move).
- **Acceleration and smoothing** (command reference, PDF p. 4, section 5): "Acc: Percentage of the
  possible acceleration, 0..100", "Smooth: Scope of smoothing in percent, 0..100"; "If corner
  smoothing is not active the robot stops at every corner for a short moment". The user guide
  (PDF p. 45, printed p. 43): smoothing joins only "immediately following motion commands of the
  same type", and "If a motion sequence is interrupted by a motion of a different type or by a
  logic instruction, the smoothing is also interrupted and the robot stops briefly". How long
  that stop is, and the shape of the speed (trapezoid or smoother), are **not given**.
- **The override** (user guide, PDF p. 37, printed p. 35): "In this tab you can also set the
  override for the robot velocity. The robot velocity changes for jog and programm execution."

## The ReBeL's "100 %"
- **Speed:** igus's technical documentation gives "Max. speed 45 [°/s]" (08/2022, p. 2, the
  reference file's `max_joint_speed`), and iRC_ROS's URDF gives every ReBeL joint
  `velocity="${pi*45/180}"`. **[INFERENCE]** iRC's "max joint velocities" for the ReBeL are
  45°/s each, so Vel 100 % is 45°/s. Not confirmed: iRC's own robot file
  (`~/RobotControl/Data/Robots/<category>/<robot type>/<robot type>.xml`, user guide PDF p. 85)
  would say, and it
  is on the arm, not public.
- **Acceleration:** no igus document found gives one. iRC_ROS's MoveIt settings give each ReBeL
  joint `max_acceleration: 5.240` (rad/s², 300.2°/s²), beside `default_acceleration_scaling_factor:
  0.1` "For beginners" (`joint_limits.yaml`). That is the ROS package's limit for its planner, not
  iRC's. **A stand-in** for iRC's "max joint acceleration", to be labelled as one.
- **Linear speed:** igus gives "Linear speed 200 [mm/s]" (p. 2). The user guide: a linear move's
  speed "in mm/s. If it exceeds the maximum allowed movement speed of the robot, it will cause a
  kinematic error during execution" (PDF p. 47, printed p. 45).

## Linear moves
Linear (command reference, section 6.2): "X, Y, Z: Cartesian position of the target position in
mm", "A, B, C: Orientation of the target position in degree, encoding in Euler angles", "Vel:
Velocity in mm/s". The TCP "follows a straight line" (user guide, PDF p. 46). Running one on the
twin needs the arm's inverse kinematics: the joint angles for each point of the line, in a
convention (Euler order, the tool frame, user frames) these sources do not give. **Left out, as
the plan allows** ("Linear moves need inverse kinematics: left out unless a source makes them
simple"). Neither source makes them simple.

## CRI
- **What it is** (user guide, PDF p. 76, printed p. 74): "The CRI interface allows you to send
  complex instructions and retrieve information and settings via the Ethernet interface using
  TCP/IP. iRC uses this interface to connect to robots with integrated control. From version 14
  this interface is alway active at the robot and in simulation". And (PDF p. 77): "At any time
  only one CRI client is able to control the robot (active), all further clients can only observe
  its state (passive)."
- **Its messages,** from Commonplace's library (`cri_controller.py`): each is framed
  `f"CRISTART {command_counter} {command} CRIEND"` (line 266), sent to port `3920` by default
  (line 130). A joint move is `f"CMD Move Joint {A1} {A2} {A3} {A4} {A5} {A6} {E1} {E2} {E3}
  {velocity}"` (line 859), with "velocity : float Velocity in percent of maximum velocity, range
  1.0-100.0" (lines 844-845); a relative one is `CMD Move RelativeJoint` with the same fields
  (line 927). Programs are uploaded and started through it: `CMD LoadProgram {program_name}`
  (line 1405), and the wiki's `CMD UploadFileInit`, `CMD UploadFileLine` and `CMD
  UploadFileFinish` send a program's XML line by line.
- **iRC_ROS drives the ReBeL through CRI** (`IrcRosCri::CmdMove`, `irc_ros_cri.cpp`), sending
  `Move Joint` with the joints in degrees and one velocity.
- **For the twin:** CRI is how a program reaches the real arm, not something the twin runs. A
  twin that received CRI commands from the lab's software would need a CRI server in front of
  Isaac Sim, which is outside this phase [INFERENCE]. The joint move CRI sends is the same as a
  program's Joint command (degrees, a percent of the top speed), so one interpreter serves both.

## iRC's angles, the URDF's and the twin's
- **iRC_ROS says iRC's angles differ from the URDF's:** its ReBeL control file, above joints 2
  and 3, reads "Position limit difference with iRC files due to 30 degree offset in joint 2 and 3",
  and gives `cri_joint_offset="-30"` for joints 2 and 3 and `cri_joint_offset="7.5"` for joint 5
  (`igus_rebel_6dof_00.ros2_control.xacro`).
- **Its sign cannot be read off the driver:** `irc_ros_cri.cpp` adds the offset both when it sends
  a target (`(set_pos_[i] * 180 / M_PI) + pos_offset_[i]`, line 286) and when it reads a position
  (`temp_pos[i] = temp_pos[i] + pos_offset_[i]`, line 469), so one of the two directions is
  inconsistent with the other.
- **The limits settle it** [INFERENCE, by arithmetic, decision 0031]: igus's documented ranges
  (joints 2 and 3: -80° to +140°; joint 5: ±95°) are the URDF's (±110° about +30°; -87.5° to
  +102.5°) with those offsets added, and "iRC files" carry igus's. So **an iRC angle is igus's
  documented angle,** measured from the arm straight up. The twin's position is then that angle
  minus the joint's angle in the photographed pose (decision 0031): joint 2 -21.81°, joint 3
  +118.82°, joint 5 +10.46°, and 0 for joints 1, 4 and 6 (assumed, not measured).

## What this answers for Phase 3
| Question | Answer |
|---|---|
| The program format | iRC's own XML: `<Program>`, an optional `<Header>`, then commands with `Nr` and `Descr`. A Joint gives `a1`... `a6` in degrees, `velPercent` and `acc` in percent, `smooth` |
| Joint move speed | Vel % of each joint's top speed, 45°/s on the ReBeL [INFERENCE from igus and the URDF]; all joints start and stop together [INFERENCE] |
| Acceleration | Acc % of a maximum igus does not publish; iRC_ROS's 300.2°/s² as a labelled stand-in |
| Linear moves | Need inverse kinematics in a convention not given: left out |
| CRI | TCP port 3920, `CRISTART n CMD Move Joint A1..A6 E1..E3 vel CRIEND`; how programs reach the arm; not simulated |
| Angles | iRC's are igus's documented ones; the twin's = iRC's minus the photographed pose's (decision 0031) |
| Not confirmed | iRC's own ReBeL robot file (top speeds and accelerations); the speed profile's shape; the stop between unsmoothed moves; the XML of RelativeJoint, counting loops and Comment |
| The lab's program | None shared. To ask the lab (visit list, item 7) |
