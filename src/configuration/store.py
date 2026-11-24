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
