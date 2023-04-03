import os
import warnings
from pathlib import Path

LNBITS_PATH = Path("lnbits").absolute()



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
