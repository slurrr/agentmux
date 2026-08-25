#!/usr/bin/env bash
set -euo pipefail
CONFIG_PATH="${VLLM_CONFIG_PATH:-/mux-config/vllm-config.yml}"
MODEL_PATH="${VLLM_MODEL_PATH:-}"

mapfile -t ARGS < <(python3 - "$CONFIG_PATH" <<'PY'
import re
import sys
from pathlib import Path
path = Path(sys.argv[1])
section = None
cfg = {"server": {}, "sampling": {}}
def parse_scalar(raw):
    raw = raw.strip()
    if " #" in raw: raw = raw.split(" #", 1)[0].rstrip()
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")): return raw[1:-1]
    low = raw.lower()
    if low in {"true", "yes", "on"}: return True
    if low in {"false", "no", "off"}: return False
    try:
        if any(ch in raw for ch in [".", "e", "E"]): return float(raw)
        return int(raw)
    except ValueError: return raw
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
        if v: args.append(opt)
    elif isinstance(v, list):
        for item in v: args.extend([opt, str(item)])
    else: args.extend([opt, str(v)])
for key, value in cfg.get("server", {}).items(): emit(key, value)
for item in args: print(item)
PY
)

echo "launching vLLM with ${#ARGS[@]} args from ${CONFIG_PATH}" >&2
if [ -n "$MODEL_PATH" ]; then
    exec python3 -m vllm.entrypoints.openai.api_server \
        --host "0.0.0.0" \
        --port "5000" \
        --model "$MODEL_PATH" \
        "${ARGS[@]}"
else
    echo "ERROR: VLLM_MODEL_PATH not set" >&2
    exit 1
fi
