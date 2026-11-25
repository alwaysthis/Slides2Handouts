from functools import lru_cache
from pathlib import Path
import os
import winreg

ALIASES={"宋体":"simsun","新宋体":"nsimsun","微软雅黑":"microsoft yahei",
         "黑体":"simhei","楷体":"kaiti","仿宋":"fangsong","等线":"dengxian"}

@lru_cache(maxsize=1)
def installed_faces():
    base=Path(os.environ["WINDIR"])/"Fonts"
    result=[]
    for hive in (winreg.HKEY_LOCAL_MACHINE,winreg.HKEY_CURRENT_USER):
        try:
            key=winreg.OpenKey(hive,r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts")
        except FileNotFoundError:
            continue
        with key:
            for i in range(winreg.QueryInfoKey(key)[1]):
                name,file,_=winreg.EnumValue(key,i)
                path=base/file
                if path.is_file():
                    result.append((name.split(" (")[0].casefold().split(" & "),path))
    return result

@lru_cache(maxsize=128)
def font_css(family,alias="Handout"):
    family=ALIASES.get(family,family.casefold())
    entries={}
    variants={"":("normal","normal"),"regular":("normal","normal"),"bold":("bold","normal"),
              "italic":("normal","italic"),"oblique":("normal","italic"),
              "bold italic":("bold","italic"),"bold oblique":("bold","italic")}
    for names,path in installed_faces():
        for name in names:
            suffix=name[len(family):].strip() if name==family or name.startswith(family+" ") else None
            if suffix not in variants:continue
            entries.setdefault(variants[suffix],path.name)
    return "".join(f"@font-face{{font-family:{alias};src:url('{file}');font-weight:{weight};font-style:{style}}}"
                   for (weight,style),file in entries.items())
