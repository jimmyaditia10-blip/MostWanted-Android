#!/usr/bin/env python3
import hashlib, json, re, subprocess, sys, zipfile
from pathlib import Path

APK=Path(sys.argv[1])
CANDIDATE=Path(sys.argv[2])
OUT=Path(sys.argv[3])
EXPECTED_APK="222da4e42a2c14bba5adf44df1539964b9809a0a4f44c8b688f944503f8d49bc"
EXPECTED_SO="9cea9cc3767d8cb0a72cad33a44edf68a66daecd75104ddd1032a17b55e9c906"
EXPECTED_SHADER_LEN=2343
EXPECTED_SHADER_VA=0x53CF5E
EXPECTED_KSHADER_OBJECT=0x1D5C0A0

def sha(b): return hashlib.sha256(b).hexdigest()
def run(*args):
    return subprocess.run(args,check=True,text=True,capture_output=True).stdout

apk=APK.read_bytes()
if sha(apk)!=EXPECTED_APK: raise SystemExit("Pustaka APK SHA-256 mismatch")
with zipfile.ZipFile(APK) as z:
    bad=z.testzip()
    if bad: raise SystemExit(f"APK ZIP CRC failure: {bad}")
    so=z.read("lib/arm64-v8a/libmain.so")
if sha(so)!=EXPECTED_SO: raise SystemExit("Pustaka libmain.so SHA-256 mismatch")

tmp=OUT/"work"; tmp.mkdir(parents=True,exist_ok=True)
so_path=tmp/"libmain.so"; so_path.write_bytes(so)
symbols=run("readelf","-Ws",str(so_path))
for name in ["d3d::DrawNosTrail","streetlight::UpdateNosTrail","streetlight::BuildNosTrail","nosfx::History::Update","nosfx::History::Mesh","nosfx::kShader"]:
    if name not in run("readelf","-Ws",str(so_path),"--wide") and name not in symbols:
        raise SystemExit(f"Missing required Pustaka symbol: {name}")
relocs=run("readelf","-rW",str(so_path))
line=next((x for x in relocs.splitlines() if re.search(rf"^\\s*{EXPECTED_KSHADER_OBJECT:016x}\\s",x)),None)
if not line or not re.search(rf"R_AARCH64_RELATIVE\\s+{EXPECTED_SHADER_VA:x}$",line):
    raise SystemExit("nosfx::kShader relocation no longer points at the expected source")
end=so.find(b"\\0",EXPECTED_SHADER_VA)
old=so[EXPECTED_SHADER_VA:end]
if len(old)!=EXPECTED_SHADER_LEN or b"coreLight" not in old or b"glowLight" not in old:
    raise SystemExit("Original NOS shader signature/length mismatch")

candidate=CANDIDATE.read_bytes()
if candidate.endswith(b"\\n"): candidate=candidate[:-1]
if not candidate or len(candidate)>len(old): raise SystemExit("Candidate shader is empty or exceeds the in-place source slot")
for marker in [b"ATTR0",b"ATTR1",b"SV_Position",b"TEXCOORD0",b"SV_Target",b"float4 vs(",b"float4 ps("]:
    if marker not in candidate: raise SystemExit(f"Candidate missing interface marker {marker!r}")
if any(x in candidate for x in [b"Texture2D",b"SamplerState",b"register(t",b"register(s"]):
    raise SystemExit("Candidate unexpectedly adds texture/sampler descriptors")

patched=bytearray(so)
patched[EXPECTED_SHADER_VA:EXPECTED_SHADER_VA+len(old)+1]=candidate+b"\\0"*(len(old)-len(candidate)+1)
if bytes(patched[:EXPECTED_SHADER_VA])!=so[:EXPECTED_SHADER_VA]: raise SystemExit("Bytes before shader changed")
if bytes(patched[EXPECTED_SHADER_VA+len(old)+1:])!=so[EXPECTED_SHADER_VA+len(old)+1:]: raise SystemExit("Bytes after shader changed")
if bytes(patched[EXPECTED_SHADER_VA:EXPECTED_SHADER_VA+len(candidate)])!=candidate: raise SystemExit("Patched shader bytes mismatch")
if patched[EXPECTED_SHADER_VA+len(candidate)]!=0: raise SystemExit("Missing candidate NUL terminator")

patch_dir=OUT/"patch-prototype"; patch_dir.mkdir(parents=True,exist_ok=True)
(patch_dir/"libmain.so").write_bytes(patched)
adapted=[]
for label,source in [("original",old),("candidate",candidate)]:
    text=source.decode("utf-8")
    text=re.sub(r"(?m)^([ \\t]*)(\\w+ v\\d+ : ATTR(\\d+);)",r"\\1[[vk::location(\\3)]] \\2",text)
    path=OUT/"shader"/f"{label}.hlsl"; path.parent.mkdir(parents=True,exist_ok=True); path.write_text(text)
    adapted.append({"name":label,"bytes":len(source),"sha256":sha(source)})
report={
 "apk_sha256":sha(apk),"libmain_sha256":sha(so),"libmain_patched_sha256":sha(bytes(patched)),
 "shader_source_va":hex(EXPECTED_SHADER_VA),"shader_source_length_original":len(old),
 "shader_source_length_candidate":len(candidate),"padding_bytes":len(old)-len(candidate),
 "patch_range_only":True,"other_libmain_bytes_unchanged":True,
 "shader_sources":adapted,
 "required_runtime_symbols":["d3d::DrawNosTrail","streetlight::UpdateNosTrail","streetlight::BuildNosTrail","nosfx::History::Update","nosfx::History::Mesh","nosfx::kShader"],
 "descriptor_policy":"no new Texture2D/SamplerState; preserves existing no-descriptor NOS shader pipeline"
}
(OUT/"patch-validation.json").write_text(json.dumps(report,indent=2)+"\\n")
print(json.dumps(report,indent=2))
