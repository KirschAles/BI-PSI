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


CLIENT_RECHARGING = 'RECHARGING'
CLIENT_FULL_POWER = 'FULL POWER'


class MaxLength:
    CLIENT_USERNAME = 20
    CLIENT_KEY_ID = 5
    CLIENT_CONFIRMATION = 7
    CLIENT_OK = 12
    CLIENT_RECHARGING = 12
    CLIENT_FULL_POWER = 12
    CLIENT_MESSAGE = 100


TIMEOUT = 1
TIMEOUT_RECHARGING = 5


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

    def recv(self, max_len: int) -> bytes:
        msg = self.remainder
        bytes_read = len(msg)
        while msg.find(MSG_DELIMITER) == -1 and bytes_read < max_len:
            msg += self.sock.recv(max_len - bytes_read)
            bytes_read = len(msg)

        if msg.find(MSG_DELIMITER) == -1:
            if to_str(msg) in CLIENT_RECHARGING:
                self.remainder = msg
                return self.recv(MaxLength.CLIENT_RECHARGING)
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


def recv_with_recharge(conn: Connection, max_len: int) -> bytes:
    msg = conn.recv(max_len)
    if to_str(msg) == CLIENT_RECHARGING:
        conn.sock.settimeout(TIMEOUT_RECHARGING)
        recharging = conn.recv(MaxLength.CLIENT_FULL_POWER)
        if to_str(recharging) != CLIENT_FULL_POWER:
            raise ArithmeticError("Robot couldn't recharge.")
        conn.sock.settimeout(TIMEOUT)
        msg = recv_with_recharge(conn, max_len)
    return msg


def is_robot_id_valid(robot_id, keys):
    return 0 <= robot_id < len(keys)


def authenticate(conn: Connection) -> bool:
    username = recv_with_recharge(conn, MaxLength.CLIENT_USERNAME)
    conn.send(SERVER_KEY_REQUEST)
    robot_id_str = to_str(recv_with_recharge(conn, MaxLength.CLIENT_KEY_ID))
    if not robot_id_str.isnumeric():
        raise ValueError('Non numeric client id')
    robot_id = int(robot_id_str)

    if not is_robot_id_valid(robot_id, KEYS):
        conn.send(SERVER_KEY_OUT_OF_RANGE_ERROR)
        return False

    robot_hash = calculate_hash(username)
    server_key = calculate_server_key(robot_hash, robot_id)
    conn.send(str(server_key) + to_str(MSG_DELIMITER))

    client_key_string = to_str(recv_with_recharge(conn, MaxLength.CLIENT_CONFIRMATION))
    if not client_key_string.isnumeric():
        raise ValueError('Client key not numeric.')
    client_key = int(client_key_string)

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

    def __hash__(self):
        return (self.x, self.y).__hash__()

    def right(self):
        return self.left() * (-1)

    def __eq__(self, other) -> bool:
        if not isinstance(other, Vector):
            return False
        return self.x == other.x and self.y == other.y

    def dist(self, other) -> int:
        return abs(self.x - other.x) + abs(self.y - other.y)

    def __neg__(self):
        return Vector(-self.x, -self.y)

    def __sub__(self, other):
        return Vector(self.x - other.x, self.y - other.y)

    def __str__(self) -> str:
        return str(self.x) + ' ' + str(self.y)

    def neighbours(self) -> list:
        neighbours = []
        vector = Vector(1, 0)
        for i in range(3):
            neighbours.append(self + vector)
            vector = vector.right()
        neighbours.append(self + vector)
        return neighbours


class Robot:
    goal = Vector(0, 0)

    def __init__(self, position: Vector, direction: Vector):
        self.position = position
        self.direction = direction
        self.collision_points = set()

    def is_at_goal(self):
        return self.position == self.goal

    def turn_left(self):
        self.direction = self.direction.left()

    def turn_right(self):
        self.direction = self.direction.right()

    def move(self):
        self.position = self.position + self.direction

    def add_collision(self, collision: Vector):
        self.collision_points.add(collision)

    def left_turns_to(self, pos: Vector) -> int:
        direction = self.direction
        for i in range(4):
            if self.position + direction == pos:
                return i
            direction = direction.left()
        raise ValueError('Not neighbour.')

    def best_next(self, prev_pos: Vector):
        distance = self.position.dist(self.goal) + 10
        best_pos = None
        for pos in self.position.neighbours():
            if pos.dist(self.goal) < distance and not (pos in self.collision_points) and pos != prev_pos:
                best_pos = pos
                distance = pos.dist(self.goal)
        return best_pos


def turn_left(conn: Connection):
    conn.send(SERVER_TURN_LEFT)
    recv_with_recharge(conn, MaxLength.CLIENT_OK)


def move(conn: Connection) -> Vector:
    # moves the robot and returns the new position
    conn.send(SERVER_MOVE)
    position_str = to_str(recv_with_recharge(conn, MaxLength.CLIENT_OK))
    position_info = position_str.split(' ')
    if len(position_info) != 3:
        raise ValueError('Wrong MOVE command')
    x, y = int(position_info[1]), int(position_info[2])
    return Vector(x, y)


def find_position_info(conn: Connection):
    position1 = move(conn)
    position2 = move(conn)
    while position2 == position1:
        turn_left(conn)
        position2 = move(conn)

    direction = position2 - position1
    return position2, direction


def get_to_goal(conn: Connection, robot: Robot) -> bool:
    prev_pos = None
    while robot.position != robot.goal:
        current_pos = robot.position
        next_pos = robot.best_next(prev_pos)
        turns = robot.left_turns_to(next_pos)
        for i in range(turns):
            turn_left(conn)
            robot.turn_left()
        new_pos = move(conn)
        robot.position = new_pos
        if new_pos != next_pos:
            robot.add_collision(next_pos)
        else:
            prev_pos = current_pos

    return True


def move_to_goal(conn: Connection):
    position, direction = find_position_info(conn)
    robot = Robot(position, direction)

    while not get_to_goal(conn, robot):
        pass


def manage_connection(conn: Connection):
    if not authenticate(conn):
        return
    move_to_goal(conn)
    conn.send(SERVER_PICK_UP)
    recv_with_recharge(conn, MAX_SECRET_MESSAGE_LENGTH)
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
            self.conn.send(SERVER_SYNTAX_ERROR)
        except ArithmeticError:
            self.conn.send(SERVER_LOGIC_ERROR)
        self.conn.close()


def manage_connections():
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, PORT))
    sock.listen()
    try:
        while True:
            conn = Connection(sock.accept()[0])
            thread = ConnectionThread(conn)
            thread.start()

    except KeyboardInterrupt:
        sock.close()


if __name__ == '__main__':
    manage_connections()
