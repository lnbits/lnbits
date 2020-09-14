all: format check lnbits/static/css/base.css requirements.txt

format: prettier black

check: mypy checkprettier checkblack

prettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --write lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

black: $(shell find lnbits -name "*.py")
	./venv/bin/black lnbits

mypy: $(shell find lnbits -name "*.py")
	./venv/bin/mypy lnbits

checkprettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --check lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

checkblack: $(shell find lnbits -name "*.py")
	./venv/bin/black --check lnbits

lnbits/static/css/base.css: lnbits/static/scss/base.scss
	./venv/bin/pyscss -o lnbits/static/css/base.css lnbits/static/scss/base.scss

requirements.txt: Pipfile.lock
	cat Pipfile.lock | jq -r '.default | map_values(.version) | to_entries | map("\(.key)\(.value)") | join("\n")' > requirements.txt
