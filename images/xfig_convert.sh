#!/usr/bin/env bash
# xfig_convert.sh — batch convert Xfig .fig files to SVG and/or PNG using fig2dev

set -u -o pipefail

# ------------ Defaults ------------
INPUT_DIR="."
OUTPUT_DIR="./out"
DO_SVG=true
DO_PNG=false
DPI=300
MAG=1.0
RECURSIVE=true
KEEP_STRUCTURE=true
OVERWRITE=false
JOBS=1   # >1 uses xargs -P if available

# ------------ Helpers -------------
usage() {
  cat <<'USAGE'
Usage: xfig_convert.sh [options]

Options:
  -i DIR   Input directory (default: .)
  -o DIR   Output root directory (default: ./out)
  --svg    Enable SVG export (default: on)
  --no-svg Disable SVG export
  --png    Enable PNG export (default: off)
  --no-png Disable PNG export
  -D N     PNG DPI (default: 300)
  -m F     Magnification factor (e.g., 2.0 ~ 200%) (default: 1.0)
  -r       Recurse into subfolders (default: on)
  -R       Do NOT recurse (only top-level)
  -S       Flatten output (do NOT mirror input subfolders)
  -w       Overwrite existing outputs (default: skip if exists)
  -j N     Parallel jobs (requires xargs -P; default: 1)
  -h       Show this help

Examples:
  # SVG only (default), recurse, mirror structure, output to ./out
  ./xfig_convert.sh -i figures -o build/graphics

  # PNG at 600 dpi + SVG, 4 parallel jobs
  ./xfig_convert.sh -i figs --png --svg -D 600 -j 4

  # Top-level only, flatten outputs, magnification 1.5
  ./xfig_convert.sh -R -S -m 1.5
USAGE
}

err() { printf "Error: %s\n" "$*" >&2; }
need() { command -v "$1" >/dev/null 2>&1 || { err "Missing dependency: $1"; exit 127; }; }

# ------------ Parse args ----------
while (( "$#" )); do
  case "$1" in
    -i) INPUT_DIR="${2:?}"; shift 2 ;;
    -o) OUTPUT_DIR="${2:?}"; shift 2 ;;
    --svg) DO_SVG=true; shift ;;
    --no-svg) DO_SVG=false; shift ;;
    --png) DO_PNG=true; shift ;;
    --no-png) DO_PNG=false; shift ;;
    -D) DPI="${2:?}"; shift 2 ;;
    -m) MAG="${2:?}"; shift 2 ;;
    -r) RECURSIVE=true; shift ;;
    -R) RECURSIVE=false; shift ;;
    -S) KEEP_STRUCTURE=false; shift ;;
    -w) OVERWRITE=true; shift ;;
    -j) JOBS="${2:?}"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) err "Unknown option: $1"; usage; exit 2 ;;
  esac
done

# ------------ Checks --------------
need fig2dev

if [[ ! -d "$INPUT_DIR" ]]; then
  err "Input directory not found: $INPUT_DIR"; exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Find .fig files
if $RECURSIVE; then
  mapfile -d '' FILES < <(find "$INPUT_DIR" -type f -name '*.fig' -print0 | sort -z)
else
  # shellcheck disable=SC2207
  FILES=($(printf '%s\0' "$INPUT_DIR"/*.fig 2>/dev/null | xargs -0 -I{} echo -n "{}"$'\0'))
fi

if (( ${#FILES[@]} == 0 )); then
  echo "[xfig_convert] No .fig files found in: $INPUT_DIR"
  exit 0
fi

echo "[xfig_convert] Found $(( ${#FILES[@]} )) .fig file(s). Output: $OUTPUT_DIR"
echo "[xfig_convert] Formats: SVG=$DO_SVG  PNG=$DO_PNG (DPI=$DPI MAG=$MAG)  Parallel jobs: $JOBS"

# ------------ Converter -----------
convert_one() {
  local in="$1"
  local rel outdir base stem svg png
  base="$(basename "$in")"
  stem="${base%.fig}"

  if $KEEP_STRUCTURE; then
    # Derive relative path under INPUT_DIR
    rel="${in#"$INPUT_DIR"/}"
    outdir="$(dirname "$OUTPUT_DIR/$rel")"
  else
    outdir="$OUTPUT_DIR"
  fi
  mkdir -p "$outdir"

  svg="$outdir/$stem.svg"
  png="$outdir/$stem.png"

  # SVG
  if $DO_SVG; then
    if $OVERWRITE || [[ ! -f "$svg" ]]; then
      if ! fig2dev -L svg "$in" "$svg" 2>/dev/null; then
        echo "  [SVG FAIL] $in" >&2
      else
        echo "  [SVG OK]   $svg"
      fi
    else
      echo "  [SVG SKIP] $svg exists"
    fi
  fi

  # PNG
  if $DO_PNG; then
    if $OVERWRITE || [[ ! -f "$png" ]]; then
      if ! fig2dev -L png -D "$DPI" -m "$MAG" "$in" "$png" 2>/dev/null; then
        echo "  [PNG FAIL] $in" >&2
      else
        echo "  [PNG OK]   $png"
      fi
    else
      echo "  [PNG SKIP] $png exists"
    fi
  fi
}

export -f convert_one
export INPUT_DIR OUTPUT_DIR DO_SVG DO_PNG DPI MAG KEEP_STRUCTURE OVERWRITE

# ------------ Run (optional parallel) ------------
if (( JOBS > 1 )) && command -v xargs >/dev/null 2>&1; then
  # Use xargs -P for parallelism
  printf '%s\0' "${FILES[@]}" | xargs -0 -n1 -P "$JOBS" bash -c 'convert_one "$0"' 
else
  # Sequential
  for f in "${FILES[@]}"; do
    convert_one "$f"
  done
fi

echo "[xfig_convert] Done."
