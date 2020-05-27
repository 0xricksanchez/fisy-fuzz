import logging
import random
import struct

from file_system_magic.fs_util import get_bytearray, write_to_file, get_mutated_bytes


class ByteFlipper:
    def __init__(self, fs, nbytes, mode=None):
        self.nbytes = nbytes
        self.fs = fs
        self.mfs = None
        self.mime = None
        self.mode = mode
        self.rnd = random.Random()
        self.rnd.seed(random.getrandbits(1024))

    def mutation_seq(self):
        byte_array = get_bytearray(self.fs)
        try:
            rnd_pos = random.randint(0, len(byte_array) - self.nbytes)
            muta_byte_seq = get_mutated_bytes(self.nbytes)
            ctr = 0
            while ctr <= self.nbytes:
                byte_array[rnd_pos + ctr] = struct.pack("B", muta_byte_seq[ctr])
                ctr += 1
        except IndexError as e:
            logging.error(e)
            return None
        return write_to_file(self.fs, self.nbytes, self.mode, byte_array)

    def mutation_rnd(self):
        ctr = 0
        byte_array = get_bytearray(self.fs)
        while ctr < self.nbytes:
            try:
                rnd_pos = random.randint(0, len(byte_array))
                muta_byte_seq = get_mutated_bytes(self.nbytes)
                byte_array[rnd_pos] = muta_byte_seq
                ctr += 1
            except IndexError as e:
                logging.error(e)
                return None
        return write_to_file(self.fs, self.nbytes, self.mode, byte_array)
