# tools

A small collection of practical Python command line tools.

The repository is intentionally simple: each tool is small enough to read in a
few minutes, has focused tests, and can be used directly from the command line.

## Setup

```bash
python -m pip install -e ".[test]"
```

## Tools

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
