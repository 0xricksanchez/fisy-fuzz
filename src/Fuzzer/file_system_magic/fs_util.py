import os
import re
import magic
import pathlib
from ctypes import sizeof
from datetime import datetime
from secrets import token_bytes


def get_int(n, signed=False):
    return int.from_bytes(n, byteorder="little", signed=signed)


def get_time(n):
    return datetime.fromtimestamp(n).strftime("%c")


def get_hstr(hex_str, inv=False):
    if len(hex_str[2:]) % 16 != 0:
        hex_str = "0" + hex_str[2:]
    else:
        hex_str = hex_str[2:]
    if inv:
        return bytes.fromhex(hex_str[::-1]).decode("ASCII")
    else:
        return bytes.fromhex(hex_str).decode("ASCII")


def make_zero(size):
    return b"\x00" * size


def make_ff(size):
    return b"\xFF" * size


def make_rnd(size):
    return token_bytes(size)


def get_bytearray(fs):
    with open(fs, "rb") as f:
        byte_array = re.findall(b".", f.read())
    return byte_array


def set_mime(fs):
    file_mime = magic.from_file(fs)
    if "Unix Fast" in file_mime and "[v1]" in file_mime:
        return "ufs1"
    elif "Unix Fast" in file_mime and "[v2]" in file_mime:
        return "ufs2"
    elif re.findall(r"ext[2-4]", file_mime):
        return "ext"
    elif "data" in file_mime:
        return "zfs"


def write_to_file(fs, nbytes, mode, byte_array):
    name = pathlib.Path(fs).name
    _path = pathlib.Path(fs).parent
    mfs = os.path.join(_path, "{}b_{}_".format(nbytes, mode) + name)
    with open(mfs, "wb") as g:
        g.write(b"".join(x for x in byte_array))
    return mfs


def get_mutated_bytes(nbytes, mode=None):
    if mode == "ff":
        return make_ff(nbytes)
    elif mode == "00":
        return make_zero(nbytes)
    else:
        return make_rnd(nbytes)


def get_offset_in_sb(fsp, fn):
    off = 0
    for i, v in fsp.fields_sb:
        if i == fn:
            return off, sizeof(v)
        off += sizeof(v)
    return None, None


if __name__ == "__main__":
    pass
