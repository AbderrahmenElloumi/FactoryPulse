# Docker and compose gotchas

- **Put `x-*` anchor blocks at the compose root, never under `services:`.**
  Under `services:`, compose runs the block as a service named after it, with
  no warning. Detect: `docker compose config --services` lists `x-spark-job`.
- **In a compose `command:`, write `$$VAR` for a container variable.** `$VAR`
  is interpolated on the host, and an unset host variable becomes an empty
  string, so the command runs with the value missing. Detect: the warning
  `The "VAR" variable is not set. Defaulting to a blank string.`
- **Never use `${VAR:?message}` in `compose.yaml`.** Compose interpolates the
  whole file, services outside the active profiles included, so one missing
  variable fails every compose command. Use `${VAR:-}` and let the consumer
  refuse the empty value. Detect: `required variable VAR is missing a value`.
- **The `minio` image has no `awk`, `sed` or `grep`.** It has `sh`, `bash`,
  `curl` and `mc`. Script a check with `mc`, `curl` or plain `sh`. Detect:
  `awk: command not found`.
