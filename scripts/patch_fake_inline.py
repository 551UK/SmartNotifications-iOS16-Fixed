#!/usr/bin/env python3
"""Patch ONLY the original SmartNotifications fake-bulletin sender.

No injected helper dylib, hook installer, notification scheduler, or new tweak.
The existing sendBulletin function is gated directly by the switch saved in
selectedFakeApp.plist, using the SAME ObjC calls as the original volume hook.

Fails closed on unknown slices, unexpected code, occupied code padding, wrong
symbol names, or incorrect assembled branch targets.
"""
import argparse
import struct
from pathlib import Path
import capstone
from keystone import Ks, KS_ARCH_ARM64, KS_MODE_LITTLE_ENDIAN

FAKE_SYMBOL = '__Z12sendBulletinP8NSStringS0_S0_'
CAVE_VA = 0x5F00
STUBS = {
  # arm64; addresses verified from the original iOS 16 1.0 binary disassembly.
  (0x0100000C, 0): {
    'start': 0x6FC8, 'class_ref': 0x1C410, 'class_func': 0x14068,
    'dictionary': 0x14540, 'object_for_key': 0x147C0, 'bool_value': 0x14240,
    'prefs_cf': 0x18690, 'toggle_cf': 0x18E70
  },
  # arm64e with PAC00 bit; signed cpu subtype becomes -0x7ffffffe.
  (0x0100000C, 0x80000002): {
    'start': 0x63B4, 'class_ref': 0x1C410, 'class_func': 0x13FC0,
    'dictionary': 0x144E0, 'object_for_key': 0x14760, 'bool_value': 0x141E0,
    'prefs_cf': 0x18690, 'toggle_cf': 0x18E70
  }
}
ks=Ks(KS_ARCH_ARM64,KS_MODE_LITTLE_ENDIAN)
cs=capstone.Cs(capstone.CS_ARCH_ARM64,capstone.CS_MODE_ARM)

def read_macho(raw,off,size):
    magic, cpu, sub, filetype, ncmds, sizeofcmds, flags, reserved=struct.unpack_from('<IiiIIIII',raw,off)
    assert magic==0xfeedfacf and filetype==6, 'Expected 64-bit Mach-O dylib'
    end=off+size
    assert off+32+sizeofcmds < end
    command=off+32
    sections=[]
    text_segment=None
    symtab=None
    for _ in range(ncmds):
        cmd,cmdsize=struct.unpack_from('<II',raw,command)
        assert cmdsize>=8 and command+cmdsize<=off+32+sizeofcmds
        if cmd==0x19: # LC_SEGMENT_64
            name,vmaddr,vmsize,fileoff,filesize,maxprot,initprot,nsects,sgflags=struct.unpack_from('<16sQQQQiiII',raw,command+8)
            name=name.rstrip(b'\0').decode()
            if name=='__TEXT':
                text_segment=(vmaddr,vmsize,fileoff,filesize,maxprot,initprot)
            for i in range(nsects):
                start=command+72+i*80
                section_name,segment_name,addr,sectionsize=struct.unpack_from('<16s16sQQ',raw,start)
                sections.append((section_name.rstrip(b'\0').decode(),addr,sectionsize))
        if cmd==2: # LC_SYMTAB
            symtab=struct.unpack_from('<IIII',raw,command+8)
        command+=cmdsize
    assert text_segment and symtab, 'Missing __TEXT or symbols'
    symoff,nsyms,stroff,strsz=symtab
    assert symoff+nsyms*16<size and stroff+strsz<=size
    send=None
    for i in range(nsyms):
        index,typ,sect,desc,value=struct.unpack_from('<IBBHQ',raw,off+symoff+16*i)
        string_end=raw.find(b'\0',off+stroff+index,off+stroff+strsz)
        if string_end<0: continue
        name=raw[off+stroff+index:string_end].decode('ascii','replace')
        if name==FAKE_SYMBOL:
            assert send is None
            send=value
            assert typ & 0x01
    assert send, 'Original fake bulletin sender symbol is missing'
    segva,segsize,segfo,segfs,maxprot,initprot=text_segment
    assert segva<=CAVE_VA<segva+segfs and initprot&4, '__TEXT cave is not executable'
    assert off+segfo+(CAVE_VA-segva)<end
    for name,va,sz in sections:
        assert not va<=CAVE_VA<va+sz, f'Code cave overlaps {name}'
    def fileoff(addr):
        assert segva<=addr<segva+segfs
        return off+segfo+(addr-segva)
    return (cpu,sub & 0xffffffff),send,fileoff,off+32+sizeofcmds

def assemble(source, addr):
    out,count=ks.asm(source,addr=addr)
    assert out and count>0
    return bytes(out)

def instructions(code,origin):
    return list(cs.disasm(code,origin))

