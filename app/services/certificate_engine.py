"""
Certificate PDF generation engine built on ReportLab.

There are two rendering paths:

1. **Built-in layout** (no active CertificateTemplate) — a clean
   vector-drawn certificate per the V1.1 spec: branding, student details,
   course details, duration, grade, and the authorized signature image.
   No QR code, no visible ID strings.

2. **Custom background** (an active CertificateTemplate with an uploaded
   image) — calibrated against Pixelwind's branded template. As of the
   June 24 template revision, the background no longer has the "ID:"
   line, the "INTERNSHIP ID:" line, or a QR placeholder baked in — only
   the ribbon, "presented to" line, and signature/seal artwork are part
   of the picture now. So unlike the previous revision, we draw the ID
   label + underline + value, and the Internship ID label + underline +
   value (in red, matching the reference), ourselves — not just the
   values. We still never redraw the ribbon, presented-to line, or
   signature, since those remain baked into the image.

   The page size is set to match the background image's own aspect ratio
   (instead of forcing it into a fixed A4-landscape box), so nothing gets
   stretched and calibrated coordinates land exactly where they look
   right in the source image.

Every variable-length field — student name, course name, the description
sentence — is measured and either wrapped onto multiple lines or shrunk
to fit before anything is drawn, so a long course name pushes later
content down/smaller instead of overlapping it.

The S/o./D/o. parent-name line and the description sentence beneath it
are rendered at the SAME font size — the sentence's fitted size is
computed first, and the parent-name line reuses it — so the two never
visually mismatch even when the sentence has to shrink to fit.
"""
import os
import re
from pathlib import Path

from reportlab.lib.pagesizes import landscape, A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase.pdfmetrics import stringWidth
from PIL import Image

from app.core.config import settings

BUILTIN_PAGE_SIZE = landscape(A4)
BUILTIN_PAGE_W, BUILTIN_PAGE_H = BUILTIN_PAGE_SIZE

# Brand palette, matching the web app's design tokens.
INK = (0.00, 0.00, 0.00)
INK_SOFT = (0.20, 0.227, 0.357)
GOLD = (0.788, 0.635, 0.153)
GOLD_DARK = (0.612, 0.494, 0.110)
SLATE = (0.318, 0.376, 0.478)
PAPER = (0.980, 0.969, 0.969)
NAME_TEAL = (0.00, 0.19, 0.24)
AICTE_RED = (0.827, 0.184, 0.184)

BUILTIN_LAYOUT = {
    "ribbon_center_y": BUILTIN_PAGE_H - 132,
    "presented_to_y": BUILTIN_PAGE_H - 192,
    "name_y": BUILTIN_PAGE_H - 236,
    "subline_top_y": BUILTIN_PAGE_H - 264,
    "body_max_width": BUILTIN_PAGE_W - 170,
    "signature": {"size": 150},
    "min_footer_y": 46,
}

# Calibrated against the June 24 revision of Pixelwind's branded template —
# the one with NO baked-in "ID:" line, "INTERNSHIP ID:" line, or QR
# placeholder. All values are FRACTIONS of page width/height (0-1, y from
# top) so they hold regardless of what size we render the page at.
CUSTOM_BG_LAYOUT = {
    "id_label": {"fx": 0.330, "fy": 0.100, "size": 18},
    "id_value": {"fx": 0.375, "fy": 0.100, "size": 18, "min_size": 10},

    "name": {"fy": 0.426, "size": 34, "min_size": 18},

    "subline": {"fy": 0.470, "size": 14},

    "body_max_width_frac": 0.72,

    "internship_label": {"fx": 0.275, "fy": 0.808, "size": 13},
    "internship_id_value": {"fx": 0.430, "fy": 0.808, "size": 13, "min_size": 8},

    "qr": {"cx": 0.86, "cy": 0.36, "size_frac": 0.14},
}


def fit_font_size(text: str, font: str, max_width: float, start_size: float, min_size: float = 14) -> float:
    """Shrinks font size in 0.5pt steps until a single line of `text` fits max_width."""
    size = start_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def wrap_lines(text: str, font: str, size: float, max_width: float) -> list[str]:
    """Greedy word-wrap of `text` into lines that each fit within max_width."""
    lines: list[str] = []
    for paragraph in text.split("\n"):
        words = paragraph.split()
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if not current or stringWidth(candidate, font, size) <= max_width:
                current = candidate
            else:
                lines.append(current)
                current = word
        if current:
            lines.append(current)
        if paragraph != text.split("\n")[-1]:
            lines.append("")
    return lines


