import shutil
from pathlib import Path

import pytest
from pydicom.data import get_testdata_file

from anondcm.__main__ import DEFAULT_PROFILE, Args, main, parse_args
from anondcm.anonymizer import default_output_path, read_dicom

PRISTINE = str(get_testdata_file("CT_small.dcm"))


def _args(**overrides: object) -> Args:
    values: dict[str, object] = {
        "input": "scan.dcm",
        "output": None,
        "profile": "research",
        "in_place": False,
    }
    values.update(overrides)
    return Args(**values)


def test_version_flag(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        parse_args(["--version"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out.strip().startswith("anondcm ")


def test_parse_args_defaults() -> None:
    args = parse_args(["scan.dcm"])
    assert args.input == "scan.dcm"
    assert args.output is None
    assert args.profile == DEFAULT_PROFILE
    assert args.in_place is False


def test_parse_args_accepts_output_and_profile() -> None:
    args = parse_args(["scan.dcm", "anon.dcm", "--profile", "strict"])
    assert args.output == "anon.dcm"
    assert args.profile == "strict"


def test_parse_args_rejects_unknown_profile() -> None:
    try:
        parse_args(["scan.dcm", "--profile", "nope"])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover
        raise AssertionError("expected argparse to reject an unknown profile")


def test_parse_args_rejects_in_place_with_output() -> None:
    try:
        parse_args(["scan.dcm", "anon.dcm", "--in-place"])
    except SystemExit as exc:
        assert exc.code == 2
    else:  # pragma: no cover
        raise AssertionError("expected --in-place with output to be rejected")


def test_main_default_writes_separate_file(tmp_path: Path) -> None:
    original_name = str(read_dicom(PRISTINE).PatientName)
    scan = tmp_path / "scan.dcm"
    shutil.copy(PRISTINE, scan)

    exit_code = main(_args(input=str(scan)))

    assert exit_code == 0
    output = default_output_path(scan)
    assert output.exists()
    # Input untouched by default.
    assert str(read_dicom(scan).PatientName) == original_name
    assert str(read_dicom(output).PatientName) != original_name


def test_main_in_place_overwrites(tmp_path: Path) -> None:
    original_name = str(read_dicom(PRISTINE).PatientName)
    scan = tmp_path / "scan.dcm"
    shutil.copy(PRISTINE, scan)

    exit_code = main(_args(input=str(scan), in_place=True))

    assert exit_code == 0
    assert str(read_dicom(scan).PatientName) != original_name


def test_main_strict_profile_blanks_dates(tmp_path: Path) -> None:
    scan = tmp_path / "scan.dcm"
    shutil.copy(PRISTINE, scan)
    output = tmp_path / "anon.dcm"

    exit_code = main(_args(input=str(scan), output=str(output), profile="strict"))

    assert exit_code == 0
    assert str(read_dicom(output).StudyDate) == ""


def test_main_reports_non_dicom(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("not a dicom file")

    exit_code = main(_args(input=str(note)))

    assert exit_code == 2


def test_main_directory_writes_to_sibling(tmp_path: Path) -> None:
    source = tmp_path / "study"
    source.mkdir()
    shutil.copy(PRISTINE, source / "a.dcm")

    exit_code = main(_args(input=str(source)))

    assert exit_code == 0
    assert (tmp_path / "study_anon" / "a.dcm").exists()


def test_main_directory_without_dicom_returns_error(tmp_path: Path) -> None:
    source = tmp_path / "empty"
    source.mkdir()
    (source / "notes.txt").write_text("not a dicom file")

    exit_code = main(_args(input=str(source)))

    assert exit_code == 1


def test_main_reports_missing_input(tmp_path: Path) -> None:
    exit_code = main(_args(input=str(tmp_path / "does_not_exist.dcm")))
    assert exit_code == 2


def test_main_warns_about_pixel_data(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    scan = tmp_path / "scan.dcm"
    shutil.copy(PRISTINE, scan)

    main(_args(input=str(scan)))

    assert "pixel data" in capsys.readouterr().out.lower()
