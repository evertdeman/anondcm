import shutil
from pathlib import Path

from pydicom.data import get_testdata_file

from anondcm import anonymize_directory, default_output_dir, read_dicom

PRISTINE = str(get_testdata_file("CT_small.dcm"))


def _make_tree(root: Path) -> Path:
    """A directory with two DICOM files (one nested) and one non-DICOM file."""
    (root / "sub").mkdir(parents=True)
    shutil.copy(PRISTINE, root / "a.dcm")
    shutil.copy(PRISTINE, root / "sub" / "b.dcm")
    (root / "notes.txt").write_text("not a dicom file")
    return root


def test_default_mirrors_tree_into_sibling(tmp_path: Path) -> None:
    source = _make_tree(tmp_path / "study")
    original_name = str(read_dicom(PRISTINE).PatientName)

    result = anonymize_directory(source)

    output = default_output_dir(source)
    assert output == tmp_path / "study_anon"
    assert (output / "a.dcm").exists()
    assert (output / "sub" / "b.dcm").exists()
    assert len(result.anonymized) == 2
    assert len(result.skipped) == 1  # notes.txt

    # Inputs untouched; outputs anonymized.
    assert str(read_dicom(source / "a.dcm").PatientName) == original_name
    assert str(read_dicom(output / "a.dcm").PatientName) != original_name


def test_pseudonyms_consistent_across_the_folder(tmp_path: Path) -> None:
    source = _make_tree(tmp_path / "study")

    anonymize_directory(source)

    output = default_output_dir(source)
    a = read_dicom(output / "a.dcm")
    b = read_dicom(output / "sub" / "b.dcm")
    assert str(a.PatientID) == str(b.PatientID)
    assert a.StudyInstanceUID == b.StudyInstanceUID


def test_explicit_output_directory(tmp_path: Path) -> None:
    source = _make_tree(tmp_path / "study")
    destination = tmp_path / "anonymized"

    anonymize_directory(source, destination)

    assert (destination / "a.dcm").exists()
    assert (destination / "sub" / "b.dcm").exists()


def test_in_place_overwrites_inputs(tmp_path: Path) -> None:
    source = _make_tree(tmp_path / "study")
    original_name = str(read_dicom(PRISTINE).PatientName)

    anonymize_directory(source, source)

    assert str(read_dicom(source / "a.dcm").PatientName) != original_name
    assert str(read_dicom(source / "sub" / "b.dcm").PatientName) != original_name


def test_non_recursive_skips_subdirectories(tmp_path: Path) -> None:
    source = _make_tree(tmp_path / "study")

    result = anonymize_directory(source, recursive=False)

    # Only the top-level a.dcm, not sub/b.dcm.
    assert [path.name for path in result.anonymized] == ["a.dcm"]
