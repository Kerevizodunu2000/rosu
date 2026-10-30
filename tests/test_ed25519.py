# SPDX-License-Identifier: GPL-3.0-or-later
"""rosu.ed25519: RFC 8032 section 7.1 vectors and rejection of malformed input."""
import pytest

from rosu import ed25519

_L = 2 ** 252 + 27742317777372353535851937790883648493
_P = 2 ** 255 - 19

# (secret key, public key, message, signature), RFC 8032 section 7.1
VECTORS = {
    "TEST 1": (
        "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
        "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    "TEST 2": (
        "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
        "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    "TEST 3": (
        "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
        "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
    "TEST SHA(abc)": (
        "833fe62409237b9d62ec77587520911e9a759cec1d19755b7da901b96dca3d42",
        "ec172b93ad5e563bf4932c70e1245034c35467ef2efd4d64ebf819683467e2bf",
        "ddaf35a193617abacc417349ae20413112e6fa4e89a97ea20a9eeee64b55d39a"
        "2192992a274fc1a836ba3c23a3feebbd454d4423643ce80e2a9ac94fa54ca49f",
        "dc2a4459e7369633a52b1bf277839a00201009a3efbf3ecb69bea2186c26b589"
        "09351fc9ac90b3ecfdfbc7c66431e0303dca179c138ac17ad9bef1177331a704"),
}


@pytest.mark.parametrize("name", VECTORS)
def test_rfc8032_vectors(name):
    seed, pub, msg, sig = (bytes.fromhex(x) for x in VECTORS[name])
    assert ed25519.public_key(seed) == pub
    assert ed25519.sign(seed, msg) == sig
    assert ed25519.verify(pub, msg, sig) is True


def _flip(data: bytes, i: int) -> bytes:
    b = bytearray(data)
    b[i] ^= 1
    return bytes(b)


_SEED, _PUB, _MSG, _SIG = (bytes.fromhex(x) for x in VECTORS["TEST 3"])


@pytest.mark.parametrize("pub,msg,sig", [
    (_PUB, _flip(_MSG, 0), _SIG),                 # message bit
    (_PUB, _MSG, _flip(_SIG, 5)),                 # signature bit (R)
    (_PUB, _MSG, _flip(_SIG, 40)),                # signature bit (S)
    (_flip(_PUB, 3), _MSG, _SIG),                 # key bit
    (_PUB, _MSG, _SIG[:32] + (int.from_bytes(_SIG[32:], "little") + _L)
     .to_bytes(32, "little")),                    # S + L, non-canonical
    ((2).to_bytes(32, "little"), _MSG, _SIG),     # y = 2 is not on the curve
    (_P.to_bytes(32, "little"), _MSG, _SIG),      # y >= p, non-canonical
    (_PUB, _MSG, (2).to_bytes(32, "little") + _SIG[32:]),   # R not a point
    (_PUB[:31], _MSG, _SIG),
    (_PUB + b"\0", _MSG, _SIG),
    (_PUB, _MSG, _SIG[:63]),
    (_PUB, _MSG, _SIG + b"\0"),
    (None, _MSG, _SIG),
    (_PUB, None, _SIG),
    (_PUB, _MSG, None),
    (_PUB.hex(), _MSG, _SIG),                     # str, not bytes
])
def test_verify_rejects_without_raising(pub, msg, sig):
    assert ed25519.verify(pub, msg, sig) is False


def test_sign_rejects_a_bad_seed():
    with pytest.raises(ValueError):
        ed25519.sign(b"short", b"m")
