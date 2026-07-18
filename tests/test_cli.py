import pytest

from freddie_pipeline import __version__
from freddie_pipeline.cli import build_parser, main


def test_no_command_is_an_error():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_version_flag(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert __version__ in capsys.readouterr().out


def test_all_subcommands_registered():
    parser = build_parser()
    text = parser.format_help()
    for command in ("init-db", "generate-sample", "load", "transform", "report", "run-all"):
        assert command in text


def test_load_missing_file_fails_cleanly_without_db():
    assert main(["load", "--orig", "no/such/file.txt"]) == 1


def test_load_missing_data_dir_fails_cleanly():
    assert main(["load", "--data-dir", "no/such/dir"]) == 1


def test_generate_sample_writes_files(tmp_path):
    out = tmp_path / "sample"
    assert main(["generate-sample", "--out-dir", str(out), "--loans", "20"]) == 0
    assert (out / "sample_orig_2022.txt").is_file()
    assert (out / "sample_svcg_2022.txt").is_file()