def _draw_centered(c, text, x, y, font, size, color=INK):
    c.setFillColorRGB(*color)
    c.setFont(font, size)
    c.drawCentredString(x, y, text)


def _draw_centered_with_bold_span(c, text, bold_span, x, y, normal_font, bold_font, size, color=INK):
    if not bold_span or bold_span not in text:
        _draw_centered(c, text, x, y, normal_font, size, color=color)
        return

    prefix, suffix = text.split(bold_span, 1)
    prefix_width = stringWidth(prefix, normal_font, size)
    bold_width = stringWidth(bold_span, bold_font, size)
    total_width = prefix_width + bold_width + stringWidth(suffix, normal_font, size)
    start_x = x - total_width / 2

    c.setFillColorRGB(*color)
    c.setFont(normal_font, size)
    c.drawString(start_x, y, prefix)
    c.setFont(bold_font, size)
    c.drawString(start_x + prefix_width, y, bold_span)
    if suffix:
        c.setFont(normal_font, size)
        c.drawString(start_x + prefix_width + bold_width, y, suffix)


def _draw_centered_with_spans(c, text, x, y, normal_font, size, spans, normal_color=INK_SOFT):
    """Segmented renderer — each character drawn exactly once, no overdraw."""
    marked: list[tuple[int, int, str, str, tuple]] = []
    for span_text, span_font, span_color in spans:
        if not span_text:
            continue
        m = re.search(re.escape(span_text), text)
        if m and not any(s <= m.start() < e or s < m.end() <= e for s, e, *_ in marked):
            marked.append((m.start(), m.end(), span_text, span_font, span_color))
    marked.sort(key=lambda t: t[0])

    segments: list[tuple[str, str, tuple]] = []
    cursor = 0
    for start, end, chunk, sfont, scolor in marked:
        if cursor < start:
            segments.append((text[cursor:start], normal_font, normal_color))
        segments.append((chunk, sfont, scolor))
        cursor = end
    if cursor < len(text):
        segments.append((text[cursor:], normal_font, normal_color))

    if not segments:
        return

    total_w = sum(stringWidth(seg, fnt, size) for seg, fnt, _ in segments)
    draw_x = x - total_w / 2
    for seg_text, seg_font, seg_color in segments:
        c.setFillColorRGB(*seg_color)
        c.setFont(seg_font, size)
        c.drawString(draw_x, y, seg_text)
        draw_x += stringWidth(seg_text, seg_font, size)


def _draw_left(c, text, x, y, font, size, color=INK):
    c.setFillColorRGB(*color)
    c.setFont(font, size)
    c.drawString(x, y, text)


def _pronoun(gender: str | None):
    g = (gender or "").strip().lower()
    if g in ("male", "m"):
        return "S/o.", "his"
    if g in ("female", "f"):
        return "D/o.", "her"
    return "C/o.", "their"


def _display_date(iso_str: str | None) -> str | None:
    if not iso_str:
        return iso_str
    parts = iso_str.split("-")
    if len(parts) == 3 and len(parts[0]) == 4:
        year, month, day = parts
        return f"{day}-{month}-{year}"
    return iso_str


def _format_internship_display_id(value: str | None) -> str | None:
    if not value:
        return value
    display = value.strip()
    if display.startswith("INTERNSHIP_"):
        core = display[len("INTERNSHIP_"):]
        if len(core) >= 12:
            return f"INT-{core[:4].upper()}-{core[4:8].upper()}-{core[-4:].upper()}"
        return display.replace("INTERNSHIP_", "INT-")
    if len(display) > 24:
        return f"{display[:12]}-{display[-4:]}"
    return display


def _training_label(training_type: str | None) -> str:
    if training_type and training_type.upper() == "INDUSTRIAL_TRAINING":
        return "Industrial Training"
    return "Internship"


def _build_sentence(course_name, admission_date, relieving_date, performance_grade, possessive, issuer_label, training_type=None):
    """Three hard-wrapped lines:
    Line 1: Successfully completed {possessive} {training_label} in "course" from
    Line 2: "start to end" in {issuer_part}
    Line 3: and achieved Performance Grade “{grade}”.   (skipped when no grade)
    """
    start_disp = _display_date(admission_date)
    end_disp = _display_date(relieving_date)

    issuer_part = issuer_label
    if settings.ISSUER_BRANCH:
        issuer_part = f"{issuer_label} ({settings.ISSUER_BRANCH})"

    training_label = _training_label(training_type)
    course_name = course_name.strip()

    line1 = f"Successfully completed {possessive} {training_label} in \u201c{course_name}\u201d"
    line2 = f"from \u201c{start_disp} to {end_disp}\u201d in {issuer_part}"

    grade = str(performance_grade).strip() if performance_grade and str(performance_grade).strip() else None
    if grade:
        return f"{line1}\n{line2}\nand achieved Performance Grade “{grade}”."
    else:
        return f"{line1}\n{line2}."


