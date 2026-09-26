#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
[[ "$(go env GOVERSION)" == go1.27.1 ]] || { echo 'requires Go 1.27.1' >&2; exit 1; }
export GOTOOLCHAIN=local
case "${1:-core}" in
  core)
    go mod verify
    go vet -mod=readonly ./...
    go test -mod=readonly -race -count=1 -v ./...
    ;;
  package) python3 package_probe.py ;;
  *) echo 'usage: check.sh core|package' >&2; exit 1 ;;
esac
