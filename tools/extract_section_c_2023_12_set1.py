from pathlib import Path
import re

src = Path(r"d:/postgraduate_exam/postgraduate_admission_exam_journey/大学英语六级/_tmp_2023_12_set1.txt")
out = Path(r"d:/postgraduate_exam/postgraduate_admission_exam_journey/大学英语六级/_tmp_2023_12_set1_section_c.txt")

text = src.read_text(encoding="utf-8")

m = re.search(r"Section C(.*?)(?:Part IV Translation|Part IV)", text, flags=re.S)
if not m:
    print("Section C not found")
    raise SystemExit(1)

section_c = m.group(1)
out.write_text(section_c, encoding="utf-8")
print("Wrote", out)
