#!/usr/bin/env bash
set -euo pipefail
CONFIG_PATH="${LLAMA_SERVER_CONFIG:-/mux-config/llama-server.yml}"

mapfile -t ARGS < <(python3 - "$CONFIG_PATH" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
section = None
cfg = {"server": {}, "sampling": {}}
def parse_scalar(raw):
    raw = raw.strip()
    if " #" in raw:
        raw = raw.split(" #", 1)[0].rstrip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        return raw[1:-1]
    low = raw.lower()
    if low in {"true", "yes", "on"}: return True
    if low in {"false", "no", "off"}: return False
    try:
        if any(ch in raw for ch in [".", "e", "E"]): return float(raw)
        return int(raw)
    except ValueError:
        return raw
for line in path.read_text(encoding="utf8").splitlines():
    if not line.strip() or line.lstrip().startswith("#"): continue
    if not line.startswith(" ") and line.rstrip().endswith(":"):
        section = line.rstrip()[:-1]; continue
    if section not in cfg or not line.startswith("  "): continue
    m = re.match(r"^\s{2}([^:#][^:]*):\s*(.*?)\s*$", line)
    if not m: continue
    key, raw = m.groups()
    if raw == "": continue
    cfg[section][key.strip()] = parse_scalar(raw)
args = []
def emit(k, v):
    opt = "--" + k
    if v is None: return
    if isinstance(v, bool):
        if k == "flash-attn": args.extend([opt, "on" if v else "off"])
        elif k == "cont-batching": args.append("--cont-batching" if v else "--no-cont-batching")
        elif k == "reasoning": args.extend([opt, "on" if v else "off"])
        elif k == "jinja": args.append("--jinja" if v else "--no-jinja")
        elif k == "slots": args.append("--slots" if v else "--no-slots")
        elif k == "ui": args.append("--ui" if v else "--no-ui")
        elif v: args.append(opt)
    else:
        args.extend([opt, str(v)])
for section_name in ["server", "sampling"]:
    for key, value in cfg.get(section_name, {}).items(): emit(key, value)
for item in args: print(item)
PY
)

echo "launching llama-server with ${#ARGS[@]} args from ${CONFIG_PATH}" >&2
printf 'llama-server args:' >&2
printf ' %q' "${ARGS[@]}" >&2
printf '
' >&2
exec llama-server "${ARGS[@]}"
