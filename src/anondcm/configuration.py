from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Action(Enum):
    """What to do with a DICOM element that is matched by a rule."""

    REMOVE = "remove"
    """Delete the element entirely."""

    BLANK = "blank"
    """Keep the element but give it an empty (zero-length) value."""

    REPLACE = "replace"
    """Set the element to a fixed value (:attr:`Rule.value`)."""

    HASH = "hash"
    """Replace the value with a deterministic pseudonym.

    The same input always maps to the same output, so identifiers such as
    ``PatientID`` and ``PatientName`` stay linkable across files without
    revealing the original value.
    """


@dataclass(frozen=True)
class Rule:
    """An :class:`Action` to apply to a tag, with an optional replacement value."""

    action: Action
    value: str = ""


# A rule can be given as a full ``Rule`` or, when no value is needed, as a bare
# ``Action`` (e.g. ``config.rules["PatientName"] = Action.HASH``).
RuleLike = Rule | Action


def as_rule(rule: RuleLike) -> Rule:
    """Normalize a :data:`RuleLike` to a :class:`Rule`."""
    return rule if isinstance(rule, Rule) else Rule(rule)


_HASH = Rule(Action.HASH)
_BLANK = Rule(Action.BLANK)
_REMOVE = Rule(Action.REMOVE)


# Identifiers: consistently pseudonymized (same in -> same out), so studies from
# the same patient stay linkable after anonymization.
_IDENTIFIER_RULES: dict[str, RuleLike] = {
    "PatientID": _HASH,
    "PatientName": _HASH,
    "OtherPatientIDs": _HASH,
    "OtherPatientNames": _HASH,
    "AccessionNumber": _HASH,
    "StudyID": _HASH,
}

# Direct patient contact details and birth information.
_PATIENT_CONTACT_RULES: dict[str, RuleLike] = {
    "PatientBirthDate": _BLANK,
    "PatientBirthTime": _BLANK,
    "PatientBirthName": _BLANK,
    "PatientMotherBirthName": _BLANK,
    "PatientAddress": _BLANK,
    "PatientTelephoneNumbers": _BLANK,
}

# Remaining patient demographics and free-text history.
_PATIENT_DETAIL_RULES: dict[str, RuleLike] = {
    **_PATIENT_CONTACT_RULES,
    "CountryOfResidence": _BLANK,
    "RegionOfResidence": _BLANK,
    "EthnicGroup": _BLANK,
    "Occupation": _BLANK,
    "PatientComments": _BLANK,
    "AdditionalPatientHistory": _BLANK,
    "MilitaryRank": _BLANK,
    "BranchOfService": _BLANK,
    "MedicalRecordLocator": _BLANK,
    "OtherPatientIDsSequence": _REMOVE,
    "ReferencedPatientSequence": _REMOVE,
}

# Staff, institution and device identifiers.
_STAFF_RULES: dict[str, RuleLike] = {
    "ReferringPhysicianName": _BLANK,
    "ReferringPhysicianAddress": _BLANK,
    "ReferringPhysicianTelephoneNumbers": _BLANK,
    "PerformingPhysicianName": _BLANK,
    "NameOfPhysiciansReadingStudy": _BLANK,
    "OperatorsName": _BLANK,
    "RequestingPhysician": _BLANK,
    "InstitutionName": _BLANK,
    "InstitutionAddress": _BLANK,
    "InstitutionalDepartmentName": _BLANK,
    "StationName": _BLANK,
    "DeviceSerialNumber": _BLANK,
}

# Dates and times that pin down when an exam happened.
_DATE_RULES: dict[str, RuleLike] = {
    "StudyDate": _BLANK,
    "StudyTime": _BLANK,
    "SeriesDate": _BLANK,
    "SeriesTime": _BLANK,
    "AcquisitionDate": _BLANK,
    "AcquisitionTime": _BLANK,
    "AcquisitionDateTime": _BLANK,
    "ContentDate": _BLANK,
    "ContentTime": _BLANK,
}

# Free-text descriptions, which can inadvertently contain identifying details.
_DESCRIPTION_RULES: dict[str, RuleLike] = {
    "StudyDescription": _BLANK,
    "SeriesDescription": _BLANK,
    "ImageComments": _BLANK,
}


# UID elements that identify a standard (SOP class, transfer syntax, software)
# rather than a specific study/series/instance, and so must be preserved.
KEEP_UIDS: frozenset[str] = frozenset(
    {
        "SOPClassUID",
        "MediaStorageSOPClassUID",
        "TransferSyntaxUID",
        "ImplementationClassUID",
    }
)


