#!/usr/bin/env python3

import argparse
import os
import pathlib
import pprint as pp
import re
import sys
from collections import OrderedDict
from ctypes import Structure, sizeof, c_uint8, c_char, c_uint32, c_uint64, c_uint16
from .fs_util import get_int

# xxd EXT_FS | 'ef53'
# at offset 1080
EXT_MAGIC = b"\x53\xef"

SBLOCK_EXT2 = 1024  # First 1024 bytes are unused, block group 0 starts with a superblock @ offset 1024d
MAGIC_BYTES_OFF = 56

EXT_SB = [
    ("e2fs_icount", c_uint32),
    ("e2fs_bcount", c_uint32),
    ("e2fs_rbcount", c_uint32),
    ("e2fs_fbcount", c_uint32),
    ("e2fs_ficount", c_uint32),
    ("e2fs_first_dblock", c_uint32),
    ("e2fs_log_bsize", c_uint32),
    ("e2fs_log_fsize", c_uint32),
    ("e2fs_bpg", c_uint32),
    ("e2fs_fpg", c_uint32),
    ("e2fs_ipg", c_uint32),
    ("e2fs_mtime", c_uint32),
    ("e2fs_wtime", c_uint32),
    ("e2fs_mnt_count", c_uint16),
    ("e2fs_max_mnt_count", c_uint16),
    ("e2fs_magic", c_uint16),
    ("e2fs_state", c_uint16),
    ("e2fs_beh", c_uint16),
    ("e2fs_minrev", c_uint16),
    ("e2fs_lastfsck", c_uint32),
    ("e2fs_fsckintv", c_uint32),
    ("e2fs_creator", c_uint32),
    ("e2fs_rev", c_uint32),
    ("e2fs_ruid", c_uint16),
    ("e2fs_rgid", c_uint16),
    ("e2fs_first_ino", c_uint32),
    ("e2fs_inode_size", c_uint16),
    ("e2fs_block_group_nr", c_uint16),
    ("e2fs_features_compat", c_uint32),
    ("e2fs_features_incompat", c_uint32),
    ("e2fs_features_rocompat", c_uint32),
    ("e2fs_uuid", c_uint8 * 16),  # arr[16], at offset 104
    ("e2fs_vname", c_char * 16),  # arr[16]
    ("e2fs_fsmnt", c_char * 64),  # arr[64]
    ("e2fs_algo", c_uint32),
    ("e2fs_prealloc", c_uint8),
    ("e2fs_dir_prealloc", c_uint8),
    ("e2fs_reserved_ngdb", c_uint16),
    ("e3fs_journal_uuid", c_char * 16),  # arr[16]
    ("e3fs_journal_inum", c_uint32),
    ("e3fs_journal_dev", c_uint32),
    ("e3fs_last_orphan", c_uint32),
    ("e3fs_hash_seed", c_uint32 * 4),  # arr[4]
    ("e3fs_def_hash_version", c_char),
    ("e3fs_jnl_backup_type", c_char),
    ("e3fs_desc_size", c_uint16),
    ("e3fs_default_mount_opts", c_uint32),
    ("e3fs_first_meta_bg", c_uint32),
    ("e3fs_mkfs_time", c_uint32),
    ("e3fs_jnl_blks", c_uint32),
    ("e4fs_bcount_hi", c_uint32),
    ("e4fs_rbcount_hi", c_uint32),
    ("e4fs_fbcount_hi", c_uint32),
    ("e4fs_min_extra_isize", c_uint16),
    ("e4fs_want_extra_isize", c_uint16),
    ("e4fs_flags", c_uint32),
    ("e4fs_raid_stride", c_uint16),
    ("e4fs_mmpintv", c_uint16),
    ("e4fs_mmpblk", c_uint64),
    ("e4fs_raid_stripe_wid", c_uint32),
    ("e4fs_log_gpf", c_uint8),
    ("e4fs_chksum_type", c_uint8),
    ("e4fs_encrypt", c_uint8),
    ("e4fs_reserved_pad", c_uint8),
    ("e4fs_kbytes_written", c_uint64),
    ("e4fs_snapinum", c_uint32),
    ("e4fs_snapid", c_uint32),
    ("e4fs_snaprbcount", c_uint64),
    ("e4fs_snaplist", c_uint32),
    ("e4fs_errcount", c_uint32),
    ("e4fs_first_errtime", c_uint32),
    ("e4fs_first_errino", c_uint32),
    ("e4fs_first_errblk", c_uint64),
    ("e4fs_first_errfunc", c_uint8 * 32),  # arr[32]
    ("e4fs_first_errline", c_uint32),
    ("e4fs_last_errtime", c_uint32),
    ("e4fs_last_errino", c_uint32),
    ("e4fs_last_errline", c_uint32),
    ("e4fs_last_errblk", c_uint64),
    ("e4fs_last_errfunc", c_uint8 * 32),  # arr[32]
    ("e4fs_mount_opts", c_uint8 * 64),  # arr[64]
    ("e4fs_usrquota_inum", c_uint32),
    ("e4fs_grpquota_inum", c_uint32),
    ("e4fs_overhead_clusters", c_uint32),
    ("e4fs_backup_bgs", c_uint32 * 2),  # arr[2]
    ("e4fs_encrypt_algos", c_uint8 * 4),  # arr[4]
    ("e4fs_encrypt_pw_salt", c_uint8 * 16),  # arr[16]
    ("e4fs_lpf_ino", c_uint32),
    ("e4fs_proj_quota_inum", c_uint32),
    ("e4fs_chksum_seed", c_uint32),
    ("e4fs_reserved", c_uint32 * 98),  # arr[98]
    ("e4fs_sbchksum", c_uint32),
]


