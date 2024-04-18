.PHONY: test

all: format check

format: prettier black ruff

check: mypy pyright checkblack checkruff checkprettier checkbundle

test: test-unit test-wallets test-api test-regtest

prettier:
	poetry run ./node_modules/.bin/prettier --write lnbits

pyright:
	poetry run ./node_modules/.bin/pyright

mypy:
	poetry run mypy

black:
	poetry run black .

ruff:
	poetry run ruff check . --fix

checkruff:
	poetry run ruff check .

checkprettier:
	poetry run ./node_modules/.bin/prettier --check lnbits

checkblack:
	poetry run black --check .

checkeditorconfig:
	editorconfig-checker

dev:
	poetry run lnbits --reload

test-wallets:
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	poetry run pytest tests/wallets

test-unit:
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	poetry run pytest tests/unit

test-api:
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	poetry run pytest tests/api

test-regtest:
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	poetry run pytest tests/regtest

test-migration:
	LNBITS_ADMIN_UI=True \
	make test-api
	HOST=0.0.0.0 \
	PORT=5002 \
	LNBITS_DATA_FOLDER="./tests/data" \
	timeout 5s poetry run lnbits --host 0.0.0.0 --port 5002 || code=$?; if [[ $code -ne 124 && $code -ne 0 ]]; then exit $code; fi
	HOST=0.0.0.0 \
	PORT=5002 \
	LNBITS_DATABASE_URL="postgres://lnbits:lnbits@localhost:5432/migration" \
	timeout 5s poetry run lnbits --host 0.0.0.0 --port 5002 || code=$?; if [[ $code -ne 124 && $code -ne 0 ]]; then exit $code; fi
	LNBITS_DATA_FOLDER="./tests/data" \
	LNBITS_DATABASE_URL="postgres://lnbits:lnbits@localhost:5432/migration" \
	poetry run python tools/conv.py

migration:
	poetry run python tools/conv.py

openapi:
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	HOST=0.0.0.0 \
	PORT=5003 \
	poetry run lnbits &
	sleep 15
	curl -s http://0.0.0.0:5003/openapi.json | poetry run openapi-spec-validator --errors=all -
	# kill -9 %1

bak:
	# LNBITS_DATABASE_URL=postgres://postgres:postgres@0.0.0.0:5432/postgres
	#

sass:
	npm run sass

bundle:
	npm install
	npm run sass
	npm run vendor_copy
	npm run vendor_json
	poetry run ./node_modules/.bin/prettier -w ./lnbits/static/vendor.json
	npm run vendor_bundle_css
	npm run vendor_minify_css
	npm run vendor_bundle_js
	npm run vendor_minify_js

checkbundle:
	cp lnbits/static/bundle.min.js lnbits/static/bundle.min.js.old
	cp lnbits/static/bundle.min.css lnbits/static/bundle.min.css.old
	make bundle
	diff -q lnbits/static/bundle.min.js lnbits/static/bundle.min.js.old || exit 1
	diff -q lnbits/static/bundle.min.css lnbits/static/bundle.min.css.old || exit 1
	@echo "Bundle is OK"
	rm lnbits/static/bundle.min.js.old
	rm lnbits/static/bundle.min.css.old

install-pre-commit-hook:
	@echo "Installing pre-commit hook to git"
	@echo "Uninstall the hook with poetry run pre-commit uninstall"
	poetry run pre-commit install

pre-commit:
	poetry run pre-commit run --all-files
