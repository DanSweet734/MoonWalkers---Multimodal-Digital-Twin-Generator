"""Setting a photo's cut-out and previewing it from the dashboard (decision 0041), driven through
FastAPI's test client. The preview runs the fake generator job, which writes placeholder files
where the real job writes its cut-outs, masks and sheet."""

import json
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from moonwalkers.api.app import create_app
from moonwalkers.api.security import CLIENT_HEADER
from moonwalkers.generators.hunyuan3d import Hunyuan3DConfig, Hunyuan3DGenerator, Hunyuan3DSettings
from moonwalkers.kb import JsonKnowledgeBase
from moonwalkers.orchestrator import JobRequest
from moonwalkers.workspace import Workspace

PNG = b"\x89PNG\r\n\x1a\n" + b"not a real image, but it starts like one"
FAKE_SCRIPT = Path(__file__).parent / "fixtures" / "fake_generator_job.py"
CORNERS = [("corner-l.png", PNG + b"l"), ("corner-r.png", PNG + b"r"), ("table.png", PNG + b"t")]
SAM = {
    "method": "sam",
    "box": [0.1, 0.1, 0.9, 0.95],
    "points": [{"x": 0.5, "y": 0.5, "keep": True}],
    "edits": [
        {"op": "add", "points": [[0.2, 0.2], [0.4, 0.2], [0.4, 0.4]], "note": "the guard"},
        {"op": "remove", "points": [[0.1, 0.1], [0.3, 0.12]], "width": 0.02},
    ],
}


def make_client(tmp_path: Path, clock, can_cut: bool) -> tuple[TestClient, Path]:
    data_dir = tmp_path / "data"
    (data_dir / "machines").mkdir(parents=True)

    def cutter() -> Hunyuan3DGenerator | None:
        if not can_cut:
            return None
        config = Hunyuan3DConfig(
            python=Path(sys.executable),
            models_dir=tmp_path / "models",
            u2net_home=tmp_path / "u2net",
            settings=Hunyuan3DSettings(),
        )
        return Hunyuan3DGenerator(config, script=FAKE_SCRIPT)

    app = create_app(
        Workspace(data_dir, clock),
        JsonKnowledgeBase(data_dir / "kb"),
        clock,
        dashboard_dir=None,
        cutter=cutter,
    )
    return TestClient(app, base_url="http://localhost", headers={CLIENT_HEADER: "tests"}), data_dir


@pytest.fixture
def client(tmp_path: Path, clock) -> tuple[TestClient, Path]:
    return make_client(tmp_path, clock, can_cut=True)


def start_job(client: TestClient) -> dict:
    """A three-photo job: two front corners fed to the generator, a detail as evidence."""
    fields = {
        "manufacturer": "Haas Automation",
        "model": "TM-1",
        "origin": ["a", "b", "c"],
        "view": ["front_operator_left", "front_operator_right", "detail"],
    }
    files = [("photo", (name, data, "image/png")) for name, data in CORNERS]
    response = client.post("/api/jobs", data=fields, files=files)
    assert response.status_code == 201, response.text
    return response.json()["job"]


def cutout_url(job: dict, index: int = 0) -> str:
    source_id = job["photos"][index]["source"]["source_id"]
    return f"/api/jobs/{job['machine']}/{job['name']}/photos/{source_id}/cutout"


def test_a_cutout_is_saved_with_its_edits_and_the_photos_view_kept(client) -> None:
    api, data_dir = client
    job = start_job(api)
    response = api.put(cutout_url(job), json={"cutout": SAM})
    assert response.status_code == 200, response.text
    detail = response.json()
    assert detail["cutouts_editable"] is True
    photo = detail["job"]["photos"][0]
    assert (photo["view"], photo["use"]) == ("front_operator_left", "generator")
    assert photo["cutout"]["edits"][0] == SAM["edits"][0]
    assert photo["cutout"]["edits"][1]["width"] == 0.02
    assert (photo["mask"], photo["preview"]) == (None, "none")
    request = JobRequest.model_validate_json(
        (data_dir / job["run"] / "request.json").read_text(encoding="utf-8")
    )
    saved = request.photos[job["photos"][0]["source"]["source_id"]]
    assert saved.cutout is not None and len(saved.cutout.edits) == 2

    cleared = api.put(cutout_url(job), json={"cutout": None}).json()["job"]["photos"][0]
    assert cleared["cutout"] is None and cleared["view"] == "front_operator_left"


