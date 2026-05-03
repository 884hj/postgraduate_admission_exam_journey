from pathlib import Path
import pdfplumber

p = Path(r'd:/postgraduate_exam/postgraduate_admission_exam_journey/大学英语六级/2024.12六级真题第3套【可复制可检索】.pdf')
out = p.parent / '_tmp_2024_12_set3.txt'

if p.exists():
    with pdfplumber.open(p) as pdf:
        text = ""
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    out.write_text(text, encoding='utf-8')
    print("Extracted to", out)
else:
    print("File not found:", p)
