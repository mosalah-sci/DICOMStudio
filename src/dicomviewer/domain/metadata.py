"""DICOM metadata model and grouping rules.

Pure data describing the metadata of one DICOM instance together with the
logical grouping rules used to present it. The model and classification carry
no DICOM parsing or GUI concerns so they can be shared by every layer without
coupling to Infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

GROUP_ORDER: tuple[str, ...] = (
    "Patient",
    "Study",
    "Series",
    "Image",
    "Acquisition",
    "Image Pixel",
    "Equipment",
    "General",
    "File Meta",
    "Other",
)

# Common keywords mapped to their logical presentation group.
_GROUP_BY_KEYWORD: dict[str, str] = {
    "PatientName": "Patient",
    "PatientID": "Patient",
    "PatientBirthDate": "Patient",
    "PatientBirthTime": "Patient",
    "PatientSex": "Patient",
    "PatientAge": "Patient",
    "PatientWeight": "Patient",
    "PatientSize": "Patient",
    "PatientAddress": "Patient",
    "PatientTelephoneNumbers": "Patient",
    "OtherPatientIDs": "Patient",
    "StudyInstanceUID": "Study",
    "StudyDate": "Study",
    "StudyTime": "Study",
    "StudyDescription": "Study",
    "StudyID": "Study",
    "AccessionNumber": "Study",
    "ReferringPhysicianName": "Study",
    "RequestedProcedureDescription": "Study",
    "ProcedureDescription": "Study",
    "SeriesInstanceUID": "Series",
    "SeriesNumber": "Series",
    "SeriesDate": "Series",
    "SeriesTime": "Series",
    "SeriesDescription": "Series",
    "Modality": "Series",
    "BodyPartExamined": "Series",
    "ProtocolName": "Series",
    "OperatorsName": "Series",
    "PerformingPhysicianName": "Series",
    "PerformedProcedureStepDescription": "Series",
    "SOPInstanceUID": "Image",
    "SOPClassUID": "Image",
    "InstanceNumber": "Image",
    "InstanceCreationDate": "Image",
    "InstanceCreationTime": "Image",
    "ContentDate": "Image",
    "ContentTime": "Image",
    "AcquisitionNumber": "Image",
    "ImageType": "Image",
    "ImagePositionPatient": "Image",
    "ImageOrientationPatient": "Image",
    "SliceLocation": "Image",
    "PositionReferenceIndicator": "Image",
    "KVP": "Acquisition",
    "ExposureTime": "Acquisition",
    "XRayTubeCurrent": "Acquisition",
    "Exposure": "Acquisition",
    "FilterType": "Acquisition",
    "ConvolutionKernel": "Acquisition",
    "SliceThickness": "Acquisition",
    "RepetitionTime": "Acquisition",
    "EchoTime": "Acquisition",
    "InversionTime": "Acquisition",
    "FlipAngle": "Acquisition",
    "NumberOfAverages": "Acquisition",
    "EchoTrainLength": "Acquisition",
    "MagneticFieldStrength": "Acquisition",
    "SpacingBetweenSlices": "Acquisition",
    "SamplesPerPixel": "Image Pixel",
    "PhotometricInterpretation": "Image Pixel",
    "Rows": "Image Pixel",
    "Columns": "Image Pixel",
    "PixelSpacing": "Image Pixel",
    "BitsAllocated": "Image Pixel",
    "BitsStored": "Image Pixel",
    "HighBit": "Image Pixel",
    "PixelRepresentation": "Image Pixel",
    "PlanarConfiguration": "Image Pixel",
    "PixelAspectRatio": "Image Pixel",
    "PixelSpacingCalibrationType": "Image Pixel",
    "RescaleIntercept": "Image Pixel",
    "RescaleSlope": "Image Pixel",
    "RescaleType": "Image Pixel",
    "WindowCenter": "Image Pixel",
    "WindowWidth": "Image Pixel",
    "WindowCenterWidthExplanation": "Image Pixel",
    "SmallestImagePixelValue": "Image Pixel",
    "LargestImagePixelValue": "Image Pixel",
    "Manufacturer": "Equipment",
    "ManufacturerModelName": "Equipment",
    "DeviceSerialNumber": "Equipment",
    "SoftwareVersions": "Equipment",
    "StationName": "Equipment",
    "InstitutionName": "Equipment",
    "InstitutionAddress": "Equipment",
    "ConversionType": "Equipment",
    "MediaStorageSOPClassUID": "File Meta",
    "MediaStorageSOPInstanceUID": "File Meta",
    "TransferSyntaxUID": "File Meta",
    "ImplementationClassUID": "File Meta",
    "ImplementationVersionName": "File Meta",
    "SourceApplicationEntityTitle": "File Meta",
}


def classify_metadata_group(group: int, keyword: str) -> str:
    """Return the logical presentation group for a DICOM tag.

    Keyword matches win because some group numbers mix concerns (for example
    group 0x0008 holds both study- and series-level tags). Private tags and
    tags without a known classification fall back to ``"Other"``.
    """
    known = _GROUP_BY_KEYWORD.get(keyword)
    if known is not None:
        return known
    if group == 0x0002:
        return "File Meta"
    if group == 0x0010:
        return "Patient"
    if group == 0x0018:
        return "Acquisition"
    if group == 0x0019:
        return "Acquisition"
    if group == 0x0020:
        return "Image"
    if group == 0x0028:
        return "Image Pixel"
    if group == 0x0008:
        return "General"
    if group == 0x0032:
        return "Study"
    return "Other"


@dataclass(frozen=True)
class MetadataElement:
    """One DICOM metadata attribute ready for display."""

    tag: str
    keyword: str
    group: str
    name: str
    value: str
    value_representation: str = ""


@dataclass(frozen=True)
class MetadataGroup:
    """A logical group of metadata elements, in display order."""

    name: str
    elements: tuple[MetadataElement, ...] = ()

    @property
    def element_count(self) -> int:
        """Return the number of elements in the group."""
        return len(self.elements)


@dataclass(frozen=True)
class MetadataDocument:
    """The full metadata of one DICOM instance, grouped and ordered."""

    source: Path
    groups: tuple[MetadataGroup, ...] = ()

    @property
    def group_count(self) -> int:
        """Return the number of non-empty groups in the document."""
        return len(self.groups)

    @property
    def element_count(self) -> int:
        """Return the total number of metadata elements in the document."""
        return sum(group.element_count for group in self.groups)

    def has_content(self) -> bool:
        """Return whether any metadata element was extracted."""
        return self.element_count > 0
