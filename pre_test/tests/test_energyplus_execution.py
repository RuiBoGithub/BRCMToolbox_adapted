from pathlib import Path

import pytest

from brcm.energyplus import get_objects_from_string, prepare_energyplus_case


def _idf(*objects: str) -> str:
    return "Version, 23.2;\n" + "\n".join(objects)


def _window(name: str, filename: str) -> str:
    return f"Construction:WindowDataFile, {name}, {filename};"


def test_case_without_external_files_only_copies_idf(tmp_path):
    source = tmp_path / "source" / "plain.idf"
    source.parent.mkdir()
    source.write_text(_idf("Zone, Room;"), encoding="utf-8")
    working = prepare_energyplus_case(source, tmp_path / "work")
    assert working.read_text() == source.read_text()
    assert list(working.parent.iterdir()) == [working]


def test_arbitrary_window_file_is_resolved_from_search_path(tmp_path):
    source = tmp_path / "case.idf"
    source.write_text(_idf(_window("Custom", r"missing\custom-window.dat")), encoding="utf-8")
    resource = tmp_path / "resources" / "custom-window.dat"
    resource.parent.mkdir()
    resource.write_text("window data", encoding="utf-8")
    working = prepare_energyplus_case(source, tmp_path / "work", [resource.parent])
    obj = next(o for o in get_objects_from_string(working.read_text()) if o.type == "Construction:WindowDataFile")
    assert obj.values[1] == r"missing\custom-window.dat"
    assert (working.parent / "missing" / "custom-window.dat").read_text() == "window data"


def test_missing_external_resource_names_original_path(tmp_path):
    source = tmp_path / "case.idf"
    source.write_text(_idf(_window("Custom", "does/not/exist.dat")), encoding="utf-8")
    with pytest.raises(FileNotFoundError, match=r"does/not/exist\.dat"):
        prepare_energyplus_case(source, tmp_path / "work")


def test_multiple_external_resources_are_resolved_independently(tmp_path):
    source = tmp_path / "source" / "case.idf"
    source.parent.mkdir()
    source.write_text(_idf(_window("First", "../one.dat"), _window("Second", "../two.dat")), encoding="utf-8")
    search = tmp_path / "resources"
    search.mkdir()
    (search / "one.dat").write_text("one")
    (search / "two.dat").write_text("two")
    working = prepare_energyplus_case(source, tmp_path / "work", [search])
    objects = [o for o in get_objects_from_string(working.read_text()) if o.type == "Construction:WindowDataFile"]
    assert len(objects) == 2
    staged = [(working.parent / o.values[1]).read_text() for o in objects]
    assert staged == ["one", "two"]
