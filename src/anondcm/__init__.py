from importlib.metadata import PackageNotFoundError, version

from anondcm.anonymizer import (
    BatchResult,
    PixelDataWarning,
    anonymize_dataset,
    anonymize_directory,
    anonymize_file,
    default_output_dir,
    default_output_path,
    read_dicom,
)
from anondcm.configuration import Action, Configuration, Rule

try:
    __version__ = version("anondcm")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0+unknown"

__all__ = [
    "Action",
    "BatchResult",
    "Configuration",
    "PixelDataWarning",
    "Rule",
    "__version__",
    "anonymize_dataset",
    "anonymize_directory",
    "anonymize_file",
    "default_output_dir",
    "default_output_path",
    "read_dicom",
]
