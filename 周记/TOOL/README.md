# PDF目录切割本地工具 PDF转anki卡片

工具入口：周记/TOOL/pdf切割.py

## 功能

- 按目录层级切割（第1级、第2级等）
- 按页码范围切割（例如：1-3,5,8-10），目录缺失也可用
- 目录模式支持交互式层级选择（不传 --level 时会提示输入）
- 默认生成 ZIP 打包文件（可关闭）

## 安装依赖

在项目根目录执行：

```bash
py -m pip install -r 周记/TOOL/requirements.txt
```

## 快速开始

直接运行（按顶部配置路径执行）：

```bash
py 周记/TOOL/pdf切割.py
```

程序会先打印实际生效路径：

- 生效原文件路径
- 生效输出根目录

然后按模式执行：

- 默认是目录模式（outline）
- 未传 --level 时会列出可选层级并让你输入

## 常用命令

1. 仅查看可用目录层级：

```bash
py 周记/TOOL/pdf切割.py --source "D:\\your.pdf" --list-levels
```

1. 按目录层级切割（显式指定第2级）：

```bash
py 周记/TOOL/pdf切割.py --source "D:\\your.pdf" --mode outline --level 2
```

1. 按目录层级切割（交互选择层级）：

```bash
py 周记/TOOL/pdf切割.py --source "D:\\your.pdf" --mode outline
```

1. 按页码范围切割：

```bash
py 周记/TOOL/pdf切割.py --source "D:\\your.pdf" --mode pages --page-ranges "1-3,5,8-10"
```

1. 指定输出目录并禁用 ZIP：

```bash
py 周记/TOOL/pdf切割.py --source "D:\\your.pdf" --output-root "D:\\out" --no-zip
```

## 参数说明

- --source：原 PDF 路径
- --output-root：输出根目录
- --mode：outline 或 pages
- --level：目录层级（目录模式可选；不传则交互选择）
- --page-ranges：页码范围（页码模式必填）
- --list-levels：仅显示可用目录层级
- --no-zip：不生成 ZIP

## 顶部关键配置

- DEFAULT_SOURCE_PDF_PATH：默认原文件路径
- DEFAULT_OUTPUT_ROOT_PATH：默认输出根目录
- DEFAULT_MODE：默认切割模式（outline/pages）
- DEFAULT_OUTLINE_LEVEL：默认目录层级（非交互环境下可作为回退）
- DEFAULT_PAGE_RANGES：默认页码范围
- DEFAULT_CREATE_ZIP：默认是否生成 ZIP

## 常见问题

1. 报错“未找到 PDF 文件”：

- 优先看程序打印的“生效原文件路径”，确认它和你预期一致
- 避免使用临时目录路径（例如 AppData\\Local\\Temp\\gradio）

1. 目录模式提示没有书签：

- 说明 PDF 不含目录书签，请改用页码模式
- 示例：--mode pages --page-ranges "1-10,11-20"
