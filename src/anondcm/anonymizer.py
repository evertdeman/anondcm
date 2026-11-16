from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pydicom
from pydicom.dataelem import DataElement
from pydicom.dataset import Dataset
from pydicom.errors import InvalidDicomError
from pydicom.uid import generate_uid

from anondcm.configuration import Action, Configuration, Rule, as_rule

PathLike = str | Path

DEIDENTIFICATION_METHOD = "anondcm"


class PixelDataWarning(UserWarning):
    """Warns that a dataset has pixel data, which anondcm does not anonymize."""


def default_output_path(input_path: PathLike) -> Path:
    """The non-overwriting default output: ``<name>_anon<ext>`` next to the input."""
    path = Path(input_path)
    return path.with_name(f"{path.stem}_anon{path.suffix}")


def default_output_dir(input_dir: PathLike) -> Path:
    """The non-overwriting default output dir: ``<name>_anon`` beside the input."""
    path = Path(input_dir)
    return path.parent / f"{path.name}_anon"


def read_dicom(path: PathLike) -> Dataset | None:
    """Read ``path`` as a DICOM dataset, or return ``None`` if it is not DICOM.

    A missing file still raises ``FileNotFoundError`` -- only non-DICOM
    content is reported as ``None``.
    """
    try:
        return pydicom.dcmread(path)
    except InvalidDicomError:
        return None


def _pseudonym(value: str, salt: str) -> str:
    """A short, deterministic pseudonym for ``value``."""
    return hashlib.sha256(f"{salt}:{value}".encode()).hexdigest()[:16].upper()


def _remap_uid(value: Any, salt: str) -> Any:
    """Deterministically replace a UID (or list of UIDs) with a valid new one."""
    if isinstance(value, str):
        return generate_uid(entropy_srcs=[salt, value])
    return [generate_uid(entropy_srcs=[salt, str(item)]) for item in value]


def _remap_uids_in(dataset: Dataset, configuration: Configuration) -> None:
    def callback(_dataset: Dataset, element: DataElement) -> None:
        if element.VR != "UI" or element.keyword in configuration.keep_uids:
            return
        if element.value in (None, ""):
            return
        element.value = _remap_uid(element.value, configuration.salt)

    dataset.walk(callback)
    file_meta = getattr(dataset, "file_meta", None)
    if file_meta is not None:
        for element in file_meta:
            callback(dataset, element)


def _apply_rule(
    dataset: Dataset, keyword: str, rule: Rule, configuration: Configuration
) -> None:
    if rule.action is Action.REMOVE:
        del dataset[keyword]
    elif rule.action is Action.BLANK:
        dataset[keyword].value = ""
    elif rule.action is Action.REPLACE:
        dataset[keyword].value = rule.value
    elif rule.action is Action.HASH:
        element = dataset[keyword]
        if element.value not in (None, ""):
            element.value = _pseudonym(str(element.value), configuration.salt)


def _apply_rules(dataset: Dataset, configuration: Configuration) -> None:
    """Apply the configured rules to ``dataset`` and, recursively, its sequences."""
    for keyword, rule_like in configuration.rules.items():
        if keyword in dataset:
            _apply_rule(dataset, keyword, as_rule(rule_like), configuration)
    for element in dataset:
        if element.VR == "SQ":
            for item in element.value:
                _apply_rules(item, configuration)


def _record_provenance(dataset: Dataset) -> None:
    """Flag the dataset as de-identified, per DICOM PS3.15."""
    dataset.PatientIdentityRemoved = "YES"
    dataset.DeidentificationMethod = DEIDENTIFICATION_METHOD


def _warn_if_pixel_data(dataset: Dataset) -> None:
    if "PixelData" not in dataset:
        return
    if str(dataset.get("BurnedInAnnotation", "")).upper() == "NO":
        return
    warnings.warn(
        "Pixel data is not anonymized; images may contain burned-in "
        "identifying information.",
        PixelDataWarning,
        stacklevel=2,
    )


def anonymize_dataset(dataset: Dataset, configuration: Configuration) -> Dataset:
    """Apply ``configuration`` to ``dataset`` in place and return it."""
    if configuration.remove_private_tags:
        dataset.remove_private_tags()

    _apply_rules(dataset, configuration)

    if configuration.consistent_uids:
        _remap_uids_in(dataset, configuration)

    if configuration.record_provenance:
        _record_provenance(dataset)

    _warn_if_pixel_data(dataset)

    return dataset


def anonymize_file(
    input_path: PathLike,
    output_path: PathLike | None = None,
    configuration: Configuration | None = None,
) -> bool:
    """Anonymize the DICOM file at ``input_path`` and save it.

    Returns ``True`` when the file was DICOM and has been anonymized, and
    ``False`` when ``input_path`` is not a DICOM file (it is then left
    untouched).

    The input is never overwritten unless requested: ``output_path`` defaults
    to :func:`default_output_path` (``<name>_anon<ext>`` next to the input).
    To overwrite in place, pass ``input_path`` as ``output_path`` explicitly.
    ``configuration`` defaults to the standard :class:`Configuration`.
    """
    if configuration is None:
        configuration = Configuration()
    dataset = read_dicom(input_path)
    if dataset is None:
        return False
    anonymize_dataset(dataset, configuration)
    target = output_path if output_path is not None else default_output_path(input_path)
    dataset.save_as(target)
    return True


@dataclass
class BatchResult:
    """The outcome of anonymizing a directory.

    ``anonymized`` lists the output paths written; ``skipped`` lists the input
    paths that were not DICOM and were left alone.
    """

    anonymized: list[Path] = field(default_factory=list)
    skipped: list[Path] = field(default_factory=list)


def anonymize_directory(
    input_dir: PathLike,
    output_dir: PathLike | None = None,
    configuration: Configuration | None = None,
    *,
    recursive: bool = True,
) -> BatchResult:
    """Anonymize every DICOM file under ``input_dir``, mirroring the tree.

    Non-DICOM files are skipped. The input is never overwritten unless
    requested: ``output_dir`` defaults to :func:`default_output_dir`
    (``<name>_anon`` beside the input). To anonymize in place, pass
    ``input_dir`` as ``output_dir``.

    A single ``configuration`` is reused for every file, so pseudonyms and
    remapped UIDs stay consistent across the whole folder (files that share a
    patient or study still share the anonymized values).
    """
    if configuration is None:
        configuration = Configuration()
    source = Path(input_dir)
    if output_dir is not None:
        target_root = Path(output_dir)
    else:
        target_root = default_output_dir(source)

    pattern = "**/*" if recursive else "*"
    files = sorted(path for path in source.glob(pattern) if path.is_file())

    result = BatchResult()
    for file in files:
        dataset = read_dicom(file)
        if dataset is None:
            result.skipped.append(file)
            continue
        anonymize_dataset(dataset, configuration)
        target = target_root / file.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        dataset.save_as(target)
        result.anonymized.append(target)
    return result
