from __future__ import annotations

import re
from typing import Iterable, List

import fitz

from models import ExtractedImage, ReportAsset


def extract_report_asset(file_name: str, file_bytes: bytes) -> ReportAsset:
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    page_text: List[str] = []
    images: List[ExtractedImage] = []

    for page_index in range(len(doc)):
        page = doc.load_page(page_index)
        text = page.get_text("text").strip()
        if text:
            header = f"\n\n--- Page {page_index + 1} ---\n"
            page_text.append(header + text)

        page_images = page.get_images(full=True)
        for image_index, image_meta in enumerate(page_images, start=1):
            xref = image_meta[0]
            base_image = doc.extract_image(xref)
            images.append(
                ExtractedImage(
                    page_number=page_index + 1,
                    image_index=image_index,
                    extension=base_image.get("ext", "png"),
                    bytes_data=base_image["image"],
                    caption=f"{file_name} page {page_index + 1} image {image_index}",
                )
            )

    return ReportAsset(name=file_name, text="\n".join(page_text), images=images)


def split_sentences(text: str) -> List[str]:
    normalized = re.sub(r"\s+", " ", text)
    chunks = re.split(r"(?<=[.!?])\s+|\n+", normalized)
    return [chunk.strip(" -") for chunk in chunks if chunk.strip()]


def find_lines_with_keywords(text: str, keywords: Iterable[str]) -> List[str]:
    lines = []
    seen = set()
    for sentence in split_sentences(text):
        lowered = sentence.lower()
        if any(keyword in lowered for keyword in keywords) and sentence not in seen:
            seen.add(sentence)
            lines.append(sentence)
    return lines


def detect_areas(text: str) -> List[str]:
    known_areas = [
        "hall",
        "living room",
        "bedroom",
        "bathroom",
        "kitchen",
        "parking",
        "balcony",
        "ceiling",
        "wall",
        "toilet",
        "lobby",
        "passage",
        "utility",
        "external wall",
    ]
    found = []
    lowered_text = text.lower()
    for area in known_areas:
        if area in lowered_text and area not in found:
            found.append(area.title())
    return found or ["General"]