def patch_slice(raw,off,size,test_only):
    arch,entry,fileoff,load_end=read_macho(raw,off,size)
    assert arch in STUBS, f'Unknown architecture {arch}'
    x=STUBS[arch]
    assert entry==x['start'],f'Sender moved: {hex(entry)} vs {hex(x["start"])}'
    assert load_end<fileoff(CAVE_VA), 'Cave overlaps load commands'
    original=bytes(raw[fileoff(entry):fileoff(entry)+4])
    decoded=instructions(original,entry)
    assert len(decoded)==1 and decoded[0].mnemonic in ('sub','pacibsp'),f'Unexpected prologue: {decoded}'
    assert bytes(raw[fileoff(CAVE_VA):fileoff(CAVE_VA)+0x100])==b'\0'*0x100,'Nonempty code cave'

    source=f"""
      sub sp, sp, #0x20
      stp x0, x1, [sp, #0]
      stp x2, x30, [sp, #0x10]
      ldr x0, #{x['class_ref']}
      bl #{x['class_func']}
      adr x2, #{x['prefs_cf']}
      bl #{x['dictionary']}
      adr x2, #{x['toggle_cf']}
      bl #{x['object_for_key']}
      bl #{x['bool_value']}
      mov w9, w0
      ldp x2, x30, [sp, #0x10]
      ldp x0, x1, [sp, #0]
      add sp, sp, #0x20
      cbz w9, skip
      nop
      b #{entry+4}
    skip:
      ret
    """
    body=bytearray(assemble(source,CAVE_VA))
    assert len(body)<0x100 and len(body)%4==0
    # Keystone interprets ADR hash immediates as relative offsets. Encode absolute
    # CFString references explicitly using ARM64's PC-relative ADR layout.
    adr_sites=[i for i in instructions(body,CAVE_VA) if i.mnemonic=='adr']
    assert len(adr_sites)==2,'Expected exactly two CFString reference instructions'
    for insn,target in zip(adr_sites,(x['prefs_cf'],x['toggle_cf'])):
        delta=target-insn.address
        assert -(1<<20)<=delta<(1<<20)
        word=0x10000002 | ((delta&3)<<29) | (((delta>>2)&0x7ffff)<<5)
        off=insn.address-CAVE_VA
        body[off:off+4]=struct.pack('<I',word)
    body=bytes(body)
    ins=instructions(body,CAVE_VA)
    assert len(ins)*4==len(body), 'Invalid disassembly'
    assert ins[-3].mnemonic=='nop' and ins[-2].mnemonic=='b' and ins[-1].mnemonic=='ret'
    patched=bytearray(body)
    patched[ins[-3].address-CAVE_VA:ins[-3].address-CAVE_VA+4]=original
    ins=instructions(patched,CAVE_VA)
    assert ins[-3].mnemonic==decoded[0].mnemonic, 'Original prologue not preserved'
    required_calls=[x[k] for k in ('class_func','dictionary','object_for_key','bool_value')]
    observed_calls=[int(i.op_str.lstrip('#'),16) for i in ins if i.mnemonic=='bl']
    assert required_calls==observed_calls,(required_calls,observed_calls)
    required_targets={x['prefs_cf'],x['toggle_cf'],x['class_ref']}
    observed_targets={int(i.op_str.split('#')[-1],16) for i in ins if i.mnemonic in ('ldr','adr') and '#' in i.op_str}
    assert required_targets<=observed_targets,(required_targets,observed_targets)
    assert int(ins[-2].op_str.lstrip('#'),16)==entry+4
    assert int(ins[-4].op_str.split('#')[-1],16)==ins[-1].address,'OFF must return before original sender'
    entry_branch=assemble(f'b #{CAVE_VA}',entry)
    assert len(entry_branch)==4 and instructions(entry_branch,entry)[0].op_str=='#'+hex(CAVE_VA)
    print(f'PASS {arch}: sender {hex(entry)}, guard {hex(CAVE_VA)}, bytes {len(body)}, original prologue {decoded[0].mnemonic}, switch OFF returns, ON proceeds')
    if not test_only:
        raw[fileoff(CAVE_VA):fileoff(CAVE_VA)+len(patched)]=patched
        raw[fileoff(entry):fileoff(entry)+4]=entry_branch

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('original')
    ap.add_argument('output')
    ap.add_argument('--dry-run',action='store_true')
    a=ap.parse_args()
    raw=bytearray(Path(a.original).read_bytes())
    assert struct.unpack_from('>I',raw,0)[0]==0xcafebabe, 'Expected fat binary'
    count=struct.unpack_from('>I',raw,4)[0]
    assert count==2,'Require both arm64 and arm64e'
    infos=[]
    for i in range(count):
        cpu,sub,off,size,align=struct.unpack_from('>IIIII',raw,8+20*i)
        infos.append((off,size))
    assert len(infos)==2 and infos[0][0]+infos[0][1]<=infos[1][0]
    for off,size in infos:
        patch_slice(raw,off,size,a.dry_run)
    if not a.dry_run:
        Path(a.output).write_bytes(raw)
        print('PASS: both architectures patched within original binary; no helper dylib')
if __name__=='__main__':
    main()
