from __future__ import annotations

import argparse
import re
import sys
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pypdf import PdfReader, PdfWriter


# ======================== 显眼配置区（按需修改） ========================
DEFAULT_SOURCE_PDF_PATH = Path(r" ")
DEFAULT_OUTPUT_ROOT_PATH = Path(r" ")
DEFAULT_MODE = "outline"  # 可选：outline / pages
DEFAULT_OUTLINE_LEVEL = 1
DEFAULT_PAGE_RANGES = ""
DEFAULT_CREATE_ZIP = True
DEFAULT_RECURSION_LIMIT = 20000
MAX_RECURSION_LIMIT = 100000
# ==================================================================


@dataclass
class BookmarkItem:
	title: str
	page_index: int
	level: int


def _safe_filename(name: str) -> str:
	cleaned = re.sub(r"[\\/:*?\"<>|]", "_", name).strip()
	cleaned = re.sub(r"\s+", " ", cleaned)
	return cleaned[:80] or "untitled"


def _ensure_recursion_limit(target_limit: int) -> None:
	current_limit = sys.getrecursionlimit()
	if current_limit >= target_limit:
		return
	sys.setrecursionlimit(target_limit)
	print(f"已将递归深度上限从 {current_limit} 提升到 {target_limit}。")


def _export_page_range_with_retry(reader: PdfReader, output_file: Path, start_page: int, end_page: int) -> None:
	limits = [DEFAULT_RECURSION_LIMIT, MAX_RECURSION_LIMIT]
	last_error: RecursionError | None = None

	for limit in limits:
		_ensure_recursion_limit(limit)
		try:
			writer = PdfWriter()
			for page_idx in range(start_page, end_page + 1):
				writer.add_page(reader.pages[page_idx])

			with output_file.open("wb") as f:
				writer.write(f)
			return
		except RecursionError as exc:
			last_error = exc
			if output_file.exists():
				output_file.unlink()

	raise RecursionError(
		f"页码范围 {start_page + 1}-{end_page + 1} 导出失败：已将递归上限提升到 {MAX_RECURSION_LIMIT} 仍无法完成。"
	) from last_error


def _get_outline(reader: PdfReader):
	outline = getattr(reader, "outline", None)
	if outline is None:
		outline = getattr(reader, "outlines", None)
	return outline or []


def _extract_bookmarks_from_outline(reader: PdfReader, outline_items, level: int = 1) -> list[BookmarkItem]:
	bookmarks: list[BookmarkItem] = []

	for entry in outline_items:
		if isinstance(entry, list):
			bookmarks.extend(_extract_bookmarks_from_outline(reader, entry, level + 1))
			continue

		title = getattr(entry, "title", str(entry)).strip() or "未命名目录"
		try:
			page_index = reader.get_destination_page_number(entry)
		except Exception:
			page_obj = getattr(entry, "page", None)
			if page_obj is None:
				continue
			try:
				page_index = reader.get_page_number(page_obj)
			except Exception:
				continue

		if page_index < 0:
			continue

		bookmarks.append(BookmarkItem(title=title, page_index=page_index, level=level))

	return bookmarks


def parse_bookmarks(pdf_path: Path) -> tuple[int, list[BookmarkItem], dict[int, int]]:
	reader = PdfReader(str(pdf_path))
	outline = _get_outline(reader)
	bookmarks = _extract_bookmarks_from_outline(reader, outline, level=1)

	level_count: dict[int, int] = {}
	for item in bookmarks:
		level_count[item.level] = level_count.get(item.level, 0) + 1

	return len(reader.pages), bookmarks, level_count


def split_pdf_by_level(pdf_path: Path, output_dir: Path, target_level: int) -> list[Path]:
	reader = PdfReader(str(pdf_path))
	bookmarks = _extract_bookmarks_from_outline(reader, _get_outline(reader), level=1)

	sections = [item for item in bookmarks if item.level == target_level]
	sections.sort(key=lambda x: x.page_index)

	if not sections:
		raise ValueError(f"没有找到第 {target_level} 级目录，无法切割。")

	output_dir.mkdir(parents=True, exist_ok=True)
	created_files: list[Path] = []
	total_pages = len(reader.pages)

	for idx, section in enumerate(sections, start=1):
		start_page = section.page_index
		end_page = (sections[idx].page_index - 1) if idx < len(sections) else (total_pages - 1)

		if start_page < 0 or start_page >= total_pages or end_page < start_page:
			continue

		filename = f"{idx:03d}_{_safe_filename(section.title)}.pdf"
		output_file = output_dir / filename
		same_name_index = 1
		while output_file.exists():
			output_file = output_dir / f"{idx:03d}_{_safe_filename(section.title)}_{same_name_index}.pdf"
			same_name_index += 1

		_export_page_range_with_retry(reader, output_file, start_page, end_page)

		created_files.append(output_file)

	if not created_files:
		raise ValueError("目录已识别，但没有生成任何切割文件，请检查 PDF 目录是否有效。")

	return created_files


