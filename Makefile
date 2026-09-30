# TGF — macOS. Kanallar: stable (default) va dev (TGF_CHANNEL=dev, alohida ~/.tgf-dev).
PY ?= python3.12
VENV := .venv
BIN := $(VENV)/bin
UID := $(shell id -u)

.PHONY: install test check run run-dev agent agent-dev unagent unagent-dev recalibrate sounds profiles logs clean

install:
	@command -v $(PY) >/dev/null || { echo "$(PY) yo'q: brew install python@3.12"; exit 1; }
	$(PY) -m venv $(VENV)
	$(BIN)/python -m pip install -U pip
	$(BIN)/python -m pip install -e ".[dev]"
	$(BIN)/python -m pip check
	$(BIN)/python -c "import cv2, mediapipe as mp; assert hasattr(mp, 'solutions'); print('OK')"

test:
	$(BIN)/python -m pytest -q

check: test
	$(BIN)/python -m tgf --version

run:
	$(BIN)/python -m tgf

run-dev:
	TGF_CHANNEL=dev $(BIN)/python -m tgf

agent:
	scripts/install_launchd.sh stable
agent-dev:
	scripts/install_launchd.sh dev
unagent:
	scripts/uninstall_launchd.sh stable
unagent-dev:
	scripts/uninstall_launchd.sh dev

recalibrate:
	launchctl kill SIGUSR1 gui/$(UID)/com.tgf.posture

sounds:
	$(BIN)/python -m tgf --list-sounds

profiles:
	$(BIN)/python -m tgf --profiles

logs:
	tail -n 50 -f ~/.tgf/stderr.log ~/.tgf/stdout.log

clean:
	rm -rf $(VENV) *.egg-info .pytest_cache
