import socket
import threading

ENCODING = 'utf8'

MAX_MESSAGE_LENGTH = 20
MSG_DELIMITER = bytes('\a\b', encoding='utf-8')

PORT = 3999
HOST = 'localhost'

KEY_CEILING = 2 ** 16

SERVER_MOVE = '102 MOVE\a\b'
SERVER_TURN_LEFT = '103 TURN LEFT\a\b'
SERVER_TURN_RIGHT = '104 TURN RIGHT\a\b'
SERVER_PICK_UP = '105 GET MESSAGE\a\b'
SERVER_LOGOUT = '106 LOGOUT\a\b'
SERVER_KEY_REQUEST = '107 KEY REQUEST\a\b'
SERVER_OK = '200 OK\a\b'
SERVER_LOGIN_FAILED = '300 LOGIN FAILED\a\b'
SERVER_SYNTAX_ERROR = '301 SYNTAX ERROR\a\b'
SERVER_LOGIC_ERROR = '302 LOGIC ERROR\a\b'
SERVER_KEY_OUT_OF_RANGE_ERROR = '303 KEY OUT OF RANGE\a\b'


class Key:
    def __init__(self, server, client):
        self.client = client
        self.server = server


KEYS = [Key(23019, 32037), Key(32037, 29295), Key(18789, 13603), Key(16443, 29533), Key(18189, 21952)]


def to_str(string: bytes):
    return str(string, encoding=ENCODING)


def calculate_hash(byte_string: bytes):
    byte_sum = 0
    for byte in byte_string:
        byte_sum += byte
    byte_sum *= 1000
    return byte_sum % KEY_CEILING


def calculate_server_key(robot_hash: int, robot_id: int):
    return (robot_hash + KEYS[robot_id].server) % KEY_CEILING


def verify_client_key(client_key: int, robot_id: int, robot_hash: int) -> bool:
    return (client_key - KEYS[robot_id].client) % KEY_CEILING == robot_hash


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

    def send(self, message: str) -> None:
        msg = bytes(message, encoding=ENCODING)
        bytes_send = 0
        while bytes_send < len(msg):
            count = self.sock.send(msg[bytes_send:])
            if count == 0:
                raise ConnectionError("Couldn't send the whole message")
            bytes_send += count

    def close(self):
        self.sock.close()


def is_robot_id_valid(robot_id, keys):
    return 0 <= robot_id < len(keys)


def authenticate(conn: Connection) -> bool:
    username = conn.recv()
    conn.send(SERVER_KEY_REQUEST)
    robot_id = int(to_str(conn.recv()))

    if not is_robot_id_valid(robot_id, KEYS):
        conn.send(SERVER_KEY_OUT_OF_RANGE_ERROR)
        return False

    robot_hash = calculate_hash(username)
    server_key = calculate_server_key(robot_hash, robot_id)
    conn.send(str(server_key) + to_str(MSG_DELIMITER))

    client_key = int(to_str(conn.recv()))

    if not verify_client_key(client_key, robot_id, robot_hash):
        conn.send(SERVER_LOGIN_FAILED)
        return False

    conn.send(SERVER_OK)
    return True


def manage_connection(conn: Connection):
    if not authenticate(conn):
        return


class ConnectionThread(threading.Thread):
    def __init__(self, conn: Connection):
        super(ConnectionThread, self).__init__()
        self.conn = conn

    def run(self):
        manage_connection(self.conn)
        self.conn.close()


def manage_connections():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen()
    try:
        while True:
            conn = Connection(sock.accept()[0])
            thread = ConnectionThread(conn)
            thread.run()

    except KeyboardInterrupt:
        sock.close()


if __name__ == '__main__':
    manage_connections()
