import os
import warnings
from pathlib import Path

LNBITS_PATH = Path("lnbits").absolute()

# from ..lnbits.helpers import vendored_js, vendored_css
vendored_js = [
    "/static/vendor/moment.js",
    "/static/vendor/underscore.js",
    "/static/vendor/axios.js",
    "/static/vendor/vue.js",
    "/static/vendor/vue-router.js",
    "/static/vendor/vue-qrcode-reader.browser.js",
    "/static/vendor/vue-qrcode.js",
    "/static/vendor/vue-i18n.js",
    "/static/vendor/vuex.js",
    "/static/vendor/quasar.ie.polyfills.umd.min.js",
    "/static/vendor/quasar.umd.js",
    "/static/vendor/Chart.bundle.js",
]

vendored_css = [
    "/static/vendor/quasar.css",
    "/static/vendor/Chart.css",
    "/static/vendor/vue-qrcode-reader.css",
]


def url_for_vendored(abspath: str) -> str:
    return f"/{os.path.relpath(abspath, LNBITS_PATH)}"


def transpile_scss():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from scss.compiler import compile_string  # type: ignore

        with open(os.path.join(LNBITS_PATH, "static/scss/base.scss")) as scss:
            with open(os.path.join(LNBITS_PATH, "static/css/base.css"), "w") as css:
                css.write(compile_string(scss.read()))


def bundle_vendored():
    for files, outputpath in [
        (vendored_js, os.path.join(LNBITS_PATH, "static/bundle.js")),
        (vendored_css, os.path.join(LNBITS_PATH, "static/bundle.css")),
    ]:
        output = ""
        for path in files:
            with open(f"{LNBITS_PATH}{path}") as f:
                output += f.read() + ";\n"
        with open(outputpath, "w") as f:
            f.write(output)


def build():
    transpile_scss()
    bundle_vendored()


if __name__ == "__main__":
    build()
