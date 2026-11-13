from __future__ import annotations
import io, json, hashlib
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
import pandas as pd
from PIL import Image

from modules.parsers import extract_pdf_smart, extract_docx_smart, extract_epub_smart, ocr_pil_image
from modules.glossary_tm import DEFAULT_TERMS, find_matched_glossary, build_global_rolling_memory
from modules.ai_engine import (
    REGISTER_PROFILES,
    deterministic_qa_audit,
    translate_super_cat,
    back_translate,
    qa_semantic_audit,
)
from modules.exporters import build_docx_pro, build_pdf_pro

APP = "BOOKMASTER AI — SUPER-CAT EDITION"
VERSION = "1.0 PRO (Modular)"

st.set_page_config(page_title=APP, page_icon="🩺", layout="wide")
st.markdown("""
<style>
.block-container{padding-top:1.1rem;max-width:1650px}
div[data-testid="stMetric"]{background:#f8fafc;border:1px solid #cbd5e1;padding:12px;border-radius:12px}
.term-badge{display:inline-block;background:#e0f2fe;color:#0369a1;padding:2px 8px;border-radius:6px;margin:2px;font-size:0.85rem;border:1px solid #bae6fd}
.qa-pass{color:#15803d;font-weight:600}
.qa-warn{color:#b45309;font-weight:600}
.qa-fail{color:#b91c1c;font-weight:600}
</style>""", unsafe_allow_html=True)

st.title("🩺 BOOKMASTER AI — SUPER-CAT EDITION")
st.caption(f"Phiên bản {VERSION} · Kiến trúc Modular Chuyên Sâu cho Dịch Thuật Sách Y Khoa & Học Thuật")

if "glossary" not in st.session_state:
    st.session_state.glossary = pd.DataFrame(DEFAULT_TERMS, columns=["Thuật ngữ gốc", "Bản dịch ưu tiên", "Lĩnh vực"])
if "records" not in st.session_state:
    st.session_state.records = []
if "source_pages" not in st.session_state:
    st.session_state.source_pages = []
if "source_name" not in st.session_state:
    st.session_state.source_name = ""
if "source_hash" not in st.session_state:
    st.session_state.source_hash = ""

with st.sidebar:
    st.header("1. Nhập Bản Thảo Sách")
    auto_ocr = st.checkbox("Tự động OCR trang PDF scan (cần Tesseract)", value=False)
    up = st.file_uploader("Tải tài liệu (PDF, DOCX, EPUB, Ảnh)", type=["pdf", "docx", "epub", "png", "jpg", "jpeg", "tif", "tiff"])
    if up:
        raw = up.getvalue()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != st.session_state.source_hash:
            try:
                ext = Path(up.name).suffix.lower()
                if ext == ".pdf":
                    pages, _ = extract_pdf_smart(raw, auto_ocr=auto_ocr)
                elif ext == ".docx":
                    pages = extract_docx_smart(raw)
                elif ext == ".epub":
                    pages = extract_epub_smart(raw)
                else:
                    txt = ocr_pil_image(Image.open(io.BytesIO(raw)), "eng+vie")
                    pages = [{"page": 1, "text": txt, "footnotes": "", "images": 1, "vectors": 0, "blocks": 1, "chars": len(txt), "ocr_used": True, "source": "Image"}]
                st.session_state.source_pages = pages
                st.session_state.source_name = up.name
                st.session_state.source_hash = digest
                st.session_state.records = []
                st.success(f"Đã phân tích cấu trúc: {len(pages)} đơn vị nội dung.")
            except Exception as e:
                st.error(f"Lỗi đọc tài liệu: {e}")

    st.header("2. Cấu Hình AI & Văn Phong")
    base = st.text_input("API Base URL", value="https://api.openai.com/v1")
    model = st.text_input("Model AI", value="gpt-4.1-mini")
    key = st.text_input("API Key", type="password", help="Chỉ lưu trong RAM phiên làm việc, không lưu ra file.")
    source_lang = st.text_input("Ngôn ngữ gốc", value="English")
    target = st.selectbox("Ngôn ngữ đích", ["Tiếng Việt", "English", "Français", "日本語", "中文"])
    register_choice = st.selectbox("Chế độ Văn phong (Register)", list(REGISTER_PROFILES.keys()))
    batch = st.number_input("Số phần tối đa mỗi lượt chạy", min_value=1, max_value=50, value=5)
    run_back_trans = st.checkbox("Bật Dịch ngược & Thẩm định QA AI", value=True, help="Tăng độ chính xác y khoa nhưng tốn thêm token API.")

