.PHONY: test

all: format check requirements.txt

format: prettier isort black

check: mypy checkprettier checkisort checkblack

prettier: $(shell find lnbits -name "*.js" -o -name ".html")
	./node_modules/.bin/prettier --write lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js lnbits/extensions/*/static/components/*/*.js  lnbits/extensions/*/static/components/*/*.html

pyright:
	./node_modules/.bin/pyright

black:
	poetry run black .

mypy:
	poetry run mypy

isort:
	poetry run isort .

checkprettier: $(shell find lnbits -name "*.js" -o -name ".html")
	./node_modules/.bin/prettier --check lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js lnbits/extensions/*/static/components/*/*.js lnbits/extensions/*/static/components/*/*.html

checkblack:
	poetry run black --check .

checkisort:
	poetry run isort --check-only .

test:
	BOLTZ_NETWORK="regtest" \
	BOLTZ_URL="http://127.0.0.1:9001" \
	BOLTZ_MEMPOOL_SPACE_URL="http://127.0.0.1:8080" \
	BOLTZ_MEMPOOL_SPACE_URL_WS="ws://127.0.0.1:8080" \
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	FAKE_WALLET_SECRET="ToTheMoon1" \
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	poetry run pytest

test-real-wallet:
	BOLTZ_NETWORK="regtest" \
	BOLTZ_URL="http://127.0.0.1:9001" \
	BOLTZ_MEMPOOL_SPACE_URL="http://127.0.0.1:8080" \
	BOLTZ_MEMPOOL_SPACE_URL_WS="ws://127.0.0.1:8080" \
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	poetry run pytest

test-venv:
	BOLTZ_NETWORK="regtest" \
	BOLTZ_URL="http://127.0.0.1:9001" \
	BOLTZ_MEMPOOL_SPACE_URL="http://127.0.0.1:8080" \
	BOLTZ_MEMPOOL_SPACE_URL_WS="ws://127.0.0.1:8080" \
	LNBITS_BACKEND_WALLET_CLASS="FakeWallet" \
	FAKE_WALLET_SECRET="ToTheMoon1" \
	LNBITS_DATA_FOLDER="./tests/data" \
	PYTHONUNBUFFERED=1 \
	DEBUG=true \
	./venv/bin/pytest --durations=1 -s --cov=lnbits --cov-report=xml tests

test-migration:
	rm -rf ./migration-data
	mkdir -p ./migration-data
	unzip tests/data/mock_data.zip -d ./migration-data
	HOST=0.0.0.0 \
	PORT=5002 \
	LNBITS_DATA_FOLDER="./migration-data" \
	timeout 5s poetry run lnbits --host 0.0.0.0 --port 5002 || code=$?; if [[ $code -ne 124 && $code -ne 0 ]]; then exit $code; fi
	HOST=0.0.0.0 \
	PORT=5002 \
	LNBITS_DATABASE_URL="postgres://lnbits:lnbits@localhost:5432/migration" \
	timeout 5s poetry run lnbits --host 0.0.0.0 --port 5002 || code=$?; if [[ $code -ne 124 && $code -ne 0 ]]; then exit $code; fi
	LNBITS_DATA_FOLDER="./migration-data" \
	LNBITS_DATABASE_URL="postgres://lnbits:lnbits@localhost:5432/migration" \
	poetry run python tools/conv.py

migration:
	poetry run python tools/conv.py

bak:
	# LNBITS_DATABASE_URL=postgres://postgres:postgres@0.0.0.0:5432/postgres