@pytest.mark.parametrize(
    ("cutout", "says"),
    [
        ({"method": "auto"}, "leave the cut-out out"),
        ({"method": "auto", "box": [0, 0, 1, 1], "edits": SAM["edits"]}, "no box"),
        ({**SAM, "edits": [{"op": "add", "points": [[0.1, 0.1], [0.2, 0.2]]}]}, "polygon"),
        ({**SAM, "edits": [{"op": "paint", "points": [[0.1, 0.1]] * 3}]}, "op"),
    ],
)
def test_a_bad_cutout_is_refused_and_nothing_is_written(client, cutout, says) -> None:
    api, data_dir = client
    job = start_job(api)
    before = (data_dir / job["run"] / "request.json").read_bytes()
    response = api.put(cutout_url(job), json={"cutout": cutout})
    assert response.status_code == 422
    assert says in json.dumps(response.json()["detail"])
    assert (data_dir / job["run"] / "request.json").read_bytes() == before


def test_a_cutout_cannot_change_once_the_mesh_is_generated(client) -> None:
    api, data_dir = client
    job = start_job(api)
    record = data_dir / job["run"] / "generator" / "run.json"
    record.parent.mkdir(parents=True)
    record.write_text(json.dumps({"generator": {"name": "fake", "version": "0"}}), "utf-8")
    response = api.put(cutout_url(job), json={"cutout": SAM})
    assert response.status_code == 409
    assert "already generated" in response.json()["detail"]
    assert api.get(f"/api/jobs/{job['machine']}/{job['name']}").json()["cutouts_editable"] is False


def test_unknown_photos_and_jobs_are_refused(client) -> None:
    api, _ = client
    job = start_job(api)
    url = f"/api/jobs/{job['machine']}/{job['name']}/photos/src-none/cutout"
    assert api.put(url, json={"cutout": SAM}).status_code == 400
    missing = f"/api/jobs/{job['machine']}/2000-01-01_run-009/photos/x/cutout"
    assert api.put(missing, json={"cutout": SAM}).status_code == 404
    assert api.post(f"/api/jobs/{job['machine']}/2000-01-01_run-009/cutouts").status_code == 404


def test_a_photo_with_no_view_gets_its_view_from_the_agent_first(client) -> None:
    api, _ = client
    files = {"photo": ("front.png", PNG, "image/png")}
    fields = {"manufacturer": "Haas Automation", "model": "TM-1", "origin": "a"}
    job = api.post("/api/jobs", data=fields, files=files).json()["job"]
    response = api.put(cutout_url(job), json={"cutout": SAM})
    assert response.status_code == 400
    assert "no view yet" in response.json()["detail"]


def test_writes_need_the_client_header(client) -> None:
    api, _ = client
    job = start_job(api)
    bare = TestClient(api.app, base_url="http://localhost")
    assert bare.put(cutout_url(job), json={"cutout": SAM}).status_code == 403
    assert bare.post(f"/api/jobs/{job['machine']}/{job['name']}/cutouts").status_code == 403


def test_the_preview_shows_each_photos_mask_and_whether_it_is_current(client) -> None:
    api, data_dir = client
    job = start_job(api)
    api.put(cutout_url(job), json={"cutout": SAM})
    response = api.post(f"/api/jobs/{job['machine']}/{job['name']}/cutouts")
    assert response.status_code == 200, response.text
    preview = response.json()
    assert preview["sheet"] == f"{job['run']}/cutouts/sheet.png"
    assert preview["photos"][0].startswith(f"{job['photos'][0]['source']['source_id']}: sam")
    photos = preview["detail"]["job"]["photos"]
    assert [p["preview"] for p in photos] == ["current", "current", "none"]  # the detail: unfed
    assert photos[0]["mask"] == f"{job['run']}/cutouts/masks/{photos[0]['source']['source_id']}.png"
    assert (data_dir / photos[0]["mask"]).is_file()

    changed = {**SAM, "edits": SAM["edits"][:1]}
    after = api.put(cutout_url(job), json={"cutout": changed}).json()["job"]["photos"]
    assert [p["preview"] for p in after] == ["stale", "current", "none"]


def test_without_the_generator_folder_the_preview_says_how_to_run_it(tmp_path, clock) -> None:
    api, _ = make_client(tmp_path, clock, can_cut=False)
    job = start_job(api)
    response = api.post(f"/api/jobs/{job['machine']}/{job['name']}/cutouts")
    assert response.status_code == 503
    assert "MOONWALKERS_GEN_ROOT" in response.json()["detail"]
    assert "pipelines.b cutouts" in response.json()["detail"]
