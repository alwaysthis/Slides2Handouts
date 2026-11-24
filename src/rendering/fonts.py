from functools import lru_cache
from pathlib import Path
import os
import winreg

@lru_cache(maxsize=64)
def font_css(family):
    base=Path(os.environ["WINDIR"])/"Fonts"
    entries=[]
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as key:
        for i in range(winreg.QueryInfoKey(key)[1]):
            name,file,_=winreg.EnumValue(key,i)
            name=name.split(" (")[0].casefold()
            primary=name.split(" & ")[0]
            if primary==family.casefold() or primary.startswith(family.casefold()+" "):
                suffix=primary[len(family):].strip()
                if suffix not in ("","regular","bold","italic","bold italic","oblique"):continue
                path=base/file
                if path.is_file():
                    weight="bold" if "bold" in suffix else "normal"
                    style="italic" if suffix in ("italic","bold italic","oblique") else "normal"
                    entries.append(f"@font-face{{font-family:Handout;src:url('{path.name}');font-weight:{weight};font-style:{style}}}")
    return "".join(entries)