if not st.session_state.source_pages:
    st.info("👈 Vui lòng tải bản thảo sách (PDF, DOCX, EPUB) ở thanh bên trái để khởi động không gian làm việc Super-CAT.")
    st.markdown("""
    ### Kiến trúc Modular của BOOKMASTER AI 1.0 PRO:
    * `modules/parsers.py`: Bóc tách PDF theo tọa độ khối, tách riêng **Chú thích cuối trang (Footnotes)**, giữ cấu trúc bảng DOCX & mục lục EPUB.
    * `modules/glossary_tm.py`: **Glossary Force-Injection** (Khóa thuật ngữ chủ động) & **Global Rolling Context** (Bộ nhớ ngữ cảnh xuyên chương).
    * `modules/ai_engine.py`: Động cơ dịch thuật chuyên ngành y khoa kết hợp **Hybrid QA** (Kiểm tra cơ học số liệu/liều lượng + Dịch ngược thẩm định lâm sàng).
    * `modules/exporters.py`: Xuất bản Word đơn ngữ, Word song ngữ đối chiếu 2 cột và PDF hỗ trợ font tiếng Việt chuẩn.
    """)
    st.stop()

pages = st.session_state.source_pages
df_audit = pd.DataFrame([{k: v for k, v in p.items() if k not in ("text", "footnotes")} for p in pages])

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Tổng đơn vị/trang", f"{len(pages):,}")
c2.metric("Tổng ký tự", f"{sum(p['chars'] for p in pages):,}")
c3.metric("Thuật ngữ từ điển", f"{len(st.session_state.glossary):,}")
c4.metric("Đã dịch", f"{len(st.session_state.records):,}")
approved_cnt = sum(1 for r in st.session_state.records if r.get("workflow_status") == "Đã duyệt xuất bản")
c5.metric("Đã duyệt xuất bản", f"{approved_cnt:,}")

tabs = st.tabs([
    "🧾 1. Phân tích cấu trúc đầu vào",
    "📖 2. Từ điển chuyên ngành (Glossary)",
    "🌐 3. Không gian Dịch & Biên tập Song ngữ",
    "📤 4. Xuất bản & Lưu trữ Dự án"
])

with tabs[0]:
    st.subheader(f"Kiểm toán cấu trúc tệp: {st.session_state.source_name}")
    st.dataframe(df_audit, use_container_width=True, hide_index=True, height=260)
    idx = st.number_input("Xem chi tiết phần/trang số", 1, len(pages), 1) - 1
    p = pages[int(idx)]

    matched_preview = find_matched_glossary(p["text"], st.session_state.glossary)
    if matched_preview:
        badges = " ".join([f"<span class='term-badge'><b>{m['src']}</b> → {m['tgt']}</span>" for m in matched_preview])
        st.markdown(f"**Thuật ngữ từ điển phát hiện trong phần này ({len(matched_preview)}):**<br>{badges}", unsafe_allow_html=True)

    col_txt, col_fn = st.columns([3, 1])
    with col_txt:
        st.text_area("Nội dung bóc tách (Đã bảo toàn cấu trúc)", p["text"], height=320)
    with col_fn:
        st.text_area("Chú thích cuối trang nhận diện", p.get("footnotes", "") or "(Không có chú thích)", height=320)