def _parse_page_ranges(page_ranges_text: str, total_pages: int) -> list[tuple[int, int]]:
	if not page_ranges_text.strip():
		raise ValueError("页码范围不能为空，请输入例如：1-3, 5, 8-10")

	normalized = page_ranges_text.replace("，", ",").replace("；", ",").replace(";", ",")
	parts = [part.strip() for part in normalized.split(",") if part.strip()]
	if not parts:
		raise ValueError("页码范围格式无效，请输入例如：1-3, 5, 8-10")

	ranges: list[tuple[int, int]] = []
	for part in parts:
		if "-" in part:
			m = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
			if not m:
				raise ValueError(f"无法解析区间：{part}，请使用类似 3-8 的格式")
			start = int(m.group(1))
			end = int(m.group(2))
		else:
			if not re.fullmatch(r"\d+", part):
				raise ValueError(f"无法解析页码：{part}")
			start = int(part)
			end = start

		if start < 1 or end < 1:
			raise ValueError(f"页码必须 >= 1，收到：{part}")
		if start > end:
			raise ValueError(f"区间起始页不能大于结束页，收到：{part}")
		if end > total_pages:
			raise ValueError(f"区间 {part} 超出总页数 {total_pages}")

		ranges.append((start, end))

	return ranges


def split_pdf_by_page_ranges(pdf_path: Path, output_dir: Path, page_ranges_text: str) -> list[Path]:
	reader = PdfReader(str(pdf_path))
	total_pages = len(reader.pages)
	page_ranges = _parse_page_ranges(page_ranges_text, total_pages)

	output_dir.mkdir(parents=True, exist_ok=True)
	created_files: list[Path] = []

	for idx, (start, end) in enumerate(page_ranges, start=1):
		filename = f"{idx:03d}_pages_{start}-{end}.pdf"
		output_file = output_dir / filename
		same_name_index = 1
		while output_file.exists():
			output_file = output_dir / f"{idx:03d}_pages_{start}-{end}_{same_name_index}.pdf"
			same_name_index += 1

		_export_page_range_with_retry(reader, output_file, start - 1, end - 1)

		created_files.append(output_file)

	if not created_files:
		raise ValueError("未生成任何切割文件，请检查页码范围输入。")

	return created_files


def build_zip(files: list[Path], zip_path: Path) -> Path:
	with zipfile.ZipFile(zip_path, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
		for pdf_file in files:
			zf.write(pdf_file, arcname=pdf_file.name)
	return zip_path


def _build_output_dir(output_root: Path, source_pdf_path: Path, mode: str, detail: str) -> Path:
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	return output_root / f"{source_pdf_path.stem}_{timestamp}" / f"{mode}_{detail}"


def _print_levels(level_count: dict[int, int]) -> None:
	if not level_count:
		print("未检测到目录书签。")
		return
	print("可用目录层级：")
	for level in sorted(level_count):
		print(f"  第{level}级：{level_count[level]} 节")


def _parse_args() -> argparse.Namespace:
	parser = argparse.ArgumentParser(description="本地 PDF 切割工具（按目录层级 / 按页码范围）")
	parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_PDF_PATH, help="原 PDF 路径")
	parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT_PATH, help="输出根目录")
	parser.add_argument("--mode", choices=["outline", "pages"], default=DEFAULT_MODE, help="切割模式")
	parser.add_argument("--level", type=int, default=None, help="目录层级模式使用的级别；不传时进入交互选择")
	parser.add_argument("--page-ranges", type=str, default=DEFAULT_PAGE_RANGES, help="页码范围，例如 1-3,5,8-10")
	parser.add_argument("--list-levels", action="store_true", help="仅显示可用目录层级，不执行切割")
	parser.add_argument("--no-zip", action="store_true", help="不生成 ZIP 打包文件")
	return parser.parse_args()


def _normalize_path_input(path_value: Path) -> Path:
	text = str(path_value).strip().strip('"').strip("'")
	return Path(text).expanduser()


def _prompt_required_path(prompt_text: str, *, must_be_pdf_file: bool = False) -> Path:
	while True:
		raw = input(prompt_text).strip()
		if not raw:
			print("输入不能为空，请重试。")
			continue

		path = _normalize_path_input(Path(raw))
		if must_be_pdf_file:
			if not path.exists():
				print(f"文件不存在：{path}")
				continue
			if path.suffix.lower() != ".pdf":
				print(f"输入文件不是 PDF：{path}")
				continue

		return path


