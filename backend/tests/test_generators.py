"""Generator adapters: the subprocess protocol, input checks, and (opt-in) the real GPU run."""

import os
import sys
from dataclasses import asdict
from pathlib import Path

import pytest
import trimesh

from moonwalkers.generators.base import GeneratorError, GeneratorRequest
from moonwalkers.generators.hunyuan3d import (
    Hunyuan3DConfig,
    Hunyuan3DGenerator,
    Hunyuan3DSettings,
)
from moonwalkers.generators.subprocess_job import run_job

FAKE_SCRIPT = Path(__file__).parent / "fixtures" / "fake_generator_job.py"
PHOTO = Path(__file__).parents[2] / "data/machines/haas-ha5c/inputs/photos"


@pytest.fixture
def image(tmp_path: Path) -> Path:
    path = tmp_path / "photo.png"
    path.write_bytes(b"not really a png; the fake generator never opens it")
    return path


def fake_generator(tmp_path: Path, settings: Hunyuan3DSettings | None = None) -> Hunyuan3DGenerator:
    config = Hunyuan3DConfig(
        python=Path(sys.executable),
        models_dir=tmp_path / "models",
        u2net_home=tmp_path / "u2net",
        settings=settings or Hunyuan3DSettings(),
    )
    return Hunyuan3DGenerator(config, script=FAKE_SCRIPT)


def test_generate_runs_the_job_script_and_reports_the_run(tmp_path: Path, image: Path) -> None:
    run = fake_generator(tmp_path).generate(
        GeneratorRequest(images={"single": image}, out_dir=tmp_path / "out")
    )
    assert run.mesh_path.is_file()
    assert len(trimesh.load(run.mesh_path, force="mesh").faces) == 12
    assert (run.generator.name, run.generator.version) == ("hunyuan3d-2", "fake")
    assert run.generator.params["seed"] == 12345
    assert run.generator.params["subfolder"] == "hunyuan3d-dit-v2-0"
    assert "fake generator ran" in run.log_path.read_text(encoding="utf-8")
    assert run.details["images_seen"] == {"single": str(image.resolve())}
    assert run.details["env_seen"] == {
        "HY3DGEN_MODELS": str(tmp_path / "models"),
        "U2NET_HOME": str(tmp_path / "u2net"),
    }


def test_relative_paths_work(tmp_path: Path, image: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # The job script runs with cwd=out_dir, so relative paths must be resolved first.
    monkeypatch.chdir(tmp_path)
    run = fake_generator(tmp_path).generate(
        GeneratorRequest(images={"single": Path(image.name)}, out_dir=Path("runs") / "out")
    )
    assert run.mesh_path.is_file()
    assert run.mesh_path.is_relative_to(tmp_path / "runs" / "out")


def test_single_image_model_refuses_named_views(tmp_path: Path, image: Path) -> None:
    with pytest.raises(ValueError, match="one image named 'single'"):
        fake_generator(tmp_path).generate(
            GeneratorRequest(images={"front": image, "left": image}, out_dir=tmp_path)
        )


def test_multiview_model_needs_known_view_names(tmp_path: Path, image: Path) -> None:
    mv = Hunyuan3DSettings(model_repo="tencent/Hunyuan3D-2mv", subfolder="hunyuan3d-dit-v2-mv")
    with pytest.raises(ValueError, match="multi-view input"):
        fake_generator(tmp_path, mv).generate(
            GeneratorRequest(images={"front": image, "top": image}, out_dir=tmp_path)
        )


def test_missing_image_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        GeneratorRequest(images={"single": tmp_path / "missing.jpg"}, out_dir=tmp_path)


def test_failed_generation_raises_with_the_log(tmp_path: Path, image: Path) -> None:
    generator = fake_generator(tmp_path, Hunyuan3DSettings(seed=666))
    with pytest.raises(GeneratorError, match="simulated failure") as exc:
        generator.generate(GeneratorRequest(images={"single": image}, out_dir=tmp_path / "out"))
    assert "generator.log" in str(exc.value)


def test_timeout_is_reported(tmp_path: Path) -> None:
    script = tmp_path / "slow.py"
    script.write_text("import time\ntime.sleep(30)\n", encoding="utf-8")
    with pytest.raises(GeneratorError, match="timed out"):
        run_job(Path(sys.executable), script, {}, tmp_path / "work", timeout_s=1)


def test_script_without_result_is_reported(tmp_path: Path) -> None:
    script = tmp_path / "silent.py"
    script.write_text("print('no result written')\n", encoding="utf-8")
    with pytest.raises(GeneratorError, match="wrote no result"):
        run_job(Path(sys.executable), script, {}, tmp_path / "work", timeout_s=30)


def test_missing_generator_python_is_reported(tmp_path: Path) -> None:
    with pytest.raises(GeneratorError, match="Python not found"):
        run_job(tmp_path / "no-python.exe", FAKE_SCRIPT, {}, tmp_path, timeout_s=5)


@pytest.mark.gpu
@pytest.mark.slow
@pytest.mark.skipif(
    not os.environ.get("MOONWALKERS_GEN_ROOT"),
    reason="set MOONWALKERS_GEN_ROOT to the generator folder (e.g. C:\\mw-gen) to run",
)
def test_real_hunyuan3d_generation(tmp_path: Path) -> None:
    photo = PHOTO / "haas-uk_HA5C_2011.original.jpg"
    if not photo.is_file():
        pytest.skip("HA5C photo not present in data/")
    config = Hunyuan3DConfig.under(Path(os.environ["MOONWALKERS_GEN_ROOT"]))
    run = Hunyuan3DGenerator(config).generate(
        GeneratorRequest(images={"single": photo}, out_dir=tmp_path)
    )
    mesh = trimesh.load(run.mesh_path, force="mesh")
    assert 1000 < len(mesh.faces) <= config.settings.max_faces


def test_fingerprint_names_every_setting(tmp_path: Path) -> None:
    settings = Hunyuan3DSettings(seed=7)
    fingerprint = fake_generator(tmp_path, settings).fingerprint()
    assert fingerprint == {"name": "hunyuan3d-2", **asdict(settings)}
    assert fingerprint != fake_generator(tmp_path).fingerprint()  # another seed, another mesh


def test_temporary_files_stay_in_the_run_and_are_removed(tmp_path: Path, image: Path) -> None:
    out_dir = tmp_path / "out"
    run = fake_generator(tmp_path).generate(
        GeneratorRequest(images={"single": image}, out_dir=out_dir)
    )
    leftover = Path(run.details["leftover_seen"])
    assert leftover.parent == out_dir.resolve() / "tmp"  # not the user's temp folder
    assert not leftover.parent.exists()
