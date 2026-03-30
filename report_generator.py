from __future__ import annotations

import json
import os
import re
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


def build_ddr_report(
    inspection: ReportAsset,
    thermal: ReportAsset,
    reference_ddr: ReportAsset | None = None,
) -> DDRReport:
    api_key = os.getenv("OPENAI_API_KEY")
    if api_key:
        try:
            return _build_with_openai(api_key, inspection, thermal, reference_ddr)
        except Exception:
            pass

    return _build_with_heuristics(inspection, thermal)


def _build_with_heuristics(inspection: ReportAsset, thermal: ReportAsset) -> DDRReport:
    findings = _parse_structured_findings(inspection.text, thermal.text)
    if not findings:
        findings = _fallback_findings(inspection.text, thermal.text)

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


def _parse_structured_findings(inspection_text: str, thermal_text: str) -> List[Finding]:
    readings = _parse_thermal_readings(thermal_text)
    findings: List[Finding] = []
    pattern = re.compile(
        r"Impacted Area\s+\d+.*?Negative side Description\s+(?P<negative>.*?)\s+Negative side photographs.*?"
        r"Positive side Description\s+(?P<positive>.*?)\s+Positive side photographs",
        flags=re.IGNORECASE | re.DOTALL,
    )

    for index, match in enumerate(pattern.finditer(inspection_text)):
        negative = _clean_segment(match.group("negative"))
        positive = _clean_segment(match.group("positive"))
        if not negative:
            continue

        area = _infer_area_name(negative, positive, fallback=f"Area {index + 1}")
        thermal_summary = readings[index] if index < len(readings) else None
        evidence = [f"Inspection observation: {negative}"]
        if positive:
            evidence.append(f"Likely source side observation: {positive}")
        if thermal_summary:
            evidence.append(thermal_summary)

        issue = negative.rstrip(".")
        root_cause = _infer_root_cause(negative, positive, thermal_summary)
        severity = _infer_severity(issue, positive, thermal_summary)
        missing = []
        if not thermal_summary:
            missing.append("Mapped thermal reading for this area was not clearly identified.")

        findings.append(
            Finding(
                area=area,
                issue=issue,
                evidence=evidence,
                probable_root_cause=root_cause,
                severity=severity,
                source_documents=["Inspection Report", "Thermal Report"],
                missing_information=missing,
            )
        )

    return findings


