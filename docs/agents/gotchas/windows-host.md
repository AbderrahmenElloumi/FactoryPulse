# Windows host gotchas

- **Prefix a `docker` command in Git Bash with `MSYS_NO_PATHCONV=1`.** Git
  Bash rewrites Linux paths in arguments; Python's `subprocess` does not.
  Detect: `the working directory 'C:/Program Files/Git/repo' is invalid`
  from `docker run -w /repo`.
- **`Path.write_text` writes CRLF on Windows.** A shell script edited that way
  breaks in a Linux container, because a bind mount runs the working copy,
  not the LF-normalized commit. Write with `open(path, "w", newline="")`.
  Detect: `set: pipefail\r: invalid option name` (`\r` is a carriage
  return), or `'bash\r': No such file`.
- **Rebuild a `.venv` after moving the repository; do not repair it.** Its
  editable `.pth` points at the old `src`. Detect: `No module named
  'factorypulse'`. Rebuild: `C:\Python314\python.exe -m venv .venv`, then
  `pip install -e . pytest -r requirements-quality.txt -r requirements-dashboard.txt`.
