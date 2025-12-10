#!/usr/bin/env bash

# Collect the last N lines from each running screen session into one file.
# Usage:
#   ./collect_screen_logs.sh [LINES] [OUTPUT_FILE]
#
# Defaults:
#   LINES       = 50
#   OUTPUT_FILE = screen_logs_YYYY-MM-DD_HHMMSS.log

set -u  # treat unset vars as an error

LINES="${1:-50}"
OUTPUT_FILE="${2:-screen_logs_$(date +%F_%H%M%S).log}"

# Ensure screen is installed
if ! command -v screen >/dev/null 2>&1; then
  echo "Error: 'screen' command not found. Please install GNU screen." >&2
  exit 1
fi

# Get list of running screen sessions (e.g. 1234.myname)
SESSIONS=$(screen -ls | awk '/[0-9]+\./ {print $1}')

if [ -z "$SESSIONS" ]; then
  echo "No running screen sessions found." >&2
  exit 0
fi

echo "Collecting last $LINES lines from each screen session..."
echo "Output file: $OUTPUT_FILE"
echo > "$OUTPUT_FILE"  # truncate/create

for SESS in $SESSIONS; do
  echo "Processing session: $SESS"

  TMPFILE=$(mktemp /tmp/screen_hardcopy.XXXXXX)

  # Ask screen to dump its scrollback/history to a temp file
  # -X sends a command to the session
  # 'hardcopy -h <file>' writes the full scrollback to that file
  if screen -S "$SESS" -X hardcopy -h "$TMPFILE" 2>/dev/null; then
    {
      echo "===== Session: $SESS ====="
      tail -n "$LINES" "$TMPFILE" || echo "(Could not read $LINES lines from hardcopy.)"
      echo
    } >> "$OUTPUT_FILE"
  else
    echo "Warning: could not hardcopy session $SESS" >&2
  fi

  rm -f "$TMPFILE"
done

echo "Done. Logs saved in: $OUTPUT_FILE"
