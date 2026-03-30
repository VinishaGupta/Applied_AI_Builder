from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import List, Sequence

from openai import OpenAI

from extractor import detect_areas, find_lines_with_keywords
from models import DDRReport, DDRSection, Finding, ReportAsset


INSPECTION_KEYWORDS = [
    "damp",
    "seepage",
    "crack",
    "hollowness",
    "leak",
    "moisture",
    "stain",
    "efflorescence",
]

THERMAL_KEYWORDS = [
    "thermal",
    "hotspot",
    "coldspot",
    "temperature",
    "anomaly",
    "heat",
    "cold",
    "infrared",
]


def build_ddr_report(inspection: ReportAsset, thermal: ReportAsset) -> DDRReport:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return _build_with_openai(api_key, inspection, thermal)
        except Exception:
            pass

    return _build_with_heuristics(inspection, thermal)


def _build_with_heuristics(inspection: ReportAsset, thermal: ReportAsset) -> DDRReport:
    inspection_lines = find_lines_with_keywords(inspection.text, INSPECTION_KEYWORDS)
    thermal_lines = find_lines_with_keywords(thermal.text, THERMAL_KEYWORDS + INSPECTION_KEYWORDS)

    area_map: dict[str, list[str]] = defaultdict(list)
    all_areas = detect_areas(inspection.text + "\n" + thermal.text)

    for sentence in inspection_lines + thermal_lines:
        assigned = False
        lowered = sentence.lower()
        for area in all_areas:
            if area.lower() in lowered:
                area_map[area].append(sentence)
                assigned = True
        if not assigned:
            area_map["General"].append(sentence)

    findings = [_compose_finding(area, sentences) for area, sentences in area_map.items()]
    sections = _build_sections(findings, inspection, thermal)

    summary_points = [f"{finding.area}: {finding.issue}" for finding in findings[:5]]
    property_issue_summary = "; ".join(summary_points) if summary_points else "No critical issues detected from the provided documents."

    probable_root_cause = _combine_root_causes(findings)
    severity_assessment = _summarize_severity(findings)
    recommended_actions = _recommended_actions(findings)
    missing_info = _collect_missing_info(findings, inspection, thermal)
    additional_notes = [
        "This draft was generated from the uploaded inspection and thermal reports.",
        "A final engineer review is recommended before client delivery.",
    ]

    return DDRReport(
        property_issue_summary=property_issue_summary,
        area_wise_observations=sections,
        probable_root_cause=probable_root_cause,
        severity_assessment=severity_assessment,
        recommended_actions=recommended_actions,
        additional_notes=additional_notes,
        missing_or_unclear_information=missing_info,
    )


def _compose_finding(area: str, sentences: Sequence[str]) -> Finding:
    issue = sentences[0] if sentences else f"Observation recorded for {area}."
    severity = "High" if any(word in issue.lower() for word in ["seepage", "leak", "crack"]) else "Medium"
    root_cause = None
    if any("bathroom" in sentence.lower() for sentence in sentences):
        root_cause = "Moisture migration from adjacent wet area."
    elif any("external" in sentence.lower() or "wall" in sentence.lower() for sentence in sentences):
        root_cause = "Water ingress through exposed wall surfaces or joints."
    elif any("temperature" in sentence.lower() or "coldspot" in sentence.lower() for sentence in sentences):
        root_cause = "Thermal anomaly indicates possible hidden moisture or insulation failure."

    missing = []
    if not any(char.isdigit() for sentence in sentences for char in sentence):
        missing.append("Exact measurement or temperature reading not clearly identified.")

    return Finding(
        area=area,
        issue=issue,
        evidence=list(dict.fromkeys(sentences))[:5],
        probable_root_cause=root_cause or "Requires expert validation based on site conditions.",
        severity=severity,
        source_documents=["Inspection Report", "Thermal Report"],
        missing_information=missing,
    )


def _build_sections(findings: Sequence[Finding], inspection: ReportAsset, thermal: ReportAsset) -> List[DDRSection]:
    sections: List[DDRSection] = []
    thermal_images = list(thermal.images)
    inspection_images = list(inspection.images)

    for index, finding in enumerate(findings, start=1):
        images = []
        if index - 1 < len(inspection_images):
            images.append(inspection_images[index - 1])
        if index - 1 < len(thermal_images):
            images.append(thermal_images[index - 1])

        evidence_lines = "\n".join(f"- {line}" for line in finding.evidence) or "- Image Not Available"
        body = (
            f"Issue: {finding.issue}\n\n"
            f"Evidence:\n{evidence_lines}\n\n"
            f"Probable Root Cause: {finding.probable_root_cause}\n"
            f"Severity: {finding.severity}"
        )
        sections.append(DDRSection(title=finding.area, body=body, images=images))

    return sections


def _combine_root_causes(findings: Sequence[Finding]) -> str:
    causes = list(dict.fromkeys(finding.probable_root_cause for finding in findings if finding.probable_root_cause))
    return " ".join(causes[:3]) if causes else "No probable root cause identified."


def _summarize_severity(findings: Sequence[Finding]) -> str:
    high_count = sum(1 for finding in findings if finding.severity == "High")
    if high_count >= 2:
        return "Overall severity is High because multiple areas suggest active seepage, leakage, or structural deterioration."
    if high_count == 1:
        return "Overall severity is Medium to High because at least one area suggests active deterioration and should be prioritized."
    return "Overall severity is Medium based on the available observations and should be verified during engineering review."


def _recommended_actions(findings: Sequence[Finding]) -> List[str]:
    actions = [
        "Inspect all highlighted moisture-prone areas with a site engineer before repair execution.",
        "Seal leakage entry points and repair defective joints, grout, or waterproofing layers.",
        "Re-scan repaired zones using thermal imaging to confirm anomaly reduction.",
    ]
    if any("crack" in finding.issue.lower() for finding in findings):
        actions.append("Assess wall cracks for structural movement and repair using the appropriate crack treatment system.")
    return actions


def _collect_missing_info(findings: Sequence[Finding], inspection: ReportAsset, thermal: ReportAsset) -> List[str]:
    missing = []
    for finding in findings:
        missing.extend(finding.missing_information)
    if not inspection.images:
        missing.append("Inspection report images were not extracted.")
    if not thermal.images:
        missing.append("Thermal report images were not extracted.")
    return list(dict.fromkeys(missing)) or ["No major missing information detected."]


def _build_with_openai(api_key: str, inspection: ReportAsset, thermal: ReportAsset) -> DDRReport:
    client = OpenAI(api_key=api_key)
    prompt = f"""
You are generating a client-ready Detailed Diagnostic Report (DDR) from two source documents.

Inspection report text:
{inspection.text[:18000]}

Thermal report text:
{thermal.text[:18000]}

Return valid JSON with this exact schema:
{{
  "property_issue_summary": "string",
  "area_wise_observations": [
    {{
      "title": "string",
      "body": "string"
    }}
  ],
  "probable_root_cause": "string",
  "severity_assessment": "string",
  "recommended_actions": ["string"],
  "additional_notes": ["string"],
  "missing_or_unclear_information": ["string"]
}}

Instructions:
- Merge duplicate findings from both documents.
- Mention conflicts or unclear information explicitly.
- Write concise professional language.
- Do not invent measurements that are not present.
"""
    response = client.responses.create(
        model="gpt-4.1-mini",
        input=prompt,
    )
    raw_text = response.output_text
    payload = json.loads(raw_text)
    sections = [DDRSection(**section) for section in payload["area_wise_observations"]]
    payload["area_wise_observations"] = sections
    return DDRReport(**payload)
