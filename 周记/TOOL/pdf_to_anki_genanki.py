import json
import re
import sqlite3
import tempfile
import uuid
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple

import genanki


def read_source_text(input_path: Path) -> str:
    suffix = input_path.suffix.lower()
    if suffix == ".txt":
        return input_path.read_text(encoding="utf-8")

    if suffix == ".pdf":
        import pdfplumber

        chunks = []
        with pdfplumber.open(str(input_path)) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    chunks.append(text)
        return "\n".join(chunks)

    raise ValueError("仅支持 .txt 或 .pdf 输入")


def split_sections(text: str) -> Dict[str, str]:
    m_answers = re.search(r"参考答案", text)
    if not m_answers:
        return {"question_part": text, "answer_part": ""}

    return {
        "question_part": text[: m_answers.start()],
        "answer_part": text[m_answers.start() :],
    }


def extract_fill_questions(question_part: str) -> List[Dict[str, object]]:
    lines = [ln.strip() for ln in question_part.splitlines()]
    questions = []
    qid = 1
    for ln in lines:
        if "______" in ln and len(ln) >= 6:
            blanks = ln.count("______")
            questions.append({"id": qid, "front": f"填空题 {qid}<br><br>{ln}", "blanks": blanks})
            qid += 1
    return questions


def extract_fill_answers(answer_part: str) -> List[str]:
    m = re.search(r"挖空题答案(.*?)(?:连线题答案|$)", answer_part, re.DOTALL)
    if not m:
        return []

    block = m.group(1)
    tokens = []
    for line in block.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = re.split(r"[；;、，,]", line)
        for p in parts:
            p = p.strip()
            if p:
                tokens.append(p)
    return tokens


def bind_fill_qa(fill_questions: List[Dict[str, object]], fill_answers: List[str]) -> List[Dict[str, str]]:
    idx = 0
    cards = []
    for q in fill_questions:
        need = int(q["blanks"])
        ans = fill_answers[idx : idx + need]
        idx += need
        back = " / ".join(ans) if ans else "（未匹配到答案）"
        cards.append({"front": str(q["front"]), "back": back, "header": "填空题"})
    return cards


def extract_matching_blocks(question_part: str) -> List[Dict[str, object]]:
    blocks = []
    pattern = re.compile(r"连线题：\s*(.*?)(?=连线题：|$)", re.DOTALL)
    parts = pattern.findall(question_part)
    for i, part in enumerate(parts, start=1):
        cleaned = part.strip()
        if cleaned:
            blocks.append({"index": i, "content": cleaned})
    return blocks


def extract_matching_answers(answer_part: str) -> Dict[int, str]:
    result = {}
    for m in re.finditer(r"连线题\s*(\d+)\s*([^\n]+)", answer_part):
        idx = int(m.group(1))
        ans = m.group(2).strip()
        result[idx] = ans
    return result


def build_matching_cards(blocks: List[Dict[str, object]], answers: Dict[int, str]) -> List[Dict[str, str]]:
    cards = []
    for b in blocks:
        idx = int(b["index"])
        content = str(b["content"]).replace("\n", "<br>")
        front = f"连线题 {idx}<br><br>{content}"
        back = answers.get(idx, "（未匹配到答案）")
        cards.append({"front": front, "back": back, "header": "连线题"})
    return cards


def load_style_model_and_media(style_apkg: Path, temp_dir: Path) -> Tuple[dict, List[Path], str]:
    with zipfile.ZipFile(style_apkg, "r") as z:
        names = z.namelist()
        db_name = "collection.anki21" if "collection.anki21" in names else "collection.anki2"
        z.extract(db_name, str(temp_dir))
        db_path = temp_dir / db_name

        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT models FROM col LIMIT 1")
        models = json.loads(cur.fetchone()[0])
        conn.close()

        model = models[next(iter(models.keys()))]

        media_files: List[Path] = []
        default_image_name = ""
        if "media" in names:
            media_map = json.loads(z.read("media").decode("utf-8"))
            for numeric_name, real_name in media_map.items():
                out_path = temp_dir / str(real_name)
                with z.open(str(numeric_name)) as src, open(out_path, "wb") as dst:
                    dst.write(src.read())
                media_files.append(out_path)
                lower_name = str(real_name).lower()
                if not default_image_name and lower_name.endswith((".png", ".jpg", ".jpeg", ".webp", ".gif")):
                    default_image_name = str(real_name)

    return model, media_files, default_image_name


