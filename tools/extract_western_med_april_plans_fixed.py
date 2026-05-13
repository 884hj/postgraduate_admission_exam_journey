from __future__ import annotations

from pathlib import Path

from rapidocr_onnxruntime import RapidOCR


def main() -> None:
    workspace = Path(__file__).resolve().parents[1]
    source_dir = workspace / "西综" / "04月"
    output_path = source_dir / "每日计划2026-04-提取文字.txt"

    # 收集所有图片（不限制文件名格式）
    image_paths = sorted(
        [
            path
            for path in source_dir.iterdir()
            if path.is_file() and path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}
        ],
        key=lambda path: path.name,
    )

    ocr = RapidOCR()
    lines: list[str] = []

    for image_path in image_paths:
        result, _ = ocr(str(image_path))
        text_lines: list[str] = []
        if result:
            for item in result:
                if len(item) >= 2:
                    text = str(item[1]).strip()
                    if text:
                        text_lines.append(text)

        lines.append(f"[{image_path.stem}]")
        lines.extend(text_lines or ["[未识别到文字]"])
        lines.append("")

    output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote {output_path}")
    print(f"Images: {len(image_paths)}")


if __name__ == "__main__":
    main()

