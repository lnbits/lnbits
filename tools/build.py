import os
import warnings
from pathlib import Path
from typing import List

LNBITS_PATH = Path("lnbits").absolute()


def get_js_vendored() -> List[str]:
    return [
        "../node_modules/moment/min/moment.min.js",
        '../node_modules/underscore/underscore-min.js',
        '../node_modules/axios/dist/axios.min.js',
        '../node_modules/vue/dist/vue.min.js',
        '../node_modules/vue-router/dist/vue-router.min.js',
        '../node_modules/vue-qrcode-reader/dist/vue-qrcode-reader.browser.js',
        '../node_modules/@chenfengyuan/vue-qrcode/dist/vue-qrcode.min.js',
        '../node_modules/vuex/dist/vuex.min.js',
        '../node_modules/quasar/dist/quasar.ie.polyfills.umd.min.js',
        '../node_modules/quasar/dist/quasar.umd.min.js',
        '../node_modules/chart.js/dist/Chart.bundle.min.js',
    ]


def get_css_vendored() -> List[str]:
    return [
        '../node_modules/quasar/dist/quasar.min.css',
        '../node_modules/chart.js/dist/Chart.min.css',
        '../node_modules/vue-qrcode-reader/dist/vue-qrcode-reader.css',
    ]


def url_for_vendored(abspath: str) -> str:
    return "/" + os.path.relpath(abspath, LNBITS_PATH)


def transpile_scss():
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        from scss.compiler import compile_string  # type: ignore

        with open(os.path.join(LNBITS_PATH, "static/scss/base.scss")) as scss:
            with open(os.path.join(LNBITS_PATH, "static/css/base.css"), "w") as css:
                css.write(compile_string(scss.read()))


def bundle_vendored():
    for getfiles, outputpath in [
        (get_js_vendored, os.path.join(LNBITS_PATH, "static/bundle.js")),
        (get_css_vendored, os.path.join(LNBITS_PATH, "static/bundle.css")),
    ]:
        output = ""
        for path in getfiles():
            with open(f"{LNBITS_PATH}/{path}") as f:
                output += "/* " + url_for_vendored(path) + " */\n" + f.read() + ";\n"
        with open(outputpath, "w") as f:
            f.write(output)


def build():
    transpile_scss()
    bundle_vendored()


if __name__ == "__main__":
    build()
