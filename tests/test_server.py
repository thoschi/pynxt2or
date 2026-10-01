import unittest
from pynxt2ors.server import OpenRobertaServer
class Resp:
    def __init__(self,j=None,content=b'',headers=None): self._j=j; self.content=content; self.headers=headers or {}; self.text='';
    def raise_for_status(self): pass
    def json(self): return self._j
class Session:
    def __init__(self): self.calls=[]
    def post(self,url,**kw): self.calls.append((url,kw)); return Resp({'cmd':'repeat'})
    def close(self): pass
class Tests(unittest.TestCase):
    def test_push(self):
        s=Session(); c=OpenRobertaServer(session=s); self.assertEqual(c.push({'cmd':'register'}),{'cmd':'repeat'}); self.assertTrue(s.calls[0][0].endswith('/rest/pushcmd'))
