import io
import os
from docx import Document
from docx.shared import RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def build_docx_pro(records: list[dict], title: str, version: str = "1.0 PRO", bilingual: bool = False) -> bytes:
    doc = Document()
    h = doc.add_heading(title, 0)
    h.alignment = WD_ALIGN_PARAGRAPH.CENTER
    sub = doc.add_paragraph(f"Xuất bản từ BOOKMASTER AI {version} · Chế độ: {'Song ngữ đối chiếu' if bilingual else 'Bản dịch hoàn chỉnh'}")
    sub.alignment = WD_ALIGN_PARAGRAPH.CENTER

    for r in records:
        doc.add_heading(f"Phần / Trang {r['page']} (Trạng thái: {r.get('workflow_status', 'Đã dịch')})", level=2)
        if bilingual:
            tbl = doc.add_table(rows=2, cols=2)
            tbl.style = "Table Grid"
            tbl.cell(0, 0).text = "NGUYÊN BẢN (SOURCE)"
            tbl.cell(0, 1).text = "BẢN DỊCH HIỆU ĐÍNH (TARGET)"
            for cell in tbl.rows[0].cells:
                for p in cell.paragraphs:
                    for run in p.runs:
                        run.bold = True
            tbl.cell(1, 0).text = r.get("source", "")
            tbl.cell(1, 1).text = r.get("translation", "")
            doc.add_paragraph("")
        else:
            for para in r.get("translation", "").split("\n\n"):
                if para.strip():
                    doc.add_paragraph(para.strip())

        issues = r.get("qa", {}).get("issues", [])
        if issues:
            p_qa = doc.add_paragraph()
            run_lbl = p_qa.add_run("⚠ Ghi chú Kiểm định QA: ")
            run_lbl.bold = True
            run_lbl.font.color.rgb = RGBColor(180, 83, 9)
            p_qa.add_run("; ".join(x.get("detail", "") for x in issues))

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()

def build_pdf_pro(records: list[dict], title: str, version: str = "1.0 PRO") -> bytes:
    buf = io.BytesIO()
    styles = getSampleStyleSheet()
    font_name = "Helvetica"
    for candidate in [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:\\Windows\\Fonts\\arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf"
    ]:
        if os.path.exists(candidate):
            try:
                pdfmetrics.registerFont(TTFont("VNFont", candidate))
                font_name = "VNFont"
                break
            except Exception:
                pass

    styles.add(ParagraphStyle(name="VNBody", parent=styles["BodyText"], fontName=font_name, fontSize=10, leading=14, spaceAfter=8))
    styles.add(ParagraphStyle(name="VNHead", parent=styles["Heading2"], fontName=font_name, fontSize=12, spaceBefore=12, spaceAfter=6))
    styles.add(ParagraphStyle(name="VNTitle", parent=styles["Title"], fontName=font_name, fontSize=16, spaceAfter=12))

    story = [
        Paragraph(title, styles["VNTitle"]),
        Paragraph(f"Tài liệu dịch thuật chuyên ngành — BOOKMASTER AI {version}", styles["VNBody"]),
        Spacer(1, 12)
    ]
    for r in records:
        story.append(Paragraph(f"Phần / Trang {r['page']}", styles["VNHead"]))
        txt = (r.get("translation", "") or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
        story.append(Paragraph(txt, styles["VNBody"]))

    SimpleDocTemplate(buf, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42, bottomMargin=42).build(story)
    return buf.getvalue()
