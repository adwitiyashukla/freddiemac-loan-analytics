import pytest

from freddie_pipeline.loader import (
    FIELD_COUNT,
    ORIGINATION_COLUMNS,
    PERFORMANCE_COLUMNS,
    _validated_lines,
    escape_copy_text,
    load_file,
)
from freddie_pipeline.utils import PipelineError

GOOD_LINE = "|".join(str(n) for n in range(FIELD_COUNT))


def test_column_lists_match_layout_width():
    assert len(ORIGINATION_COLUMNS) == FIELD_COUNT
    assert len(PERFORMANCE_COLUMNS) == FIELD_COUNT
    assert len(set(ORIGINATION_COLUMNS)) == FIELD_COUNT
    assert len(set(PERFORMANCE_COLUMNS)) == FIELD_COUNT


def test_escape_copy_text():
    assert escape_copy_text("plain") == "plain"
    assert escape_copy_text("") == ""
    assert escape_copy_text("a\\b") == "a\\\\b"
    assert escape_copy_text("\\") == "\\\\"


def test_validated_lines_accepts_good_input(tmp_path):
    path = tmp_path / "good.txt"
    path.write_text(f"{GOOD_LINE}\n{GOOD_LINE}\n")
    rejects: list[tuple] = []
    lines = list(_validated_lines(path, "good.txt", rejects))
    assert len(lines) == 2
    assert rejects == []
    assert lines[0].split("|")[-1] == "good.txt"
    assert len(lines[0].split("|")) == FIELD_COUNT + 1


def test_validated_lines_rejects_corrupt_rows(tmp_path):
    path = tmp_path / "mixed.txt"
    path.write_text(
        f"{GOOD_LINE}\n"
        "only|three|fields\n"
        f"{GOOD_LINE}|extra\n"
        "\n"
        f"{GOOD_LINE}\n"
    )
    rejects: list[tuple] = []
    lines = list(_validated_lines(path, "mixed.txt", rejects))
    assert len(lines) == 2
    assert len(rejects) == 2
    assert rejects[0][1] == 2
    assert rejects[0][2] == 3
    assert "expected 32" in rejects[0][3]
    assert rejects[1][2] == 33


def test_load_file_unknown_kind():
    with pytest.raises(PipelineError, match="Unknown load kind"):
        load_file(None, "nonsense", "whatever.txt")


def test_load_file_missing_file():
    with pytest.raises(PipelineError, match="not found"):
        load_file(None, "origination", "does/not/exist.txt")


def test_load_file_empty_file(tmp_path):
    path = tmp_path / "empty.txt"
    path.write_text("")
    with pytest.raises(PipelineError, match="empty"):
        load_file(None, "origination", path)
