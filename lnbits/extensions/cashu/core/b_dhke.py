# Don't trust me with cryptography.

"""
Implementation of https://gist.github.com/RubenSomsen/be7a4760dd4596d06963d67baf140406
Alice:
A = a*G
return A
Bob:
Y = hash_to_point(secret_message)
r = random blinding factor
B'= Y + r*G
return B'
Alice:
C' = a*B'
  (= a*Y + a*r*G)
return C'
Bob:
C = C' - r*A
 (= C' - a*r*G)
 (= a*Y)
return C, secret_message
Alice:
Y = hash_to_point(secret_message)
C == a*Y
If true, C must have originated from Alice
"""

import hashlib

from secp256k1 import PrivateKey, PublicKey


def hash_to_point(secret_msg):
    """Generates x coordinate from the message hash and checks if the point lies on the curve.
    If it does not, it tries computing again a new x coordinate from the hash of the coordinate."""
    point = None
    msg = secret_msg
    while point is None:
        _hash = hashlib.sha256(msg).hexdigest().encode("utf-8")
        try:
            # We construct compressed pub which has x coordinate encoded with even y
            _hash = list(_hash[:33])  # take the 33 bytes and get a list of bytes
            _hash[0] = 0x02  # set first byte to represent even y coord
            _hash = bytes(_hash)
            point = PublicKey(_hash, raw=True)
        except:
            msg = _hash

    return point


def step1_alice(secret_msg):
    secret_msg = secret_msg.encode("utf-8")
    Y = hash_to_point(secret_msg)
    r = PrivateKey()
    B_ = Y + r.pubkey
    return B_, r


def step2_bob(B_, a):
    C_ = B_.mult(a)
    return C_


def step3_alice(C_, r, A):
    C = C_ - A.mult(r)
    return C


def verify(a, C, secret_msg):
    Y = hash_to_point(secret_msg.encode("utf-8"))
    return C == Y.mult(a)


### Below is a test of a simple positive and negative case

# # Alice's keys
# a = PrivateKey()
# A = a.pubkey
# secret_msg = "test"
# B_, r = step1_alice(secret_msg)
# C_ = step2_bob(B_, a)
# C = step3_alice(C_, r, A)
# print("C:{}, secret_msg:{}".format(C, secret_msg))
# assert verify(a, C, secret_msg)
# assert verify(a, C + C, secret_msg) == False  # adding C twice shouldn't pass
# assert verify(a, A, secret_msg) == False  # A shouldn't pass

# # Test operations
# b = PrivateKey()
# B = b.pubkey
# assert -A -A + A == -A  # neg
# assert B.mult(a) == A.mult(b)  # a*B = A*b
