import math


def si_classifier(val):
    suffixes = {
        24: {"long_suffix": "yotta", "short_suffix": "Y", "scalar": 10**24},
        21: {"long_suffix": "zetta", "short_suffix": "Z", "scalar": 10**21},
        18: {"long_suffix": "exa", "short_suffix": "E", "scalar": 10**18},
        15: {"long_suffix": "peta", "short_suffix": "P", "scalar": 10**15},
        12: {"long_suffix": "tera", "short_suffix": "T", "scalar": 10**12},
        9: {"long_suffix": "giga", "short_suffix": "G", "scalar": 10**9},
        6: {"long_suffix": "mega", "short_suffix": "M", "scalar": 10**6},
        3: {"long_suffix": "kilo", "short_suffix": "k", "scalar": 10**3},
        0: {"long_suffix": "", "short_suffix": "", "scalar": 10**0},
        -3: {"long_suffix": "milli", "short_suffix": "m", "scalar": 10**-3},
        -6: {"long_suffix": "micro", "short_suffix": "µ", "scalar": 10**-6},
        -9: {"long_suffix": "nano", "short_suffix": "n", "scalar": 10**-9},
        -12: {"long_suffix": "pico", "short_suffix": "p", "scalar": 10**-12},
        -15: {"long_suffix": "femto", "short_suffix": "f", "scalar": 10**-15},
        -18: {"long_suffix": "atto", "short_suffix": "a", "scalar": 10**-18},
        -21: {"long_suffix": "zepto", "short_suffix": "z", "scalar": 10**-21},
        -24: {"long_suffix": "yocto", "short_suffix": "y", "scalar": 10**-24},
    }
    exponent = int(math.floor(math.log10(abs(val)) / 3.0) * 3)
    return suffixes.get(exponent, None)


def si_formatter(value):
    """
    Return a triple of scaled value, short suffix, long suffix, or None if
    the value cannot be classified.
    """
    classifier = si_classifier(value)
    if classifier == None:
        # Don't know how to classify this value
        return None

    scaled = value / classifier["scalar"]
    return (scaled, classifier["short_suffix"], classifier["long_suffix"])


def si_format(value, precision=4, long_form=False, separator=""):
    """
    "SI prefix" formatted string: return a string with the given precision
    and an appropriate order-of-3-magnitudes suffix, e.g.:
        si_format(1001.0) => '1.00K'
        si_format(0.00000000123, long_form=True, separator=' ') => '1.230 nano'
    """
    scaled, short_suffix, long_suffix = si_formatter(value)

    if scaled == None:
        # Don't know how to format this value
        return value

    suffix = long_suffix if long_form else short_suffix

    if abs(scaled) < 10:
        precision = precision - 1
    elif abs(scaled) < 100:
        precision = precision - 2
    else:
        precision = precision - 3

    return "{scaled:.{precision}f}{separator}{suffix}".format(
        scaled=scaled, precision=precision, separator=separator, suffix=suffix
    )
