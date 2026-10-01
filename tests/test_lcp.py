import unittest
from pynxt2ors.lcp import NXTUSB, NXTProtocolError

class FakeDev:
    def __init__(self,replies): self.replies=list(replies); self.writes=[]
    def write(self,ep,data,timeout=None): self.writes.append((ep,bytes(data))); return len(data)
    def read(self,ep,n,timeout=None): return self.replies.pop(0)

class Tests(unittest.TestCase):
    def nxt(self,*replies): return NXTUSB(device=FakeDev(replies))
    def test_battery(self):
        n=self.nxt(bytes([2,0x0b,0,0x88,0x13])); self.assertEqual(n.get_battery_level(),5000); self.assertEqual(n.dev.writes[0][1],bytes([0,0x0b]))
    def test_firmware(self):
        n=self.nxt(bytes([2,0x88,0,1,2,31,1])); self.assertEqual(n.get_firmware_version()["firmware"],"1.31")
    def test_device(self):
        r=bytearray(33); r[0:3]=bytes([2,0x9b,0]); r[3:7]=b"GS06"; r[18:24]=bytes.fromhex("0016530A8414")
        d=self.nxt(bytes(r)).get_device_info(); self.assertEqual(d.brickname,"GS06"); self.assertEqual(d.macaddr,"00:16:53:0A:84:14")
    def test_no_program(self):
        n=self.nxt(bytes([2,0x11,0xEC])); self.assertIsNone(n.get_current_program_name())
    def test_filename_matches_legacy_limit(self): self.assertEqual(NXTUSB.rxe_name("abcdefghijklmnop.q"),"abcdefghijklmn.rxe")
