# tools

A small collection of practical Python command line tools.

The repository is intentionally simple: each tool is small enough to read in a
few minutes, has focused tests, and can be used directly from the command line.

## Setup

```bash
python -m pip install -e ".[test]"
```

## Tools

### json-format

Format JSON from a file or from standard input.

```bash
json-format --file payload.json
python -m daily_tools.json_format --minify --sort-keys < payload.json
```

### csv-select

Extract selected columns from a CSV file or from standard input.

```bash
csv-select name email --file contacts.csv
python -m daily_tools.csv_select city country --file addresses.csv --delimiter ";"
```

### file-hash

Calculate file or stdin digests with standard-library hash algorithms.

```bash
file-hash README.md
python -m daily_tools.file_hash --algorithm md5 README.md TOOL_INDEX.md
```

### course-anonymizer

Create an anonymized copy of a course-material directory before publishing it.

```bash
python -m course_anonymizer sanitize "path/to/course" --config course-anonymizer/privacy-map.example.json --output "path/to/sanitized-course" --report privacy_report.json
```

### text-stats

Summarize text from one or more files, or from standard input.

```bash
text-stats README.md
python -m daily_tools.text_stats --json README.md
```

## Development

Run the test suite before committing changes:

```bash
python -m pytest
```
