import hashlib
import os

preimage = os.urandom(32)
preimage_hash = hashlib.sha256(preimage).hexdigest()

print(f"preimage hash: {preimage_hash}")
print(f"preimage: {preimage.hex()}")
