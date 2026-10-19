"""The API, driven through FastAPI's test client the way the dashboard drives it (decision 0014).

Twins are stored through the orchestrator from the illustrative Pipeline B result (conftest), with
a photo file and a saved copy of a web page added as sources, so every endpoint has data to show.
"""

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from moonwalkers.api.app import create_app
from moonwalkers.api.security import CLIENT_HEADER
from moonwalkers.contracts.pipeline_result import (
    Citation,
    Fact,
    InputType,
    PipelineId,
    PipelineResult,
    Source,
)
from moonwalkers.kb import JsonKnowledgeBase, KnowledgeBase
from moonwalkers.orchestrator import JobRequest, MachineHint, Orchestrator
from moonwalkers.pipelines import Pipeline, result_id_for
from moonwalkers.workspace import Workspace

PNG = b"\x89PNG\r\n\x1a\n" + b"not a real image, but it starts like one"
HA5C = MachineHint(manufacturer="Haas Automation", model="HA5C")
LOCAL = "http://localhost"


class StaticPipeline(Pipeline):
    """Pipeline B returning a fixed result for whatever job it is given."""

    pipeline_id = PipelineId.B

    def __init__(self, result: PipelineResult) -> None:
        self.result = result

    def run(self, job_id: str, sources: list[Source]) -> PipelineResult:
        return self.result.model_copy(
            update={"job_id": job_id, "result_id": result_id_for(job_id, PipelineId.B)}
        )


@dataclass
class Api:
    client: TestClient
    data_dir: Path
    kb: KnowledgeBase
    clock: object

    def store_twin(self, result: PipelineResult, run: str, new_version: bool = False) -> str:
        """Store a twin version whose files sit in run folder ``run``; returns its twin id."""
        run_dir = self.data_dir / "machines" / "haas-ha5c" / "runs" / run
        run_dir.mkdir(parents=True, exist_ok=True)

        def exporter(twin, results) -> str:
            (run_dir / "twin.usdc").write_bytes(b"usd")
            return f"machines/haas-ha5c/runs/{run}/twin.usdc"

        photo = Source(
            source_id="src-photo",
            kind="file",
            input_type=InputType.MACHINE_PHOTO,
            uri="machines/haas-ha5c/inputs/photos/front.png",
            retrieved_at=result.produced_at,
        )
        orchestrator = Orchestrator(
            self.kb, {PipelineId.B: StaticPipeline(result)}, clock=self.clock, exporter=exporter
        )
        request = JobRequest(
            job_id=f"job-{run}", sources=[photo], machine=HA5C, new_version=new_version
        )
        return orchestrator.run_job(request).twin.twin_id

    def upload(self, data: bytes = PNG, **form: str):
        fields = {"manufacturer": "Haas Automation", "model": "HA5C", "origin": "test photo"}
        files = {"photo": ("front.png", data, "image/png")}
        return self.client.post("/api/jobs", data=fields | form, files=files)


@pytest.fixture
def api(tmp_path: Path, clock) -> Api:
    data_dir = tmp_path / "data"
    (data_dir / "machines").mkdir(parents=True)
    kb = JsonKnowledgeBase(data_dir / "kb")
    app = create_app(
        Workspace(data_dir, clock), kb, clock, dashboard_dir=None, max_upload_bytes=1000
    )
    client = TestClient(app, base_url=LOCAL, headers={CLIENT_HEADER: "tests"})
    return Api(client, data_dir, kb, clock)


@pytest.fixture
def cited_result(example_result: PipelineResult, api: Api) -> PipelineResult:
    """The example result plus a photo file and a URL source whose saved copy is hashed."""
    documents = api.data_dir / "machines" / "haas-ha5c" / "inputs" / "documents"
    documents.mkdir(parents=True)
    page = documents / "page.html"
    page.write_text("<html><script>alert(1)</script></html>", encoding="utf-8")
    photos = api.data_dir / "machines" / "haas-ha5c" / "inputs" / "photos"
    photos.mkdir(parents=True)
    (photos / "front.png").write_bytes(PNG)
    when = example_result.produced_at
    extra = [
        Source(
            source_id="src-front-photo",
            kind="file",
            input_type=InputType.MACHINE_PHOTO,
            uri="machines/haas-ha5c/inputs/photos/front.png",
            retrieved_at=when,
        ),
        Source(
            source_id="src-saved-page",
            kind="url",
            uri="https://example.com/ha5c",
            sha256=hashlib.sha256(page.read_bytes()).hexdigest(),
            retrieved_at=when,
        ),
    ]
    quote = Citation(source_id="src-saved-page", locator="Specs", quote="410 deg/s")
    fact = Fact(key="page_speed", value=410, unit="deg/s", confidence=0.9, citations=[quote])
    return example_result.model_copy(
        update={
            "sources": [*example_result.sources, *extra],
            "facts": [*example_result.facts, fact],
        }
    )


