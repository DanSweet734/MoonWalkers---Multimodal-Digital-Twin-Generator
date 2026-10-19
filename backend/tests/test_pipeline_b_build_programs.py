"""A build whose control behaviour carries a program writes its program folder (decision 0016);
if that fails, the build leaves no files behind and stores nothing."""

import pytest

from moonwalkers.orchestrator import JobRequest
from moonwalkers.pipelines.b import build
from moonwalkers.usd.exporter import ExportError

EXAMPLE_3 = [[1, 90.0, 270.0, 4, 91], [2, 72.0, 270.0, 5, 91], [3, 0.0, 270.0, 1, 99]]


@pytest.fixture
def ready_run(photo_run, write_spec, test_reference):
    """A run folder with its request and spec, and reading notes whose behaviour has a program."""
    photo_run.run_dir.mkdir(parents=True)
    request = JobRequest(job_id="job-1", sources=[photo_run.photo])
    (photo_run.run_dir / "request.json").write_text(request.model_dump_json(), encoding="utf-8")
    write_spec(photo_run.run_dir)
    reference = test_reference.model_copy(deep=True)
    reference.control[0].spec = {"program": {"rows": EXAMPLE_3}}
    return photo_run, reference


def run_build(photo_run, reference, generator, kb):
    run_dir = photo_run.run_dir
    return build.build_run(
        run_dir, photo_run.data_dir, run_dir / "request.json", reference, None, generator, kb
    )


def test_a_failed_program_folder_leaves_nothing_then_a_retry_builds(
    ready_run, fake_generator, kb, monkeypatch
) -> None:
    photo_run, reference = ready_run
    generator = fake_generator()

    def broken(*_args, **_kwargs):
        raise ExportError("disk full")

    monkeypatch.setattr(build, "write_program_folder", broken)
    with pytest.raises(ExportError, match="disk full"):
        run_build(photo_run, reference, generator, kb)
    run_dir = photo_run.run_dir
    assert list(run_dir.glob("twin.usd*")) == []
    assert [p for p in (run_dir / "checks").rglob("*") if p.is_file()] == []
    assert not (run_dir / "programs" / "index-program").exists()
    assert kb.list_machines() == []

    monkeypatch.undo()
    outcome = run_build(photo_run, reference, generator, kb)
    folder = run_dir / "programs" / "index-program"
    assert (folder / "program.usdc").is_file() and (folder / "PROGRAM.md").is_file()
    assert outcome.twin_file == run_dir / "twin.usdc"
    assert generator.calls == 1  # the retry reused the mesh