def _fallback_findings(inspection_text: str, thermal_text: str) -> List[Finding]:
    inspection_lines = find_lines_with_keywords(inspection_text, INSPECTION_KEYWORDS)
    thermal_lines = find_lines_with_keywords(thermal_text, THERMAL_KEYWORDS + INSPECTION_KEYWORDS)

    area_map: dict[str, list[str]] = defaultdict(list)
    all_areas = detect_areas(inspection_text + "\n" + thermal_text)

    for sentence in inspection_lines + thermal_lines:
        assigned = False
        lowered = sentence.lower()
        for area in all_areas:
            if area.lower() in lowered:
                area_map[area].append(sentence)
                assigned = True
        if not assigned:
            area_map["General"].append(sentence)

    return [_compose_finding(area, sentences) for area, sentences in area_map.items()]


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
    thermal_images = [image for image in thermal.images if image.image_index == 0]
    inspection_images = [image for image in inspection.images if image.image_index == 0]

    for index, finding in enumerate(findings, start=1):
        images = []
        if inspection_images:
            images.append(inspection_images[min(index - 1, len(inspection_images) - 1)])
        if thermal_images:
            images.append(thermal_images[min(index - 1, len(thermal_images) - 1)])

        recommended_action = _action_for_finding(finding)
        evidence_lines = "\n".join(f"- {line}" for line in finding.evidence) or "- Image Not Available"
        body = (
            f"Observation: {finding.issue}\n"
            f"Thermal / Visual Evidence:\n{evidence_lines}\n"
            f"Probable Root Cause: {finding.probable_root_cause}\n"
            f"Severity: {finding.severity}\n"
            f"Recommended Action: {recommended_action}"
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
    actions = list(dict.fromkeys(_action_for_finding(finding) for finding in findings))
    actions.append("Re-scan repaired zones using thermal imaging to confirm anomaly reduction.")
    return actions[:6]


def _collect_missing_info(findings: Sequence[Finding], inspection: ReportAsset, thermal: ReportAsset) -> List[str]:
    missing = []
    for finding in findings:
        missing.extend(finding.missing_information)
    if not inspection.images:
        missing.append("Inspection report images were not extracted.")
    if not thermal.images:
        missing.append("Thermal report images were not extracted.")
    return list(dict.fromkeys(missing)) or ["No major missing information detected."]


def _build_with_openai(
    api_key: str,
    inspection: ReportAsset,
    thermal: ReportAsset,
    reference_ddr: ReportAsset | None = None,
) -> DDRReport:
    client = OpenAI(api_key=api_key)
    reference_text = reference_ddr.text[:12000] if reference_ddr else "No reference DDR provided."
    prompt = f"""
You are generating a client-ready Detailed Diagnostic Report (DDR) from two source documents.

Inspection report text:
{inspection.text[:18000]}

Thermal report text:
{thermal.text[:18000]}

Reference DDR style and structure:
{reference_text}

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
- Follow the tone and sectioning style of the reference DDR when useful.
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


def _parse_thermal_readings(thermal_text: str) -> List[str]:
    readings: List[str] = []
    pattern = re.compile(
        r"Hotspot\s*:\s*(?P<hot>[0-9]+(?:\.[0-9]+)?)\s*°C.*?Coldspot\s*:\s*(?P<cold>[0-9]+(?:\.[0-9]+)?)\s*°C",
        flags=re.IGNORECASE | re.DOTALL,
    )
    for index, match in enumerate(pattern.finditer(thermal_text), start=1):
        readings.append(
            f"Thermal scan {index}: hotspot {match.group('hot')}°C and coldspot {match.group('cold')}°C."
        )
    return readings


def _clean_segment(value: str) -> str:
    cleaned = re.sub(r"\s+", " ", value).strip(" -")
    cleaned = re.sub(r"(Photo\s+\d+)+", "", cleaned, flags=re.IGNORECASE).strip(" -")
    return cleaned


def _infer_area_name(negative: str, positive: str, fallback: str) -> str:
    area_candidates = [
        "Master Bedroom",
        "Common Bathroom",
        "Parking Area",
        "Bedroom",
        "Kitchen",
        "Hall",
        "Bathroom",
        "External Wall",
        "Ceiling",
    ]
    combined = f"{negative} {positive}".lower()
    for candidate in area_candidates:
        if candidate.lower() in combined:
            return candidate
    return fallback


def _infer_root_cause(negative: str, positive: str, thermal_summary: str | None) -> str:
    combined = f"{negative} {positive}".lower()
    if "tile hollowness" in combined:
        return "Water migration is likely linked to tile hollowness and failed grout or bedding on the positive side."
    if "plumbing issue" in combined or "joint open" in combined or "leakage" in combined:
        return "Leakage is likely associated with plumbing joints, open tile joints, or outlet connections."
    if "external wall crack" in combined or "duct issue" in combined:
        return "Moisture ingress is likely occurring through external wall cracks, duct penetrations, or failed sealant lines."
    if "ceiling" in combined:
        return "Upper-floor wet-area leakage or outlet seepage is likely affecting the ceiling zone."
    if thermal_summary:
        return "Thermal variation supports the presence of moisture accumulation behind the finished surface."
    return "Requires expert validation based on the observed site conditions."


def _infer_severity(issue: str, positive: str, thermal_summary: str | None) -> str:
    combined = f"{issue} {positive} {thermal_summary or ''}".lower()
    if any(token in combined for token in ["seepage", "leak", "crack", "ceiling"]):
        return "High"
    if "dampness" in combined or "coldspot" in combined:
        return "Medium"
    return "Low"


def _action_for_finding(finding: Finding) -> str:
    combined = f"{finding.issue} {finding.probable_root_cause}".lower()
    if "tile hollowness" in combined or "grout" in combined:
        return "Carry out tile regrouting, replace hollow tiles where required, and restore waterproofing continuity."
    if "plumbing" in combined or "joint" in combined or "outlet" in combined:
        return "Inspect and rectify plumbing joints and outlet interfaces, then perform localized waterproofing repairs."
    if "external wall" in combined or "duct" in combined or "crack" in combined:
        return "Seal external cracks and duct penetrations, and repair the wall protection system after substrate treatment."
    if "ceiling" in combined:
        return "Trace the upper source, repair leakage paths, and allow the area to dry before re-finishing the ceiling."
    return "Verify the source on site and execute targeted waterproofing and re-finishing repairs."
