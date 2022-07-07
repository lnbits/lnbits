.PHONY: test

all: format check requirements.txt

format: prettier isort black 

check: mypy checkprettier checkblack

prettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --write lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

black: $(shell find lnbits -name "*.py")
	./venv/bin/black lnbits

isort: $(shell find lnbits -name "*.py") 
	./venv/bin/isort --profile black lnbits

mypy: $(shell find lnbits -name "*.py")
	./venv/bin/mypy lnbits
	./venv/bin/mypy lnbits/core
	./venv/bin/mypy lnbits/extensions/*

checkprettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --check lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

checkblack: $(shell find lnbits -name "*.py")
	./venv/bin/black --check lnbits

checkisort: $(shell find lnbits -name "*.py")
	./venv/bin/isort --check-only --profile black lnbits

Pipfile.lock: Pipfile
	./venv/bin/pipenv lock

requirements.txt: Pipfile.lock
	cat Pipfile.lock | jq -r '.default | map_values(.version) | to_entries | map("\(.key)\(.value)") | join("\n")' > requirements.txt

test:
	rm -rf ./tests/data
	mkdir -p ./tests/data
	FAKE_WALLET_SECRET="ToTheMoon1" \
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	./venv/bin/pytest -s

bak:
	# LNBITS_DATABASE_URL=postgres://postgres:postgres@0.0.0.0:5432/postgres
