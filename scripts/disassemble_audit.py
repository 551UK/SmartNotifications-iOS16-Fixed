#!/usr/bin/env python3
import lief,capstone
from pathlib import Path
from collections import Counter
p=Path('audit/pkg/var/jb/Library/MobileSubstrate/DynamicLibraries/SmartNotificationsiOS16.dylib')
fat=lief.MachO.parse(str(p))
print('ARCHES',len(fat))
for m in fat:
    print('\n==============',m.header.cpu_type,'================')
    text=next(s for s in m.sections if s.name=='__text')
    md=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)
    md.detail=True
    ins=list(md.disasm(bytes(text.content),text.virtual_address))
    funcs=sorted([(s.value,s.name) for s in m.symbols if s.value and text.virtual_address<=s.value<text.virtual_address+text.size])
    print('FUNCTIONS',funcs)
    target=next((addr for addr,name in funcs if 'sendBulletin' in name),None)
    if target:
        print('==== SEND BULLETIN ====')
        for x in ins:
            if target-32<=x.address<target+1800:
                print(f'{x.address:08x}: {x.mnemonic:<10} {x.op_str}')
        print('==== SEND BULLETIN CALLERS ====')
        sites=[x.address for x in ins if x.mnemonic=='bl' and x.operands[0].type==capstone.arm64.ARM64_OP_IMM and x.operands[0].imm==target]
        print('CALLER SITES', [hex(x) for x in sites])
        for addr in sites:
            print('--- CALL SITE',hex(addr),'---')
            for x in ins:
                if addr-450<=x.address<addr+120: print(f'{x.address:08x}: {x.mnemonic:<10} {x.op_str}')
    # key CF string in __cstring (simple string inspection)
    print('==== FAKE-RELATED CSTRINGS ====')
    for sec in m.sections:
        if sec.name in ('__cstring','__objc_methname'):
            raw=bytes(sec.content)
            import re
            for match in re.finditer(rb'[\x20-\x7e]{4,}',raw):
                s=match.group(0).decode('ascii',errors='replace')
                if any(k in s.lower() for k in ('fake','selected','value','notif','volume','up','down','button','dispatch','ringer','sound','misc','app','plist')):
                    print(f'{sec.virtual_address+match.start():08x}',sec.name,s)
