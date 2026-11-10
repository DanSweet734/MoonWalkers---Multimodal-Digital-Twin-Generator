"""Uploaded photos: saved once under the machine's inputs, never overwritten, and listed."""

import hashlib
from pathlib import Path

import pytest

from moonwalkers.workspace import UnsupportedPhotoError, photo_suffix, save_photo
from moonwalkers.workspace.inputs import safe_stem

PNG = b"\x89PNG\r\n\x1a\n" + b"fake image data"
JPEG = b"\xff\xd8\xff\xe0" + b"fake image data"


def test_the_type_comes_from_the_bytes_not_the_name() -> None:
    assert photo_suffix(PNG) == ".png" and photo_suffix(JPEG) == ".jpg"
    for data in (b"GIF89a...", b"", b"<html>", b"RIFF....WEBP"):
        with pytest.raises(UnsupportedPhotoError, match="JPEG or PNG"):
            photo_suffix(data)


@pytest.mark.parametrize(
    ("name", "stem"),
    [
        ("IMG 0042.JPG", "IMG-0042"),
        ("C:\\fakepath\\lab photo.png", "lab-photo"),
        ("../../etc/passwd", "passwd"),
        (".hidden.png", "hidden"),
        ("...", "photo"),
        ("Haas|HA5C (front).jpeg", "Haas-HA5C-front"),
    ],
)
def test_file_names_are_made_safe(name: str, stem: str) -> None:
    assert safe_stem(name) == stem


def test_a_photo_is_saved_once_and_listed_in_sources(tmp_path: Path, fixed_time) -> None:
    machine = tmp_path / "machines" / "haas-ha5c"
    day = fixed_time.astimezone().date().isoformat()
    saved = save_photo(machine, JPEG, "front.JPG", "Taken by Daniel | CSUN lab", None, fixed_time)

    assert saved.path == machine / "inputs" / "photos" / f"{day}_front.jpg"
    assert saved.path.read_bytes() == JPEG and not saved.already_saved
    assert saved.sha256 == hashlib.sha256(JPEG).hexdigest()
    sources = (machine / "inputs" / "SOURCES.md").read_text(encoding="utf-8")
    assert sources.startswith("# Sources for haas-ha5c inputs\n")
    assert sources.endswith(
        f"| photos/{day}_front.jpg | Taken by Daniel \\| CSUN lab | "
        "2026-10-16 (12:00:00 UTC), uploaded through the dashboard | "
        f"{saved.sha256} | not given |\n"
    )

    again = save_photo(machine, JPEG, "renamed.jpg", "elsewhere", "x", fixed_time)
    assert again.already_saved and again.path == saved.path
    assert (machine / "inputs" / "SOURCES.md").read_text(encoding="utf-8") == sources


def test_a_photo_filed_in_any_photo_folder_is_found_again(tmp_path: Path, fixed_time) -> None:
    """The manual's figures in photos/manual/, and photos filed by hand in folders of their own,
    are the same photo when uploaded again (the lab's machines plan, tool gap 6)."""
    machine = tmp_path / "machines" / "grizzly-t33901"
    figure = machine / "inputs" / "photos" / "manual" / "p09_fig-1.png"
    filed = machine / "inputs" / "photos" / "2026-11-05" / "front.jpg"
    for path, data in ((figure, PNG), (filed, JPEG)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    for path, data in ((figure, PNG), (filed, JPEG)):
        again = save_photo(machine, data, "upload.jpg", "the dashboard", None, fixed_time)
        assert again.already_saved and again.path == path
    assert not (machine / "inputs" / "SOURCES.md").exists()  # nothing new to list
    assert sorted(p.name for p in (machine / "inputs" / "photos").iterdir()) == [
        "2026-11-05",
        "manual",
    ]


def test_a_different_photo_with_a_taken_name_gets_a_number(tmp_path: Path, fixed_time) -> None:
    machine = tmp_path / "machines" / "haas-ha5c"
    sources = machine / "inputs" / "SOURCES.md"
    sources.parent.mkdir(parents=True)
    sources.write_text("# Sources\n\n| File | ... |\n|---|---|\n| a.jpg | ... |", encoding="utf-8")
    first = save_photo(machine, JPEG, "front.jpg", "one", "internal only", fixed_time)
    second = save_photo(machine, JPEG + b"other", "front.jpg", "two", "internal only", fixed_time)

    assert second.path.name == first.path.name.replace(".jpg", "-2.jpg")
    assert first.path.read_bytes() == JPEG  # never overwritten
    lines = sources.read_text(encoding="utf-8").splitlines()
    assert lines[4] == "| a.jpg | ... |"  # the line without a newline was ended first
    assert [line.split(" | ")[1] for line in lines[5:]] == ["one", "two"]
