#!/bin/sh
set -eu
cd "$(dirname "$0")/control"
node --check web/app.js
node --check web/system.js
node ../test-system-ui.js
node ../test-roaming-ui.js
node ../test-wifi-ui.js
node ../test-vowifi-ui.js
node ../test-ui-actions.js
python3 ../compress-web.py
# Go 1.26 adds an unused 32 MiB FIPS entropy buffer to .bss. B03 kills that
# executable during execve. Pin this target's supported, tested toolchain.
export GOTOOLCHAIN=go1.25.12
gofmt -w ./*.go
go test ./...
GOOS=linux GOARCH=arm GOARM=7,softfloat CGO_ENABLED=0 go build -buildvcs=false -trimpath -ldflags='-s -w' -o ../build/mf79u-control .
