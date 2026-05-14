import sys
from pathlib import Path

pdf_path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
out_path = Path(sys.argv[2]) if len(sys.argv) > 2 else Path(pdf_path.parent) / (pdf_path.stem + '.txt')

if pdf_path is None or not pdf_path.exists():
    print('Usage: python extract_pdf_to_txt.py <pdf_path> [out_path]')
    sys.exit(1)

try:
    import pdfplumber
    with pdfplumber.open(str(pdf_path)) as pdf:
        with out_path.open('w', encoding='utf-8') as f:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text:
                    f.write(text + '\n')
    print(f'Extracted text to {out_path}')
except Exception as e:
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        with out_path.open('w', encoding='utf-8') as f:
            for page in doc:
                text = page.get_text()
                if text:
                    f.write(text + '\n')
        print(f'Extracted text to {out_path} using PyMuPDF')
    except Exception as e2:
        print('Failed to extract text:', e)
        print('Fallback also failed:', e2)
        sys.exit(2)
