.PHONY: test

all: format check requirements.txt

format: prettier isort black

check: mypy checkprettier checkblack

prettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --write lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

black: $(shell find lnbits -name "*.py")
	./venv/bin/black lnbits

mypy: $(shell find lnbits -name "*.py")
	./venv/bin/mypy lnbits
	./venv/bin/mypy lnbits/core
	./venv/bin/mypy lnbits/extensions/*

isort: $(shell find lnbits -name "*.py")
	./venv/bin/isort --profile black lnbits

checkprettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --check lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

checkblack: $(shell find lnbits -name "*.py")
	./venv/bin/black --check lnbits

checkisort: $(shell find lnbits -name "*.py")
	./venv/bin/isort --profile black --check-only lnbits

Pipfile.lock: Pipfile
	./venv/bin/pipenv lock

requirements.txt: Pipfile.lock
	cat Pipfile.lock | jq -r '.default | map_values(.version) | to_entries | map("\(.key)\(.value)") | join("\n")' > requirements.txt

test:
	mkdir -p ./tests/data
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	FAKE_WALLET_SECRET="ToTheMoon1" \
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	./venv/bin/pytest --durations=1 -s --cov=lnbits --cov-report=xml tests

test-real-wallet:
	mkdir -p ./tests/data
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	./venv/bin/pytest --durations=1 -s --cov=lnbits --cov-report=xml tests

test-pipenv:
	mkdir -p ./tests/data
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	FAKE_WALLET_SECRET="ToTheMoon1" \
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	pipenv run pytest --durations=1 -s --cov=lnbits --cov-report=xml tests

bak:
	# LNBITS_DATABASE_URL=postgres://postgres:postgres@0.0.0.0:5432/postgres
