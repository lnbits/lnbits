.PHONY: test

all: format check

format: prettier black ruff

check: mypy pyright checkblack checkruff checkprettier checkbundle

test: test-unit test-wallets test-api test-regtest

prettier:
	uv run ./node_modules/.bin/prettier --write .

pyright:
	uv run ./node_modules/.bin/pyright

mypy:
	uv run mypy

black:
	uv run black .

ruff:
	uv run ruff check . --fix

checkruff:
	uv run ruff check .

checkprettier:
	uv run ./node_modules/.bin/prettier --check .

checkblack:
	uv run black --check .

checkeditorconfig:
	editorconfig-checker

dev:
	uv run lnbits --reload

docker:
	docker build -t lnbits/lnbits .

test-wallets:
	LNBITS_DATA_FOLDER="./tests/data" \
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	uv run pytest tests/wallets

test-unit:
	LNBITS_DATA_FOLDER="./tests/data" \
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	uv run pytest tests/unit

test-api:
	LNBITS_DATA_FOLDER="./tests/data" \
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	uv run pytest tests/api

test-e2e:
	npm exec playwright install chromium
	npm run test:e2e

test-regtest:
	rm -rf ./tests/data
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	uv run pytest tests/regtest

test-migration:
	LNBITS_ADMIN_UI=True \
	make test-api
	HOST=0.0.0.0 \
	PORT=5002 \
	LNBITS_DATA_FOLDER="./tests/data" \
	timeout 5s uv run lnbits --host 0.0.0.0 --port 5002 || code=$?; if [[ $code -ne 124 && $code -ne 0 ]]; then exit $code; fi
	HOST=0.0.0.0 \
	PORT=5002 \
	LNBITS_DATABASE_URL="postgres://lnbits:lnbits@localhost:5432/migration" \
	LNBITS_ADMIN_UI=False \
	timeout 5s uv run lnbits --host 0.0.0.0 --port 5002 || code=$?; if [[ $code -ne 124 && $code -ne 0 ]]; then exit $code; fi
	LNBITS_DATA_FOLDER="./tests/data" \
	LNBITS_DATABASE_URL="postgres://lnbits:lnbits@localhost:5432/migration" \
	uv run python tools/conv.py

migration:
	uv run python tools/conv.py

openapi:
	@OPENAPI_SPEC_FILE=$$(mktemp); \
	OPENAPI_DATA_DIR=$$(mktemp -d); \
	LNBITS_ADMIN_UI=False \
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	LNBITS_DATA_FOLDER="$$OPENAPI_DATA_DIR" \
	LNBITS_EXTENSIONS_DEFAULT_INSTALL='[]' \
	LNBITS_EXTENSIONS_DEACTIVATE_ALL=true \
	PYTHONUNBUFFERED=1 \
	DEBUG=false \
	HOST=0.0.0.0 \
	PORT=5003 \
	uv run lnbits & \
	OPENAPI_SERVER_PID=$$!; \
	trap 'kill "$$OPENAPI_SERVER_PID" 2>/dev/null || true; wait "$$OPENAPI_SERVER_PID" 2>/dev/null || true; rm -f "$$OPENAPI_SPEC_FILE"; rm -rf "$$OPENAPI_DATA_DIR"' EXIT; \
	OPENAPI_ATTEMPT=0; \
	while [ "$$OPENAPI_ATTEMPT" -lt 60 ]; do \
		if curl --fail --silent --max-time 2 --output "$$OPENAPI_SPEC_FILE" \
			http://127.0.0.1:5003/openapi.json; then \
			uv run openapi-spec-validator --errors=all "$$OPENAPI_SPEC_FILE"; \
			exit $$?; \
		fi; \
		if ! kill -0 "$$OPENAPI_SERVER_PID" 2>/dev/null; then \
			echo "LNbits exited before serving the OpenAPI schema." >&2; \
			exit 1; \
		fi; \
		OPENAPI_ATTEMPT=$$((OPENAPI_ATTEMPT + 1)); \
		sleep 1; \
	done; \
	echo "LNbits did not serve the OpenAPI schema within 60 seconds." >&2; \
	exit 1

bak:
	# LNBITS_DATABASE_URL=postgres://postgres:postgres@0.0.0.0:5432/postgres
	#

sass:
	npm run sass

bundle:
	npm install
	npm run bundle
	uv run ./node_modules/.bin/prettier -w ./lnbits/static/vendor.json

checkbundle:
	cp lnbits/static/bundle.min.js lnbits/static/bundle.min.js.old
	cp lnbits/static/bundle.min.css lnbits/static/bundle.min.css.old
	cp lnbits/static/bundle-components.min.js lnbits/static/bundle-components.min.js.old
	make bundle
	diff -q lnbits/static/bundle.min.js lnbits/static/bundle.min.js.old || exit 1
	diff -q lnbits/static/bundle.min.css lnbits/static/bundle.min.css.old || exit 1
	diff -q lnbits/static/bundle-components.min.js lnbits/static/bundle-components.min.js.old || exit 1
	@echo "Bundle is OK"
	rm lnbits/static/bundle.min.js.old
	rm lnbits/static/bundle.min.css.old
	rm lnbits/static/bundle-components.min.js.old

install-pre-commit-hook:
	@echo "Installing pre-commit hook to git"
	@echo "Uninstall the hook with uv run pre-commit uninstall"
	uv run pre-commit install

pre-commit:
	uv run pre-commit run --all-files
