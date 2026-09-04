#!/usr/bin/env bash
set -euo pipefail

if [[ "$#" -ne 1 ]]; then
  printf 'usage: %s <release-tag>\n' "${0##*/}" >&2
  exit 2
fi

tag="$1"
ref="refs/tags/$tag"

object_type="$(git cat-file -t "$ref" 2>/dev/null || true)"
if [[ "$object_type" != "tag" ]]; then
  printf 'release tag must exist as an annotated tag object: %s (found %s)\n' \
    "$tag" "${object_type:-missing}" >&2
  exit 2
fi

target_type="$(git cat-file -p "$ref" | awk '$1 == "type" {print $2; exit}')"
if [[ "$target_type" != "commit" ]]; then
  printf 'annotated release tag must point directly to a commit: %s (found %s)\n' \
    "$tag" "${target_type:-unknown}" >&2
  exit 2
fi

source_sha="$(git rev-list -n 1 "$tag")"
checkout_sha="$(git rev-parse HEAD)"
if [[ "$source_sha" != "$checkout_sha" ]]; then
  printf 'release tag resolves to %s but checkout is %s\n' \
    "$source_sha" "$checkout_sha" >&2
  exit 2
fi

printf '%s\n' "$source_sha"
