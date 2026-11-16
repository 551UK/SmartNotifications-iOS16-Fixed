import hashlib, struct, subprocess, sys, tempfile, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from patch_fake_inline import patch_slice,read_macho,assemble
from patch_audio import patch,ARCHES,CAVE
from unicorn import Uc,UC_ARCH_ARM64,UC_MODE_ARM,UC_HOOK_CODE
from unicorn.arm64_const import *

class AudioBridgeTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  deb=Path('input/smartnotificationsios16_v1.0_iphoneos-arm64.deb')
  assert hashlib.sha256(deb.read_bytes()).hexdigest()=='74959924fb5eeac098fb7a7a51fd3d3295a646dd04d96349d9f2773d79ae9ef2'
  with tempfile.TemporaryDirectory() as td:
   subprocess.run(['dpkg-deb','-x',str(deb),td],check=True)
   raw=bytearray((Path(td)/'var/jb/Library/MobileSubstrate/DynamicLibraries/SmartNotificationsiOS16.dylib').read_bytes())
  for i in range(2):
   _,_,off,size,_=struct.unpack_from('>IIIII',raw,8+i*20)
   patch_slice(raw,off,size,False)
  cls.base=bytes(raw);cls.output=patch(cls.base)
 def test_bridge_present_and_missing_both_architectures(self):
  for i in range(2):
   _,sub,off,size,_=struct.unpack_from('>IIIII',self.output,8+i*20)
   _,_,fo,_=read_macho(self.output,off,size);cfg=ARCHES[sub]
   for exists in (False,True):
    with self.subTest(arch=hex(sub),helper=exists):
     emu=Uc(UC_ARCH_ARM64,UC_MODE_ARM);emu.mem_map(0,0x40000)
     emu.mem_write(0,self.output[off:off+size])
     sp=0x30000;lr=0x20000;player=0x21000;prefs=0x22000
     emu.reg_write(UC_ARM64_REG_SP,sp);emu.reg_write(UC_ARM64_REG_X0,player);emu.reg_write(UC_ARM64_REG_LR,lr)
     emu.reg_write(UC_ARM64_REG_X19,0x1234)
     emu.mem_write(sp+0x90,struct.pack('<Q',prefs))
     emu.mem_write(0x1c2c8,struct.pack('<Q',0x23000))
     called=[]
     def hook(uc,addr,n,user):
      if addr==cfg['responds']:
       self.assertEqual(uc.reg_read(UC_ARM64_REG_X0),player)
       self.assertEqual(uc.reg_read(UC_ARM64_REG_X1),0x23000)
       uc.reg_write(UC_ARM64_REG_X0,int(exists));uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
      elif addr==cfg['volume_stub']:
       called.append(True)
       self.assertEqual(uc.reg_read(UC_ARM64_REG_X0),player)
       self.assertEqual(uc.reg_read(UC_ARM64_REG_X2),prefs)
       self.assertEqual(uc.reg_read(UC_ARM64_REG_SP),sp)
       uc.reg_write(UC_ARM64_REG_PC,uc.reg_read(UC_ARM64_REG_LR))
     emu.hook_add(UC_HOOK_CODE,hook)
     emu.emu_start(CAVE,lr,count=100)
     self.assertEqual(emu.reg_read(UC_ARM64_REG_PC),lr)
     self.assertEqual(emu.reg_read(UC_ARM64_REG_SP),sp)
     self.assertEqual(emu.reg_read(UC_ARM64_REG_X19),0x1234)
     self.assertEqual(bool(called),exists)
 def test_only_allowlisted_bytes_change(self):
  allowed=set()
  for i in range(2):
   _,sub,off,size,_=struct.unpack_from('>IIIII',self.base,8+i*20)
   _,_,fo,_=read_macho(self.base,off,size);cfg=ARCHES[sub]
   for addr in [cfg['volume']]+cfg['category']+cfg['play']:
    allowed.update(range(fo(addr),fo(addr)+4))
   allowed.update(range(fo(CAVE),fo(CAVE)+0x100))
   loc=self.base.find(b'setMediaVolume:\0',off,off+size)
   allowed.update(range(loc,loc+16))
  changed={i for i,(a,b) in enumerate(zip(self.base,self.output)) if a!=b}
  self.assertTrue(changed);self.assertTrue(changed<=allowed)
  self.assertEqual(len(self.base),len(self.output))
 def test_unknown_binary_rejected(self):
  raw=bytearray(self.base)
  _,_,off,size,_=struct.unpack_from('>IIIII',raw,8)
  _,_,fo,_=read_macho(raw,off,size)
  raw[fo(ARCHES[0]['volume'])]^=1
  with self.assertRaises(AssertionError):patch(raw)
 def test_repatch_rejected(self):
  with self.assertRaises(AssertionError):patch(self.output)
