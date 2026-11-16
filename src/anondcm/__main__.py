from __future__ import annotations

import argparse
import warnings
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Literal

from anondcm import __version__
from anondcm.anonymizer import (
    PixelDataWarning,
    anonymize_directory,
    anonymize_file,
    default_output_dir,
    default_output_path,
)
from anondcm.configuration import Configuration

Profile = Literal["research", "strict", "minimal"]

PROFILES: dict[Profile, Callable[[], Configuration]] = {
    "research": Configuration.research,
    "strict": Configuration.strict,
    "minimal": Configuration.minimal,
}
DEFAULT_PROFILE: Profile = "research"


class Args(argparse.Namespace):
    input: str
    output: str | None
    profile: Profile
    in_place: bool


def parse_args(argv: Sequence[str] | None = None) -> Args:
    parser = argparse.ArgumentParser(
        prog="anondcm",
        description="Anonymize a DICOM file.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    parser.add_argument(
        "input", type=str, help="Path to the input DICOM file or a directory of them"
    )
    parser.add_argument(
        "output",
        type=str,
        nargs="?",
        default=None,
        help=(
            "Where to write the result (default: '<name>_anon' next to the input). "
            "For a file this is the output file; for a directory, the output directory"
        ),
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite the inputs instead of writing to a separate location",
    )
    parser.add_argument(
        "--profile",
        choices=tuple(PROFILES),
        default=DEFAULT_PROFILE,
        help=(
            "Anonymization profile: 'research' keeps clinically useful tags such "
            "as dates and descriptions, 'strict' also blanks those, and 'minimal' "
            "only scrubs direct patient identifiers (default: %(default)s)"
        ),
    )
    args = parser.parse_args(argv, namespace=Args())
    if args.in_place and args.output is not None:
        parser.error("argument output: not allowed with --in-place")
    return args


def main(args: Args) -> int:
    input_path = Path(args.input)
    if not input_path.exists():
        print(f"{input_path}: no such file or directory")
        return 2
    configuration = PROFILES[args.profile]()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        if input_path.is_dir():
            code = _anonymize_directory(args, input_path, configuration)
        else:
            code = _anonymize_file(args, input_path, configuration)

    if any(issubclass(entry.category, PixelDataWarning) for entry in caught):
        print(
            "Warning: pixel data is not anonymized; "
            "images may contain burned-in identifying information."
        )
    return code


def _anonymize_file(args: Args, input_path: Path, configuration: Configuration) -> int:
    if args.in_place:
        output_path = input_path
    elif args.output is not None:
        output_path = Path(args.output)
    else:
        output_path = default_output_path(input_path)
    if anonymize_file(input_path, output_path, configuration):
        print(f"Anonymized {input_path} -> {output_path} ({args.profile} profile)")
        return 0
    print(f"{input_path} is not a DICOM file; skipping")
    return 2


def _anonymize_directory(
    args: Args, input_path: Path, configuration: Configuration
) -> int:
    if args.in_place:
        output_dir: Path | None = input_path
    elif args.output is not None:
        output_dir = Path(args.output)
    else:
        output_dir = None
    if output_dir is not None:
        destination = output_dir
    else:
        destination = default_output_dir(input_path)

    result = anonymize_directory(input_path, output_dir, configuration)
    if not result.anonymized:
        print(f"No DICOM files found in {input_path}")
        return 1

    message = (
        f"Anonymized {len(result.anonymized)} file(s) -> {destination} "
        f"({args.profile} profile)"
    )
    if result.skipped:
        message += f", skipped {len(result.skipped)} non-DICOM file(s)"
    print(message)
    return 0


def cli() -> int:
    return main(parse_args())


if __name__ == "__main__":
    raise SystemExit(cli())
