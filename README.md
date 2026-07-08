# tools

A small collection of practical Python command line tools.

The repository is intentionally simple: each tool is small enough to read in a
few minutes, has focused tests, and can be used directly from the command line.

这是一个轻量的 Python 命令行工具集合。每个工具都尽量保持小而清晰，
方便直接阅读源码、运行测试，并在日常任务中通过命令行使用。

## Setup

安装开发环境：

```bash
python -m pip install -e ".[test]"
```

## Tools

### json-format

Format JSON from a file or from standard input.

从文件或标准输入读取 JSON，并输出格式化或压缩后的结果。

```bash
json-format --file payload.json
python -m daily_tools.json_format --minify --sort-keys < payload.json
```

### csv-select

Extract selected columns from a CSV file or from standard input.

从 CSV 文件或标准输入中提取指定列，并保持原有行顺序。

```bash
csv-select name email --file contacts.csv
python -m daily_tools.csv_select city country --file addresses.csv --delimiter ";"
```

### file-hash

Calculate file or stdin digests with standard-library hash algorithms.

使用 Python 标准库支持的哈希算法计算文件或标准输入的摘要。

```bash
file-hash README.md
python -m daily_tools.file_hash --algorithm md5 README.md TOOL_INDEX.md
```

### course-anonymizer

Create an anonymized copy of a course-material directory before publishing it.

为课程资料目录生成脱敏副本，适合在公开发布前替换姓名、学号等个人信息。
源目录不会被修改。

```bash
python -m course_anonymizer sanitize "path/to/course" --config course-anonymizer/privacy-map.example.json --output "path/to/sanitized-course" --report privacy_report.json
```

### course-clean

Scan a course-material directory or create a cleaned copy without generated
files, build outputs, dependency folders, IDE metadata, and large files.

扫描课程资料目录，或生成清理后的副本，跳过编译产物、依赖目录、IDE 元数据和
过大的文件。源目录不会被修改。

```bash
python -m course_clean scan "path/to/course" --report cleanup_report.json
python -m course_clean copy "path/to/course" --output "path/to/cleaned-course" --report cleanup_report.json
```

### text-stats

Summarize text from one or more files, or from standard input.

统计一个或多个文本文件，或标准输入中的字符数、词数、行数、句子数和段落数。

```bash
text-stats README.md
python -m daily_tools.text_stats --json README.md
```

## Development

Run the test suite before committing changes:

提交修改前请运行测试：

```bash
python -m pytest
```
