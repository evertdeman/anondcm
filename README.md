# anondcm

A small, typed tool to anonymize DICOM files — from the command line or as a Python library.

It scrubs identifying header tags, consistently pseudonymizes identifiers so related
studies stay linkable, and deterministically remaps instance UIDs, while keeping
clinically useful, non-identifying tags.

## ⚠️ Disclaimer — read before use

**Use at your own risk. This software is provided "as is", without warranty of any
kind (see [LICENSE](LICENSE)).**

- **It does not anonymize pixel data.** There is no removal of burned-in text and no
  defacing / skull-stripping. Images (e.g. ultrasound, secondary capture, screenshots)
  can contain identifying information *in the pixels* that this tool leaves untouched.
  anondcm warns when a file contains pixel data as a reminder.
- **It scrubs only known header tags** on a best-effort basis. It does **not** guarantee
  complete de-identification and is **not certified** for HIPAA Safe Harbor, GDPR, or any
  other regulatory standard.
- **You are responsible for validating the output** before sharing or publishing any data.
- This is **not a medical device** and is not intended for clinical decision-making.

## Installation

```bash
pip install anondcm
```

## Command line

```bash
# Writes scan_anon.dcm next to the input; the input is never overwritten.
anondcm scan.dcm

# Choose where to write it.
anondcm scan.dcm anonymized.dcm

# Overwrite the input in place (explicit).
anondcm scan.dcm --in-place

# Pick a profile (default: research).
anondcm scan.dcm --profile strict

# Print the version.
anondcm --version
```

By default the input file is left untouched and the result is written to
`<name>_anon<ext>`. Overwriting only happens when you ask for it (`--in-place`, or by
passing the input path as the output).

## Library

```python
from anondcm import anonymize_file, Configuration

# Standard profile, writes scan_anon.dcm, returns True if the file was DICOM.
anonymize_file("scan.dcm")

# Explicit output and a stricter profile.
anonymize_file("scan.dcm", "anonymized.dcm", Configuration.strict())
```

## Profiles

| Profile | Behavior |
|---|---|
| `research` (default) | Scrub identifiers; keep clinically useful tags such as study dates and descriptions. |
| `strict` | Also blank dates and free-text descriptions. |
| `minimal` | Only scrub direct patient identifiers; keep private tags and the rest. |

## Configuration

Build a configuration in code — there is no config file. Start from a profile and adjust
it with helper methods:

```python
from anondcm import Configuration, anonymize_file

config = (
    Configuration.research()
    .blank("StudyDescription")          # empty a tag's value
    .replace("PatientName", "ANON")     # set a fixed value
    .hash("PatientID")                  # consistent pseudonym
    .remove("SomeSequence")             # delete a tag
    .keep("PatientBirthDate")           # stop anonymizing a tag
)

anonymize_file("scan.dcm", configuration=config)
```

Rules can also be edited directly via `config.rules`, using an `Action` or a `Rule`:

```python
from anondcm import Action, Rule

config.rules["InstitutionName"] = Action.BLANK
config.rules["PatientName"] = Rule(Action.REPLACE, "ANON")
```

### Consistency

Identifiers such as `PatientID` and `PatientName`, and all instance UIDs
(`StudyInstanceUID`, `SeriesInstanceUID`, `SOPInstanceUID`, …), are replaced
deterministically: the same input always maps to the same output. Files from the same
patient or study therefore stay linkable after anonymization, without the originals being
recoverable. Set `Configuration.salt` to make the mapping unlinkable to that of another
dataset.

Rules are applied throughout nested sequences, not just at the top level, and
anonymized files are flagged with `PatientIdentityRemoved` / `DeidentificationMethod`
per DICOM PS3.15.

## License

[Apache-2.0](LICENSE)
