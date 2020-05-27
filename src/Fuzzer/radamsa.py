import logging
import os
import pathlib
import random
import re
import subprocess
import sys

from file_system_magic.ufs_superblock_parser import UFS, UFS_MAGIC
from file_system_magic.ext_superblock_parser import EXT, EXT_MAGIC
from file_system_magic.zfs_uberblock_parser import ZFS, ZFS_MAGIC
from file_system_magic.fs_util import get_offset_in_sb, set_mime


class Radamsa:
    def __init__(self, path_to_file_system):
        self.radamsa_seed = None
        self.path_to_file_system = path_to_file_system
        self.path_to_mutated_file_system = None
        self.mime = None

    @staticmethod
    def _get_ufs_zfs_magic_pos(path_to_file_system, file_system_type=None):
        with open(path_to_file_system, "rb") as f:
            data = f.read()
            magic_positions = []
            if file_system_type == "ufs":
                magic_sequence = UFS_MAGIC
            elif file_system_type == "zfs":
                magic_sequence = ZFS_MAGIC
            else:
                return False
            matches = re.finditer(magic_sequence, data)
            for m in matches:
                magic_positions.append(m.span()[0])
            return magic_positions

    @staticmethod
    def _get_ext_magic_pos(path_to_file_system):
        with open(path_to_file_system, "rb") as f:
            data = f.read()
            match = data.find(EXT_MAGIC)
            return [match]

    def _set_magic(self, mgc_offs, mime=None):
        # logging.error("[*] Restoring magic bytes in {}".format(self.path_to_mutated_file_system))
        if "ext" in mime:
            mgc_seq = EXT_MAGIC
        elif "ufs" in mime:
            mgc_seq = UFS_MAGIC
        elif mime == "zfs":
            mgc_seq = ZFS_MAGIC
        else:
            print("[!] Unknown mime type - Cannot restore magic bytes - radamsa")
            sys.exit(1)
        with open(self.path_to_mutated_file_system, "rb+") as f:
            for m in mgc_offs:
                f.seek(m)
                f.write(mgc_seq)

    def _restore_magic_bytes(self):
        if "ufs" in self.mime:
            fs_p = UFS(fs=self.path_to_file_system, fst=self.mime)
            fn = "fs_magic"
        elif self.mime == "ext":
            fs_p = EXT(fs=self.path_to_file_system, fst=self.mime)
            fn = "ext2fs_magic"
        elif self.mime == "zfs":
            fs_p = ZFS(fs=self.path_to_file_system, fst=self.mime)
            fn = "ub_magic"
        else:
            logging.error("Could not detect file system type correctly")
            sys.exit(1)
        sb_locs = self._get_magic_offs_lst(fs_p, fn)
        self._set_magic(sb_locs, self.mime)

    @staticmethod
    def _get_magic_offs_lst(fs_p, mgc_n):
        sb_locs = fs_p.find_all_superblocks()
        magic_off, _ = get_offset_in_sb(fs_p, mgc_n)
        for i, _ in enumerate(sb_locs):
            sb_locs[i] = sb_locs[i] + magic_off
        return sb_locs

    def _restore_uberblock(self):
        sbs = []
        if "ufs" in self.mime:
            fsp = UFS(fs=self.path_to_file_system, fst=self.mime)
        elif "ext" in self.mime:
            fsp = EXT(fs=self.path_to_file_system, fst=self.mime)
        elif self.mime == "zfs":
            fsp = ZFS(fs=self.path_to_file_system, fst=self.mime)
        else:
            logging.error("Could not detect file system type correctly")
            return 0
        sb_locs = fsp.find_all_superblocks()
        with open(self.path_to_file_system, "rb") as f:
            for loc in sb_locs:
                f.seek(loc)
                sbs += f.read(fsp.expected_sb_len)
        with open(self.path_to_mutated_file_system, "wb") as f:
            for i, loc in enumerate(sb_locs):
                f.seek(loc)
                f.write(sbs[i])

    def mutation(self, preserve_magic=True, preserve_uberblock=False, determinism=True):
        self.mime = set_mime(self.path_to_file_system)
        name = pathlib.Path(self.path_to_file_system).name
        _path = pathlib.Path(self.path_to_file_system).parent
        self.path_to_mutated_file_system = os.path.join(_path, "radamsa_" + name)
        if determinism:
            self.radamsa_seed = random.getrandbits(100)
            cmd = "radamsa {} -s {} > {}".format(self.path_to_file_system, self.radamsa_seed, self.path_to_mutated_file_system,)
        else:
            cmd = "radamsa {} > {}".format(self.path_to_file_system, self.path_to_mutated_file_system)
        if preserve_uberblock:
            preserve_magic = False
        subprocess.call(cmd, shell=True)
        if preserve_magic:
            self._restore_magic_bytes()
        if preserve_uberblock:
            self._restore_uberblock()
        return self.radamsa_seed, self.path_to_mutated_file_system


def main():
    rad = Radamsa(sys.argv[1])
    rad.mutation(preserve_magic=True)


if __name__ == "__main__":
    sys.exit(main())