# --------------------------------------------------------------------------------------- jobs
def test_an_empty_data_folder(api: Api) -> None:
    status = api.client.get("/api/status").json()
    assert (status["machines"], status["twin_versions"], status["open_jobs"]) == (0, 0, 0)
    assert status["data_dir"] == str(api.data_dir.resolve())
    for path in ("/api/jobs", "/api/twins", "/api/sources"):
        assert api.client.get(path).json() == []


def test_an_uploaded_photo_starts_a_job_that_waits_for_the_agent(api: Api, fixed_time) -> None:
    response = api.upload(origin="Taken by Daniel in the lab", license_note="internal only")
    assert response.status_code == 201, response.text
    detail = response.json()
    job = detail["job"]
    assert (job["stage"], job["machine_key"], job["new_version"]) == (
        "waiting_for_agent",
        "haas/ha5c",
        False,
    )
    day = fixed_time.astimezone().date().isoformat()
    photo_uri = f"machines/haas-ha5c/inputs/photos/{day}_front.png"
    assert job["photo"]["uri"] == photo_uri
    assert job["photo"]["title"] == "Taken by Daniel in the lab (uploaded through the dashboard)"
    assert job["photo"]["sha256"] == hashlib.sha256(PNG).hexdigest()
    assert job["run"] in detail["agent_prompt"] and detail["notes"] is None
    assert (api.data_dir / photo_uri).read_bytes() == PNG
    sources = (api.data_dir / "machines/haas-ha5c/inputs/SOURCES.md").read_text(encoding="utf-8")
    assert f"| photos/{day}_front.png | Taken by Daniel in the lab |" in sources

    assert [j["run"] for j in api.client.get("/api/jobs").json()] == [job["run"]]
    machine, run = job["machine"], job["name"]
    assert api.client.get(f"/api/jobs/{machine}/{run}").json()["job"] == job
    assert api.client.get("/api/status").json()["open_jobs"] == 1


def test_an_upload_for_a_machine_with_a_twin_reuses_it(api: Api, example_result) -> None:
    twin_id = api.store_twin(example_result, "2026-10-16_run-001")
    reused = api.upload().json()
    assert (reused["job"]["stage"], reused["job"]["twin_id"]) == ("reused", twin_id)
    assert reused["agent_prompt"] is None
    run_dir = api.data_dir / reused["job"]["run"]
    result = json.loads((run_dir / "request.job_result.json").read_text(encoding="utf-8"))
    assert result["reused_existing"] and result["message"].startswith(
        "Found an existing twin (v1, needs review) for haas/ha5c; reused it."
    )

    rebuild = api.upload(new_version="true").json()["job"]
    assert (rebuild["stage"], rebuild["new_version"]) == ("waiting_for_agent", True)
    assert rebuild["photo"]["uri"] == reused["job"]["photo"]["uri"]  # the same file, kept once
    sources = (api.data_dir / "machines/haas-ha5c/inputs/SOURCES.md").read_text(encoding="utf-8")
    assert sources.count("uploaded through the dashboard") == 1


def test_bad_uploads_are_refused_before_anything_is_saved(api: Api) -> None:
    assert api.upload(data=b"GIF89a, not a JPEG or PNG").status_code == 415
    assert api.upload(data=PNG + b"x" * 1000).status_code == 413
    assert api.upload(manufacturer="!!!").status_code == 400
    assert (
        api.client.post(
            "/api/jobs", data={"manufacturer": "Haas", "model": "HA5C"}, files={"photo": ("a", PNG)}
        ).status_code
        == 422
    )  # no origin
    assert list((api.data_dir / "machines").iterdir()) == []


def test_unknown_jobs_are_not_found(api: Api) -> None:
    for path in ("haas-ha5c/2026-10-16_run-009", "Haas/run", "haas-ha5c/..%2F..%2Fkb"):
        assert api.client.get(f"/api/jobs/{path}").status_code == 404


