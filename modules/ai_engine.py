import re
import json
import time
import urllib.request
import urllib.error
from collections import Counter

REGISTER_PROFILES = {
    "Hàn lâm / Bác sĩ chuyên khoa": "Văn phong y khoa chuẩn mực, hàn lâm, súc tích, giữ nguyên tính chất khoa học chuyên sâu dành cho bác sĩ, giảng viên và nhà nghiên cứu.",
    "Giáo trình / Sinh viên Y khoa": "Văn phong sư phạm y khoa rõ ràng, mạch lạc, giải thích chính xác cơ chế bệnh sinh và kỹ thuật lâm sàng dành cho sinh viên y dược.",
    "Y học thường thức / Bệnh nhân": "Văn phong y khoa dễ hiểu, thân thiện với người bệnh nhưng tuyệt đối không làm sai lệch bản chất y học và các cảnh báo an toàn.",
}

def deterministic_qa_audit(source: str, translation: str, matched_terms: list[dict]) -> list[dict]:
    issues = []
    src_nums = Counter(re.findall(r"\b\d+(?:[\.,]\d+)?\b", source))
    tgt_nums = Counter(re.findall(r"\b\d+(?:[\.,]\d+)?\b", translation))
    for num, count in src_nums.items():
        alt_num = num.replace(".", ",") if "." in num else num.replace(",", ".")
        tgt_count = tgt_nums.get(num, 0) + tgt_nums.get(alt_num, 0)
        if tgt_count < count:
            issues.append({
                "type": "Sai lệch số liệu/Liều lượng",
                "severity": "high",
                "detail": f"Số '{num}' xuất hiện {count} lần ở bản gốc nhưng chỉ thấy {tgt_count} lần ở bản dịch.",
                "suggestion": f"Kiểm tra lại toàn bộ số liệu và đơn vị đo lường chứa '{num}'."
            })

    tgt_lower = translation.lower()
    for item in matched_terms:
        if item["tgt"].lower() not in tgt_lower:
            issues.append({
                "type": "Vi phạm từ điển khóa (Glossary)",
                "severity": "high",
                "detail": f"Thuật ngữ gốc '{item['src']}' yêu cầu dịch là '{item['tgt']}' nhưng không tìm thấy trong bản dịch.",
                "suggestion": f"Sửa lại theo đúng chuẩn từ điển: {item['src']} -> {item['tgt']}."
            })

    if "--- [CHÚ THÍCH CUỐI TRANG] ---" in source and "CHÚ THÍCH" not in translation.upper():
        issues.append({
            "type": "Mất khối chú thích",
            "severity": "medium",
            "detail": "Bản gốc có phần Chú thích cuối trang (Footnotes) nhưng bản dịch bị thiếu nhãn phân tách.",
            "suggestion": "Đối chiếu lại phần chú thích cuối trang của nguyên bản."
        })
    return issues

def call_chat_resilient(base_url, api_key, model, messages, temperature=0.1, retries=3):
    url = base_url.rstrip("/") + "/chat/completions"
    payload = json.dumps({"model": model, "messages": messages, "temperature": temperature}).encode()
    for attempt in range(retries):
        req = urllib.request.Request(
            url, data=payload,
            headers={"Authorization": "Bearer " + api_key, "Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                obj = json.loads(r.read().decode())
            return obj["choices"][0]["message"]["content"].strip()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(2 ** (attempt + 1))
                continue
            detail = e.read().decode("utf-8", "ignore")[:1000]
            raise RuntimeError(f"API HTTP {e.code}: {detail}")
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2)
                continue
            raise RuntimeError(f"Lỗi kết nối AI: {e}")

def translate_super_cat(text, neighbor_ctx, global_mem, matched_terms, register_desc, target, base, key, model):
    if matched_terms:
        locked_glossary_str = "\n".join(
            f"- \"{m['src']}\"  ===>  BẮT BUỘC DỊCH LÀ: \"{m['tgt']}\" (Chuyên ngành: {m['domain']})"
            for m in matched_terms
        )
    else:
        locked_glossary_str = "(Không có thuật ngữ khóa đặc biệt trong đoạn này)"

    system = f"""Bạn là Chuyên gia Dịch thuật Y khoa & Học thuật cao cấp. Hãy dịch văn bản sang {target}.
ĐỊNH HƯỚNG VĂN PHONG (REGISTER): {register_desc}

QUY TẮC BẮT BUỘC (KHÔNG ĐƯỢC VI PHẠM):
1. KHÓA THUẬT NGỮ (GLOSSARY LOCK): Bắt buộc sử dụng chính xác 100% các thuật ngữ tiếng Việt được quy định dưới đây:
{locked_glossary_str}
2. BẢO TOÀN ĐỊNH DẠNG & CẤU TRÚC: Giữ nguyên cấu trúc đoạn văn, tiêu đề [Heading], cấu trúc bảng [BẢNG DỮ LIỆU] (giữ nguyên dấu phân cách |), và khối --- [CHÚ THÍCH CUỐI TRANG] ---.
3. AN TOÀN Y KHOA: Giữ nguyên tuyệt đối mọi con số, liều lượng thuốc, đơn vị đo lường, ký hiệu giải phẫu (trái/phải), công thức và các từ phủ định (không, chống chỉ định, ngoại trừ).
4. Không tóm tắt, không lược bỏ, không thêm lời bình luận ngoài bản dịch."""

    user = f"""=== BỘ NHỚ NGỮ CẢNH CÁC PHẦN TRƯỚC (Để giữ sự liền mạch văn phong toàn sách) ===
{global_mem}

=== NGỮ CẢNH LIỀN KỀ TRƯỚC/SAU (Chỉ tham khảo mạch ý, không dịch lại) ===
{neighbor_ctx}

=== VĂN BẢN GỐC CẦN DỊCH ===
{text}"""

    return call_chat_resilient(base, key, model, [{"role": "system", "content": system}, {"role": "user", "content": user}], 0.1)

def back_translate(text, source_lang, base, key, model):
    return call_chat_resilient(base, key, model, [
        {"role": "system", "content": f"Translate the following medical/academic text back into {source_lang}. Preserve exact meaning, numbers, dosages, negation, and anatomical terms. Return only the back-translation."},
        {"role": "user", "content": text}
    ], 0.0)

def qa_semantic_audit(original, translated, back, base, key, model):
    prompt = f"""Bạn là Thẩm định viên Chất lượng Dịch thuật Y khoa độc lập. Hãy đối chiếu Bản gốc, Bản dịch và Bản dịch ngược.
Kiểm tra sâu: (1) Sai lệch ý nghĩa lâm sàng; (2) Đảo ngược phủ định/chống chỉ định; (3) Nhầm lẫn giải phẫu trái-phải/hướng vận động; (4) Thiếu sót nội dung.
Trả về DUY NHẤT một chuỗi JSON hợp lệ theo cấu trúc:
{{"status":"Xanh|Vàng|Đỏ","score":0-100,"issues":[{{"type":"...","severity":"low|medium|high","detail":"...","suggestion":"..."}}],"summary":"..."}}

ORIGINAL:
{original}

TRANSLATION:
{translated}

BACK TRANSLATION:
{back}"""
    raw = call_chat_resilient(base, key, model, [
        {"role": "system", "content": "You are a strict medical translation auditor. Output valid JSON only."},
        {"role": "user", "content": prompt}
    ], 0.0)
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        raise ValueError("QA AI không trả về JSON hợp lệ")
    return json.loads(m.group(0))