def _draw_ribbon(c, cx, cy, text):
    width, height, notch = 300, 42, 15
    left, right = cx - width / 2, cx + width / 2
    top, bottom = cy + height / 2, cy - height / 2

    c.saveState()
    c.setFillColorRGB(*GOLD)
    path = c.beginPath()
    path.moveTo(left, top)
    path.lineTo(right, top)
    path.lineTo(right - notch, cy)
    path.lineTo(right, bottom)
    path.lineTo(left, bottom)
    path.lineTo(left + notch, cy)
    path.close()
    c.drawPath(path, fill=1, stroke=0)
    c.restoreState()

    _draw_centered(c, text, cx, cy - 5, "Helvetica-Bold", 15, color=INK)


def _draw_diagonal_corners(c, page_w, page_h, inset=36, length=50, line_width=1.2):
    c.saveState()
    c.setStrokeColorRGB(*GOLD)
    c.setLineWidth(line_width)
    c.line(inset, page_h - inset, inset + length, page_h - inset - length)
    c.line(inset, page_h - inset - length, inset + length, page_h - inset)
    c.line(page_w - inset, page_h - inset, page_w - inset - length, page_h - inset - length)
    c.line(page_w - inset, page_h - inset - length, page_w - inset - length, page_h - inset)
    c.line(inset, inset, inset + length, inset + length)
    c.line(inset, inset + length, inset + length, inset)
    c.line(page_w - inset, inset, page_w - inset - length, inset + length)
    c.line(page_w - inset, inset + length, page_w - inset - length, inset)
    c.restoreState()


def _render_builtin(c, ctx, layout):
    page_w, page_h = BUILTIN_PAGE_W, BUILTIN_PAGE_H
    margin = 70
    content_w = page_w - 2 * margin

    c.setFillColorRGB(*PAPER)
    c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    _draw_diagonal_corners(c, page_w, page_h)
    c.setStrokeColorRGB(*GOLD)
    c.setLineWidth(1.2)
    c.rect(40, 40, page_w - 80, page_h - 80, fill=0, stroke=1)
    _draw_ribbon(c, page_w / 2, layout["ribbon_center_y"], "CERTIFICATE OF MERIT")
    _draw_centered(c, "THIS CERTIFICATE IS PRESENTED TO", page_w / 2, layout["presented_to_y"], "Helvetica", 12, color=SLATE)

    issuer_label = (settings.ISSUER_NAME or "Pixelwind Technologies").replace("Pixel Wind", "Pixelwind")
    training_label = _training_label(ctx.get("training_type"))
    c.setFillColorRGB(*INK)
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(page_w - margin, page_h - 70, issuer_label)
    c.setFillColorRGB(*SLATE)
    c.setFont("Helvetica", 8)
    c.drawRightString(page_w - margin, page_h - 84, f"Certificate of {training_label}")

    name_text = ctx["student_name"].upper()
    name_font = "Helvetica-Bold"
    name_size = fit_font_size(name_text, name_font, content_w - 100, 27, min_size=18)
    name_y = layout["name_y"] + 10
    _draw_centered(c, name_text, page_w / 2, name_y, name_font, name_size, color=NAME_TEAL)
    name_w = stringWidth(name_text, name_font, name_size)
    c.setStrokeColorRGB(*GOLD)
    c.setLineWidth(1.2)
    c.line(page_w / 2 - name_w * 0.485, name_y - 14, page_w / 2 + name_w * 0.485, name_y - 14)

    relation, possessive = _pronoun(ctx["gender"])
    cursor_y = layout["subline_top_y"] - 8
    if ctx["father_name"]:
        _draw_centered(c, f"{relation} {ctx['father_name']}", page_w / 2, cursor_y, "Times-Roman", 21, color=INK_SOFT)
        cursor_y -= 10
    if ctx["college_name"]:
        _draw_centered(c, ctx["college_name"], page_w / 2, cursor_y, "Helvetica", 9.5, color=SLATE)
        cursor_y -= 18

    course_name = ctx["course_name"].strip()
    grade_value = ctx.get("performance_grade")
    sentence = _build_sentence(
        course_name, ctx["admission_date"], ctx["relieving_date"],
        grade_value, possessive, issuer_label, ctx.get("training_type"),
    )

    body_font, body_size = "Times-Roman", 24
    lines = wrap_lines(sentence, body_font, body_size, layout["body_max_width"])
    while body_size > 14 and any(stringWidth(line, body_font, body_size) > layout["body_max_width"] for line in lines):
        body_size -= 0.5
        lines = wrap_lines(sentence, body_font, body_size, layout["body_max_width"])

    # line_height = exactly the font size — zero extra leading between lines
    line_height = body_size
    body_y = cursor_y - 9
    start_disp = _display_date(ctx["admission_date"])
    end_disp = _display_date(ctx["relieving_date"])
    grade_span = str(grade_value).strip() if grade_value and str(grade_value).strip() else None
    for line in lines:
        spans = []
        if start_disp and start_disp in line:
            spans.append((start_disp, "Times-Bold", AICTE_RED))
        if end_disp and end_disp in line:
            spans.append((end_disp, "Times-Bold", AICTE_RED))
        if course_name and course_name in line:
            spans.append((course_name, "Times-Bold", NAME_TEAL))
        if grade_span and grade_span in line:
            spans.append((grade_span, "Times-Bold", NAME_TEAL))
        if spans:
            _draw_centered_with_spans(c, line, page_w / 2, body_y, body_font, body_size, spans)
        else:
            _draw_centered(c, line, page_w / 2, body_y, body_font, body_size, color=INK_SOFT)
        body_y -= line_height

    signature_top_y = body_y - 24
    sig_w = layout["signature"]["size"]
    sig_x = page_w / 2 - sig_w / 2
    if ctx["signature_path"] and os.path.exists(ctx["signature_path"]):
        c.drawImage(
            ImageReader(ctx["signature_path"]), sig_x, signature_top_y - 38,
            width=sig_w, height=sig_w * 0.3, preserveAspectRatio=True, mask="auto",
        )
    c.setStrokeColorRGB(*GOLD_DARK)
    c.setLineWidth(0.8)
    c.line(sig_x, signature_top_y - 42, sig_x + sig_w, signature_top_y - 42)
    _draw_centered(c, "MANAGING DIRECTOR", page_w / 2, signature_top_y - 50, "Helvetica-Bold", 9.5, color=INK)

    footer_y = max(signature_top_y - 78, layout["min_footer_y"])
    _draw_centered(c, f"Issued on {ctx['issue_date']}", page_w / 2, footer_y, "Helvetica", 8, color=SLATE)


