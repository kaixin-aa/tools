# word-to-pdf

Recursively convert Word documents in a course-material directory to PDFs while
preserving their relative directory structure. The source directory is never
modified, and non-Word files are not copied to the output directory.

递归转换课程资料目录中的 Word 文档，并在输出目录中保留原有相对目录结构。
工具不会修改源目录，也不会把非 Word 文件复制到输出目录。

## Requirements / 运行要求

- Windows: Microsoft Word and Windows PowerShell. This backend has the best
  compatibility with legacy `.doc` files, equations, tables, and page layout.
- Windows：需要安装 Microsoft Word 和 Windows PowerShell。对于旧版 `.doc`、
  公式、表格和复杂分页，Word 后端兼容性最好。
- Other platforms: install LibreOffice and make `soffice` available on `PATH`.
- 其他平台：安装 LibreOffice，并确保命令行能够找到 `soffice`。

Install the repository in editable mode / 安装本仓库：

```bash
python -m pip install -e ".[test]"
```

## Usage / 使用方法

```bash
python -m word_to_pdf convert "path/to/course" \
  --output "path/to/course-pdfs" \
  --report conversion_report.json
```

The installed command is equivalent / 安装后也可以使用：

```bash
word-to-pdf convert "path/to/course" \
  --output "path/to/course-pdfs" \
  --report conversion_report.json
```

Select a backend explicitly when needed / 如有需要可指定后端：

```bash
word-to-pdf convert INPUT --output OUTPUT --report REPORT --backend word
word-to-pdf convert INPUT --output OUTPUT --report REPORT --backend libreoffice
```

`--backend auto` is the default. It prefers Microsoft Word and falls back to
LibreOffice. The output directory must be absent or empty and must not be inside
the source directory.

默认使用 `--backend auto`，优先选择 Microsoft Word，找不到时再使用
LibreOffice。输出目录必须不存在或为空，并且不能位于源目录内部。

## Supported files / 支持格式

The tool recognizes `.doc`, `.docx`, `.docm`, `.dot`, `.dotx`, `.dotm`, and
`.rtf` files. Word lock files whose names start with `~$` are skipped and listed
in the report.

工具支持 `.doc`、`.docx`、`.docm`、`.dot`、`.dotx`、`.dotm` 和 `.rtf`。
以 `~$` 开头的 Word 临时锁文件会被跳过，并记录在报告中。

## Reports and safety / 报告与安全

The JSON report records every converted, failed, and skipped file. A bilingual
Markdown summary is written next to it unless `--markdown-report` is supplied.
If one document fails, the remaining documents are still processed and the
command exits with status 1.

JSON 报告会记录每个成功、失败和跳过的文件；默认还会在旁边生成中英文
Markdown 摘要。单个文档转换失败不会中断整个批次，但命令最终会以状态码 1
退出，便于在脚本或 CI 中发现问题。

Microsoft Word is opened invisibly and read-only. Macros and alerts are disabled,
and document properties are excluded from Word's PDF export. Visible personal
information in the document body is not removed: run `course-anonymizer` before
conversion when publishing private course materials.

Microsoft Word 会以隐藏、只读方式打开文件，同时禁用宏和弹窗，并在导出时
排除文档属性。正文中可见的姓名、学号等内容不会被本工具删除；公开课程资料前，
仍应先运行 `course-anonymizer`。
