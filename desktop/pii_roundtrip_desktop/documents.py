"""Reading documents into plain text and saving results in the format the user started with.

Word: the text is read from headers, the body (paragraphs and tables, cells joined by " | ")
and footers, in that order. A cleaned copy keeps the original formatting: placeholders are
written into the same runs. After saving, every text part of the file (body, headers,
footers, footnotes, comments, text boxes) is checked for the masked values; if any is
found, the copy is rejected. The document properties (author and similar) are cleared.

PDF: a cleaned copy keeps the layout: every page is rendered with an opaque box and the
placeholder over each masked fragment, and an invisible layer carries the cleaned text.
"""

from __future__ import annotations

import re
import zipfile
from pathlib import Path

SUPPORTED = (".docx", ".pdf", ".txt", ".md")
FONTS = Path(__file__).with_name("fonts")


class DocumentError(Exception):
    """The file cannot be read as a document."""


class UnsupportedFormat(DocumentError):
    """Not Word, PDF or text."""


class ScannedPDF(DocumentError):
    """A PDF without a text layer."""


class UnsafeCopy(DocumentError):
    """A cleaned Word copy still contains a masked value somewhere in the file."""


_PLACEHOLDER = re.compile(r"\[[A-Z]+(?:_[A-Z]+)*_\d+\]")


def read_text(path: str | Path) -> str:
    p = Path(path)
    suffix = p.suffix.lower()
    if suffix == ".docx":
        return _read_docx(p)[0]
    if suffix == ".pdf":
        return _read_pdf(p)
    if suffix in (".txt", ".md"):
        for encoding in ("utf-8", "cp1251"):
            try:
                return p.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        raise DocumentError(f"{p.name}: unknown text encoding")
    raise UnsupportedFormat(f"{p.name}: unsupported format; supported: {', '.join(SUPPORTED)}")


# ---------- Word ----------


def _open_docx(p: Path):
    from docx import Document

    try:
        return Document(str(p))
    except Exception as e:
        raise DocumentError(f"{p.name}: not a Word document ({e})") from None


