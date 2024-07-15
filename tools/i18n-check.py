import os
import re


def get_translation_ids_from_source():
    # find all HTML files in selected directories
    files = []
    for start in ["lnbits/core/templates", "lnbits/templates", "lnbits/static/js"]:
        for check_dir, _, filenames in os.walk(start):
            for filename in filenames:
                if filename.endswith(".html") or filename.endswith(".js"):
                    fn = os.path.join(check_dir, filename)
                    files.append(fn)
    # find all $t('...') and $t("...") calls in HTML files
    # and extract the string inside the quotes
    p1 = re.compile(r"\$t\('([^']*)'")
    p2 = re.compile(r'\$t\("([^"]*)"')
    ids = []
    for fn in files:
        with open(fn) as f:
            text = f.read()
            m1 = re.findall(p1, text)
            m2 = re.findall(p2, text)
            for m in m1:
                ids.append(m)
            for m in m2:
                ids.append(m)
    return ids


def get_translation_ids_for_language(language):
    ids = []
    for line in open(f"lnbits/static/i18n/{language}.js"):
        # extract ids from lines like that start with exactly 2 spaces
        if line.startswith("  ") and not line.startswith("   "):
            m = line[2:].split(":")[0]
            ids.append(m)
    return ids


src_ids = get_translation_ids_from_source()
print(f"Number of ids from source: {len(src_ids)}")

en_ids = get_translation_ids_for_language("en")
missing = set(src_ids) - set(en_ids)
extra = set(en_ids) - set(src_ids)
if len(missing) > 0:
    print()
    print(f'Missing ids in language "en": {len(missing)}')
    for i in sorted(missing):
        print(f"  {i}")
if len(extra) > 0:
    print()
    print(f'Extraneous ids in language "en": {len(extra)}')
    for i in sorted(extra):
        print(f"  {i}")

languages = []

for *_, filenames in os.walk("lnbits/static/i18n"):
    for filename in filenames:
        if filename.endswith(".js") and filename not in ["i18n.js", "en.js"]:
            languages.append(filename.split(".")[0])

for lang in sorted(languages):
    ids = get_translation_ids_for_language(lang)
    missing = set(en_ids) - set(ids)
    extra = set(ids) - set(en_ids)
    if len(missing) > 0:
        print()
        print(f'Missing ids in language "{lang}": {len(missing)}')
        for i in sorted(missing):
            print(f"  {i}")
    if len(extra) > 0:
        print()
        print(f'Extraneous ids in language "{lang}": {len(extra)}')
        for i in sorted(extra):
            print(f"  {i}")
