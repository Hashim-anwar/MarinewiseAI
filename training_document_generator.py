from __future__ import annotations

import argparse
import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

import fitz
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT
from docx.shared import Inches, Pt
from pptx import Presentation
from pptx.util import Inches as PptInches, Pt as PptPt
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image as RLImage,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


OUTPUT_DIR = Path("training_package")
IMAGE_DIR = OUTPUT_DIR / "oem_images"

REQUIRED_SECTIONS = [
    "TRAINING OBJECTIVE",
    "ENGINE INTRODUCTION",
    "SYSTEM OVERVIEW",
    "COMPONENT IDENTIFICATION",
    "TOOLS REQUIRED",
    "SAFETY PRECAUTIONS",
    "REMOVAL PROCEDURE",
    "INSPECTION",
    "INSTALLATION",
    "TORQUE AND SPECIFICATIONS",
    "COMMON FAULTS",
    "TROUBLESHOOTING",
    "PRACTICAL EXERCISE",
    "KNOWLEDGE CHECK",
    "FINAL ASSESSMENT",
    "OEM REFERENCES",
    "EVIDENCE STATUS",
]


VISUAL_KEYWORDS = {
    "SYSTEM OVERVIEW": [
        "fuel",
        "system",
        "circuit",
        "diagram",
        "schematic",
        "flow",
    ],
    "COMPONENT IDENTIFICATION": [
        "injector",
        "fuel",
        "component",
        "assembly",
        "cylinder",
        "nozzle",
    ],
    "REMOVAL PROCEDURE": [
        "remove",
        "removal",
        "injector",
        "disassembly",
        "dismantling",
    ],
    "INSPECTION": [
        "inspection",
        "check",
        "measure",
        "wear",
        "injector",
        "nozzle",
    ],
    "INSTALLATION": [
        "install",
        "installation",
        "assembly",
        "injector",
        "mounting",
    ],
    "TROUBLESHOOTING": [
        "fault",
        "troubleshooting",
        "alarm",
        "fuel",
        "injector",
        "failure",
    ],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--answer",
        default="training_answer.json",
    )

    parser.add_argument(
        "--workflow",
        default="training_workflow.json",
    )

    parser.add_argument(
        "--manual-dir",
        default="selected_manuals",
    )

    parser.add_argument(
        "--output-dir",
        default="training_package",
    )

    return parser.parse_args()


def load_json(path: str | Path) -> dict[str, Any]:
    file = Path(path)

    if not file.exists():
        raise FileNotFoundError(
            f"Required file not found: {file}"
        )

    return json.loads(
        file.read_text(
            encoding="utf-8"
        )
    )