def _lines(doc):
    """The document as lines; each line is a list of paragraphs joined by a separator.

    Yields (paragraphs, separator): a body paragraph is ([p], ""); a table row is the first
    paragraph list of every distinct cell, cells joined by " | " and paragraphs inside a
    cell joined by a line break."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    def paragraphs_of(container):
        for block in container._element.iterchildren():
            tag = block.tag.rsplit("}", 1)[-1]
            if tag == "p":
                yield ("p", Paragraph(block, container))
            elif tag == "tbl":
                yield ("row_table", Table(block, container))

    # only headers and footers that exist: reading a missing one would create it
    headers = [s.header for s in doc.sections if not s.header.is_linked_to_previous]
    footers = [s.footer for s in doc.sections if not s.footer.is_linked_to_previous]
    for c in [*headers, _Body(doc), *footers]:
        for kind, obj in paragraphs_of(c):
            if kind == "p":
                yield [[obj]], " | "
            else:
                for row in obj.rows:
                    cells, last = [], None
                    for cell in row.cells:
                        if cell._tc is last:
                            continue  # a merged cell repeats itself
                        last = cell._tc
                        cells.append(list(cell.paragraphs))
                    yield cells, " | "


class _Body:
    """Adapter so the document body iterates like a header or footer."""

    def __init__(self, doc):
        self._element = doc.element.body
        self.part = doc.part


def _read_docx(p: Path) -> tuple[str, list]:
    """Text of a Word file and, for each line, its cells with paragraph offsets in that text."""
    doc = _open_docx(p)
    text_parts, layout, pos = [], [], 0
    for cells, sep in _lines(doc):
        line_parts, cell_layout = [], []
        for ci, paragraphs in enumerate(cells):
            if ci:
                line_parts.append(sep)
                pos += len(sep)
            para_layout = []
            for pi, para in enumerate(paragraphs):
                if pi:
                    line_parts.append("\n")
                    pos += 1
                para_layout.append((pos, para))
                line_parts.append(para.text)
                pos += len(para.text)
            cell_layout.append(para_layout)
        text_parts.append("".join(line_parts) + "\n")
        pos += 1
        layout.append(cell_layout)
    flat = "".join(text_parts)
    lead = len(flat) - len(flat.lstrip())
    return flat.strip() + "\n", [(lead, layout)]


def _replace_in_paragraph(para, local: list[tuple[int, int, str]]) -> None:
    runs = list(para.runs)
    if "".join(r.text for r in runs) != para.text or not runs:
        # hyperlinks or fields: rewrite the paragraph text in its first run
        text = para.text
        for start, end, label in sorted(local, reverse=True):
            text = text[:start] + label + text[end:]
        if runs:
            runs[0].text = text
            for r in runs[1:]:
                r.text = ""
        return
    bounds, pos = [], 0
    for r in runs:
        bounds.append((pos, pos + len(r.text)))
        pos += len(r.text)

    def locate(offset: int, end: bool) -> tuple[int, int]:
        for i, (a, b) in enumerate(bounds):
            if a <= offset < b or (end and a < offset <= b):
                return i, offset - a
        return len(runs) - 1, len(runs[-1].text)

    for start, end, label in sorted(local, reverse=True):
        i, oi = locate(start, False)
        j, oj = locate(end, True)
        if i == j:
            runs[i].text = runs[i].text[:oi] + label + runs[i].text[oj:]
        else:
            runs[i].text = runs[i].text[:oi] + label
            for k in range(i + 1, j):
                runs[k].text = ""
            runs[j].text = runs[j].text[oj:]


def save_clean_docx(src: str | Path, dst: str | Path, spans: list[tuple[int, int, str]], values: list[str]) -> None:
    """A cleaned copy of a Word file with its formatting: ``spans`` are (start, end, label)
    in the text returned by read_text; ``values`` are the masked originals used to verify."""
    _rewrite_docx(Path(src), dst, spans)
    leaked = _find_values(Path(dst), values)
    if leaked:
        Path(dst).unlink(missing_ok=True)
        raise UnsafeCopy(f"{len(leaked)} masked values remain in parts of the file the app cannot clean")


def save_restored_docx(src: str | Path, dst: str | Path, spans: list[tuple[int, int, str]]) -> None:
    """A Word file with placeholders with the real values written back, formatting kept."""
    _rewrite_docx(Path(src), dst, spans)


def _rewrite_docx(src: Path, dst: str | Path, spans: list[tuple[int, int, str]]) -> None:
    doc = _open_docx(src)
    _, [(lead, _layout)] = _read_docx(src)
    # rebuild the layout on this document object (paragraph objects must belong to it)
    pos, layout = 0, []
    for cells, sep in _lines(doc):
        for ci, paragraphs in enumerate(cells):
            if ci:
                pos += len(sep)
            for pi, para in enumerate(paragraphs):
                if pi:
                    pos += 1
                layout.append((pos, para))
                pos += len(para.text)
        pos += 1
    for start_flat, para in layout:
        a, b = start_flat, start_flat + len(para.text)
        local = []
        for start, end, label in spans:
            s, e = start + lead, end + lead
            if s < b and e > a:
                cs, ce = max(s, a) - a, min(e, b) - a
                local.append((cs, ce, label if s >= a else ""))
        if local:
            _replace_in_paragraph(para, local)
    props = doc.core_properties
    for name in ("author", "last_modified_by", "title", "subject", "keywords", "comments", "category"):
        setattr(props, name, "")
    doc.save(str(dst))


def _find_values(path: Path, values: list[str]) -> list[str]:
    """Masked values still present anywhere in the text of a .docx file."""
    found = []
    with zipfile.ZipFile(path) as z:
        texts = []
        for name in z.namelist():
            if name.endswith(".xml") and (name.startswith("word/") or name.startswith("docProps/")):
                xml = z.read(name).decode("utf-8", "ignore")
                texts.append("".join(re.findall(r"<w:t(?:\s[^>]*)?>([^<]*)</w:t>", xml)))
                texts.append(re.sub(r"<[^>]+>", " ", xml) if name.startswith("docProps/") else "")
        whole = "\n".join(texts)
    norm = re.sub(r"\s+", " ", whole)
    for v in values:
        v = v.strip()
        if len(v) >= 3 and re.sub(r"\s+", " ", v) in norm:
            found.append(v)
    return found


# ---------- PDF and text ----------


def _pdf_pages(p: Path):
    """Per page: the text (CRLF folded to LF) and, for each of its characters, the pdfium
    character index, so a span in the text can be mapped back to boxes on the page."""
    import pypdfium2 as pdfium

    try:
        pdf = pdfium.PdfDocument(str(p))
    except Exception as e:
        raise DocumentError(f"{p.name}: cannot read PDF ({e})") from None
    pages = []
    for page in pdf:
        tp = page.get_textpage()
        n = tp.count_chars()
        raw = tp.get_text_range(0, n) if n else ""
        text, index, i = [], [], 0
        while i < len(raw):
            if raw[i] == "\r" and i + 1 < len(raw) and raw[i + 1] == "\n":
                text.append("\n")
                index.append(i)
                i += 2
                continue
            text.append(raw[i])
            index.append(i)
            i += 1
        pages.append(("".join(text), index))
    return pdf, pages


def _pdf_flat(pages) -> tuple[str, int, list[int]]:
    """The text of all pages joined by a blank line, its leading strip, and page offsets."""
    parts, starts, pos = [], [], 0
    for k, (text, _index) in enumerate(pages):
        if k:
            parts.append("\n\n")
            pos += 2
        starts.append(pos)
        parts.append(text)
        pos += len(text)
    flat = "".join(parts)
    return flat, len(flat) - len(flat.lstrip()), starts


def _read_pdf(p: Path) -> str:
    _pdf, pages = _pdf_pages(p)
    flat, _lead, _starts = _pdf_flat(pages)
    text = flat.strip()
    if len(text) < 20 * max(1, len(pages)):
        raise ScannedPDF(f"{p.name}: the PDF has no text layer (a scan); recognise the text first")
    return text + "\n"


def _span_boxes(text: str, index: list[int], tp, s: int, e: int) -> list[list[float]]:
    """Boxes (left, bottom, right, top) in PDF points covering text[s:e], one per line."""
    boxes: list[list[float]] = []
    for c in range(s, e):
        if text[c].isspace():
            continue
        left, bottom, right, top = tp.get_charbox(index[c], loose=False)
        if text[c] in "[]()_|" and boxes:
            # tall or low marks would make the box, and so the restored text, too big
            box = boxes[-1]
            box[0], box[2] = min(box[0], left), max(box[2], right)
            continue
        # the same line: the letter overlaps the box vertically (a comma or a dot is small and low)
        same_line = boxes and bottom < boxes[-1][3] and top > boxes[-1][1]
        if same_line and left >= boxes[-1][0] - 1:
            box = boxes[-1]
            box[0], box[1], box[2], box[3] = (
                min(box[0], left),
                min(box[1], bottom),
                max(box[2], right),
                max(box[3], top),
            )
        else:
            boxes.append([left, bottom, right, top])
    return boxes


def _visible(tp, index: list[int], s: int, e: int) -> bool:
    """True if the letters of text[s:e] are drawn on the page, not an invisible text layer."""
    import pypdfium2.raw as raw

    for c in range(s, e):
        obj = raw.FPDFText_GetTextObject(tp.raw, index[c])
        if obj:
            return raw.FPDFTextObj_GetTextRenderMode(obj) != raw.FPDF_TEXTRENDERMODE_INVISIBLE
    return False


def _font_size_near(tp, text: str, index: list[int], s: int, e: int) -> float:
    """Font size in points of the nearest letter outside text[s:e] on the same line."""
    import pypdfium2.raw as raw

    for c in list(range(s - 1, max(-1, s - 40), -1)) + list(range(e, min(len(text), e + 40))):
        ch = text[c]
        if ch == "\n":
            continue
        if ch.isalnum():
            size = raw.FPDFText_GetFontSize(tp.raw, index[c])
            if size > 0:
                return float(size)
    return 0.0


def _restore_lines(image, scale, width, height, text, index, tp, local, face) -> None:
    """Restore values into a PDF whose text is drawn as letters (a file an AI tool wrote): on
    each line with a label, the line from the first label to its end is redrawn with the values
    in place, so a value longer than its label moves the rest of the line instead of being
    squeezed into the label's width. The line keeps within the page's right margin."""
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(image)
    by_line: dict[int, list] = {}
    for s, e, new in local:
        by_line.setdefault(text.rfind("\n", 0, s) + 1, []).append((s, e, " ".join(new.split())))
    for line_start, items in by_line.items():
        line_end = text.find("\n", line_start)
        line_end = len(text) if line_end < 0 else line_end
        first = items[0][0]
        last = max(e for _, e, _ in items)
        boxes = _span_boxes(text, index, tp, first, line_end)
        if len(boxes) != 1 or last > line_end:
            # a label across lines: write each value into its own place
            for s, e, new in items:
                for n, (x0, y0, x1, y1) in enumerate(_span_boxes(text, index, tp, s, e)):
                    rect = [
                        (x0 - 1.2) * scale,
                        (height - y1 - 2.5) * scale,
                        (x1 + 1.2) * scale,
                        (height - y0 + 2.5) * scale,
                    ]
                    draw.rectangle(rect, fill=(255, 255, 255))
                    if n == 0:
                        size = _font_size_near(tp, text, index, s, e) or (y1 - y0) * 1.3
                        _draw_squeezed(image, new, face, rect, size * scale)
            continue
        x0, y0, x1, y1 = boxes[0]
        tail, pos = [], first
        for s, e, new in items:
            tail += [text[pos:s], new]
            pos = e
        tail.append(text[pos:line_end])
        tail_text = "".join(tail).rstrip()
        size = _font_size_near(tp, text, index, first, last) or (y1 - y0) * 1.3
        font = ImageFont.truetype(str(face), max(6, int(size * scale)))
        room = max(x1, width - 36) - x0  # up to the right margin of the page
        cover = [(x0 - 1.2) * scale, (height - y1 - 2.5) * scale, (x1 + 1.2) * scale, (height - y0 + 2.5) * scale]
        draw.rectangle(cover, fill=(255, 255, 255))
        rect = [x0 * scale, cover[1], (x0 + room) * scale, cover[3]]
        if draw.textlength(tail_text, font=font) <= rect[2] - rect[0]:
            rect[2] = rect[0] + draw.textlength(tail_text, font=font) + 2
        _draw_squeezed(image, tail_text, face, rect, size * scale)


def _draw_squeezed(image, text: str, face: Path, rect: list[float], size_px: float) -> None:
    """Write a restored value into its box at the height of the surrounding text, narrowing it
    if it is wider than the box, so that it never runs into the next word."""
    from PIL import Image, ImageDraw, ImageFont

    height = rect[3] - rect[1]
    width = max(1, int(rect[2] - rect[0]))
    font = ImageFont.truetype(str(face), max(6, int(size_px)))
    left, top, right, bottom = font.getbbox(text)
    w, h = max(1, right - left), max(1, bottom - top)
    tile = Image.new("L", (w, h), 0)
    ImageDraw.Draw(tile).text((-left, -top), text, fill=255, font=font)
    if w > width:
        tile = tile.resize((width, h), Image.Resampling.LANCZOS)
    y = int(rect[1] + (height - h) / 2)
    ink = Image.new("RGB", tile.size, (17, 24, 39))
    image.paste(ink, (int(rect[0]), y), tile)


def _fit_font(draw, text: str, path: Path, height: float, width: float, ratio: float = 0.62):
    from PIL import ImageFont

    size = max(8, int(height * ratio))
    font = ImageFont.truetype(str(path), size)
    while size > 6 and draw.textlength(text, font=font) > width - 4:
        size -= 1
        font = ImageFont.truetype(str(path), size)
    return font


_BOXES = "pii-roundtrip-boxes:"


FILL = (229, 231, 235)  # the grey of a placeholder box drawn by save_clean_pdf


def _grey_share(image, rect: list[float]) -> float:
    """Share of the pixels inside rect (image pixels) that have the placeholder box grey."""
    import numpy as np

    x0, y0, x1, y1 = (int(round(v)) for v in rect)
    x0, y0 = max(0, x0 + 2), max(0, y0 + 2)
    x1, y1 = min(image.width, x1 - 2), min(image.height, y1 - 2)
    if x1 <= x0 or y1 <= y0:
        return 0.0
    a = np.asarray(image.crop((x0, y0, x1, y1)), dtype=np.int16)
    return float((np.abs(a - np.array(FILL)).max(axis=2) <= 4).mean())


class UnplacedLabels(DocumentError):
    """The labels seen on a page cannot be matched to the labels of its text."""


def _rewrite_pdf(
    src: Path, dst: str | Path, spans: list[tuple[int, int, str]], restore: bool, known: dict[str, str] | None = None
) -> None:
    """Render every page as an image and paint each span over: a grey box with the placeholder
    (cleaning) or a white box with the real value (restoring); the data are removed from the
    file, not just covered. An invisible text layer carries the new text for copying and for AI
    tools. A cleaned file records where each placeholder box is and the font size of the text
    it replaced (labels, coordinates and sizes only). Restoring such a file writes the values
    exactly into those boxes, whatever was edited in its text layer since: its pages are
    pictures, so the boxes, not the text layer, say where the labels are seen."""
    import json

    from PIL import ImageDraw
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfgen import canvas

    pdf, pages = _pdf_pages(src)
    flat, lead, starts = _pdf_flat(pages)
    recorded = _recorded_boxes(pdf) if restore else None
    canon = {k.strip("[]").upper(): v for k, v in (known or {}).items()}
    if "Inter" not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont("Inter", str(FONTS / "Inter-400.ttf")))
    face = FONTS / ("Inter-400.ttf" if restore else "SpaceGrotesk-600.ttf")
    scale = 2.0
    out = canvas.Canvas(str(dst))
    for setter in (out.setAuthor, out.setTitle, out.setCreator, out.setProducer, out.setSubject):
        setter("")
    record: list[list] = []
    for k, page in enumerate(pdf):
        text, index = pages[k]
        a, b = starts[k], starts[k] + len(text)
        tp = page.get_textpage()
        width, height = page.get_size()
        image = page.render(scale=scale).to_pil().convert("RGB")
        draw = ImageDraw.Draw(image)
        local = sorted(
            (max(s + lead, a) - a, min(e + lead, b) - a, new) for s, e, new in spans if s + lead < b and e + lead > a
        )
        page_text, pos = [], 0
        for s, e, new in local:
            page_text += [text[pos:s], " ".join(new.split())]
            pos = e
        page_text.append(text[pos:])
        page_record = []

        def paint(rect_pt, value, size_pt, n, widest):
            left, bottom, right, top = rect_pt
            rect = [left * scale, (height - top) * scale, right * scale, (height - bottom) * scale]
            if restore:
                draw.rectangle([rect[0] - 0.5, rect[1] - 1, rect[2] + 0.5, rect[3] + 1], fill=(255, 255, 255))
                if n == widest:
                    _draw_squeezed(image, value, face, rect, size_pt * scale * 0.92)
            else:
                draw.rectangle(rect, fill=(229, 231, 235), outline=(156, 163, 175))
                if n == widest:
                    font = _fit_font(draw, value, face, rect[3] - rect[1], rect[2] - rect[0])
                    draw.text((rect[0] + 2, (rect[1] + rect[3]) / 2), value, fill=(11, 16, 38), font=font, anchor="lm")

        page_boxes = None
        if recorded is not None:
            # our own cleaned file: every recorded box gets its value, matched by label in order
            page_boxes = recorded[k] if k < len(recorded) else []
            restored_by_label: dict[str, list[str]] = {}
            for s, e, new in local:
                restored_by_label.setdefault(text[s:e].strip("[]").upper(), []).append(" ".join(new.split()))
            in_place = all(
                _grey_share(image, [r[0] * scale, (height - r[3]) * scale, r[2] * scale, (height - r[1]) * scale])
                > 0.35
                for entry in page_boxes
                for r in entry[1]
            )
            if not in_place:
                if all(_visible(tp, index, s, e) for s, e, _ in local):
                    page_boxes = None  # redrawn with real text (an AI tool made a new PDF): use its letters
                else:
                    # redrawn as a picture: where its labels are seen cannot be known for sure,
                    # and a guess could put a value in the wrong place
                    raise UnplacedLabels(f"page {k + 1} was changed after cleaning")
        if page_boxes is not None:
            for entry in page_boxes:
                label, rects = entry[0], entry[1]
                key = label.strip("[]").upper()
                queue = restored_by_label.get(key)
                value = queue.pop(0) if queue else canon.get(key)
                if value is None:
                    continue  # unknown label: left as it is
                rects = [r for r in rects]
                size_pt = entry[2] if len(entry) > 2 else max(4.0, ((rects[0][3] - rects[0][1]) - 3) * 0.95)
                widest = max(range(len(rects)), key=lambda i: rects[i][2] - rects[i][0])
                for n, r in enumerate(rects):
                    paint(r, value, size_pt, n, widest)
        elif restore:
            for s, e, _ in local:
                if not _visible(tp, index, s, e):
                    # only an invisible text layer knows this label (a scan with recognised text):
                    # its letters do not say where the label is seen
                    raise UnplacedLabels(f"page {k + 1}: the labels are not drawn as text")
            _restore_lines(image, scale, width, height, text, index, tp, local, face)
        else:
            for s, e, new in local:
                new = " ".join(new.split())  # a value may have spanned a line break in the source
                if restore and not _visible(tp, index, s, e):
                    # only an invisible text layer knows this label (a scan with recognised text):
                    # its letters do not say where the label is seen
                    raise UnplacedLabels(f"page {k + 1}: the labels are not drawn as text")
                boxes = _span_boxes(text, index, tp, s, e)
                if not boxes:
                    continue
                padx, pady = (1.2, 2.5) if restore else (0.6, 1.5)
                rects = [[x0 - padx, y0 - pady, x1 + padx, y1 + pady] for x0, y0, x1, y1 in boxes]
                size_pt = _font_size_near(tp, text, index, s, e) or (boxes[0][3] - boxes[0][1]) * 1.3
                widest = max(range(len(rects)), key=lambda i: rects[i][2] - rects[i][0])
                for n, r in enumerate(rects):
                    paint(r, new, size_pt, n, widest)
                if not restore:
                    page_record.append([new, [[round(v, 2) for v in r] for r in rects], round(size_pt, 2)])
        record.append(page_record)
        out.setPageSize((width, height))
        out.drawImage(ImageReader(image), 0, 0, width=width, height=height)
        layer = out.beginText(36, height - 36)
        layer.setTextRenderMode(3)  # invisible: present for text extraction only
        layer.setFont("Inter", 9)
        for line in "".join(page_text).splitlines():
            layer.textLine(line)
        out.drawText(layer)
        out.showPage()
        image.close()
    if not restore:
        out.setKeywords(_BOXES + json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    out.save()


def _recorded_boxes(pdf) -> list | None:
    import json

    keywords = (pdf.get_metadata_dict() or {}).get("Keywords", "")
    if not keywords.startswith(_BOXES):
        return None
    try:
        return json.loads(keywords[len(_BOXES) :])
    except ValueError:
        return None


def _line_parts(text: str, s: int, e: int):
    """(start, line) for each line of text[s:e]."""
    pos = s
    for line in text[s:e].split("\n"):
        yield pos, line
        pos += len(line) + 1


def _union(boxes: list[list[float]]) -> list[float]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


def save_clean_pdf(src: str | Path, dst: str | Path, spans: list[tuple[int, int, str]], values: list[str]) -> None:
    """A cleaned copy of a PDF that keeps its layout: the masked fragments are removed from the
    file, not just covered (pages become images), each replaced by a box with its placeholder.
    The result is checked for the masked values."""
    _rewrite_pdf(Path(src), dst, spans, restore=False)
    left = _pdf_values(Path(dst), values)
    if left:
        Path(dst).unlink(missing_ok=True)
        raise UnsafeCopy(f"{len(left)} masked values remain in the PDF")


def save_restored_pdf(
    src: str | Path, dst: str | Path, spans: list[tuple[int, int, str]], known: dict[str, str] | None = None
) -> None:
    """A PDF with placeholders (a cleaned file or an AI answer) with the real values written
    back in place, keeping the layout. ``spans`` are (start, end, value) in read_text; ``known``
    gives the value of a label seen on a page but no longer in its edited text layer."""
    _rewrite_pdf(Path(src), dst, spans, restore=True, known=known)


def _pdf_values(path: Path, values: list[str]) -> list[str]:
    _pdf, pages = _pdf_pages(path)
    whole = re.sub(r"\s+", " ", " ".join(t for t, _ in pages))
    return [v for v in values if len(v.strip()) >= 3 and re.sub(r"\s+", " ", v.strip()) in whole]


def file_hash(path: str | Path) -> str:
    import hashlib

    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def replacement_spans(
    before: str, after: str, known: dict[str, str] | None = None
) -> list[tuple[int, int, str]] | None:
    """Where each placeholder of ``before`` went in ``after`` (the restored text):
    (start, end, value) in ``before``. Restoring changes only the placeholders, so the text
    between them is the same in both. ``known`` maps placeholders to their values, which pins
    down every value restored as it was; a value whose form may change (a name inflected for
    its context) ends where the next piece of text follows and the walk can go on from there.
    The walk is linear, with a short look-ahead only after inflected names. None if the texts
    do not line up."""
    from pii_roundtrip.core import PLACEHOLDER_ANY, placeholder_parts

    known = known or {}
    canon = {k.strip("[]").upper(): v for k, v in known.items()}
    # every form the engine restores: [PERSON_1], [Person_1], [PERSON 1], [Company: ORG_1],
    # a lost bracket ([ORG_1, ORG_1]) and PERSON_1
    marks = []
    for m in PLACEHOLDER_ANY.finditer(before):
        _, t, n, _ = placeholder_parts(m)
        marks.append((m.start(), m.end(), f"{t.upper()}_{n}"))
    if not marks:
        return [] if before == after else None
    literals, prev = [], 0
    for a, b, _ in marks:
        literals.append(before[prev:a])
        prev = b
    literals.append(before[prev:])
    n = len(marks)
    failed: set[tuple[int, int]] = set()

    def walk(k: int, pos: int) -> list[str] | None:
        """Values for placeholders k.. when literal k starts at pos in after."""
        values: list[str] = []
        while True:
            lit = literals[k]
            if not after.startswith(lit, pos):
                return None
            pos += len(lit)
            if k == n:
                return values if pos == len(after) else None
            a, b, key = marks[k]
            nxt = literals[k + 1]
            exact = [v for v in {canon.get(key), before[a:b]} if v is not None and after.startswith(v + nxt, pos)]
            if len(exact) == 1 or (exact and k + 1 == n):
                values.append(exact[0])
                pos += len(exact[0])
                k += 1
                continue
            if k + 1 == n and not nxt:
                values.append(after[pos:])  # the last value runs to the end of the text
                return values
            # the value's form is not known in advance: try each place where the next text follows
            start = pos
            while True:
                end = after.find(nxt, start) if nxt else start
                if end < 0 or end - pos > 400:
                    return None
                if (k + 1, end) not in failed:
                    rest = walk(k + 1, end)
                    if rest is not None:
                        return values + [after[pos:end]] + rest
                    failed.add((k + 1, end))
                start = end + 1
                if not nxt:
                    return None

    import sys

    limit = sys.getrecursionlimit()
    sys.setrecursionlimit(max(limit, 4 * n + 100))
    try:
        values = walk(0, 0)
    finally:
        sys.setrecursionlimit(limit)
    if values is None:
        return None
    return [(a, b, v) for (a, b, _), v in zip(marks, values) if v != before[a:b]]


_ITEM = re.compile(r"^\s*(?:\d+(?:\.\d+)*\.?\s|[-–—•·*]\s|\(?[а-яa-z]\)\s|[IVX]+\.\s)")
_END = '.:;!?»)"…'


_PAGE_NO = re.compile(r"^\s*(?:Страница|Стр\.|Page)\s*\d+\s*(?:из|of|/)\s*\d+\s*$|^\s*-?\s*\d{1,4}\s*-?\s*$", re.I)


def drop_page_furniture(text: str) -> str:
    """Lines that a PDF repeats on its pages (page numbers, a stamp of electronic signing in the
    footer) do not belong in the running text: page numbers go, any other line seen on three
    pages or more is kept once, at its last place."""
    lines = text.split("\n")
    key = lambda line: re.sub(r"\d+", "#", line.strip())  # noqa: E731
    counts: dict[str, int] = {}
    for line in lines:
        if line.strip():
            counts[key(line)] = counts.get(key(line), 0) + 1
    last = {key(line): i for i, line in enumerate(lines) if line.strip()}
    out = []
    for i, line in enumerate(lines):
        if _PAGE_NO.match(line):
            continue
        if line.strip() and counts[key(line)] >= 3 and len(line.strip()) > 3 and last[key(line)] != i:
            continue
        out.append(line)
    return "\n".join(out)


def reflow(text: str) -> str:
    """Paragraphs back from the lines of a PDF: a line that does not end a sentence is joined
    with the next one when that continues it, and a word split across the lines (рабо|ты) is
    put back together when the joined word is in the dictionary. Numbered points, list items
    and blank lines keep their own lines."""
    lines = [line.rstrip() for line in text.split("\n")]
    widths = sorted(len(line) for line in lines if line.strip())
    full = widths[int(len(widths) * 0.9)] if widths else 0  # the length of a full line
    morph = None
    out: list[str] = []
    last = ""  # the previous line as it was, before joining
    for line in lines:
        before, last = last, line
        if not out or not out[-1].strip() or not line.strip() or _ITEM.match(line):
            out.append(line)
            continue
        prev = out[-1]
        nxt = line.lstrip()
        letters = [c for c in prev if c.isalpha()]
        if letters and all(c.isupper() for c in letters):
            out.append(line)  # a heading in capitals stays on its own line
            continue
        if prev.endswith(tuple(_END)) and not nxt.lstrip('«"(')[:1].islower():
            out.append(line)
            continue
        starts_upper = nxt[:1].isupper()  # a quote or a bracket does not start a new line by itself
        if starts_upper and (prev.endswith(tuple(_END)) or len(before) < 0.7 * full):
            # a short line followed by a capital: the line ended there
            out.append(line)
            continue
        glue = " "
        tail = re.search(r"([А-Яа-яЁёA-Za-z]+)-?$", prev)
        head = re.match(r"[А-Яа-яЁёA-Za-z]+", nxt)
        if tail and head and nxt[:1].islower():
            if morph is None:
                import pymorphy3

                morph = pymorphy3.MorphAnalyzer()
            whole = tail.group(1) + head.group(0)
            if morph.word_is_known(whole.lower()):
                glue = ""
                prev = prev[:-1] if prev.endswith("-") else prev
        out[-1] = prev + glue + nxt
    return "\n".join(out)


def write_docx(path: str | Path, text: str) -> None:
    """Save text as a simple Word document, one paragraph per line."""
    from docx import Document

    doc = Document()
    # the python-docx template carries its own author and comments; leave nothing behind
    props = doc.core_properties
    props.author = props.last_modified_by = props.comments = props.title = props.subject = props.keywords = ""
    props.category = props.content_status = props.identifier = props.language = props.version = ""
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(str(path))


def write_pdf(path: str | Path, text: str) -> None:
    """Save text as a simple A4 PDF in Inter (Cyrillic and Latin)."""
    from xml.sax.saxutils import escape

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY

    for name, file in (("Inter", "Inter-400.ttf"), ("Inter-Bold", "Inter-600.ttf")):
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, str(FONTS / file)))
    body = ParagraphStyle("body", fontName="Inter", fontSize=10.5, leading=15, alignment=TA_JUSTIFY, spaceAfter=5)
    short = ParagraphStyle("short", parent=body, alignment=0)  # a line or two: justifying only stretches it
    head = ParagraphStyle(
        "head", fontName="Inter-Bold", fontSize=11, leading=15, alignment=TA_CENTER, spaceBefore=8, spaceAfter=6
    )
    story = []
    for block in text.split("\n"):
        if not block.strip():
            story.append(Spacer(1, 6))
            continue
        letters = [c for c in block if c.isalpha()]
        chars = [c for c in block if not c.isspace()]
        heading = (
            len(block) < 120
            and len(letters) >= 4
            and len(letters) >= 0.6 * len(chars)  # a date with "GMT" is not a heading
            and all(c.isupper() for c in letters)
        )
        style = head if heading else (body if len(block) > 160 and " " in block.strip()[-40:] else short)
        story.append(Paragraph(escape(block.strip()), style))
    SimpleDocTemplate(
        str(path), pagesize=A4, leftMargin=20 * mm, rightMargin=20 * mm, topMargin=20 * mm, bottomMargin=20 * mm
    ).build(story)


def write_text(path: str | Path, text: str) -> None:
    Path(path).write_text(text, encoding="utf-8")


def docx_to_html(path: str | Path) -> str:
    """A formatted preview of a Word file: headers, headings, bold, italic, underline,
    alignment and tables, as HTML for a light "paper" view. Placeholders are highlighted."""
    from html import escape

    doc = _open_docx(Path(path))

    def runs_html(para) -> str:
        out = []
        for r in para.runs:
            t = escape(r.text)
            if not t:
                continue
            if r.bold:
                t = f"<b>{t}</b>"
            if r.italic:
                t = f"<i>{t}</i>"
            if r.underline:
                t = f"<u>{t}</u>"
            out.append(t)
        html = "".join(out) or escape(para.text)
        return re.sub(
            r"\[[A-Z]+(?:_[A-Z]+)*_\d+\]",
            lambda m: f"<span style='background-color:#E5E7EB;color:#0B1026;font-family:\"Space Grotesk\";font-weight:600'>&nbsp;{m.group()}&nbsp;</span>",
            html,
        )

    def para_html(para, small: bool = False) -> str:
        style = (para.style.name or "").lower() if para.style is not None else ""
        align = {1: "center", 2: "right", 3: "justify"}.get(
            int(para.alignment) if para.alignment is not None else 0, "left"
        )
        body = runs_html(para) or "&nbsp;"
        if style.startswith(("heading", "заголовок", "title")):
            size = 20 if style in ("title", "heading 1", "заголовок 1") else 16
            return f"<p style='margin:14px 0 6px 0;font-size:{size}px;font-weight:700;text-align:{align}'>{body}</p>"
        size = "12px" if small else "14px"
        return f"<p style='margin:0 0 8px 0;font-size:{size};text-align:{align}'>{body}</p>"

    from docx.table import Table
    from docx.text.paragraph import Paragraph

    parts = []
    for section in doc.sections:
        if not section.header.is_linked_to_previous:
            parts += [para_html(p, small=True) for p in section.header.paragraphs if p.text.strip()]
            parts.append("<hr style='border:none;border-top:1px solid #D1D5DB'>")
    body = _Body(doc)
    for block in body._element.iterchildren():
        tag = block.tag.rsplit("}", 1)[-1]
        if tag == "p":
            parts.append(para_html(Paragraph(block, body)))
        elif tag == "tbl":
            rows = []
            for row in Table(block, body).rows:
                cells, last = [], None
                for cell in row.cells:
                    if cell._tc is last:
                        continue
                    last = cell._tc
                    inner = "".join(para_html(p) for p in cell.paragraphs)
                    cells.append(
                        f"<td style='border:1px solid #D1D5DB;padding:6px 8px;vertical-align:top'>{inner}</td>"
                    )
                rows.append("<tr>" + "".join(cells) + "</tr>")
            parts.append(
                "<table cellspacing='0' style='border-collapse:collapse;margin:8px 0 12px 0'>"
                + "".join(rows)
                + "</table>"
            )
    for section in doc.sections:
        if not section.footer.is_linked_to_previous:
            parts.append("<hr style='border:none;border-top:1px solid #D1D5DB'>")
            parts += [para_html(p, small=True) for p in section.footer.paragraphs if p.text.strip()]
    return "<div style='font-family:Inter;color:#111827'>" + "".join(parts) + "</div>"
