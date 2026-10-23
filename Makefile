# Windows `bash` is the WSL launcher; use Git Bash by short path (make can't take spaces).
ifeq ($(OS),Windows_NT)
SHELL := C:/PROGRA~1/Git/bin/bash.exe
else
SHELL := bash
endif
.SHELLFLAGS := -eu -o pipefail -c
.DEFAULT_GOAL := test

AGENT := agent
CONTROL_PLANE := control-plane

.PHONY: setup test test-py test-go lint fmt up down

setup:
	@command -v uv >/dev/null || { echo "uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/" >&2; exit 1; }
	cd $(AGENT) && uv sync --locked
	cd $(CONTROL_PLANE) && go mod download

test: test-py test-go

test-py:
	cd $(AGENT) && uv run pytest

test-go:
	cd $(CONTROL_PLANE) && go test -race ./...

lint:
	cd $(AGENT) && uv run ruff check && uv run ruff format --check
	@cd $(CONTROL_PLANE) && unformatted="$$(gofmt -l .)" && if [ -n "$$unformatted" ]; then echo "$$unformatted"; echo "gofmt: files above need formatting, run make fmt" >&2; exit 1; fi
	cd $(CONTROL_PLANE) && go vet ./...

fmt:
	cd $(AGENT) && uv run ruff check --fix-only && uv run ruff format
	cd $(CONTROL_PLANE) && gofmt -w .

up:
	docker compose up -d --wait

down:
	docker compose down
