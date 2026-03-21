#!/usr/bin/env bash

_shell_env_repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

_strip_wrapping_quotes() {
  local value="${1:-}"
  if [ "${#value}" -ge 2 ]; then
    case "$value" in
      \"*\") printf '%s\n' "${value:1:${#value}-2}"; return 0 ;;
      \'*\') printf '%s\n' "${value:1:${#value}-2}"; return 0 ;;
    esac
  fi
  printf '%s\n' "$value"
}

_read_env_key() {
  local env_file="$1"
  local key="$2"
  awk -v key="$key" '
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*$/ { next }
    {
      line = $0
      eq = index(line, "=")
      if (eq == 0) next
      lhs = substr(line, 1, eq - 1)
      rhs = substr(line, eq + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", lhs)
      if (lhs != key) next
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", rhs)
      print rhs
      exit
    }
  ' "$env_file"
}

bootstrap_python_bin() {
  local env_file="${1:-${_shell_env_repo_root}/.env}"
  local env_python_bin=""

  if [ -z "${PYTHON_BIN:-}" ] && [ -f "$env_file" ]; then
    env_python_bin="$(_read_env_key "$env_file" "PYTHON_BIN")"
    env_python_bin="$(_strip_wrapping_quotes "$env_python_bin")"
    if [ -n "$env_python_bin" ]; then
      PYTHON_BIN="$env_python_bin"
    fi
  fi

  if [ -z "${PYTHON_BIN:-}" ]; then
    if command -v python >/dev/null 2>&1; then
      PYTHON_BIN="python"
    elif command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="python3"
    else
      echo "[ERR] python interpreter not found (tried python and python3)." >&2
      return 1
    fi
  fi

  if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
    echo "[ERR] PYTHON_BIN not found: $PYTHON_BIN" >&2
    return 1
  fi

  export PYTHON_BIN
}

load_repo_env_if_present() {
  local env_file="${1:-${_shell_env_repo_root}/.env}"
  bootstrap_python_bin "$env_file" || return 1
  if [ -f "$env_file" ]; then
    eval "$("$PYTHON_BIN" "${_shell_env_repo_root}/analysis/dotenv_shell.py" --env-file "$env_file")"
  fi
}