with tabs[1]:
    st.subheader("Cơ sở dữ liệu Thuật ngữ Khóa (Glossary Lock)")
    st.caption("Mọi thuật ngữ trong bảng này sẽ tự động được nhận diện trong văn bản gốc và ép AI tuân thủ tuyệt đối khi dịch.")
    st.session_state.glossary = st.data_editor(
        st.session_state.glossary,
        num_rows="dynamic",
        use_container_width=True,
        key="glossary_pro_editor"
    )
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.download_button(
            "⬇ Xuất từ điển CSV",
            st.session_state.glossary.to_csv(index=False).encode("utf-8-sig"),
            "bookmaster_medical_glossary.csv",
            "text/csv"
        )
    with col_g2:
        gfile = st.file_uploader("Nhập từ điển từ CSV hoặc Excel (.xlsx)", type=["csv", "xlsx"], key="glossary_upload_pro")
        if gfile:
            try:
                new_df = pd.read_excel(gfile) if gfile.name.endswith(".xlsx") else pd.read_csv(gfile)
                if {"Thuật ngữ gốc", "Bản dịch ưu tiên"}.issubset(set(new_df.columns)):
                    if "Lĩnh vực" not in new_df.columns:
                        new_df["Lĩnh vực"] = "Y khoa"
                    st.session_state.glossary = new_df[["Thuật ngữ gốc", "Bản dịch ưu tiên", "Lĩnh vực"]]
                    st.success(f"Đã nạp thành công {len(new_df)} thuật ngữ chuyên ngành!")
                else:
                    st.error("File từ điển cần có ít nhất 2 cột: 'Thuật ngữ gốc' và 'Bản dịch ưu tiên'.")
            except Exception as e:
                st.error(f"Lỗi đọc từ điển: {e}")

