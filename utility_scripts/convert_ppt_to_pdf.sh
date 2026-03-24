#!/usr/bin/env bash

set -euo pipefail

delete_original=0
input_path=""

usage() {
  echo "Usage: $0 [--delete-original] /absolute/path/to/file-or-folder" >&2
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -d|--delete-original)
      delete_original=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    -*)
      echo "Error: unknown option: $1" >&2
      usage
      exit 1
      ;;
    *)
      if [[ -n "$input_path" ]]; then
        echo "Error: only one file or folder path may be provided" >&2
        usage
        exit 1
      fi
      input_path=$1
      shift
      ;;
  esac
done

if [[ -z "$input_path" ]]; then
  usage
  exit 1
fi

if ! command -v soffice >/dev/null 2>&1; then
  echo "Error: soffice is not installed. Install LibreOffice first." >&2
  exit 1
fi

convert_file() {
  local file_path=$1
  local dir_path
  local base_name
  local pdf_path
  dir_path=$(dirname "$file_path")
  base_name=$(basename "$file_path")
  base_name=${base_name%.*}
  pdf_path="$dir_path/$base_name.pdf"

  soffice --headless --convert-to pdf --outdir "$dir_path" "$file_path"

  if [[ $delete_original -eq 1 ]]; then
    if [[ -f "$pdf_path" ]]; then
      rm "$file_path"
    else
      echo "Error: expected PDF was not created for: $file_path" >&2
      exit 1
    fi
  fi
}

if [[ -f "$input_path" ]]; then
  case "$input_path" in
    *.ppt|*.PPT|*.pptx|*.PPTX)
      convert_file "$input_path"
      ;;
    *)
      echo "Error: file must end in .ppt or .pptx" >&2
      exit 1
      ;;
  esac
elif [[ -d "$input_path" ]]; then
  found=0
  while IFS= read -r -d '' file_path; do
    found=1
    convert_file "$file_path"
  done < <(find "$input_path" -maxdepth 1 -type f \( -name '*.ppt' -o -name '*.PPT' -o -name '*.pptx' -o -name '*.PPTX' \) -print0)

  if [[ $found -eq 0 ]]; then
    echo "No .ppt or .pptx files found in: $input_path" >&2
    exit 1
  fi
else
  echo "Error: path not found: $input_path" >&2
  exit 1
fi
