import socket

MAX_MESSAGE_LENGTH = 20
MSG_DELIMITER = b'\a\b'


class Connection:
    def __init__(self, sock: socket.socket):
        self.sock = sock
        self.remainder = b''

    def recv(self) -> bytes:
        msg = self.remainder
        bytes_read = len(msg)
        while msg.find(MSG_DELIMITER) == -1 and bytes_read < MAX_MESSAGE_LENGTH:
            msg += self.sock.recv(MAX_MESSAGE_LENGTH - bytes_read)
            bytes_read = len(msg)

        if msg.find(MSG_DELIMITER) == -1:
            raise ValueError('Message either too long or without delimiter')
        messages = msg.split(MSG_DELIMITER)
        msg = messages[0]
        self.remainder = MSG_DELIMITER.join(messages[1:])
        return msg

    def send(self, msg: bytes) -> None:
        bytes_send = 0
        while bytes_send < len(msg):
            count = self.sock.send(msg[bytes_send:])
            if count == 0:
                raise ConnectionError("Couldn't send the whole message")
            bytes_send += count





def calculate_hash(byte_string: bytes):
    ceiling = 2**16

    byte_sum = 0
    for byte in byte_string:
        byte_sum += byte
    byte_sum *= 1000
    return byte_sum % ceiling