with tabs[2]:
    st.subheader("Trạm Dịch thuật & Biên tập Song ngữ (CAT Workspace)")

    c_run1, c_run2, c_run3, c_run4 = st.columns([1, 1, 1.5, 1.5])
    start = c_run1.number_input("Từ phần", 1, len(pages), 1, key="start_pro")
    end = c_run2.number_input("Đến phần", int(start), len(pages), min(len(pages), int(start) + int(batch) - 1), key="end_pro")
    context_chars = c_run3.slider("Ngữ cảnh liền kề (ký tự)", 0, 2500, 800, 100)
    overwrite_existing = c_run4.checkbox("Dịch lại cả các phần đã có", value=False)

    if st.button("▶ Chạy Siêu Dịch Thuật + Kiểm Định QA", type="primary", disabled=not bool(key)):
        existing_map = {r["page"]: i for i, r in enumerate(st.session_state.records)}
        prog = st.progress(0)
        status = st.empty()
        total_steps = int(end) - int(start) + 1
        try:
            for step, j in enumerate(range(int(start) - 1, int(end))):
                page_num = j + 1
                src = pages[j]["text"]
                if not src.strip():
                    continue
                if page_num in existing_map and not overwrite_existing:
                    prog.progress((step + 1) / total_steps)
                    continue

                status.info(f"⏳ Đang xử lý phần {page_num}/{len(pages)}: Khớp từ điển & dịch chuyên sâu...")
                matched_terms = find_matched_glossary(src, st.session_state.glossary)
                before = pages[j - 1]["text"][-context_chars:] if j > 0 and context_chars else ""
                after = pages[j + 1]["text"][:context_chars] if j + 1 < len(pages) and context_chars else ""
                neighbor_ctx = f"Đoạn trước: {before}\nĐoạn sau: {after}"
                global_mem = build_global_rolling_memory(st.session_state.records, page_num)

                tr = translate_super_cat(
                    src, neighbor_ctx, global_mem, matched_terms,
                    REGISTER_PROFILES[register_choice], target, base, key, model
                )

                det_issues = deterministic_qa_audit(src, tr, matched_terms)

                back = ""
                ai_qa = {"status": "Xanh", "score": 95, "issues": [], "summary": "Đã kiểm tra cơ học."}
                if run_back_trans:
                    status.info(f"🔍 Đang dịch ngược & thẩm định lâm sàng phần {page_num}...")
                    back = back_translate(tr, source_lang, base, key, model)
                    try:
                        ai_qa = qa_semantic_audit(src, tr, back, base, key, model)
                    except Exception as qerr:
                        ai_qa = {"status": "Vàng", "score": None, "issues": [], "summary": f"Lỗi QA AI: {qerr}"}

                all_issues = det_issues + ai_qa.get("issues", [])
                final_status = ai_qa.get("status", "Xanh")
                if any(i.get("severity") == "high" for i in det_issues):
                    final_status = "Đỏ"
                elif det_issues and final_status == "Xanh":
                    final_status = "Vàng"

                final_qa = {
                    "status": final_status,
                    "score": ai_qa.get("score"),
                    "issues": all_issues,
                    "summary": ai_qa.get("summary", "")
                }

                new_rec = {
                    "page": page_num,
                    "source": src,
                    "translation": tr,
                    "back_translation": back,
                    "matched_terms": matched_terms,
                    "qa": final_qa,
                    "workflow_status": "Chờ hiệu đính",
                    "reviewer_note": ""
                }

                if page_num in existing_map:
                    st.session_state.records[existing_map[page_num]] = new_rec
                else:
                    st.session_state.records.append(new_rec)

                prog.progress((step + 1) / total_steps)
            status.success("✅ Hoàn tất phiên dịch thuật và thẩm định chất lượng!")
        except Exception as e:
            status.error(f"❌ Dừng xử lý do lỗi: {e}")

    st.divider()

    if st.session_state.records:
        rr = sorted(st.session_state.records, key=lambda x: x["page"])
        options = [r["page"] for r in rr]
        chosen = st.selectbox(
            "Chọn phần để hiệu đính song ngữ",
            options,
            format_func=lambda p_no: f"Phần {p_no} — [{next(x['workflow_status'] for x in rr if x['page'] == p_no)}] (QA: {next(x['qa']['status'] for x in rr if x['page'] == p_no)})"
        )
        r = next(x for x in rr if x["page"] == chosen)

        m_terms = r.get("matched_terms", [])
        if m_terms:
            badges = " ".join([f"<span class='term-badge'>🔒 <b>{m['src']}</b> = {m['tgt']}</span>" for m in m_terms])
            st.markdown(f"**Thuật ngữ đã khóa trong đoạn này:** {badges}", unsafe_allow_html=True)

        col_src, col_tgt = st.columns(2)
        with col_src:
            st.markdown("**📄 Nguyên bản (Source)**")
            st.text_area("Source", r["source"], height=380, label_visibility="collapsed", key=f"src_view_{chosen}")
        with col_tgt:
            st.markdown("**✍️ Bản dịch Hiệu đính (Target - Sửa trực tiếp)**")
            edited_tr = st.text_area("Target", r["translation"], height=380, label_visibility="collapsed", key=f"tgt_edit_{chosen}")

        col_wf1, col_wf2, col_wf3 = st.columns([1.2, 2, 1])
        wf_options = ["Chờ hiệu đính", "Đang thảo luận chuyên môn", "Đã duyệt xuất bản"]
        curr_wf_idx = wf_options.index(r.get("workflow_status", "Chờ hiệu đính")) if r.get("workflow_status") in wf_options else 0
        new_wf = col_wf1.selectbox("Trạng thái quy trình", wf_options, index=curr_wf_idx, key=f"wf_{chosen}")
        new_note = col_wf2.text_input("Ghi chú dịch giả / Hội chẩn thuật ngữ", value=r.get("reviewer_note", ""), key=f"note_{chosen}")

        with col_wf3:
            st.write("")
            st.write("")
            if st.button("💾 Lưu Hiệu Đính", use_container_width=True, key=f"save_btn_{chosen}"):
                r["translation"] = edited_tr
                r["workflow_status"] = new_wf
                r["reviewer_note"] = new_note
                det_recheck = deterministic_qa_audit(r["source"], edited_tr, m_terms)
                r["qa"]["issues"] = det_recheck + [i for i in r["qa"].get("issues", []) if i.get("type") not in ("Sai lệch số liệu/Liều lượng", "Vi phạm từ điển khóa (Glossary)")]
                st.success(f"Đã lưu hiệu đính cho Phần {chosen}!")

        qa = r.get("qa", {})
        q_stat = qa.get("status", "Chưa rõ")
        css_cls = {"Xanh": "qa-pass", "Vàng": "qa-warn", "Đỏ": "qa-fail"}.get(q_stat, "")
        st.markdown(f"**Báo cáo Thẩm định QA:** <span class='{css_cls}'>{q_stat}</span> · Điểm tham khảo: **{qa.get('score', '—')}** — {qa.get('summary', '')}", unsafe_allow_html=True)

        if qa.get("issues"):
            st.dataframe(pd.DataFrame(qa["issues"]), use_container_width=True, hide_index=True)

        if r.get("back_translation"):
            with st.expander("🔄 Xem bản Dịch ngược đối chiếu (Back-translation)"):
                st.write(r["back_translation"])

