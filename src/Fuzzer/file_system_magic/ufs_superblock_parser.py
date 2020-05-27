#!/usr/bin/env python3

import argparse
import os
import pathlib
import pprint as pp
import re
from collections import OrderedDict
from ctypes import Structure, sizeof, c_int32, c_int64, c_uint8, c_char, c_int8, c_uint32, c_int16, c_void_p, c_uint64, c_size_t
from .fs_util import get_int

# xxd UFS_FS | grep '1901 5419'
# multiple offsets
UFS_MAGIC = b"\x19\x01\x54\x19"
CG_MAGIC = b"\x55\x02\x09"
SBLOCK_PIGGY = 262144
SBLOCKSIZE = 8192
MAXMNTLEN = 468
MAXVOLLEN = 32
FSMAXSNAP = 20
NOCSPTRS = int(128 / (sizeof(c_void_p)) - 4)
MAXFRAG = 8
SBLOCK_UFS1 = 8192
SBLOCK_UFS2 = 65536

ufs_time_t = c_int64
ufs2_daddr_t = c_int64

UFS_SB = [
    ("fs_firstfield", c_int32),
    ("fs_unused_1", c_int32),
    ("fs_sblkno", c_int32),
    ("fs_cblkno", c_int32),
    ("fs_iblkno", c_int32),
    ("fs_dblkno", c_int32),
    ("fs_old_cgoffset", c_int32),
    ("fs_old_cgmask", c_int32),
    ("fs_old_time", c_int32),
    ("fs_old_size", c_int32),
    ("fs_old_dsize", c_int32),
    ("fs_ncg", c_uint32),
    ("fs_bsize", c_int32),
    ("fs_fsize", c_int32),
    ("fs_frag", c_int32),
    ("fs_minfree", c_int32),
    ("fs_old_rotdelay", c_int32),
    ("fs_old_rps", c_int32),
    ("fs_bmask", c_int32),
    ("fs_fmask", c_int32),
    ("fs_bshift", c_int32),
    ("fs_fshift", c_int32),
    ("fs_maxcontig", c_int32),
    ("fs_maxbpg", c_int32),
    ("fs_fragshift", c_int32),
    ("fs_fsbtodb", c_int32),
    ("fs_sbsize", c_int32),
    ("fs_spare1", c_int32 * 2),  # arr[2]
    ("fs_nindir", c_int32),
    ("fs_inopb", c_uint32),
    ("fs_old_nspf", c_int32),
    ("fs_optim", c_int32),
    ("fs_old_npsect", c_int32),
    ("fs_old_interleave", c_int32),
    ("fs_old_trackskew", c_int32),
    ("fs_id", c_int32 * 2),  # arr[2]
    ("fs_old_csaddr", c_int32),
    ("fs_cssize", c_int32),
    ("fs_cgsize", c_int32),
    ("fs_spare2", c_int32),
    ("fs_old_nsect", c_int32),
    ("fs_old_spc", c_int32),
    ("fs_old_ncyl", c_int32),
    ("fs_old_cpg", c_int32),
    ("fs_ipg", c_uint32),
    ("fs_fpg", c_int32),
    ("fs_old_cstotal__cs_ndir", c_int32),
    ("fs_old_cstotal__cs_nbfree", c_int32),
    ("fs_old_cstotal__cs_nifree", c_int32),
    ("fs_old_cstotal__cs_nffree", c_int32),
    # ('fs_old_cstotal', c_int32 * 4),  # struct csum
    ("fs_fmod", c_int8),
    ("fs_clean", c_int8),
    ("fs_ronly", c_int8),
    ("fs_old_flags", c_int8),
    ("fs_fsmnt", c_char * MAXMNTLEN),
    ("fs_volname", c_char * MAXVOLLEN),
    ("fs_swuid", c_uint64),
    ("fs_pad", c_int32),
    ("fs_cgrotor", c_int32),
    ("*fs_ocsp", c_void_p * NOCSPTRS),  # void 	*fs_ocsp[NOCSPTRS]
    ("*fs_contigdirs", c_size_t),  # *fs_contigdirs
    ("*fs_csp", c_size_t),  # struct csum *fs_csp
    ("*fs_maxcluster", c_size_t),
    ("*fs_active", c_uint64),
    ("fs_old_cpc", c_int32),
    ("fs_maxbsize", c_int32),
    ("fs_unrefs", c_int64),
    ("fs_providersize", c_int64),
    ("fs_metaspace", c_int64),
    ("fs_sparecon64", c_int64 * 13),  # arr[13]
    ("fs_sblockactualloc", c_int64),
    ("fs_sblockloc", c_int64),
    ("fs_cstotal__cs_ndir", c_int64),
    ("fs_cstotal__cs_nbfree", c_int64),
    ("fs_cstotal__cs_nifree", c_int64),
    ("fs_cstotal__cs_nffree", c_int64),
    ("fs_cstotal__cs_numclusters", c_int64),
    ("fs_cstotal__cs_spare", c_int64 * 3),
    # ('fs_cstotal', c_size_t * 8),  # struct csum_total
    ("fs_time", ufs_time_t),
    ("fs_size", c_int64),
    ("fs_dsize", c_int64),
    ("fs_csaddr", ufs2_daddr_t),
    ("fs_pendingblocks", c_int64),
    ("fs_pendinginodes", c_uint32),
    ("fs_snapinum", c_uint32 * FSMAXSNAP),
    ("fs_avgfilesize", c_uint32),
    ("fs_avgfpdir", c_uint32),
    ("fs_save_cgsize", c_int32),
    ("fs_mtime", ufs_time_t),
    ("fs_sujfree", c_int32),
    ("fs_sparecon32", c_int32 * 21),  # arr[21]
    ("fs_ckhash", c_uint32),
    ("fs_metackhash", c_uint32),
    ("fs_flags", c_int32),
    ("fs_contigsumsize", c_int32),
    ("fs_maxsymlinklen", c_int32),
    ("fs_old_inodefmt", c_int32),
    ("fs_maxfilesize", c_uint64),
    ("fs_qbmask", c_int64),
    ("fs_qfmask", c_int64),
    ("fs_state", c_int32),
    ("fs_old_postblformat", c_int32),
    ("fs_old_nrpos", c_int32),
    ("fs_spare5", c_int32 * 2),  # arr[2]
    ("fs_magic", c_int32),
]

