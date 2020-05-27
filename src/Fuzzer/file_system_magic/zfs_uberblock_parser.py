#!/usr/bin/env python3

import argparse
import os
import pathlib
import re
from collections import OrderedDict
from ctypes import Structure, sizeof, c_uint64, c_uint8, c_uint16

# xxd ZFS_FS | grep '0cb1 ba00'
# multiple offsets
ZFS_MAGIC = b"\x0c\xb1\xba\x00\x00\x00\x00\x00"
# xxd test_zfs | grep '117a 0cb1 7ada 1002'
ZBT_MAGIC = b"\x11\x7a\x0c\xb1\x7a\xda\x10\x02"
# xxf test_zfs | grep '11ea 1ca1 0000 0000'
MMP_MAGIC = b"\x11\xea\x1c\xa1\x00\x00\x00\x00"

# TODO: Finish ZFS implementation https://github.com/freebsd/freebsd/blob/master/sys/cddl/boot/zfs/zfsimpl.h
ZFS_UB = [
    ("ub_magic", c_uint64),
    ("ub_version", c_uint64),
    ("ub_txg", c_uint64),
    ("ub_guid_sum", c_uint64),
    ("ub_timestamp", c_uint64),
    # ("blk_dva0", c_uint64),
    # ("blk_dva1", c_uint64),
    # ("blk_prop", c_uint64),
    # ("blk_pad0", c_uint64),
    # ("blk_pad1", c_uint64),
    # ("blk_phys_birth", c_uint64),
    # ("blk_birth", c_uint64),
    # ("blk_fill", c_uint64),
    # ("blk_cksum0", c_uint64),
    # ("blk_cksum1", c_uint64),
    # ("blk_cksum2", c_uint64),
    # ("blk_cksum3", c_uint64),
    ("TODO_resolve_data_fields", c_uint64 * 117),
    ("ub_software_version", c_uint64),
    ("ub_mmp_magic", c_uint64),
    ("ub_mmp_delay", c_uint64),
    ("ub_mmp_config", c_uint64),
    ("ub_mmp_config_VALID", c_uint8),
    ("ub_mmp_config_write_interval", c_uint8 * 3),
    ("ub_mmp_config_seq", c_uint16),
    ("ub_mmp_config_fail_intervals", c_uint16),
    ("ub_checkpoint_txg", c_uint64),
]


class ZFS(Structure):
    def __init__(self, fs, fst):
        super(Structure).__init__()
        self.sb = OrderedDict()
        self.sb_expected_len = 1024
        self.fs = fs
        self.fst = fst
        self.sb_locs = []
        self.fields_sb = ZFS_UB

    def _sanity_check(self):
        res_ub = 0
        for _, v in self.fields_sb:
            res_ub += sizeof(v)
        assert res_ub == self.sb_expected_len

    def get_superblock(self, n=0):
        self.find_all_superblocks()
        self._read_superblock_in_dict(self.sb_locs[n])
        return self.sb

    def _read_superblock_in_dict(self, loc=None):
        with open(self.fs, "rb") as f:
            f.seek(loc)
            for field in self.fields_sb:
                self.sb[field[0]] = f.read(sizeof(field[1]))

    def find_all_superblocks(self):
        with open(self.fs, "rb") as f:
            data = f.read()
            matches = re.finditer(ZFS_MAGIC, data)
            for m in matches:
                self.sb_locs.append(m.span()[0])
        return self.sb_locs

    def dump_superblock(self, n=0):
        if not self.sb_locs:
            self.find_all_superblocks()
        self._read_superblock_in_dict(loc=self.sb_locs[n])
        p = str(pathlib.Path(self.fs).parent)
        c = str(pathlib.Path(self.fs).name)
        fp = os.path.join(p, f"superblock_{hex(n)}_" + c + ".dump")
        with open(fp, "wb") as f:
            for _, value in self.sb.items():
                f.write(value)
        print(f"[+] Dumped {fp}")

    def dump_all_superblocks(self):
        self.find_all_superblocks()
        for i, _ in enumerate(self.sb_locs):
            self.dump_superblock(n=i)


def main():
    parser = argparse.ArgumentParser(description="UFS file system parser")
    parser.add_argument(
        "--dump", "-d", action="store_true", default=False, dest="dump", help="Dumps the first superblock to disk"
    )
    parser.add_argument(
        "--dump_all", "-da", action="store_true", default=False, dest="dump_all", help="Dumps all superblocks to disk"
    )
    parser.add_argument(
        "--find_all",
        "-fa",
        action="store_true",
        default=False,
        dest="find_all",
        help="Finds all superblock locations and prints them to stdout. Default: %(default)s",
    )
    parser.add_argument("--file_system", "-f", required=True, type=pathlib.Path, help="UFS Filesystem")
    parser.add_argument(
        "--file_system_type", "-ft", type=str, default="zfs2", dest="fst", help="[zfs1, zfs2]. Default: %(default)s"
    )

    args = parser.parse_args()

    zfs = ZFS(args.file_system, args.fst)
    if args.dump:
        zfs.dump_superblock()
    if args.dump_all:
        zfs.dump_all_superblocks()
    if args.find_all:
        zfs.find_all_superblocks()
        res = ", ".join(hex(e) for e in zfs.sb_locs)
        print(f"[+] Found superblock offsets: {res}")


if __name__ == "__main__":
    main()