def create_styled_apkg(cards: List[Dict[str, str]], output_apkg: Path, deck_name: str, style_apkg: Path) -> None:
    with tempfile.TemporaryDirectory() as td:
        temp_dir = Path(td)
        style_model, style_media_files, default_image_name = load_style_model_and_media(style_apkg, temp_dir)

        fields = [{"name": f["name"]} for f in style_model["flds"]]
        templates = [{"name": t["name"], "qfmt": t["qfmt"], "afmt": t["afmt"]} for t in style_model["tmpls"]]

        model = genanki.Model(
            int(style_model["id"]),
            style_model["name"],
            fields=fields,
            templates=templates,
            css=style_model.get("css", ""),
        )

        deck = genanki.Deck(2059400111, deck_name)
        field_names = [f["name"] for f in style_model["flds"]]

        for c in cards:
            image_html = f'<img src="{default_image_name}" />' if default_image_name else ""
            values = {
                "ID": f"{uuid.uuid4()}__auto",
                "Header": f"生理学复习｜{c['header']}",
                "Image": image_html,
                "Text": c["front"],
                "Masks": "",
                "Source": "PDF自动转换",
                "Notes": c["back"],
                "Mode": "free_guess",
                "Index": "",
                "Colors": "#4D5DE6,#FFEBA2",
                "Reversed": "",
            }
            note_fields = [values.get(name, "") for name in field_names]
            note = genanki.Note(model=model, fields=note_fields)
            deck.add_note(note)

        package = genanki.Package(deck)
        package.media_files = [str(p) for p in style_media_files]
        package.write_to_file(str(output_apkg))


def convert(input_file: Path, output_apkg: Path, deck_name: str, style_apkg: Path) -> None:
    text = read_source_text(input_file)
    sections = split_sections(text)

    fill_questions = extract_fill_questions(sections["question_part"])
    fill_answers = extract_fill_answers(sections["answer_part"])
    fill_cards = bind_fill_qa(fill_questions, fill_answers)

    matching_blocks = extract_matching_blocks(sections["question_part"])
    matching_answers = extract_matching_answers(sections["answer_part"])
    matching_cards = build_matching_cards(matching_blocks, matching_answers)

    cards = fill_cards + matching_cards
    create_styled_apkg(cards, output_apkg, deck_name, style_apkg)

    print(f"[OK] 已生成: {output_apkg}")
    print(f"[OK] 卡片数量: {len(cards)} (填空 {len(fill_cards)} + 连线 {len(matching_cards)})")


def main() -> None:
    base = Path(__file__).parent

    txt_candidate = base / "生理学·绪论复习题.txt"
    pdf_candidate = base / "天天师兄 27 生理学（1）绪论.pdf"
    style_candidate = base / "天天师兄课后巩固__01绪论、跨膜转运【ttsx】.apkg"

    if txt_candidate.exists():
        source = txt_candidate
    elif pdf_candidate.exists():
        source = pdf_candidate
    else:
        raise FileNotFoundError("未找到输入文件：生理学·绪论复习题.txt 或 天天师兄 27 生理学（1）绪论.pdf")

    if not style_candidate.exists():
        raise FileNotFoundError("未找到样式参考包：天天师兄课后巩固__01绪论、跨膜转运【ttsx】.apkg")

    output = base / "生理学复习_同款样式.apkg"
    convert(source, output, "生理学复习（同款样式）", style_candidate)


if __name__ == "__main__":
    main()