with tabs[3]:
    st.subheader("Xuất Bản Thảo & Lưu Trữ Dự Án")
    if not st.session_state.records:
        st.info("Chưa có dữ liệu bản dịch để xuất.")
    else:
        records = sorted(st.session_state.records, key=lambda x: x["page"])
        doc_title = st.text_input("Tên sách / Tài liệu xuất bản", Path(st.session_state.source_name).stem)

        col_ex1, col_ex2, col_ex3 = st.columns(3)
        with col_ex1:
            st.download_button(
                "⬇ Xuất Word Hoàn Chỉnh (.docx)",
                build_docx_pro(records, doc_title, VERSION, bilingual=False),
                file_name=f"{doc_title}_BanDich.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        with col_ex2:
            st.download_button(
                "⬇ Xuất Word Song Ngữ Đối Chiếu (.docx)",
                build_docx_pro(records, doc_title, VERSION, bilingual=True),
                file_name=f"{doc_title}_SongNgu.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                use_container_width=True
            )
        with col_ex3:
            st.download_button(
                "⬇ Xuất PDF Tiếng Việt Chuẩn (.pdf)",
                build_pdf_pro(records, doc_title, VERSION),
                file_name=f"{doc_title}_BanDich.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        st.divider()
        st.markdown("### 💾 Sao lưu & Khôi phục Phiên làm việc (Project Snapshot)")
        project_snapshot = {
            "app": APP,
            "version": VERSION,
            "source_name": st.session_state.source_name,
            "source_sha256": st.session_state.source_hash,
            "glossary": st.session_state.glossary.to_dict(orient="records"),
            "records": records,
            "saved_at": datetime.now(timezone.utc).isoformat()
        }
        st.download_button(
            "💾 Tải tệp Dự án (.json) về máy",
            json.dumps(project_snapshot, ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=f"{doc_title}_project_v1.json",
            mime="application/json"
        )

    restore = st.file_uploader("Khôi phục dự án từ tệp JSON đã lưu", type=["json"], key="restore_pro")
    if restore and st.button("Nạp dữ liệu dự án"):
        try:
            obj = json.load(restore)
            st.session_state.records = obj.get("records", [])
            st.session_state.glossary = pd.DataFrame(
                obj.get("glossary", DEFAULT_TERMS),
                columns=["Thuật ngữ gốc", "Bản dịch ưu tiên", "Lĩnh vực"]
            )
            st.success("Đã khôi phục toàn bộ tiến độ dịch, từ điển và ghi chú hiệu đính!")
        except Exception as e:
            st.error(f"Lỗi khôi phục dự án: {e}")