# ------------------------------------------------------------------------------------- twins
def test_a_twin_version_shows_its_sources_and_what_cites_them(api: Api, cited_result) -> None:
    api.store_twin(cited_result, "2026-10-16_run-001")
    run_dir = api.data_dir / "machines/haas-ha5c/runs/2026-10-16_run-001"
    (run_dir / "preview" / "assembled").mkdir(parents=True)
    (run_dir / "preview" / "assembled" / "views.png").write_bytes(PNG)

    machines = api.client.get("/api/twins").json()
    assert [(m["machine_key"], m["reusable_version"]) for m in machines] == [("haas/ha5c", 1)]
    version = machines[0]["versions"][0]
    assert (version["review_status"], version["reusable"], version["run"]) == (
        "needs_review",
        True,
        "machines/haas-ha5c/runs/2026-10-16_run-001",
    )
    detail = api.client.get("/api/twins/haas/ha5c/versions/1").json()
    assert [r["result_id"] for r in detail["results"]] == ["res-job-2026-10-16_run-001-b"]
    uses = {u["source"]["source_id"]: u for u in detail["sources"]}
    assert [c["item"] for c in uses["src-product-page"]["cited_by"]] == [
        "identity",
        "fact center_height",
        "fact max_spindle_speed",
        "joint spindle_rotation",
    ]
    assert uses["src-saved-page"]["cited_by"] == [
        {"item": "fact page_speed", "locator": "Specs", "quote": "410 deg/s"}
    ]
    assert uses["src-saved-page"]["local_file"] == "machines/haas-ha5c/inputs/documents/page.html"
    assert uses["src-front-photo"]["local_file"] == "machines/haas-ha5c/inputs/photos/front.png"
    assert uses["src-product-page"]["local_file"] is None
    assert [i["label"] for i in detail["images"]] == ["Preview: assembled"]
    assert [o["kind"] for o in detail["outputs"]] == ["usd"]
    assert api.client.get("/api/twins/haas/ha5c/versions/2").status_code == 404
    assert api.client.get("/api/twins/grizzly/t33901").status_code == 404
    assert api.client.get("/api/twins/Haas/HA5C").status_code == 400


def test_reviews_decide_the_status_and_what_is_reused(api: Api, example_result) -> None:
    api.store_twin(example_result, "2026-10-16_run-001")
    api.store_twin(example_result, "2026-10-16_run-002", new_version=True)
    review = {"decision": "rejected", "reviewer": " Daniel Sweet ", "reason": "Split is wrong."}
    response = api.client.post("/api/twins/haas/ha5c/versions/2/reviews", json=review)
    assert response.status_code == 201, response.text
    assert response.json()["number"] == 1 and response.json()["reviewer"] == "Daniel Sweet"

    machine = api.client.get("/api/twins/haas/ha5c").json()
    assert machine["reusable_version"] == 1
    assert [
        (v["twin"]["version"], v["review_status"], v["reusable"]) for v in machine["versions"]
    ] == [
        (2, "rejected", False),
        (1, "needs_review", True),
    ]
    assert machine["versions"][0]["latest_review"]["reason"] == "Split is wrong."
    reused = api.upload().json()["job"]
    assert reused["twin_id"] == "haas/ha5c@v1"  # the rejected v2 is never reused

    approve = review | {"decision": "approved", "reason": "Looked again: it is right."}
    api.client.post("/api/twins/haas/ha5c/versions/2/reviews", json=approve)
    detail = api.client.get("/api/twins/haas/ha5c/versions/2").json()
    assert [r["decision"] for r in detail["reviews"]] == ["rejected", "approved"]
    assert detail["version"]["review_status"] == "approved" and detail["version"]["reusable"]

    assert (
        api.client.post("/api/twins/haas/ha5c/versions/9/reviews", json=review).status_code == 404
    )
    assert api.client.post("/api/twins/Haas/x/versions/1/reviews", json=review).status_code == 400
    maybe = review | {"decision": "maybe"}
    assert api.client.post("/api/twins/haas/ha5c/versions/1/reviews", json=maybe).status_code == 422
    blank = review | {"reason": "   "}
    assert api.client.post("/api/twins/haas/ha5c/versions/1/reviews", json=blank).status_code == 422


# ----------------------------------------------------------------------------------- sources
def test_sources_are_listed_once_per_document(api: Api, cited_result) -> None:
    api.store_twin(cited_result, "2026-10-16_run-001")
    renamed = [
        s.model_copy(update={"source_id": "src-page-again"})
        if s.source_id == "src-saved-page"
        else s
        for s in cited_result.sources
    ]
    again = cited_result.model_copy(update={"sources": renamed, "facts": cited_result.facts[:-1]})
    api.store_twin(again, "2026-10-16_run-002", new_version=True)

    listings = {tuple(s["source_ids"]): s for s in api.client.get("/api/sources").json()}
    page = listings[("src-saved-page", "src-page-again")]
    assert page["twins"] == ["haas/ha5c@v1", "haas/ha5c@v2"]
    assert page["source"]["source_id"] == "src-page-again"  # as the newest twin recorded it
    assert page["local_file"] == "machines/haas-ha5c/inputs/documents/page.html"
    assert listings[("src-user-calibration",)]["twins"] == ["haas/ha5c@v1", "haas/ha5c@v2"]