UFS_CG = [
    ("cg_firstfield", c_int32),
    ("cg_magic", c_int32),
    ("cg_old_time", c_int32),
    ("cg_cgx", c_uint32),
    ("cg_old_nyl", c_int16),
    ("cg_old_niblk", c_int16),
    ("cg_ndblk", c_uint32),
    ("cg_cs__cs_ndir", c_int32),
    ("cg_cs__cs_nbfree", c_int32),
    ("cg_cs__cs_nifree", c_int32),
    ("cg_cs__cs_nffree", c_int32),
    ("cg_rotor", c_uint32),
    ("cg_frotor", c_uint32),
    ("cg_irotor", c_uint32),
    ("cg_frsum", c_uint32 * MAXFRAG),  # arr[MAXFRAG]
    ("cg_old_btotoff", c_int32),
    ("cg_old_boff", c_int32),
    ("cg_iusedoff", c_uint32),
    ("cg_freeoff", c_uint32),
    ("cg_nextfreeoff", c_uint32),
    ("cg_clustersumoff", c_uint32),
    ("cg_clusteroff", c_uint32),
    ("cg_nclusterblks", c_uint32),
    ("cg_niblk", c_uint32),
    ("cg_initediblk", c_uint32),
    ("cg_unrefs", c_uint32),
    ("cg_sparecon32", c_int32),
    ("cg_ckhash", c_uint32),
    ("cg_time", ufs_time_t),
    ("cg_sparecon64", c_uint64 * 3),  # arr[3]
    ("cg_space", c_uint8),
]


