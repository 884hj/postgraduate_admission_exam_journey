from pathlib import Path
import pdfplumber

pdf_path = Path(r"d:/postgraduate_exam/postgraduate_admission_exam_journey/大学英语六级/2023.12六级真题第1套【可复制可检索，打印首选】.pdf")
out_txt = pdf_path.parent / "_tmp_2023_12_set1.txt"

if not pdf_path.exists():
    print("File not found:", pdf_path)
    raise SystemExit(1)

text_parts = []
with pdfplumber.open(str(pdf_path)) as pdf:
    for page in pdf.pages:
        t = page.extract_text() or ""
        text_parts.append(t)

out_txt.write_text("\n".join(text_parts), encoding="utf-8")
print("Extracted to", out_txt)