# ------------------------------------------------------------------------------------- files
def test_files_are_served_only_from_inputs_and_runs(api: Api, cited_result) -> None:
    api.store_twin(cited_result, "2026-10-16_run-001")
    kb_file = "kb/twins/haas/ha5c/v0001.json"
    assert (api.data_dir / kb_file).is_file()
    (api.data_dir / "machines/haas-ha5c/inputs/photos/.secret.png").write_bytes(PNG)
    (api.data_dir / "machines/haas-ha5c/inputs/photos/tool.exe").write_bytes(b"MZ")

    photo = api.client.get("/api/files/machines/haas-ha5c/inputs/photos/front.png")
    assert (photo.status_code, photo.headers["content-type"]) == (200, "image/png")
    assert photo.headers["content-security-policy"] == "sandbox"
    assert photo.headers["content-disposition"].startswith("inline")
    page = api.client.get("/api/files/machines/haas-ha5c/inputs/documents/page.html")
    assert page.headers["content-type"] == "text/plain; charset=utf-8"  # its script never runs
    usd = api.client.get("/api/files/machines/haas-ha5c/runs/2026-10-16_run-001/twin.usdc")
    assert usd.headers["content-disposition"] == 'attachment; filename="twin.usdc"'
    for refused in (
        kb_file,
        "machines/haas-ha5c/runs/2026-10-16_run-001/missing.png",
        "machines/haas-ha5c/inputs/photos/..%2F..%2F..%2Fkb%2Ftwins%2Fhaas%2Fha5c%2Fv0001.json",
        "machines/haas-ha5c/runs/%2E%2E/%2E%2E/%2E%2E/kb/twins/haas/ha5c/v0001.json",
        "machines/haas-ha5c/inputs/photos/.secret.png",  # hidden or temporary files
        "machines/haas-ha5c/inputs/photos/tool.exe",  # not a known file type
    ):
        assert api.client.get(f"/api/files/{refused}").status_code == 404, refused
    sources = api.client.get("/api/files/machines/haas-ha5c/inputs/SOURCES.md")
    assert sources.status_code == 404  # not written yet in this test: no upload happened


# ---------------------------------------------------------------------------------- security
def test_writes_need_the_client_header_and_a_local_origin(api: Api) -> None:
    plain = TestClient(api.client.app, base_url=LOCAL)
    assert plain.get("/api/status").status_code == 200  # reading needs no header
    refused = plain.post("/api/jobs", data={"manufacturer": "x"})
    assert refused.status_code == 403 and CLIENT_HEADER in refused.json()["detail"]

    def post(headers: dict[str, str]) -> int:
        return api.client.post(
            "/api/jobs",
            data={"manufacturer": "Haas", "model": "HA5C", "origin": "x"},
            files={"photo": ("a.png", PNG)},
            headers=headers,
        ).status_code

    assert post({"Sec-Fetch-Site": "cross-site"}) == 403
    assert post({"Origin": "https://example.com"}) == 403
    assert post({"Origin": "http://localhost:5173", "Sec-Fetch-Site": "same-site"}) == 201
    assert list((api.data_dir / "machines").iterdir()) == [api.data_dir / "machines/haas-ha5c"]


def test_only_local_host_names_are_accepted(api: Api) -> None:
    for host in ("http://evil.example", "http://192.168.1.20:8000"):
        assert TestClient(api.client.app, base_url=host).get("/api/status").status_code == 400
    assert (
        TestClient(api.client.app, base_url="http://127.0.0.1:8000").get("/api/status").status_code
        == 200
    )


def test_the_built_dashboard_is_served_with_a_content_security_policy(
    tmp_path: Path, clock
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<!doctype html><title>MoonWalkers</title>", encoding="utf-8")
    app = create_app(Workspace(tmp_path / "data", clock), dashboard_dir=dist)
    client = TestClient(app, base_url=LOCAL)
    page = client.get("/")
    assert page.status_code == 200 and "MoonWalkers" in page.text
    assert "default-src 'self'" in page.headers["content-security-policy"]
    assert page.headers["x-frame-options"] == "DENY"
    assert client.get("/api/status").status_code == 200
    assert "content-security-policy" not in client.get("/api/status").headers