class EXT(Structure):
    def __init__(self, fs, fst):
        super(Structure).__init__()
        self.sb = OrderedDict()
        self.sb_expected_len = 960
        self.fs = fs
        self.fst = fst
        self.sb_locs = []
        self.sb_locs = []
        self.fields_sb = EXT_SB

    def _sanity_check(self):
        res_sb = 0
        for _, v in self.fields_sb:
            res_sb += sizeof(v)
        assert res_sb == self.sb_expected_len

    @staticmethod
    def get_offset_in_sb(fn):
        off = 0
        sb = EXT_SB
        for i, v in sb:
            if i == fn:
                return off, sizeof(v)
            off += sizeof(v)
        return None, None

    def read_superblock_in_dict(self, loc=SBLOCK_EXT2):
        with open(self.fs, "rb") as f:
            f.seek(loc)
            for field in self.fields_sb:
                self.sb[field[0]] = f.read(sizeof(field[1]))

    def find_all_superblocks(self):
        self.read_superblock_in_dict()
        with open(self.fs, "rb") as f:
            f.seek(0)
            data = f.read()
            # Using uuid because the EXT2 magic is too short to yield good results
            matches = re.finditer(self.sb["e2fs_uuid"], data)
            for m in matches:
                bytearr = bytearray()
                sb = m.span()[0] - 104
                bytearr.append(data[sb + MAGIC_BYTES_OFF])
                bytearr.append(data[sb + MAGIC_BYTES_OFF + 1])
                if bytearr == EXT_MAGIC:
                    self.sb_locs.append(sb)
        return self.sb_locs

    def find_all_cylinder_groups(self):
        self.cg_locs = []

    def print_superblock(self):
        tmp = OrderedDict()
        for key, value in self.sb.items():
            if key in ["e3fs_def_hash_version", "e3fs_jnl_backup_type", "e3fs_journal_uuid", "e2fs_fsmnt", "e2fs_vname"]:
                tmp[key] = hex(get_int(value, signed=False))
            else:
                tmp[key] = hex(get_int(value, signed=False))
        pp.pprint(tmp)

    def dump_superblock(self, n=SBLOCK_EXT2):
        self.read_superblock_in_dict(loc=n)
        p = str(pathlib.Path(self.fs).parent)
        c = str(pathlib.Path(self.fs).name)
        fp = os.path.join(p, f"superblock_{hex(n)}_" + c + ".dump")
        with open(fp, "wb") as f:
            for _, value in self.sb.items():
                f.write(value)
        print(f"[+] Dumped {fp}")

    def dump_all_superblocks(self):
        self.find_all_superblocks()
        for i in self.sb_locs:
            self.dump_superblock(n=i)


def main():
    parser = argparse.ArgumentParser(description="EXT file system parser")
    parser.add_argument(
        "--dump", "-d", action="store_true", default=False, dest="dump", help="Dumps the first superblock to disk"
    )
    parser.add_argument(
        "--dump_all", "-da", action="store_true", default=False, dest="dump_all", help="Dumps all superblocks to disk"
    )
    parser.add_argument(
        "--print_superblock",
        "-ps",
        type=int,
        default=-1,
        dest="print_sb",
        help="Print the n-th superblock to stdout. Default: %(default)s",
    )
    parser.add_argument(
        "--find_all",
        "-fa",
        action="store_true",
        default=False,
        dest="find_all",
        help="Finds all superblock locations and prints them to stdout",
    )
    parser.add_argument("--file_system", "-f", required=True, type=pathlib.Path, help="UFS Filesystem")

    args = parser.parse_args()

    ext = EXT(args.file_system, "ext")
    if args.dump:
        ext.dump_superblock()
    if args.dump_all:
        ext.dump_all_superblocks()
    if args.find_all:
        ext.find_all_superblocks()
        res = ", ".join(hex(e) for e in ext.sb_locs)
        print(f"[+] Found superblock offsets: {res}")
    if args.print_sb >= 0:
        ext.find_all_superblocks()
        ext.read_superblock_in_dict(ext.sb_locs[args.print_sb])
        ext.print_superblock()


if __name__ == "__main__":
    sys.exit(main())
