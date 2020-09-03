all: format check

format: prettier black

check: mypy checkprettier checkblack

prettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --write lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

black: $(shell find lnbits -name "*.py")
	./venv/bin/black --line-length 120 lnbits

mypy: $(shell find lnbits -name "*.py")
	./venv/bin/mypy lnbits

checkprettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --check lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

checkblack: $(shell find lnbits -name "*.py")
	./venv/bin/black --check --line-length 120 lnbits
