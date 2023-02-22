import socket
import threading

ENCODING = 'utf8'

MAX_MESSAGE_LENGTH = 20
MAX_SECRET_MESSAGE_LENGTH = 100
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


TIMEOUT = 1


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
        self.sock.settimeout(TIMEOUT)
        self.remainder = b''

    def recv(self, max_len=MAX_MESSAGE_LENGTH) -> bytes:
        msg = self.remainder
        bytes_read = len(msg)
        while msg.find(MSG_DELIMITER) == -1 and bytes_read < max_len:
            msg += self.sock.recv(max_len - bytes_read)
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


class Vector:
    def __init__(self, x: int, y: int):
        self._x = x
        self._y = y

    @property
    def x(self) -> int:
        return self._x

    @property
    def y(self) -> int:
        return self._y

    def __add__(self, other):
        return Vector(self.x + other.x, self.y + other.y)

    def __mul__(self, k: int):
        return Vector(self.x * k, self.y * k)

    def left(self):
        if self.x == 1:
            new_x = 0
            new_y = 1
        elif self.x == -1:
            new_x = 0
            new_y = -1
        elif self.y == 1:
            new_x = -1
            new_y = 0
        else:
            new_x = 1
            new_y = 0
        return Vector(new_x, new_y)

    def right(self):
        return self.left() * (-1)

    def __eq__(self, other) -> bool:
        return self.x == other.x and self.y == other.y

    def dist(self, other) -> int:
        return abs(self.x - other.x) + abs(self.y + other.y)

    def __neg__(self):
        return Vector(-self.x, -self.y)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def __str__(self) -> str:
        return str(self.x) + ' ' + str(self.y)


class Robot:
    goal = Vector(0, 0)

    def __init__(self, position: Vector, direction: Vector):
        self.position = position
        self.direction = direction

    def is_at_goal(self):
        return self.position == self.goal

    def turn_left(self):
        self.direction = self.direction.left()

    def turn_right(self):
        self.direction = self.direction.right()

    def optimal_right_turns(self) -> int:
        min_distance = self.position.dist(self.goal)
        direction = self.direction
        for i in range(4):
            if (direction + self.position).dist(self.goal) < min_distance:
                return i
            direction = direction.right()
        raise ValueError("Impossible situation")

    def move(self):
        self.position = self.position + self.direction


def turn_right(conn: Connection):
    conn.send(SERVER_TURN_RIGHT)
    conn.recv()


def turn_left(conn: Connection):
    conn.send(SERVER_TURN_LEFT)
    conn.recv()


def move(conn: Connection) -> Vector:
    # moves the robot and returns the new position
    conn.send(SERVER_MOVE)
    position_str = to_str(conn.recv())
    position_info = position_str.split(' ')
    x, y = int(position_info[1]), int(position_info[2])
    return Vector(x, y)


def find_position_info(conn: Connection):
    position1 = move(conn)
    position2 = move(conn)
    while position2 == position1:
        turn_right(conn)
        position2 = move(conn)

    direction = position2 - position1
    return position2, direction


def turn_right_n_times(n: int, conn: Connection):
    for i in range(n):
        turn_right(conn)


def turn(robot: Robot, conn: Connection):
    turns = robot.optimal_right_turns()
    turn_right_n_times(turns, conn)
    for i in range(turns):
        robot.turn_right()


def move_with_turning(conn: Connection, robot: Robot):
    position = move(conn)
    while position == robot.position:
        pos_left = robot.position + robot.direction.left()
        pos_right = robot.position + robot.direction.right()
        if pos_left.dist(robot.goal) < pos_right.dist(robot.goal):
            turn_left(conn)
            robot.turn_left()
        else:
            turn_right(conn)
            robot.turn_right()
        position = move(conn)
        robot.move()
    return position


def move_to_goal(conn: Connection):
    position, direction = find_position_info(conn)
    robot = Robot(position, direction)
    while not robot.is_at_goal():
        turn(robot, conn)
        position = move_with_turning(conn, robot)
        direction = position - robot.position
        robot = Robot(position, direction)


def manage_connection(conn: Connection):
    if not authenticate(conn):
        return
    move_to_goal(conn)
    conn.send(SERVER_PICK_UP)
    conn.recv(MAX_SECRET_MESSAGE_LENGTH)
    conn.send(SERVER_LOGOUT)


class ConnectionThread(threading.Thread):
    def __init__(self, conn: Connection):
        super(ConnectionThread, self).__init__()
        self.conn = conn

    def run(self):
        try:
            manage_connection(self.conn)
        except socket.timeout:
            pass
        except ValueError:
            pass
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