def _research_rules() -> dict[str, RuleLike]:
    return {**_IDENTIFIER_RULES, **_PATIENT_DETAIL_RULES, **_STAFF_RULES}


@dataclass
class Configuration:
    """How a DICOM dataset should be anonymized.

    ``Configuration()`` is the ``research`` profile: it scrubs identifying
    information while keeping clinically useful, non-identifying tags such as
    study dates and descriptions. Pick a different starting point with
    :meth:`strict`, :meth:`research` or :meth:`minimal`, then adjust it with the
    helper methods::

        config = (
            Configuration.research()
            .blank("StudyDescription")
            .replace("PatientName", "ANONYMOUS")
            .keep("PatientBirthDate")      # stop anonymizing this tag
        )

    Rules can also be edited directly via :attr:`rules`, using a :class:`Rule`
    or a bare :class:`Action`::

        config.rules["InstitutionName"] = Action.BLANK

    Attributes:
        rules: Maps a DICOM keyword to the rule applied to it. Any keyword not
            present is left untouched, so non-identifying tags are kept.
        remove_private_tags: Strip all private (vendor-specific) tags, which may
            hide identifying information.
        consistent_uids: Deterministically remap instance UIDs (e.g.
            ``StudyInstanceUID``). Equal input UIDs map to equal output UIDs, so
            cross-references and shared studies stay intact while the originals
            are not recoverable.
        keep_uids: UID keywords preserved when ``consistent_uids`` is enabled.
        salt: Mixed into every pseudonym and remapped UID. Change it to make the
            mapping unlinkable to that of another dataset.
        record_provenance: Record that de-identification happened by setting
            ``PatientIdentityRemoved`` and ``DeidentificationMethod`` (PS3.15).
    """

    rules: dict[str, RuleLike] = field(default_factory=_research_rules)
    remove_private_tags: bool = True
    consistent_uids: bool = True
    keep_uids: frozenset[str] = KEEP_UIDS
    salt: str = ""
    record_provenance: bool = True

    # -- Profiles -----------------------------------------------------------

    @classmethod
    def research(cls) -> Configuration:
        """Scrub identifiers but keep clinically useful tags (dates, descriptions).

        This is the same as ``Configuration()``.
        """
        return cls()

    @classmethod
    def strict(cls) -> Configuration:
        """A conservative profile that also blanks dates and free-text descriptions."""
        rules = {**_research_rules(), **_DATE_RULES, **_DESCRIPTION_RULES}
        return cls(rules=rules)

    @classmethod
    def minimal(cls) -> Configuration:
        """Only scrub direct patient identifiers; keep private tags and the rest."""
        rules = {**_IDENTIFIER_RULES, **_PATIENT_CONTACT_RULES}
        return cls(rules=rules, remove_private_tags=False)

    @classmethod
    def ps315(cls) -> Configuration:
        """The DICOM PS3.15 Basic Confidentiality Profile (header attributes).

        Applies the Basic Profile action for every catalogued attribute (remove,
        blank, or -- for key identifiers -- a consistent pseudonym), remaps UIDs,
        and removes private tags. This covers far more tags than :meth:`research`
        and is the most standards-aligned profile, but it discards many
        non-identifying tags that ``research`` keeps (dates, descriptions, patient
        characteristics). Pixel data and other image content are still not
        de-identified; PS3.15 pixel/structured-content options are out of scope.
        """
        from anondcm._ps315 import PS315_RULES

        return cls(rules=dict(PS315_RULES))

    @classmethod
    def default(cls) -> Configuration:
        """The default profile (:meth:`research`)."""
        return cls.research()

    # -- Editing helpers ----------------------------------------------------

    def blank(self, *keywords: str) -> Configuration:
        """Blank the given tags (keep them, but empty their value)."""
        for keyword in keywords:
            self.rules[keyword] = _BLANK
        return self

    def remove(self, *keywords: str) -> Configuration:
        """Delete the given tags entirely."""
        for keyword in keywords:
            self.rules[keyword] = _REMOVE
        return self

    def hash(self, *keywords: str) -> Configuration:
        """Replace the given tags with a consistent pseudonym."""
        for keyword in keywords:
            self.rules[keyword] = _HASH
        return self

    def replace(self, keyword: str, value: str) -> Configuration:
        """Set the given tag to a fixed ``value``."""
        self.rules[keyword] = Rule(Action.REPLACE, value)
        return self

    def keep(self, *keywords: str) -> Configuration:
        """Stop anonymizing the given tags (remove any rule for them)."""
        for keyword in keywords:
            self.rules.pop(keyword, None)
        return self
