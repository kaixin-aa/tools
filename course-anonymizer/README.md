# course-anonymizer

Create an anonymized copy of a course-material directory before publishing files
to a public repository. The source directory is never modified.

在公开发布课程资料前，使用该工具生成一个脱敏副本。工具会按照配置替换
姓名、学号、账号名等个人信息，并且不会修改原始课程目录。

```bash
python -m course_anonymizer sanitize "path/to/course" \
  --config course-anonymizer/privacy-map.example.json \
  --output "path/to/sanitized-course" \
  --report privacy_report.json
```

The JSON privacy map uses `source` to `replacement` rules. Labels appear in the
report instead of the raw source text, so the report does not reintroduce the
private strings it detected.

JSON 配置文件使用 `source` 到 `replacement` 的替换规则。报告中只显示
规则标签和命中次数，不直接写回原始敏感词，避免报告本身再次泄露隐私。

Supported sanitization:

- file and directory names
- common text/source formats
- Office Open XML files such as `.docx`, `.xlsx`, and `.pptx`
- `.zip`, `.jar`, and `.war` member paths and supported member content

支持的脱敏范围：

- 文件名和目录名
- 常见文本、源码、配置文件
- `.docx`、`.xlsx`、`.pptx` 等 Office Open XML 文件
- `.zip`、`.jar`、`.war` 内部路径和可识别的文本内容

Files that cannot be reliably rewritten, such as PDFs, old `.doc` files,
images, and `.class` files, are retained and listed as warnings for manual
review.

PDF、旧版 `.doc`、图片、`.class` 等无法可靠改写的文件会原样保留，并在报告中
作为警告汇总，方便上传前人工复核。
