import base64
import binascii
import json
import hashlib
from pathlib import Path
from tempfile import NamedTemporaryFile
from os import replace

def identity(path):
    with open(path,"rb") as stream:
        return hashlib.file_digest(stream,"sha256").hexdigest()

def write(path,kind,data):
    path=Path(path)
    with NamedTemporaryFile("w",dir=path.parent,delete=False,encoding="utf8") as out:
        json.dump(dict(version=1,kind=kind,data=data),out,ensure_ascii=False,indent=2)
    replace(out.name,path)

def read(path,kind):
    record=json.loads(Path(path).read_text(encoding="utf8"))
    if record["version"]!=1 or record["kind"]!=kind: raise ValueError("配置类型或版本不匹配")
    return record["data"]

def write_project(path,state,source_snapshot):
    source=state.get("source")
    if not source:
        write(path,"project",state)
        return
    payload=Path(source_snapshot).read_bytes()
    if hashlib.sha256(payload).hexdigest()!=source["sha256"]:
        raise ValueError("原稿文件指纹不匹配，无法保存工程")
    packaged=state | {"source":source | {"embedded_pptx":base64.b64encode(payload).decode("ascii")}}
    write(path,"project",packaged)

def unpack_project_source(source,destination):
    try:
        payload=base64.b64decode(source.pop("embedded_pptx"),validate=True)
    except (ValueError,TypeError,binascii.Error) as error:
        raise ValueError("工程中的内嵌 PPTX 已损坏") from error
    if hashlib.sha256(payload).hexdigest()!=source["sha256"]:
        raise ValueError("工程中的内嵌 PPTX 指纹不匹配")
    destination.write_bytes(payload)
    return destination