class UFS(Structure):
    def __init__(self, fs, fst):
        super(Structure).__init__()
        self.sb = OrderedDict()
        self.cg = OrderedDict()
        self.sb_expected_len = 1376
        self.cg_expected_len = 169
        self.fs = fs
        self.fst = fst
        if fst == "ufs2":
            self.sbo = SBLOCK_UFS2
        else:
            self.sbo = SBLOCK_UFS1
        self.sb_locs = []
        self.fields_sb = UFS_SB
        self.cg_locs = []
        self.fields_cg = UFS_CG
        self._sanity_check()

    def _sanity_check(self):
        res_sb = 0
        res_cg = 0
        for _, v in self.fields_sb:
            res_sb += sizeof(v)
        for _, v in self.fields_cg:
            res_cg += sizeof(v)
        assert res_sb == self.sb_expected_len
        assert res_cg == self.cg_expected_len

    def get_superblock(self, n=0):
        self.find_all_superblocks()
        self._read_superblock_in_dict(self.sb_locs[n])
        return self.sb

    def get_cylinder_group(self, n=0):
        self.find_all_cylinder_groups()
        self._read_cylinder_group_in_dict(self.cg_locs[n])
        return self.cg

    def _read_superblock_in_dict(self, loc=SBLOCK_UFS2):

        with open(self.fs, "rb") as f:
            f.seek(loc)
            for field in self.fields_sb:
                self.sb[field[0]] = f.read(sizeof(field[1]))

    def _read_cylinder_group_in_dict(self, loc=None):
        with open(self.fs, "rb") as f:
            f.seek(loc)
            for field in self.fields_cg:
                self.cg[field[0]] = f.read(sizeof(field[1]))

    def find_all_superblocks(self):
        with open(self.fs, "rb") as f:
            data = f.read()
            matches = re.finditer(UFS_MAGIC, data)
            for m in matches:
                sb = m.span()[0] - (self.sb_expected_len - 4)
                self.sb_locs.append(sb)
        self.sb_locs = self.sb_locs[1:]
        if (not self.sb_locs or SBLOCK_UFS2 not in self.sb_locs) and self.fst == "ufs2":
            self.sb_locs = [SBLOCK_UFS2] + self.sb_locs
        elif (not self.sb_locs or SBLOCK_UFS1 not in self.sb_locs) and self.fst == "ufs1":
            self.sb_locs = [SBLOCK_UFS1] + self.sb_locs
        return self.sb_locs

    def find_all_cylinder_groups(self):
        with open(self.fs, "rb") as f:
            data = f.read()
            matches = re.finditer(CG_MAGIC, data)
            for m in matches:
                cg = m.span()[0] - 4
                self.cg_locs.append(cg)
        return self.cg_locs

    def print_superblock(self):
        tmp = OrderedDict()
        for key, value in self.sb.items():
            if key in [
                "fs_maxfilesize",
                "fs_metackhash",
                "fs_ckhash",
                "fs_avgfpdir",
                "fs_avgfilesize",
                "fs_snapinum",
                "fs_pendinginodes",
                "*fs_active",
                "fs_swuid",
                "fs_ipg",
                "fs_inopb",
                "fs_ncg",
            ]:
                tmp[key] = hex(get_int(value, signed=False))
            else:
                tmp[key] = hex(get_int(value))
        pp.pprint(tmp)

    def print_cylinder_group(self):
        tmp = OrderedDict()
        for key, value in self.cg.items():
            if key in [
                "cg_firstfield",
                "cg_magic",
                "cg_old_time",
                "cg_old_ncyl",
                "cg_old_niblk",
                "cg_old_btotoff",
                "cg_old_boff",
                "cg_sparecon32",
                "cg_time",
                "cg_sparecon64",
                "cg_cs__cs_ndir",
                "cg_cs__cs_nbfree",
                "cg_cs__cs_nifree",
                "cg_cs__cs_nffree",
            ]:
                tmp[key] = hex(get_int(value, signed=True))
            else:
                tmp[key] = hex(get_int(value))
        pp.pprint(tmp)

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
        "--print_superblock",
        "-ps",
        type=int,
        default=-1,
        dest="print_sb",
        help="Print the n-th superblock to stdout. Default: %(default)s",
    )
    parser.add_argument(
        "--print_cylinder_groups",
        "-pcg",
        type=int,
        help="Print the n-th cylinder group to stdout. Default: %(default)s",
        default=-1,
        dest="print_cg",
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
        "--file_system_type", "-ft", type=str, default="ufs2", dest="fst", help="[ufs1, ufs2]. Default: %(default)s"
    )

    args = parser.parse_args()

    ufs = UFS(args.file_system, args.fst)
    if args.dump:
        ufs.dump_superblock()
    if args.dump_all:
        ufs.dump_all_superblocks()
    if args.find_all:
        ufs.find_all_superblocks()
        ufs.find_all_cylinder_groups()
        res = ", ".join(hex(e) for e in ufs.sb_locs)
        print(f"[+] Found superblock offsets: {res}")
        res = ", ".join(hex(e) for e in ufs.cg_locs)
        print(f"[+] Found cylinder group offsets: {res}")
    if args.print_sb >= 0:
        ufs.find_all_superblocks()
        if not ufs.sb_locs and args.fst == "ufs2":
            ufs.sb_locs.append(SBLOCK_UFS2)
        elif not ufs.sb_locs and args.fst == "ufs1":
            ufs.sb_locs.append(SBLOCK_UFS1)
        ufs._read_superblock_in_dict(ufs.sb_locs[args.print_sb])
        ufs.print_superblock()
    if args.print_cg >= 0:
        ufs.find_all_cylinder_groups()
        ufs._read_cylinder_group_in_dict(ufs.cg_locs[args.print_cg])
        ufs.print_cylinder_group()


if __name__ == "__main__":
    main()
