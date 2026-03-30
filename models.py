from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class ExtractedImage(BaseModel):
    page_number: int
    image_index: int
    extension: str
    bytes_data: bytes
    caption: Optional[str] = None


class ReportAsset(BaseModel):
    name: str
    text: str
    images: List[ExtractedImage] = Field(default_factory=list)


class Finding(BaseModel):
    area: str
    issue: str
    evidence: List[str] = Field(default_factory=list)
    probable_root_cause: Optional[str] = None
    severity: str = "Medium"
    severity_reasoning: Optional[str] = None
    source_documents: List[str] = Field(default_factory=list)
    conflicts: List[str] = Field(default_factory=list)
    missing_information: List[str] = Field(default_factory=list)


class DDRSection(BaseModel):
    title: str
    body: str
    images: List[ExtractedImage] = Field(default_factory=list)


class DDRReport(BaseModel):
    property_issue_summary: str
    area_wise_observations: List[DDRSection]
    probable_root_cause: str
    severity_assessment: str
    recommended_actions: List[str]
    additional_notes: List[str]
    missing_or_unclear_information: List[str]
