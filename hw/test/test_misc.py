import main
import pytest


def test_hash():
    assert(main.calculate_hash(b'Mnau!') == 40784)
    assert(main.calculate_hash(b'') == 0)
    assert(main.calculate_hash(bytes('+ěýřáčíšěž=', encoding='utf-8')))


def test_verify_client_key():
    hash1 = main.calculate_hash(bytes('Oompa Loompa', encoding='utf-8'))
    assert(main.verify_client_key(8389, 0, hash1))