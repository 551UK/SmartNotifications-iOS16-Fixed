#!/usr/bin/env python3
"""Read Mach-O nlist metadata without binary-analysis dependencies."""
import struct
from pathlib import Path

p=Path('audit/pkg/var/jb/Library/MobileSubstrate/DynamicLibraries/SmartNotificationsiOS16.dylib')
data=p.read_bytes()
magic=struct.unpack_from('>I',data)[0]
if magic==0xcafebabe:
    nfat=struct.unpack_from('>I',data,4)[0]
    slices=[]
    for i in range(nfat):
        cpu,sub,off,size,align=struct.unpack_from('>IIIII',data,8+i*20)
        slices.append((cpu,sub,data[off:off+size]))
else:
    slices=[(0,0,data)]
for cpu,sub,b in slices:
    (mg,mcpu,msub,ftype,ncmds,cmdsize,flags,reserved)=struct.unpack_from('<IiiIIIII',b,0)
    assert mg==0xfeedfacf,hex(mg)
    print('ARCH',hex(mcpu),hex(msub),'cmds',ncmds)
    offset=32
    sym=None
    for i in range(ncmds):
        cmd,sz=struct.unpack_from('<II',b,offset)
        if cmd==0x2:
            sym=struct.unpack_from('<IIIIII',b,offset)
        offset+=sz
    assert sym, 'No symbol table'
    _,_,symoff,nsyms,stroff,strsz=sym
    print('symbols:',nsyms,'string bytes:',strsz)
    found=False
    for i in range(nsyms):
        n_strx,n_type,n_sect,n_desc,n_value=struct.unpack_from('<IBBHQ',b,symoff+16*i)
        e=b.find(b'\0',stroff+n_strx)
        name=b[stroff+n_strx:e].decode('utf8','replace')
        if 'sendBulletin' in name or 'MSHookFunction' in name:
            print('SYMBOL',name,'addr',hex(n_value),'type',hex(n_type),'external',bool(n_type&1),'private',bool(n_type&0x10))
            if 'sendBulletin' in name:
                found=True
    assert found,'Expected helper symbol is missing'
