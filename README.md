# BOOKMASTER AI 1.0 PRO — SUPER-CAT EDITION (Modular Architecture)

Phiên bản nâng cấp toàn diện theo kiến trúc **Modular** chuyên nghiệp dành cho dịch thuật sách y khoa, giải phẫu, phục hồi chức năng và học thuật.

## Cấu trúc thư mục dự án
```text
BOOKMASTER_AI_1.0_PRO_MODULAR/
├── app.py                            # Giao diện điều khiển chính (Bilingual CAT Workspace)
├── requirements.txt                  # Danh sách thư viện Python cần thiết
├── run_windows.bat                   # Script khởi chạy nhanh trên Windows
├── run_mac_linux.sh                  # Script khởi chạy nhanh trên macOS / Linux
├── data/
│   └── sample_medical_glossary.csv   # Bộ từ điển thuật ngữ y khoa chuẩn mẫu
└── modules/
    ├── __init__.py
    ├── parsers.py                    # Module bóc tách PDF (tọa độ khối + Footnotes), DOCX, EPUB, OCR
    ├── glossary_tm.py                # Module Khóa thuật ngữ chủ động & Bộ nhớ ngữ cảnh xuyên chương
    ├── ai_engine.py                  # Module Dịch thuật chuyên sâu & Kiểm định chất lượng kép (Hybrid QA)
    └── exporters.py                  # Module Xuất bản Word đơn ngữ, Word song ngữ 2 cột & PDF Unicode
```

## Hướng dẫn khởi chạy
1. **Trên Windows:** Nhấp đúp chuột vào tệp `run_windows.bat`.
2. **Trên macOS / Linux:** Mở Terminal tại thư mục này và chạy:
   ```bash
   chmod +x run_mac_linux.sh
   ./run_mac_linux.sh
   ```
