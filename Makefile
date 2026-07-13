MAKEFLAGS += -j 2

VENV_DIR := .env

ifeq ($(OS),Windows_NT)
PYTHON ?= py -3
VENV_PYTHON := $(VENV_DIR)\Scripts\python.exe
RUN_CMD := powershell -NoProfile -ExecutionPolicy Bypass -Command "& { . .\$(VENV_DIR)\Scripts\Activate.ps1; uvicorn main:app --reload --host 0.0.0.0 --port 5000 }"
else
PYTHON ?= python3
VENV_PYTHON := $(VENV_DIR)/bin/python
RUN_CMD := . $(VENV_DIR)/bin/activate && uvicorn main:app --reload --host 0.0.0.0 --port 5000
endif

.PHONY: setup run test setup_win setup_linux run_win run_linux test_win test_linux

setup:
	$(PYTHON) -m venv $(VENV_DIR)
	$(VENV_PYTHON) -m pip install --upgrade pip
	$(VENV_PYTHON) -m pip install -r requirements.txt

run:
	$(RUN_CMD)

test:
	$(VENV_PYTHON) -m pytest -q

setup_win: setup

setup_linux: setup

run_win:
	$(RUN_CMD)

run_linux:
	$(RUN_CMD)

test_win: test

test_linux: test
