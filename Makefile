prettier: $(shell find lnbits -name "*.js" -name ".html")
	./node_modules/.bin/prettier --write lnbits/static/js/*.js lnbits/core/static/js/*.js lnbits/extensions/*/templates/*/*.html ./lnbits/core/templates/core/*.html lnbits/templates/*.html lnbits/extensions/*/static/js/*.js

mypy: $(shell find lnbits -name "*.py")
	mypy lnbits
