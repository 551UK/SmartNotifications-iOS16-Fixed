#!/usr/bin/env python3
"""Locate the real fake toggle storage and original sender behavior."""
from pathlib import Path
import re,struct,lief,capstone

paths=[
 'audit/pkg/var/jb/Library/MobileSubstrate/DynamicLibraries/SmartNotificationsiOS16.dylib',
 'audit/pkg/var/jb/Library/PreferenceBundles/SmartNotifications.bundle/SmartNotifications'
]
for path in paths:
    fat=lief.MachO.parse(path)
    m=next(iter(fat))
    print('\n###',path,'arch:',m.header.cpu_type)
    ss=list(m.sections)
    def read(va,n):
        for s in ss:
            if s.virtual_address<=va and va+n <= s.virtual_address+len(s.content):
                return bytes(s.content)[va-s.virtual_address:va-s.virtual_address+n]
        return b''
    def cstring(addr,n):
        b=read(addr&0xffffffff,n)
        return b.decode('utf8','replace') if len(b)==n else '?'
    cs={}
    for s in ss:
        if s.name=='__cfstring':
            for va in range(s.virtual_address,s.virtual_address+len(s.content),32):
                b=read(va,32)
                if len(b)<32: continue
                ptr,ln=struct.unpack_from('<QQ',b,16)
                if ln<500:
                    cs[va]=cstring(ptr,ln)
    interesting={a:v for a,v in cs.items() if any(t in v.lower() for t in ['fake','selected','message','sender','prefs','switch','enable','disabled'])}
    print('FAKE OR RELATED CFSTRINGS', [(hex(a),v) for a,v in interesting.items()])
    sel={}
    for s in ss:
        if s.name=='__objc_methname':
            raw=bytes(s.content)
            for match in re.finditer(rb'[\x20-\x7e]{4,}',raw):
                v=match.group().decode('utf8','replace')
                if any(t in v.lower() for t in ('fake','enable','boolforkey','setbool','setobject','objectforkey','write','synchronize','mutablecopy')):
                    sel[s.virtual_address+match.start()]=v
    print('RELEVANT SELECTORS', [(hex(a),v) for a,v in sel.items()])
    sec=next(s for s in ss if s.name=='__text')
    md=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
    ins=list(md.disasm(bytes(sec.content),sec.virtual_address))
    # Xrefs to matching CFStrings, globals, and selectors. ADR/ADRP/LDR: capstone value is already decoded.
    addrlist=set(interesting)|set(sel)
    candidates=[]
    for i,x in enumerate(ins):
        if x.mnemonic in ('adr','ldr','adrp') and '#' in x.op_str:
            try: address=int(x.op_str.split('#')[1],16)
            except: continue
            if address in addrlist:
                candidates.append((i,address))
    print('XREF COUNT',len(candidates))
    for i,a in candidates:
        print('\nXREF',hex(ins[i].address),'to',hex(a),repr(interesting.get(a) or sel.get(a)))
        for x in ins[max(i-14,0):min(i+21,len(ins))]:
            print(f'{x.address:08x} {x.mnemonic:<9} {x.op_str}')
