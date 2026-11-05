#!/usr/bin/env python3
import lief,capstone,struct,re
fat=lief.MachO.parse('audit/pkg/var/jb/Library/MobileSubstrate/DynamicLibraries/SmartNotificationsiOS16.dylib')
for m in fat:
    print('======= ARCH',m.header.cpu_type,'=======')
    secs=list(m.sections)
    def read(addr,n):
        for s in secs:
            if s.virtual_address<=addr and addr+n<=s.virtual_address+len(s.content):
                off=addr-s.virtual_address
                return bytes(s.content)[off:off+n]
        return b''
    sect=next(s for s in secs if s.name=='__cfstring')
    print('CFSTRINGS:')
    for va in range(sect.virtual_address,sect.virtual_address+len(sect.content),32):
        b=read(va,32)
        if len(b)<32: continue
        q=struct.unpack('<QQQQ',b)
        raw=read(q[2] & 0xffffffff, q[3])
        if len(raw)==q[3] and q[3]<1000:
            t=raw.decode('utf-8','replace')
        else:
            t='?'
        print(hex(va),'ptr',hex(q[2] & 0xffffffff),'len',q[3],repr(t))
    text=next(s for s in secs if s.name=='__text')
    cs=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
    print('CALLERS OF sendBulletin')
    send=next((s.value for s in m.symbols if 'sendBulletin' in s.name),None)
    ins=list(cs.disasm(bytes(text.content),text.virtual_address))
    for i,x in enumerate(ins):
        if x.mnemonic=='bl' and x.op_str=='#'+hex(send):
            print('CALL',hex(x.address))
            for y in ins[max(0,i-24):i+4]:
                print('  ',hex(y.address),y.mnemonic,y.op_str)
    print('INIT_OFFSETS')
    for s in secs:
        if s.name=='__init_offsets': print(s.virtual_address,bytes(s.content).hex())