def _render_custom_bg(c, ctx, page_w, page_h, layout):
    c.drawImage(ImageReader(ctx["template_bg_path"]), 0, 0, width=page_w, height=page_h)

    issuer_label = (settings.ISSUER_NAME or "Pixelwind Technologies").replace("Pixel Wind", "Pixelwind")
    relation, possessive = _pronoun(ctx["gender"])

    # --- "ID:" label + our own internship_id value -------------------------
    id_text = _format_internship_display_id(ctx["internship_id"])
    if id_text:
        idv = layout["id_value"]
        id_max_w = page_w * 0.70
        id_size = fit_font_size(f"ID: {id_text}", "Helvetica-Bold", id_max_w, idv["size"] - 2, min_size=idv["min_size"])
        _draw_centered(c, f"ID: {id_text}", page_w / 2, page_h * (1 - idv["fy"]) - 24, "Helvetica-Bold", id_size, color=INK)

    # --- Student name ------------------------------------------------------
    name_cfg = layout["name"]
    name_text = ctx["student_name"].upper()
    name_size = fit_font_size(name_text, "Helvetica-Bold", page_w * 0.56, name_cfg["size"], min_size=name_cfg["min_size"])
    name_y = page_h * (1 - name_cfg["fy"]) + 8
    _draw_centered(c, name_text, page_w / 2, name_y, "Helvetica-Bold", name_size, color=NAME_TEAL)

    # --- Body sentence — S/o./D/o. flows directly into it, single anchor ---
    # Each \n-separated line must fit on EXACTLY ONE printed line — no word
    # wrap. We shrink the shared font size until every line fits within max_w.
    sub_cfg = layout["subline"]
    body_font = "Times-Roman"
    body_size = 26
    max_w = page_w * layout["body_max_width_frac"]

    course_name = ctx["course_name"].strip()
    start_disp = _display_date(ctx["admission_date"])
    end_disp = _display_date(ctx["relieving_date"])
    grade_value = ctx.get("performance_grade")
    sentence = _build_sentence(
        course_name, ctx["admission_date"], ctx["relieving_date"],
        grade_value, possessive, issuer_label, ctx.get("training_type"),
    )

    # Split on the hard \n breaks only — no further wrapping.
    lines = [l for l in sentence.split("\n") if l]
    while body_size > 10 and any(stringWidth(line, body_font, body_size) > max_w for line in lines):
        body_size -= 0.5

    # Tight leading — comfortable but not airy
    line_height = body_size * 1.1

    # Small gap between the name underline and S/o./D/o. line
    cursor_y = page_h * (1 - sub_cfg["fy"]) - 8
    if ctx["father_name"]:
        _draw_centered(c, f"{relation} {ctx['father_name']}", page_w / 2, cursor_y, "Times-Roman", body_size, color=INK)
        cursor_y -= line_height

    body_y = cursor_y
    grade_span = str(grade_value).strip() if grade_value and str(grade_value).strip() else None
    for line in lines:
        spans = []
        if start_disp and start_disp in line:
            spans.append((start_disp, "Times-Bold", AICTE_RED))
        if end_disp and end_disp in line:
            spans.append((end_disp, "Times-Bold", AICTE_RED))
        if course_name and course_name in line:
            spans.append((course_name, "Times-Bold", NAME_TEAL))
        if grade_span and grade_span in line:
            spans.append((grade_span, "Times-Bold", NAME_TEAL))
        if spans:
            _draw_centered_with_spans(c, line, page_w / 2, body_y, body_font, body_size, spans, normal_color=INK)
        else:
            _draw_centered(c, line, page_w / 2, body_y, body_font, body_size, color=INK)
        body_y -= line_height

    # --- QR code -----------------------------------------------------------
    qr_cfg = layout["qr"]
    if ctx["qr_code_path"] and os.path.exists(ctx["qr_code_path"]):
        size = qr_cfg["size_frac"] * page_w
        cx, cy = qr_cfg["cx"] * page_w, page_h * (1 - qr_cfg["cy"])
        c.drawImage(
            ImageReader(ctx["qr_code_path"]), cx - size / 2, cy - size / 2,
            width=size, height=size, preserveAspectRatio=True, mask="auto",
        )

    # --- AICTE Internship ID -----------------------------------------------
    if ctx["aicte_internship_id"]:
        iidl = layout["internship_label"]
        _draw_left(
            c, "", iidl["fx"] * page_w, page_h * (1 - iidl["fy"]),
            "Helvetica-Bold", iidl["size"], color=AICTE_RED,
        )
        iidv = layout["internship_id_value"]
        iid_max_w = page_w * 0.94
        iid_size = fit_font_size(ctx["aicte_internship_id"], "Helvetica-Bold", iid_max_w, iidv["size"], min_size=iidv["min_size"])
        _draw_centered(
            c, ctx["aicte_internship_id"], page_w / 2, page_h * (1 - iidv["fy"]),
            "Helvetica-Bold", iid_size, color=AICTE_RED,
        )


