import re
import pandas as pd

DEFAULT_TERMS = [
    ("Rehabilitation", "Phục hồi chức năng", "Phục hồi chức năng"),
    ("Range of Motion", "Tầm vận động", "Phục hồi chức năng"),
    ("Active Range of Motion", "Tầm vận động chủ động", "Phục hồi chức năng"),
    ("Passive Range of Motion", "Tầm vận động thụ động", "Phục hồi chức năng"),
    ("Muscle Strength", "Sức mạnh cơ", "Phục hồi chức năng"),
    ("Joint Mobilization", "Vận động khớp", "Phục hồi chức năng"),
    ("Tendinopathy", "Bệnh lý gân", "Cơ xương khớp"),
    ("Supraspinatus", "Cơ trên gai", "Giải phẫu"),
    ("Infraspinatus", "Cơ dưới gai", "Giải phẫu"),
    ("Subscapularis", "Cơ dưới vai", "Giải phẫu"),
    ("Teres minor", "Cơ tròn bé", "Giải phẫu"),
    ("Quadriceps", "Cơ tứ đầu đùi", "Giải phẫu"),
    ("Hamstrings", "Nhóm cơ gân kheo", "Giải phẫu"),
    ("Rotator cuff", "Chóp xoay", "Giải phẫu"),
    ("Isometric", "Đẳng trường", "Vận động học"),
    ("Isotonic", "Đẳng trương", "Vận động học"),
    ("Concentric", "Co cơ hướng tâm", "Vận động học"),
    ("Eccentric", "Co cơ ly tâm", "Vận động học"),
    ("Contraindication", "Chống chỉ định", "Lâm sàng"),
    ("Precaution", "Thận trọng", "Lâm sàng"),
    ("Myocardial infarction", "Nhồi máu cơ tim", "Tim mạch"),
    ("Hypertension", "Tăng huyết áp", "Tim mạch"),
    ("Stroke", "Đột quỵ", "Thần kinh"),
]

def find_matched_glossary(text: str, glossary_df: pd.DataFrame) -> list[dict]:
    if glossary_df is None or glossary_df.empty or not text:
        return []
    matched = []
    text_lower = text.lower()
    for _, r in glossary_df.iterrows():
        src_term = str(r.get("Thuật ngữ gốc", "")).strip()
        tgt_term = str(r.get("Bản dịch ưu tiên", "")).strip()
        domain = str(r.get("Lĩnh vực", "Chung")).strip()
        if not src_term or not tgt_term:
            continue
        pattern = r"\b" + re.escape(src_term.lower()) + r"\b"
        if re.search(pattern, text_lower):
            matched.append({"src": src_term, "tgt": tgt_term, "domain": domain})
    matched.sort(key=lambda x: len(x["src"]), reverse=True)
    return matched

def build_global_rolling_memory(records: list[dict], current_page: int, max_items: int = 3) -> str:
    prev_records = [r for r in records if r["page"] < current_page]
    prev_records.sort(key=lambda x: x["page"], reverse=True)
    selected = prev_records[:max_items]
    if not selected:
        return "(Đây là phần đầu tiên được dịch, chưa có lịch sử chương trước.)"
    snippets = []
    for r in reversed(selected):
        tr_tail = r.get("translation", "")[-450:]
        snippets.append(f"[Phần {r['page']} đã dịch]: ...{tr_tail}")
    return "\n".join(snippets)
