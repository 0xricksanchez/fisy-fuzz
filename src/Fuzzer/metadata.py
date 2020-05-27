import logging
import random
import sys

from file_system_magic.ext_superblock_parser import EXT
from file_system_magic.fs_util import get_bytearray, set_mime, write_to_file, get_mutated_bytes
from file_system_magic.ufs_superblock_parser import UFS
from file_system_magic.zfs_uberblock_parser import ZFS


class MetaMutation:
    def __init__(self, fs, nbytes=5, restore=True, mode=None):
        self.nbytes = nbytes
        self.fs = fs
        self.mfs = None
        self.mime = None
        self.mode = mode
        self.s_locs = None
        self.restore = restore
        self.rnd = random.Random()
        self.rnd.seed(random.getrandbits(1024))

    def mutation(self):
        barray = get_bytearray(self.fs)
        self.mime = set_mime(self.fs)
        if "ufs" in self.mime:
            fs_p = UFS(fs=self.fs, fst=self.mime)
        elif self.mime == "ext":
            fs_p = EXT(fs=self.fs, fst=self.mime)
        elif self.mime == "zfs":
            fs_p = ZFS(fs=self.fs, fst=self.mime)
        else:
            logging.error("Could not detect file system type correctly")
            sys.exit(1)
        self.s_locs = fs_p.find_all_superblocks()

        good_locs = []
        for i in self.s_locs:
            for j in range(fs_p.sb_expected_len):
                good_locs += i + j

        ctr = 0
        while ctr < self.nbytes:
            try:
                rnd_pos = random.choice(good_locs)
                muta_byte_seq = get_mutated_bytes(1)
                barray[rnd_pos] = muta_byte_seq
                ctr += 1
            except IndexError as e:
                logging.error(e)
                return None
        return write_to_file(self.fs, self.nbytes, self.mode, barray)