def render_certificate_pdf(
    output_path: str,
    student_name: str,
    father_name: str | None,
    college_name: str,
    course_name: str,
    internship_id: str,
    certificate_id: str,
    issue_date: str,
    performance_grade: str | None,
    admission_date: str | None,
    relieving_date: str | None,
    template_bg_path: str | None,
    signature_path: str | None,
    gender: str | None = None,
    training_type: str | None = None,
    qr_code_path: str | None = None,
    aicte_internship_id: str | None = None,
    layout_config: dict | None = None,
) -> str:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    ctx = dict(
        student_name=student_name, father_name=father_name, college_name=college_name,
        course_name=course_name, internship_id=internship_id,
        certificate_id=certificate_id, issue_date=issue_date, performance_grade=performance_grade,
        admission_date=admission_date, relieving_date=relieving_date,
        template_bg_path=template_bg_path, signature_path=signature_path, gender=gender,
        qr_code_path=qr_code_path, aicte_internship_id=aicte_internship_id,
        training_type=training_type,
    )

    has_custom_bg = bool(template_bg_path and os.path.exists(template_bg_path))

    if has_custom_bg:
        with Image.open(template_bg_path) as im:
            img_w, img_h = im.size
        page_w = 842.0
        page_h = page_w * (img_h / img_w)
        layout = {**CUSTOM_BG_LAYOUT, **(layout_config or {})}
        c = canvas.Canvas(output_path, pagesize=(page_w, page_h))
        _render_custom_bg(c, ctx, page_w, page_h, layout)
    else:
        layout = {**BUILTIN_LAYOUT, **(layout_config or {})}
        c = canvas.Canvas(output_path, pagesize=BUILTIN_PAGE_SIZE)
        _render_builtin(c, ctx, layout)

    c.showPage()
    c.save()
    return output_path