import shutil
from pathlib import Path

import pydicom
import pytest
from pydicom.data import get_testdata_file
from pydicom.dataset import Dataset

from anondcm import (
    Action,
    Configuration,
    PixelDataWarning,
    Rule,
    anonymize_file,
    default_output_path,
    read_dicom,
)

PRISTINE = str(get_testdata_file("CT_small.dcm"))


def _copy(tmp_path: Path, name: str = "scan.dcm") -> Path:
    """A fresh, unmodified copy of the bundled sample DICOM."""
    destination = tmp_path / name
    shutil.copy(PRISTINE, destination)
    return destination


def _anonymized(scan: Path, config: Configuration | None = None) -> Dataset:
    """Anonymize ``scan`` to a separate file and return the result dataset."""
    output = scan.with_name(f"anon_{scan.name}")
    assert anonymize_file(scan, output, config) is True
    result = read_dicom(output)
    assert result is not None
    return result


def test_read_dicom_returns_none_for_non_dicom(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("not a dicom file")
    assert read_dicom(note) is None


# -- Output handling --------------------------------------------------------


def test_default_writes_separate_file_keeping_input(tmp_path: Path) -> None:
    scan = _copy(tmp_path)
    original_name = str(read_dicom(scan).PatientName)

    assert anonymize_file(scan) is True

    output = default_output_path(scan)
    assert output == tmp_path / "scan_anon.dcm"
    assert output.exists()
    # Input is untouched; the anonymized data lives in the new file.
    assert str(read_dicom(scan).PatientName) == original_name
    assert str(read_dicom(output).PatientName) != original_name


def test_in_place_overwrite_when_explicitly_requested(tmp_path: Path) -> None:
    scan = _copy(tmp_path)
    original_name = str(read_dicom(scan).PatientName)

    # Passing the input path as the output is the explicit overwrite request.
    assert anonymize_file(scan, scan) is True

    assert str(read_dicom(scan).PatientName) != original_name


# -- Anonymization behavior -------------------------------------------------


def test_identifiers_are_pseudonymized(tmp_path: Path) -> None:
    original = read_dicom(PRISTINE)
    result = _anonymized(_copy(tmp_path))

    assert str(result.PatientName) != str(original.PatientName)
    assert str(result.PatientID) != str(original.PatientID)
    assert str(result.PatientName) != ""
    assert str(result.PatientID) != ""


def test_pseudonyms_are_consistent_across_files(tmp_path: Path) -> None:
    first = _anonymized(_copy(tmp_path, "a.dcm"))
    second = _anonymized(_copy(tmp_path, "b.dcm"))

    # Same originals -> same anonymized values (linkable), including UIDs.
    assert str(first.PatientID) == str(second.PatientID)
    assert str(first.PatientName) == str(second.PatientName)
    assert first.StudyInstanceUID == second.StudyInstanceUID
    assert first.SeriesInstanceUID == second.SeriesInstanceUID
    assert first.SOPInstanceUID == second.SOPInstanceUID


def test_instance_uids_change_but_class_uid_is_kept(tmp_path: Path) -> None:
    original = read_dicom(PRISTINE)
    result = _anonymized(_copy(tmp_path))

    assert result.StudyInstanceUID != original.StudyInstanceUID
    assert result.SOPInstanceUID != original.SOPInstanceUID
    # SOP Class UID identifies the object type, not the patient -> preserved.
    assert result.SOPClassUID == original.SOPClassUID
    # The file-meta instance UID is remapped consistently with the dataset.
    assert result.file_meta.MediaStorageSOPInstanceUID == result.SOPInstanceUID


def test_remapped_uids_are_valid(tmp_path: Path) -> None:
    result = _anonymized(_copy(tmp_path))
    assert result.StudyInstanceUID.is_valid


def test_clinical_tags_are_preserved(tmp_path: Path) -> None:
    original = read_dicom(PRISTINE)
    result = _anonymized(_copy(tmp_path))

    assert result.Modality == original.Modality
    assert result.Rows == original.Rows
    assert result.Columns == original.Columns


def test_private_tags_are_removed(tmp_path: Path) -> None:
    scan = _copy(tmp_path)
    # The sample file ships with vendor private tags.
    assert any(element.tag.is_private for element in read_dicom(scan))

    result = _anonymized(scan)

    assert not any(element.tag.is_private for element in result)


def test_private_tags_kept_when_disabled(tmp_path: Path) -> None:
    config = Configuration()
    config.remove_private_tags = False
    result = _anonymized(_copy(tmp_path), config)

    assert any(element.tag.is_private for element in result)


def test_custom_rule_overrides_default(tmp_path: Path) -> None:
    config = Configuration()
    config.rules["PatientName"] = Rule(Action.REPLACE, "ANONYMOUS")
    result = _anonymized(_copy(tmp_path), config)

    assert str(result.PatientName) == "ANONYMOUS"


def test_anonymize_file_returns_false_for_non_dicom(tmp_path: Path) -> None:
    note = tmp_path / "note.txt"
    note.write_text("not a dicom file")
    assert anonymize_file(note) is False


# -- Editing helpers --------------------------------------------------------


def test_helper_methods_edit_rules(tmp_path: Path) -> None:
    original = read_dicom(PRISTINE)
    config = (
        Configuration()
        .replace("PatientName", "ANONYMOUS")
        .blank("StudyDescription")
        .keep("PatientID")
    )
    result = _anonymized(_copy(tmp_path), config)

    assert str(result.PatientName) == "ANONYMOUS"
    assert str(result.StudyDescription) == ""
    # keep() stopped PatientID from being touched.
    assert str(result.PatientID) == str(original.PatientID)


def test_helpers_are_chainable() -> None:
    config = Configuration()
    assert config.blank("A").hash("B").remove("C") is config


def test_action_can_be_assigned_directly(tmp_path: Path) -> None:
    config = Configuration()
    config.rules["StudyDescription"] = Action.BLANK
    result = _anonymized(_copy(tmp_path), config)

    assert str(result.StudyDescription) == ""


# -- Profiles ---------------------------------------------------------------


def test_research_profile_keeps_dates_and_descriptions(tmp_path: Path) -> None:
    original = read_dicom(PRISTINE)
    result = _anonymized(_copy(tmp_path), Configuration.research())

    assert result.StudyDate == original.StudyDate
    assert result.StudyDescription == original.StudyDescription
    # ...but still scrubs identifiers and institution.
    assert str(result.PatientName) != str(original.PatientName)
    assert str(result.InstitutionName) == ""


def test_strict_profile_blanks_dates_and_descriptions(tmp_path: Path) -> None:
    result = _anonymized(_copy(tmp_path), Configuration.strict())

    assert str(result.StudyDate) == ""
    assert str(result.StudyDescription) == ""


def test_minimal_profile_keeps_institution_and_private_tags(tmp_path: Path) -> None:
    original = read_dicom(PRISTINE)
    result = _anonymized(_copy(tmp_path), Configuration.minimal())

    # Direct identifiers still scrubbed...
    assert str(result.PatientName) != str(original.PatientName)
    # ...but institution and private tags are left alone.
    assert result.InstitutionName == original.InstitutionName
    assert any(element.tag.is_private for element in result)


# -- Nested sequences -------------------------------------------------------


def test_rules_apply_inside_sequences(tmp_path: Path) -> None:
    dataset = pydicom.dcmread(PRISTINE)
    original_pid = str(dataset.PatientID)
    item = Dataset()
    item.PatientID = original_pid  # same value as the top-level PatientID
    item.PatientName = "Nested^Patient"
    dataset.RequestAttributesSequence = [item]
    scan = tmp_path / "nested.dcm"
    dataset.save_as(scan)

    result = _anonymized(scan)

    nested = result.RequestAttributesSequence[0]
    # Nested PHI is scrubbed...
    assert str(nested.PatientName) != "Nested^Patient"
    assert str(nested.PatientID) != original_pid
    # ...and hashes consistently with the top-level value (same in -> same out).
    assert str(nested.PatientID) == str(result.PatientID)


# -- Provenance -------------------------------------------------------------


def test_provenance_tags_are_recorded(tmp_path: Path) -> None:
    result = _anonymized(_copy(tmp_path))
    assert str(result.PatientIdentityRemoved) == "YES"
    assert "anondcm" in str(result.DeidentificationMethod)


def test_provenance_can_be_disabled(tmp_path: Path) -> None:
    config = Configuration()
    config.record_provenance = False
    result = _anonymized(_copy(tmp_path), config)
    assert "PatientIdentityRemoved" not in result


# -- Pixel data warning -----------------------------------------------------


def test_warns_about_pixel_data(tmp_path: Path) -> None:
    scan = _copy(tmp_path)
    with pytest.warns(PixelDataWarning):
        anonymize_file(scan, tmp_path / "out.dcm")


# -- Modalities -------------------------------------------------------------


@pytest.mark.parametrize("filename", ["CT_small.dcm", "MR_small.dcm"])
def test_pixel_data_preserved_across_modalities(tmp_path: Path, filename: str) -> None:
    source = str(get_testdata_file(filename))
    original = read_dicom(source)
    scan = tmp_path / filename
    shutil.copy(source, scan)

    result = _anonymized(scan)

    assert result.Modality == original.Modality
    assert result.PixelData == original.PixelData
    assert str(result.PatientName) != str(original.PatientName)
