# Public entry point for every supported build, test and device operation.
SHELL := /bin/sh
.DEFAULT_GOAL := help
.NOTPARALLEL:
ROOT := $(abspath $(dir $(lastword $(MAKEFILE_LIST))))
FW := firmware/mf79u
PYTHON ?= python3
PY := $(ROOT)/.venv/bin/python
ADB ?= adb
DEVICE_SERIAL := $(ANDROID_SERIAL)
SERIAL ?= $(DEVICE_SERIAL)
HOST_IP ?= 192.168.0.169
HTTP_PORT ?= 18089
TASK ?=
ARGS ?=
VENDOR_ROOT ?=
KERNEL ?=
PACKAGE ?= dist/mf79u-gateway.tar.gz
REBOOT ?= 0
BACKUP ?=
GITLEAKS ?= auto
export ADB HOST_IP HTTP_PORT TASK ARGS VENDOR_ROOT KERNEL PACKAGE REBOOT BACKUP GITLEAKS
export ANDROID_SERIAL := $(SERIAL)
export GOTOOLCHAIN := go1.25.12
export PATH := $(ROOT)/.venv/bin:$(PATH)
.PHONY: fetch-check clean-checkout workflow-check migration-coverage test-workflow build-host-tools usb-at
build-host-tools:
	@cd "$(ROOT)" && $(PYTHON) scripts/host-tool.py
usb-at: build-host-tools
	@cd "$(ROOT)" && $(PYTHON) scripts/host-tool.py --run
workflow-check:
	@cd "$(ROOT)" && go run github.com/rhysd/actionlint/cmd/actionlint@v1.7.7 .github/workflows/firmware.yml
fetch-check:
	@cd "$(ROOT)" && $(PYTHON) scripts/fetch-check.py
clean-checkout:
	@cd "$(ROOT)" && $(PYTHON) scripts/clean-checkout.py
.PHONY: help bootstrap deps toolchain sdk build build-control build-native build-sip build-ims build-cs build-vowifi build-system build-adb build-helpers test test-go test-js test-native test-sip lint audit secrets verify-migration package package-check vendor-import vendor-check device-status verify-device install install-plan restore task tasks clean ci

help:
	@printf '%s\n' 'make bootstrap       Python environment' 'make build           All firmware components (Docker + Go + Node)' 'make test            Offline tests; no modem or PBX access' 'make ci              Full build, isolated tests and package audit' 'make package         Complete checked overlay + on-device B03 patch recipes' 'make install-plan    Read-only compatibility/idle/checksum/space check' 'make install         Install/update complete overlay; SERIAL=... HOST_IP=...' 'make verify-device   Read-only installed-artifact/runtime verification' 'make restore         Restore the local backup; BACKUP=...' 'make vendor-import   Optional private historical inputs: VENDOR_ROOT=... KERNEL=...' 'make audit           Migration coverage, documentation and secret checks' 'make task TASK=name ARGS="..."   Historical tools through this Makefile' 'make tasks           List preserved tools'

bootstrap:
	@cd "$(ROOT)" && $(PYTHON) scripts/bootstrap.py

deps: bootstrap
	@cd "$(ROOT)" && $(PY) scripts/deps.py

toolchain:
	@cd "$(ROOT)" && docker build -t mf79u-build-tools:local -f $(FW)/Dockerfile .
	@docker tag mf79u-build-tools:local mf79u-system-tools:local

sdk: toolchain
	@cd "$(ROOT)" && $(PYTHON) scripts/sdk.py

build: deps sdk build-control build-native build-sip build-ims build-cs build-vowifi build-system build-adb build-helpers

build-control:
	@cd "$(ROOT)" && mkdir -p $(FW)/build && sh $(FW)/build-control.sh
build-native: deps toolchain
	@cd "$(ROOT)" && sh $(FW)/build-native-cp.sh
build-sip: deps toolchain
	@cd "$(ROOT)" && sh $(FW)/build-sip-deps.sh && sh $(FW)/build-sip-gateway.sh
build-ims: deps sdk
	@cd "$(ROOT)" && sh $(FW)/build-codec.sh && sh $(FW)/build-ims-diagnostics.sh
build-cs: bootstrap toolchain
	@cd "$(ROOT)" && $(PY) $(FW)/build-cs-voice.py && sh $(FW)/build-cs-runtime.sh
build-vowifi: deps toolchain
	@cd "$(ROOT)" && sh $(FW)/build-vowifi.sh
build-system: deps toolchain
	@cd "$(ROOT)" && sh $(FW)/build-system-tools.sh
build-adb: sdk
	@cd "$(ROOT)" && sh $(FW)/build-adb-boot.sh
build-helpers: toolchain
	@cd "$(ROOT)" && $(PYTHON) scripts/build-helpers.py

test: deps sdk build-native build-sip lint test-go test-js test-native test-sip test-workflow
test-workflow:
	@cd "$(ROOT)" && $(PYTHON) scripts/test-workflow.py
test-go: build-control toolchain
	@cd "$(ROOT)" && $(PYTHON) scripts/test-go.py
test-js:
	@cd "$(ROOT)" && node $(FW)/test-system-ui.js && node $(FW)/test-roaming-ui.js && node $(FW)/test-wifi-ui.js && node $(FW)/test-vowifi-ui.js
test-native: toolchain
	@cd "$(ROOT)" && $(PYTHON) scripts/test-native.py
test-sip: build-native build-sip
	@cd "$(ROOT)" && $(PYTHON) scripts/test-sip.py
lint:
	@cd "$(ROOT)" && $(PYTHON) scripts/audit.py --lint
audit: lint migration-coverage secrets
	@cd "$(ROOT)" && $(PYTHON) scripts/audit.py
secrets:
	@cd "$(ROOT)" && $(PYTHON) scripts/audit.py --publication
verify-migration:
	@cd "$(ROOT)" && $(PYTHON) scripts/audit.py --migration --strict
migration-coverage:
	@cd "$(ROOT)" && $(PYTHON) scripts/audit.py --migration
package: build
	@cd "$(ROOT)" && $(PYTHON) scripts/package.py
package-check:
	@cd "$(ROOT)" && $(PYTHON) scripts/package.py --check
vendor-import: bootstrap
	@cd "$(ROOT)" && $(PY) scripts/vendor.py --import-inputs
vendor-check:
	@cd "$(ROOT)" && $(PYTHON) scripts/vendor.py
device-status:
	@cd "$(ROOT)" && $(PYTHON) scripts/device.py status
verify-device:
	@cd "$(ROOT)" && $(PYTHON) scripts/device.py verify
install-plan:
	@cd "$(ROOT)" && $(PYTHON) scripts/device.py plan
install:
	@cd "$(ROOT)" && $(PYTHON) scripts/device.py install
restore:
	@cd "$(ROOT)" && $(PYTHON) scripts/device.py restore
tasks:
	@cd "$(ROOT)" && $(PYTHON) scripts/task.py --list
task: bootstrap
	@cd "$(ROOT)" && $(PY) scripts/task.py
clean:
	@cd "$(ROOT)" && $(PYTHON) scripts/clean.py
ci: workflow-check build test package package-check audit
