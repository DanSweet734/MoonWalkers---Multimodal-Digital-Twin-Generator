"""PhysX schemas written by name: the tokens and attribute names Isaac Sim 6.2 reads."""

import pytest
from pxr import Sdf, Usd

from moonwalkers.usd.physx_schemas import (
    applied_schemas,
    apply_mimic,
    define_rack_and_pinion,
    mimic_axes,
    set_joint_state,
)


@pytest.fixture
def stage() -> Usd.Stage:
    return Usd.Stage.CreateInMemory()


def test_mimic_names_follow_the_multiple_apply_schema(stage) -> None:
    prim = stage.DefinePrim("/follower")
    apply_mimic(prim, "rotZ", Sdf.Path("/leader"), gearing=-2.0, offset=1.5)
    assert applied_schemas(prim) == ["PhysxMimicJointAPI:rotZ"]
    assert mimic_axes(prim) == ["rotZ"]
    assert prim.GetAttribute("physxMimicJoint:rotZ:gearing").Get() == -2.0
    assert prim.GetAttribute("physxMimicJoint:rotZ:offset").Get() == 1.5
    rel = prim.GetRelationship("physxMimicJoint:rotZ:referenceJoint")
    assert rel.GetTargets() == [Sdf.Path("/leader")]
    assert not prim.GetAttribute("physxMimicJoint:rotZ:gearing").IsCustom()


def test_usd_core_does_not_know_these_schemas(stage) -> None:
    """Why the helpers exist: usd-core leaves unknown schemas out of GetAppliedSchemas."""
    prim = stage.DefinePrim("/follower")
    apply_mimic(prim, "rotX", Sdf.Path("/leader"), gearing=1.0, offset=0.0)
    assert prim.GetAppliedSchemas() == []
    assert applied_schemas(prim) == ["PhysxMimicJointAPI:rotX"]


def test_rack_and_pinion_is_a_typed_prim_out_of_the_articulation(stage) -> None:
    prim = define_rack_and_pinion(
        stage,
        Sdf.Path("/rack_and_pinion"),
        pinion_body=Sdf.Path("/pinion"),
        rack_body=Sdf.Path("/rack"),
        hinge=Sdf.Path("/hinge"),
        prismatic=Sdf.Path("/slide"),
        ratio_deg_per_distance=360.0,
    )
    assert prim.GetTypeName() == "PhysxPhysicsRackAndPinionJoint"
    assert prim.GetRelationship("physics:body0").GetTargets() == [Sdf.Path("/pinion")]
    assert prim.GetRelationship("physics:body1").GetTargets() == [Sdf.Path("/rack")]
    assert prim.GetAttribute("physics:ratio").Get() == 360.0
    exclude = prim.GetAttribute("physics:excludeFromArticulation")
    assert exclude.Get() is True
    assert exclude.GetVariability() == Sdf.VariabilityUniform


def test_joint_state_names(stage) -> None:
    prim = stage.DefinePrim("/joint")
    set_joint_state(prim, "linear", 0.25)
    assert applied_schemas(prim) == ["PhysicsJointStateAPI:linear"]
    assert prim.GetAttribute("state:linear:physics:position").Get() == 0.25
    assert prim.GetAttribute("state:linear:physics:velocity").Get() == 0.0


@pytest.mark.parametrize(
    ("call", "message"),
    [
        (lambda p: apply_mimic(p, "transX", Sdf.Path("/leader"), 1.0, 0.0), "mimic"),
        (lambda p: set_joint_state(p, "rotX", 0.0), "joint state"),
    ],
)
def test_unknown_axes_are_refused(stage, call, message) -> None:
    with pytest.raises(ValueError, match=message):
        call(stage.DefinePrim("/joint"))
