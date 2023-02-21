import main
import pytest


def test_hash():
    assert(main.calculate_hash(b'Mnau!') == 40784)
    assert(main.calculate_hash(b'') == 0)
    assert(main.calculate_hash(bytes('+ěýřáčíšěž=', encoding='utf-8')))