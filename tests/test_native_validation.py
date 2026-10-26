import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from verify_shared_libs import MACHINES, verify_elf
import struct

class ELFTest(unittest.TestCase):
    def synthetic(self, abi, alignment=16384):
        cls, machine = MACHINES[abi]
        d = bytearray(256)
        d[:6] = bytes([127, 69, 76, 70, cls, 1]); struct.pack_into('<H', d, 18, machine)
        if cls == 2:
            struct.pack_into('<Q', d, 32, 64)
            struct.pack_into('<HH', d, 54, 56, 1)
            struct.pack_into('<I', d, 64, 1)
            struct.pack_into('<Q', d, 64 + 48, alignment)
        else:
            struct.pack_into('<I', d, 28, 52)
            struct.pack_into('<HH', d, 42, 32, 1)
            struct.pack_into('<I', d, 52, 1)
            struct.pack_into('<I', d, 52 + 28, alignment)
        return bytes(d)

    def test_all_four_abi_16k(self):
        for abi in MACHINES:
            with self.subTest(abi=abi):
                self.assertEqual(verify_elf(self.synthetic(abi), abi), [16384])

    def test_all_four_abi_4k_rejected(self):
        for abi in MACHINES:
            with self.subTest(abi=abi), self.assertRaises(ValueError):
                verify_elf(self.synthetic(abi, 4096), abi)

if __name__ == '__main__':
    unittest.main()
