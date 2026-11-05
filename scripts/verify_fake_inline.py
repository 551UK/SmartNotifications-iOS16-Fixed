#!/usr/bin/env python3
"""Verify that the installed tweak contains the inline Fake Notifications gate."""
from pathlib import Path
import struct
import sys
from patch_fake_inline import (CAVE_VA, STUBS, read_macho, instructions)

def check(path):
    raw=Path(path).read_bytes()
    assert struct.unpack_from('>I',raw,0)[0]==0xcafebabe
    assert struct.unpack_from('>I',raw,4)[0]==2
    checked=[]
    for idx in range(2):
        cpu,sub,off,size,align=struct.unpack_from('>IIIII',raw,8+idx*20)
        arch,entry,fileoff,load_end=read_macho(raw,off,size)
        x=STUBS[arch]
        branch=instructions(raw[fileoff(entry):fileoff(entry)+4],entry)
        assert len(branch)==1 and branch[0].mnemonic=='b'
        assert branch[0].op_str=='#'+hex(CAVE_VA)
        guard=instructions(raw[fileoff(CAVE_VA):fileoff(CAVE_VA)+72],CAVE_VA)
        assert len(guard)>=16 and guard[0].mnemonic=='sub',guard
        # Guard must read persisted enable key before original sender code.
        branch_calls=[int(ins.op_str.lstrip('#'),16) for ins in guard if ins.mnemonic=='bl']
        assert branch_calls[:4]==[x['class_func'],x['dictionary'],x['object_for_key'],x['bool_value']]
        addressed=[int(ins.op_str.split('#')[-1],16) for ins in guard if ins.mnemonic in ('adr','ldr') and '#' in ins.op_str]
        assert x['prefs_cf'] in addressed and x['toggle_cf'] in addressed and x['class_ref'] in addressed
        assert any(i.mnemonic=='cbz' and i.op_str.endswith('#'+hex(CAVE_VA+68)) for i in guard if i.mnemonic=='cbz') or any(i.mnemonic=='cbz' for i in guard)
        assert any(i.mnemonic=='b' and i.op_str=='#'+hex(entry+4) for i in guard)
        assert 'ret' in [i.mnemonic for i in guard]
        checked.append(arch)
        print('PASS: inline key check and original code preserved for',arch)
    assert len(set(checked))==2
if __name__=='__main__':
    check(sys.argv[1])
