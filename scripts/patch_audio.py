#!/usr/bin/env python3
"""Redirect only the original custom-sound calls; preserve Mach-O layout/fixups.
Input must already contain the 1.0.3 fake-toggle guard. Re-sign output afterward.
"""
import argparse, struct
from pathlib import Path
from patch_fake_inline import read_macho, assemble, instructions
CAVE=0x6000
ARCHES={
  0: dict(volume=0xafec, category=[0xb410,0xb438], play=[0xb494,0xb4a0],
          volume_stub=0x14a80, category_stub=0x149c0, play_stub=0x147e0, responds=0x140d4),
  0x80000002: dict(volume=0xa804, category=[0xac28,0xac50], play=[0xacac,0xacb8],
          volume_stub=0x14a20, category_stub=0x14960, play_stub=0x14780, responds=0x14050),
}
def patch(original):
 raw=bytearray(original)
 assert struct.unpack_from('>II',raw,0)==(0xcafebabe,2)
 for i in range(2):
  cpu,sub,off,size,align=struct.unpack_from('>IIIII',raw,8+20*i)
  arch,entry,fo,load_end=read_macho(raw,off,size)
  cfg=ARCHES[sub]
  assert bytes(raw[fo(0x5f00):fo(0x5f00)+4])==assemble('sub sp, sp, #0x20',0x5f00), 'Missing fake-toggle guard'
  assert fo(CAVE)>load_end and raw[fo(CAVE):fo(CAVE)+0x100]==b'\0'*0x100
  def replace(addr,old,new):
   expected=assemble(old,addr)
   assert bytes(raw[fo(addr):fo(addr)+len(expected)])==expected, f'Unexpected instruction at {addr:x}'
   b=assemble(new,addr);assert len(b)==len(expected)
   raw[fo(addr):fo(addr)+len(b)]=b
  replace(cfg['volume'],f"bl #{cfg['volume_stub']}",'nop')
  for a in cfg['category']: replace(a,f"bl #{cfg['category_stub']}",'mov w0, #1')
  # Reuse the now-unused volume selector slot. No bind/chained-fixup changes.
  needle=b'setMediaVolume:\0';new=b'snPlayPrefs:\0'
  loc=raw.find(needle,off,off+size)
  assert loc>=0 and raw.find(needle,loc+1,off+size)==-1
  raw[loc:loc+len(needle)]=new+b'\0'*(len(needle)-len(new))
  # Receiver is the original player; x2 is THIS invocation's retained prefs.
  # Guard missing helper, preserve caller LR and stack alignment on both slices.
  code=assemble(f'''
   sub sp, sp, #0x20
   stp x0, x30, [sp]
   ldr x1, #0x1c2c8
   bl #{cfg['responds']}
   cbz w0, absent
   ldp x0, x30, [sp]
   ldr x2, [sp, #0xb0]
   add sp, sp, #0x20
   b #{cfg['volume_stub']}
  absent:
   ldr x30, [sp, #8]
   add sp, sp, #0x20
   mov w0, #0
   ret
  ''',CAVE)
  assert len(code)<0x100
  raw[fo(CAVE):fo(CAVE)+len(code)]=code
  for a in cfg['play']: replace(a,f"bl #{cfg['play_stub']}",f'bl #{CAVE}')
  print(f'PASS {sub:x}: scoped playback bridge, no media-volume/session writes')
 assert len(raw)==len(original)
 return bytes(raw)
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('input');ap.add_argument('output');args=ap.parse_args()
 Path(args.output).write_bytes(patch(Path(args.input).read_bytes()))
