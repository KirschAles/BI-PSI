

def calculate_hash(byte_string: bytes):
    ceiling = 2**16

    byte_sum = 0
    for byte in byte_string:
        byte_sum += byte
    byte_sum *= 1000
    return byte_sum % ceiling
