import re
import socket


# Function to validate domain name.
def isValidDomain(str):
    # Regex to check valid
    # domain name.
    regex = "^((?!-)[A-Za-z0-9-]{1,63}(?<!-)\\.)+[A-Za-z]{2,6}"
    # Compile the ReGex
    p = re.compile(regex)

    # If the string is empty
    # return false
    if str is None:
        return False

    # Return if the string
    # matched the ReGex
    if re.search(p, str):
        return True
    else:
        return False


# Function to validate IP address
def isvalidIPAddress(str):
    try:
        socket.inet_aton(str)
        return True
    except socket.error:
        return False
