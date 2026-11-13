import io
import re
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET
import fitz
from PIL import Image
from docx import Document
from docx.oxml.text.paragraph import CT_P
from docx.oxml.table import CT_Tbl
from docx.text.paragraph import Paragraph as DocxPara
from docx.table import Table as DocxTable

def ocr_pil_image(img: Image.Image, lang: str = "eng+vie") -> str:
    try:
        import pytesseract
        return pytesseract.image_to_string(img, lang=lang).strip()
    except Exception as e:
        return f"[OCR không khả dụng - cần cài Tesseract: {e}]"

def extract_pdf_smart(raw: bytes, auto_ocr: bool = False, ocr_lang: str = "eng"):
    doc = fitz.open(stream=raw, filetype="pdf")
    pages = []
    for i, page in enumerate(doc):
        blocks = page.get_text("blocks", sort=True)
        structured_lines = []
        footnote_lines = []
        page_height = page.rect.height

        for b in blocks:
            x0, y0, x1, y1, btext, block_no, block_type = b
            if block_type != 0:
                continue
            clean_b = re.sub(r"[ \t]+", " ", btext).strip()
            if not clean_b:
                continue
            # Nhận diện Footnote ở 15% cuối trang bắt đầu bằng số/ký hiệu
            if y0 > page_height * 0.85 and re.match(r"^(\d+[\.\)\s]|\*|\†)", clean_b):
                footnote_lines.append(clean_b)
            else:
                structured_lines.append(clean_b)

        main_text = "\n\n".join(structured_lines)
        footnotes = "\n".join(footnote_lines)
        full_text = main_text
        if footnotes:
            full_text += f"\n\n--- [CHÚ THÍCH CUỐI TRANG] ---\n{footnotes}"

        ocr_used = False
        if len(full_text.strip()) < 30 and len(page.get_images(full=True)) > 0 and auto_ocr:
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            ocr_txt = ocr_pil_image(img, ocr_lang)
            if ocr_txt and not ocr_txt.startswith("[OCR không khả dụng"):
                full_text = f"[OCR TỰ ĐỘNG]\n{ocr_txt}"
                ocr_used = True

        pages.append({
            "page": i + 1,
            "text": full_text,
            "footnotes": footnotes,
            "images": len(page.get_images(full=True)),
            "vectors": len(page.get_drawings()),
            "blocks": len(blocks),
            "chars": len(full_text),
            "ocr_used": ocr_used,
            "source": "PDF"
        })
    return pages, doc.page_count

def extract_docx_smart(raw: bytes):
    doc = Document(io.BytesIO(raw))
    chunks = []
    idx = 0
    for child in doc.element.body:
        if isinstance(child, CT_P):
            p = DocxPara(child, doc)
            txt = p.text.strip()
            if txt:
                idx += 1
                style_name = p.style.name if p.style else "Normal"
                prefix = f"[{style_name}] " if "Heading" in style_name else ""
                chunks.append({
                    "page": idx, "text": prefix + txt, "footnotes": "",
                    "images": 0, "vectors": 0, "blocks": 1, "chars": len(txt),
                    "ocr_used": False, "source": f"DOCX ({style_name})"
                })
        elif isinstance(child, CT_Tbl):
            t = DocxTable(child, doc)
            rows_txt = []
            for row in t.rows:
                rows_txt.append(" | ".join(c.text.replace("\n", " / ").strip() for c in row.cells))
            table_block = "[BẢNG DỮ LIỆU]\n" + "\n".join(rows_txt)
            if rows_txt:
                idx += 1
                chunks.append({
                    "page": idx, "text": table_block, "footnotes": "",
                    "images": 0, "vectors": 0, "blocks": len(t.rows), "chars": len(table_block),
                    "ocr_used": False, "source": "DOCX (Table)"
                })
    return chunks

def extract_epub_smart(raw: bytes):
    chunks = []
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        opf_files = [n for n in z.namelist() if n.endswith(".opf")]
        ordered_names = []
        if opf_files:
            try:
                opf_data = z.read(opf_files[0])
                root = ET.fromstring(opf_data)
                ns = {"opf": "http://www.idpf.org/2007/opf"}
                manifest = {}
                base_dir = str(Path(opf_files[0]).parent)
                for item in root.findall(".//opf:manifest/opf:item", ns):
                    href = item.attrib.get("href", "")
                    full_href = f"{base_dir}/{href}" if base_dir != "." else href
                    manifest[item.attrib.get("id")] = full_href
                for itemref in root.findall(".//opf:spine/opf:itemref", ns):
                    idref = itemref.attrib.get("idref")
                    if idref in manifest and manifest[idref] in z.namelist():
                        ordered_names.append(manifest[idref])
            except Exception:
                ordered_names = []

        if not ordered_names:
            ordered_names = sorted([n for n in z.namelist() if n.lower().endswith((".xhtml", ".html", ".htm"))])

        for name in ordered_names:
            try:
                data = z.read(name).decode("utf-8", "ignore")
                text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", data)
                text = re.sub(r"(?i)</(p|div|h1|h2|h3|h4|li|tr)>", "\n", text)
                text = re.sub(r"(?s)<[^>]+>", " ", text)
                text = re.sub(r"&nbsp;", " ", text)
                text = re.sub(r"&amp;", "&", text)
                text = re.sub(r"\n{3,}", "\n\n", text).strip()
                if text:
                    chunks.append({
                        "page": len(chunks) + 1, "text": text, "footnotes": "",
                        "images": 0, "vectors": 0, "blocks": 1, "chars": len(text),
                        "ocr_used": False, "source": name
                    })
            except Exception:
                pass
    return chunks