def clean(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def normalize_filename(value: str) -> str:
    value = re.sub(
        r"[^\w\-. ]+",
        "_",
        value,
    )

    return value[:150]


def split_sections(
    content: str,
) -> dict[str, str]:

    lines = content.splitlines()

    positions = []

    normalized_required = {
        section.upper(): section
        for section in REQUIRED_SECTIONS
    }

    for index, line in enumerate(lines):
        normalized = (
            line.strip()
            .upper()
            .replace(":", "")
        )

        if normalized in normalized_required:
            positions.append(
                (
                    index,
                    normalized_required[normalized],
                )
            )

    sections: dict[str, str] = {}

    for position, (
        start,
        name,
    ) in enumerate(positions):

        end = (
            positions[position + 1][0]
            if position + 1 < len(positions)
            else len(lines)
        )

        body = "\n".join(
            lines[start + 1:end]
        ).strip()

        sections[name] = body

    return sections


def find_manual_files(
    manual_dir: Path,
) -> list[Path]:

    if not manual_dir.exists():
        return []

    files = []

    for pattern in (
        "*.pdf",
        "*.PDF",
    ):
        files.extend(
            manual_dir.rglob(pattern)
        )

    return sorted(
        set(files)
    )


def get_manual_metadata(
    workflow: dict[str, Any],
) -> list[dict[str, Any]]:

    manual_selection = workflow.get(
        "manual_selection",
        {},
    )

    manuals = manual_selection.get(
        "selected_manuals",
        [],
    )

    if not isinstance(manuals, list):
        return []

    return [
        item
        for item in manuals
        if isinstance(item, dict)
    ]


def manual_matches(
    pdf_path: Path,
    metadata: list[dict[str, Any]],
) -> dict[str, Any] | None:

    name = pdf_path.name.lower()

    for item in metadata:

        possible_names = [
            item.get("source_file"),
            item.get("file_name"),
            item.get("name"),
            item.get("filename"),
        ]

        for possible in possible_names:
            if possible and Path(
                str(possible)
            ).name.lower() == name:
                return item

    return None


def search_oem_pages(
    pdf_path: Path,
    keywords: list[str],
    max_pages: int = 3,
) -> list[dict[str, Any]]:

    matches = []

    try:
        document = fitz.open(
            pdf_path
        )
    except Exception:
        return matches

    try:
        for page_number in range(
            len(document)
        ):

            page = document[
                page_number
            ]

            text = page.get_text(
                "text"
            )

            lower = text.lower()

            score = 0
            matched_terms = []

            for keyword in keywords:

                if keyword.lower() in lower:
                    score += 1
                    matched_terms.append(
                        keyword
                    )

            if score > 0:
                matches.append(
                    {
                        "pdf": str(pdf_path),
                        "page": page_number + 1,
                        "score": score,
                        "matched_terms": matched_terms,
                        "text_preview": re.sub(
                            r"\s+",
                            " ",
                            text,
                        )[:700],
                    }
                )

    finally:
        document.close()

    matches.sort(
        key=lambda item: (
            -item["score"],
            item["page"],
        )
    )

    return matches[:max_pages]


def render_page(
    pdf_path: Path,
    page_number: int,
    output_path: Path,
) -> bool:

    try:
        document = fitz.open(
            pdf_path
        )

        page = document[
            page_number - 1
        ]

        matrix = fitz.Matrix(
            1.5,
            1.5,
        )

        pixmap = page.get_pixmap(
            matrix=matrix,
            alpha=False,
        )

        pixmap.save(
            str(output_path)
        )

        document.close()

        return True

    except Exception as exc:
        print(
            f"WARNING - Could not render "
            f"{pdf_path.name} page {page_number}: {exc}"
        )

        return False


def collect_visuals(
    sections: dict[str, str],
    manual_files: list[Path],
    metadata: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:

    visuals: dict[
        str,
        list[dict[str, Any]]
    ] = {}

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    for section, keywords in VISUAL_KEYWORDS.items():

        if section not in sections:
            continue

        candidates = []

        for pdf in manual_files:

            matches = search_oem_pages(
                pdf,
                keywords,
                max_pages=2,
            )

            for match in matches:

                match["metadata"] = (
                    manual_matches(
                        pdf,
                        metadata,
                    )
                    or {}
                )

                candidates.append(
                    match
                )

        candidates.sort(
            key=lambda item: (
                -item["score"],
                item["page"],
            )
        )

        selected = []

        seen = set()

        for candidate in candidates:

            key = (
                Path(
                    candidate["pdf"]
                ).name,
                candidate["page"],
            )

            if key in seen:
                continue

            seen.add(key)

            image_name = normalize_filename(
                f"{section}_{Path(candidate['pdf']).stem}"
                f"_page_{candidate['page']}.png"
            )

            image_path = (
                IMAGE_DIR / image_name
            )

            if render_page(
                Path(candidate["pdf"]),
                candidate["page"],
                image_path,
            ):

                candidate[
                    "image_path"
                ] = str(image_path)

                candidate[
                    "source_file"
                ] = Path(
                    candidate["pdf"]
                ).name

                candidate[
                    "citation"
                ] = (
                    f"[OEM: "
                    f"{Path(candidate['pdf']).name}, "
                    f"Page {candidate['page']}]"
                )

                selected.append(
                    candidate
                )

            if len(selected) >= 2:
                break

        if selected:
            visuals[section] = selected

    return visuals


def set_doc_defaults(
    document: Document,
) -> None:

    section = document.sections[0]

    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    section.left_margin = Inches(0.8)
    section.right_margin = Inches(0.8)

    styles = document.styles

    normal = styles["Normal"]

    normal.font.name = "Times New Roman"
    normal.font.size = Pt(11)

    for style_name in [
        "Title",
        "Heading 1",
        "Heading 2",
    ]:

        style = styles[style_name]

        style.font.name = "Times New Roman"

    styles["Heading 1"].font.size = Pt(16)
    styles["Heading 2"].font.size = Pt(13)


def add_doc_paragraph(
    document: Document,
    text: str,
) -> None:

    if not text:
        return

    paragraphs = text.split("\n")

    for line in paragraphs:

        line = line.strip()

        if not line:
            continue

        paragraph = document.add_paragraph()

        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

        run = paragraph.add_run(
            line
        )

        run.font.name = "Times New Roman"
        run.font.size = Pt(11)


def add_doc_visual(
    document: Document,
    visual: dict[str, Any],
) -> None:

    image_path = Path(
        visual["image_path"]
    )

    if not image_path.exists():
        return

    paragraph = document.add_paragraph()

    paragraph.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    run = paragraph.add_run()

    run.add_picture(
        str(image_path),
        width=Inches(6.2),
    )

    caption = document.add_paragraph()

    caption.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    caption_run = caption.add_run(
        "OEM Training Visual — "
        f"{visual['source_file']}, "
        f"Page {visual['page']}"
    )

    caption_run.bold = True
    caption_run.font.name = "Times New Roman"
    caption_run.font.size = Pt(9)


def build_docx(
    sections: dict[str, str],
    visuals: dict[str, list[dict[str, Any]]],
    workflow: dict[str, Any],
    output_path: Path,
) -> None:

    document = Document()

    set_doc_defaults(
        document
    )

    input_data = workflow.get(
        "input",
        {},
    )

    manufacturer = clean(
        input_data.get(
            "manufacturer"
        )
    )

    engine = clean(
        input_data.get(
            "engine_model"
        )
    )

    topic = clean(
        input_data.get(
            "topic"
        )
    )

    duration = clean(
        input_data.get(
            "duration"
        )
    )

    vessel = clean(
        input_data.get(
            "vessel"
        )
    )

    title = document.add_paragraph()

    title.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    run = title.add_run(
        "MARINEWISE AI"
    )

    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(24)

    subtitle = document.add_paragraph()

    subtitle.alignment = (
        WD_ALIGN_PARAGRAPH.CENTER
    )

    run = subtitle.add_run(
        "MARINE ENGINE TECHNICIAN TRAINING MANUAL"
    )

    run.bold = True
    run.font.name = "Times New Roman"
    run.font.size = Pt(18)

    document.add_paragraph()

    info = document.add_table(
        rows=5,
        cols=2,
    )

    info.style = "Table Grid"

    values = [
        ("Manufacturer", manufacturer),
        ("Engine Model", engine),
        ("Training Topic", topic),
        ("Duration", duration),
        ("Vessel", vessel),
    ]

    for row, (
        label,
        value,
    ) in zip(
        info.rows,
        values,
    ):

        row.cells[0].text = label
        row.cells[1].text = value

        for cell in row.cells:
            cell.vertical_alignment = (
                WD_CELL_VERTICAL_ALIGNMENT.CENTER
            )

            for paragraph in cell.paragraphs:
                for run in paragraph.runs:
                    run.font.name = "Times New Roman"
                    run.font.size = Pt(11)

    document.add_page_break()

    for section in REQUIRED_SECTIONS:

        heading = document.add_heading(
            section,
            level=1,
        )

        heading.runs[0].font.name = (
            "Times New Roman"
        )

        content = sections.get(
            section,
            "",
        )

        add_doc_paragraph(
            document,
            content,
        )

        for visual in visuals.get(
            section,
            [],
        ):

            add_doc_visual(
                document,
                visual,
            )

        document.add_paragraph()

    document.save(
        output_path
    )


def make_pdf_styles():
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        "MarineTitle",
        parent=styles["Title"],
        fontName="Times-Roman",
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        spaceAfter=12,
    )

    heading_style = ParagraphStyle(
        "MarineHeading",
        parent=styles["Heading1"],
        fontName="Times-Bold",
        fontSize=15,
        leading=18,
        spaceBefore=10,
        spaceAfter=8,
    )

    body_style = ParagraphStyle(
        "MarineBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=11,
        leading=15,
        alignment=TA_JUSTIFY,
        spaceAfter=7,
    )

    caption_style = ParagraphStyle(
        "MarineCaption",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
    )

    return (
        title_style,
        heading_style,
        body_style,
        caption_style,
    )


def build_pdf(
    sections: dict[str, str],
    visuals: dict[str, list[dict[str, Any]]],
    workflow: dict[str, Any],
    output_path: Path,
) -> None:

    (
        title_style,
        heading_style,
        body_style,
        caption_style,
    ) = make_pdf_styles()

    document = SimpleDocTemplate(
        str(output_path),
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
    )

    input_data = workflow.get(
        "input",
        {},
    )

    manufacturer = clean(
        input_data.get("manufacturer")
    )

    engine = clean(
        input_data.get("engine_model")
    )

    topic = clean(
        input_data.get("topic")
    )

    duration = clean(
        input_data.get("duration")
    )

    vessel = clean(
        input_data.get("vessel")
    )

    story = []

    story.append(
        Paragraph(
            "MARINEWISE AI",
            title_style,
        )
    )

    story.append(
        Paragraph(
            "MARINE ENGINE TECHNICIAN TRAINING MANUAL",
            heading_style,
        )
    )

    table_data = [
        ["Manufacturer", manufacturer],
        ["Engine Model", engine],
        ["Training Topic", topic],
        ["Duration", duration],
        ["Vessel", vessel],
    ]

    table = Table(
        table_data,
        colWidths=[
            45 * mm,
            120 * mm,
        ],
    )

    table.setStyle(
        TableStyle(
            [
                (
                    "GRID",
                    (0, 0),
                    (-1, -1),
                    0.5,
                    "black",
                ),
                (
                    "FONTNAME",
                    (0, 0),
                    (-1, -1),
                    "Times-Roman",
                ),
                (
                    "FONTSIZE",
                    (0, 0),
                    (-1, -1),
                    10,
                ),
                (
                    "VALIGN",
                    (0, 0),
                    (-1, -1),
                    "MIDDLE",
                ),
            ]
        )
    )

    story.append(
        Spacer(
            1,
            10,
        )
    )

    story.append(table)
    story.append(PageBreak())

    for section in REQUIRED_SECTIONS:

        story.append(
            Paragraph(
                section,
                heading_style,
            )
        )

        content = sections.get(
            section,
            "",
        )

        for paragraph in content.split(
            "\n"
        ):

            paragraph = paragraph.strip()

            if not paragraph:
                continue

            safe = (
                paragraph
                .replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
            )

            story.append(
                Paragraph(
                    safe,
                    body_style,
                )
            )

        for visual in visuals.get(
            section,
            [],
        ):

            image_path = Path(
                visual["image_path"]
            )

            if not image_path.exists():
                continue

            story.append(
                RLImage(
                    str(image_path),
                    width=165 * mm,
                    height=115 * mm,
                    kind="proportional",
                )
            )

            story.append(
                Paragraph(
                    "OEM Training Visual — "
                    f"{visual['source_file']}, "
                    f"Page {visual['page']}",
                    caption_style,
                )
            )

            story.append(
                Spacer(
                    1,
                    6,
                )
            )

    document.build(
        story
    )


def add_ppt_text(
    slide,
    title: str,
    content: str,
) -> None:

    title_box = slide.shapes.add_textbox(
        PptInches(0.5),
        PptInches(0.3),
        PptInches(12),
        PptInches(0.7),
    )

    title_frame = title_box.text_frame

    title_frame.text = title

    for paragraph in title_frame.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Times New Roman"
            run.font.size = PptPt(24)
            run.font.bold = True

    body_box = slide.shapes.add_textbox(
        PptInches(0.7),
        PptInches(1.2),
        PptInches(11.8),
        PptInches(5.6),
    )

    frame = body_box.text_frame

    frame.word_wrap = True

    frame.text = content[:4500]

    for paragraph in frame.paragraphs:
        for run in paragraph.runs:
            run.font.name = "Times New Roman"
            run.font.size = PptPt(14)


def build_pptx(
    sections: dict[str, str],
    visuals: dict[str, list[dict[str, Any]]],
    workflow: dict[str, Any],
    output_path: Path,
) -> None:

    presentation = Presentation()

    presentation.slide_width = PptInches(13.333)
    presentation.slide_height = PptInches(7.5)

    input_data = workflow.get(
        "input",
        {},
    )

    title_slide = presentation.slides[0]

    title_slide.shapes.title.text = (
        "MARINEWISE AI"
    )

    subtitle = title_slide.placeholders[1]

    subtitle.text = (
        "Marine Engine Technician Training\n"
        f"{clean(input_data.get('engine_model'))}\n"
        f"{clean(input_data.get('topic'))}"
    )

    for section in REQUIRED_SECTIONS:

        content = sections.get(
            section,
            "",
        )

        section_visuals = visuals.get(
            section,
            [],
        )

        slide = presentation.slides.add_slide(
            presentation.slide_layouts[6]
        )

        if section_visuals:

            visual = section_visuals[0]

            image_path = Path(
                visual["image_path"]
            )

            if image_path.exists():

                slide.shapes.add_picture(
                    str(image_path),
                    PptInches(7.0),
                    PptInches(1.2),
                    width=PptInches(5.7),
                    height=PptInches(5.3),
                )

                text_content = (
                    content[:2200]
                    + "\n\n"
                    + visual["citation"]
                )

                add_ppt_text(
                    slide,
                    section,
                    text_content,
                )

                continue

        add_ppt_text(
            slide,
            section,
            content,
        )

    presentation.save(
        output_path
    )


def main() -> None:

    args = parse_args()

    answer = load_json(
        args.answer
    )

    workflow = load_json(
        args.workflow
    )

    content = answer.get(
        "training_content",
        "",
    )

    if not content:
        raise ValueError(
            "training_answer.json contains no training_content."
        )

    sections = split_sections(
        content
    )

    missing = [
        section
        for section in REQUIRED_SECTIONS
        if section not in sections
    ]

    if missing:
        raise ValueError(
            "Missing required sections: "
            + ", ".join(missing)
        )

    output_dir = Path(
        args.output_dir
    )

    if output_dir.exists():
        shutil.rmtree(
            output_dir
        )

    output_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    IMAGE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    manual_dir = Path(
        args.manual_dir
    )

    manual_files = find_manual_files(
        manual_dir
    )

    metadata = get_manual_metadata(
        workflow
    )

    print("=" * 70)
    print("MARINEWISE AI - STEP 32A")
    print("VISUAL TRAINING DOCUMENT GENERATOR")
    print("=" * 70)

    print(
        f"Manual PDFs found : {len(manual_files)}"
    )

    if not manual_files:
        raise RuntimeError(
            "No selected OEM PDF manuals were found."
        )

    visuals = collect_visuals(
        sections,
        manual_files,
        metadata,
    )

    visual_count = sum(
        len(items)
        for items in visuals.values()
    )

    print(
        f"OEM visual pages   : {visual_count}"
    )

    docx_path = (
        output_dir
        / "MarineWise_Training_Manual.docx"
    )

    pdf_path = (
        output_dir
        / "MarineWise_Training_Manual.pdf"
    )

    pptx_path = (
        output_dir
        / "MarineWise_Training_Presentation.pptx"
    )

    build_docx(
        sections,
        visuals,
        workflow,
        docx_path,
    )

    print(
        f"DOCX created       : {docx_path}"
    )

    build_pdf(
        sections,
        visuals,
        workflow,
        pdf_path,
    )

    print(
        f"PDF created        : {pdf_path}"
    )

    build_pptx(
        sections,
        visuals,
        workflow,
        pptx_path,
    )

    print(
        f"PPTX created       : {pptx_path}"
    )

    manifest = {
        "step": 32,
        "stage": "visual_training_document_generator",
        "status": "SUCCESS",
        "source_answer": args.answer,
        "source_workflow": args.workflow,
        "manual_count": len(manual_files),
        "visual_count": visual_count,
        "visual_sections": list(
            visuals.keys()
        ),
        "outputs": [
            str(docx_path),
            str(pdf_path),
            str(pptx_path),
        ],
        "visual_policy": {
            "oem_pages_prioritized": True,
            "technical_visuals_from_oem_manuals": True,
            "source_page_captions": True,
            "fake_oem_figures_blocked": True,
        },
    }

    manifest_path = (
        output_dir
        / "training_package_manifest.json"
    )

    manifest_path.write_text(
        json.dumps(
            manifest,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print("=" * 70)
    print("STEP 32A GENERATION COMPLETE")
    print("=" * 70)

    print(
        f"Manual PDFs       : {len(manual_files)}"
    )

    print(
        f"OEM visual pages  : {visual_count}"
    )

    print(
        f"DOCX              : {docx_path.name}"
    )

    print(
        f"PDF               : {pdf_path.name}"
    )

    print(
        f"PPTX              : {pptx_path.name}"
    )

    print()
    print("STEP 32A: SUCCESS")
    print("GREEN")


if __name__ == "__main__":
    main()
