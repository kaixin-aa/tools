# course-anonymizer

Create an anonymized copy of a course-material directory before publishing files
to a public repository. The source directory is never modified.

```bash
python -m course_anonymizer sanitize "path/to/course" \
  --config course-anonymizer/privacy-map.example.json \
  --output "path/to/sanitized-course" \
  --report privacy_report.json
```

The JSON privacy map uses `source` to `replacement` rules. Labels appear in the
report instead of the raw source text, so the report does not reintroduce the
private strings it detected.

Supported sanitization:

- file and directory names
- common text/source formats
- Office Open XML files such as `.docx`, `.xlsx`, and `.pptx`
- `.zip`, `.jar`, and `.war` member paths and supported member content

Files that cannot be reliably rewritten, such as PDFs, old `.doc` files,
images, and `.class` files, are retained and listed as warnings for manual
review.
