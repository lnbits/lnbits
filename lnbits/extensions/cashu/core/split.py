def amount_split(amount):
    """Given an amount returns a list of amounts returned e.g. 13 is [1, 4, 8]."""
    bits_amt = bin(amount)[::-1][:-2]
    rv = []
    for (pos, bit) in enumerate(bits_amt):
        if bit == "1":
            rv.append(2**pos)
    return rv