def _collect_interactive_paths() -> tuple[Path, Path]:
	print("\n=== PDF 切割交互模式 ===")
	source_pdf_path = _prompt_required_path("请输入需要拆分的 PDF 文件路径：", must_be_pdf_file=True)
	output_root = _prompt_required_path("请输入保存分割结果的文件夹路径：")
	return source_pdf_path, output_root


def _pause_before_exit(enabled: bool) -> None:
	if not enabled:
		return
	try:
		input("\n按回车键退出...")
	except EOFError:
		pass


def _not_found_hint(source_pdf_path: Path) -> str:
	path_text = str(source_pdf_path).lower()
	if "appdata\\local\\temp\\gradio" in path_text:
		return "提示：你现在配置的是 Gradio 临时目录文件，临时文件通常会被系统清理。请改成你本地长期保存的 PDF 路径。"
	return "提示：请确认路径是绝对路径、文件名无误，且文件确实存在。"


def _resolve_outline_level(selected_level: int | None, level_count: dict[int, int]) -> int:
	available_levels = sorted(level_count)
	if not available_levels:
		raise ValueError("该 PDF 没有目录书签，请改用 --mode pages 与 --page-ranges。")

	if selected_level is not None:
		if selected_level not in level_count:
			available_text = "、".join(str(level) for level in available_levels)
			raise ValueError(f"指定的层级 {selected_level} 不存在，可选层级：{available_text}")
		return selected_level

	_print_levels(level_count)
	default_level = DEFAULT_OUTLINE_LEVEL if DEFAULT_OUTLINE_LEVEL in level_count else available_levels[0]

	if not sys.stdin.isatty():
		print(f"未传 --level 且当前非交互环境，自动使用第{default_level}级目录。")
		return default_level

	available_text = "、".join(str(level) for level in available_levels)
	while True:
		user_input = input(f"请输入要切割的目录层级（可选：{available_text}，回车默认第{default_level}级）：").strip()
		if not user_input:
			return default_level
		if re.fullmatch(r"\d+", user_input):
			level = int(user_input)
			if level in level_count:
				return level
		print(f"输入无效，请输入可选层级之一：{available_text}")


def main() -> int:
	args = _parse_args()
	interactive_launch = len(sys.argv) == 1 and sys.stdin.isatty()
	_ensure_recursion_limit(DEFAULT_RECURSION_LIMIT)

	if interactive_launch:
		source_pdf_path, output_root = _collect_interactive_paths()
	else:
		source_pdf_path = _normalize_path_input(args.source)
		output_root = _normalize_path_input(args.output_root)

	print(f"\n生效原文件路径：{source_pdf_path}")
	print(f"生效输出根目录：{output_root}")

	if not source_pdf_path.exists():
		print(f"错误：未找到 PDF 文件：{source_pdf_path}")
		print(_not_found_hint(source_pdf_path))
		return 1

	if source_pdf_path.suffix.lower() != ".pdf":
		print(f"错误：输入文件不是 PDF：{source_pdf_path}")
		return 1

	output_root.mkdir(parents=True, exist_ok=True)

	try:
		total_pages, _, level_count = parse_bookmarks(source_pdf_path)
		print(f"文件：{source_pdf_path}")
		print(f"总页数：{total_pages}")

		if args.list_levels:
			_print_levels(level_count)
			return 0

		if args.mode == "outline":
			target_level = _resolve_outline_level(args.level, level_count)
			print(f"本次选择目录层级：第{target_level}级")

			output_dir = _build_output_dir(output_root, source_pdf_path, "outline", f"level_{target_level}")
			split_files = split_pdf_by_level(source_pdf_path, output_dir, target_level=target_level)
		elif args.mode == "pages":
			if not args.page_ranges.strip():
				raise ValueError("页码模式必须传入 --page-ranges，例如：--page-ranges \"1-3,5,8-10\"")

			output_dir = _build_output_dir(output_root, source_pdf_path, "pages", "ranges")
			split_files = split_pdf_by_page_ranges(source_pdf_path, output_dir, args.page_ranges)
		else:
			raise ValueError(f"未知模式：{args.mode}")

		zip_path = None
		if not args.no_zip and DEFAULT_CREATE_ZIP:
			zip_path = build_zip(split_files, output_dir / "split_result.zip")

		print("\n切割完成")
		print(f"输出目录：{output_dir}")
		print(f"生成文件数：{len(split_files)}")
		if zip_path is not None:
			print(f"ZIP 文件：{zip_path}")

		print("\n文件列表：")
		for item in split_files:
			print(f"- {item}")

		return 0
	except Exception as exc:
		print(f"错误：{exc}")
		return 1
	finally:
		_pause_before_exit(interactive_launch)


if __name__ == "__main__":
	sys.exit(main())
