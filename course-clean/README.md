# course-clean

Scan a course-material directory or create a cleaned copy before publishing it
to GitHub. The tool is non-destructive: it never deletes files from the source
directory.

在上传课程资料到 GitHub 前，使用该工具扫描目录或生成清理后的副本。工具不会删除
原始目录中的文件。

```bash
python -m course_clean scan "path/to/course" --report cleanup_report.json

python -m course_clean copy "path/to/course" \
  --output "path/to/cleaned-course" \
  --report cleanup_report.json
```

Built-in cleanup rules skip common generated or upload-unfriendly files:

- IDE and VCS directories such as `.git`, `.idea`, and `.vscode`
- dependency/build directories such as `node_modules`, `target`, `out`, `build`, and `dist`
- generated files such as `.class`, `.pyc`, `.war`, logs, temporary files, and OS metadata
- files larger than 95 MiB by default, matching GitHub's practical upload limit

内置规则会跳过常见的生成物和不适合上传的内容：

- `.git`、`.idea`、`.vscode` 等版本控制或 IDE 目录
- `node_modules`、`target`、`out`、`build`、`dist` 等依赖或构建目录
- `.class`、`.pyc`、`.war`、日志、临时文件、系统元数据等生成文件
- 默认跳过大于 95 MiB 的文件，避免触碰 GitHub 的大文件限制

Use `--exclude-name`, `--exclude-suffix`, `--keep-name`, and `--max-size-mib` to
adjust the rules for a specific course.

可以通过 `--exclude-name`、`--exclude-suffix`、`--keep-name` 和
`--max-size-mib` 针对具体课程调整规则。
