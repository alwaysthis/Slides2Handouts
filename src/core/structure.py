from copy import deepcopy
from .model import paper, DEFAULT

def section_start(pages,index):
    return next((i for i in range(index,0,-1) if pages[i].get("section")),0)

def section_objects(state,index):
    pages=state["pages"]
    start=section_start(pages,index)
    return pages[start].setdefault("section_objects",[])

def regions(settings,index=0):
    w,h=paper(settings)
    l,t,r,b=settings["margins"]
    t+=settings.get("header_space",0)
    b+=settings.get("footer_space",0)
    if settings.get("number_enabled",True):
        from .model import footer_box
        b=max(b,h-footer_box(settings)[1]+10)
    mode=settings.get("division","horizontal")
    width,height=max(1,w-l-r),max(1,h-t-b)
    if mode=="none":return [l,t,width,height],None
    ratio=settings.get("notes_ratio",.46)
    gap=min(settings.get("region_gap",12),(width if mode=="horizontal" else height)/4)
    flip=settings.get("odd_side" if index%2==0 else "even_side","left")=="right" if settings.get("alternate") else settings.get("odd_side")=="right"
    if mode=="vertical":
        slides=(height-gap)*(1-ratio)
        return [l,t,width,slides],[l,t+slides+gap,width,height-gap-slides]
    slides=(width-gap)*(1-ratio)
    notes=width-gap-slides
    return ([l+notes+gap,t,slides,height],[l,t,notes,height]) if flip else ([l,t,slides,height],[l+slides+gap,t,notes,height])

def boundaries(settings,index):
    slides,notes=regions(settings,index)
    def place(area,override,prefix):
        if not area:return None
        if override:return override
        x,y,w,h=area
        inset=settings.get(prefix+"_inset",0)
        nw=max(1,(w-2*inset)*settings.get(prefix+"_width_ratio",1))
        nh=max(1,(h-2*inset)*settings.get(prefix+"_height_ratio",1))
        return [x+(w-nw)*{"left":0,"center":.5,"right":1}[settings.get(prefix+"_align","right" if prefix=="notes" else "center")],
                y+(h-nh)*{"top":0,"center":.5,"bottom":1}[settings.get(prefix+"_valign","center")],nw,nh]
    return place(slides,settings.get("content_box"),"slides"),place(notes,settings.get("notes_box"),"notes")

def format_number(value,style):
    if value<1 or style=="decimal":return str(value)
    if style in ("A","a"):
        result=""
        while value:
            value,rem=divmod(value-1,26)
            result=chr(65+rem)+result
        return result if style=="A" else result.lower()
    result=""
    for number,letter in [(1000,"M"),(900,"CM"),(500,"D"),(400,"CD"),(100,"C"),(90,"XC"),(50,"L"),(40,"XL"),(10,"X"),(9,"IX"),(5,"V"),(4,"IV"),(1,"I")]:
        count,value=divmod(value,number)
        result+=letter*count
    return result if style=="I" else result.lower()

class DisplayNumber(int):
    def __new__(cls,value,style):
        obj=super().__new__(cls,value)
        obj.style=style
        return obj
    def __format__(self,spec):
        return super().__format__(spec) if spec else format_number(int(self),self.style)

def contents(state):
    from .textstyles import styled,numbered_pages
    lines=[]
    for i in range(len(state["pages"])):
        for obj in numbered_pages(state,i):
            obj=styled(state["settings"],obj)
            level=obj.get("level",0)
            if level and obj.get("enabled",True):
                lines.append("  "*(level-1)+obj["text"].replace("\n"," ")+"    "+str(i+1))
    return "\n".join(lines)


def band_owner(pages,index,kind):
    start=section_start(pages,index)
    while start and pages[start].get(kind+"_inherit"):
        start=section_start(pages,start-1)
    return pages[start]


def section_band(pages,index,kind):
    owner=band_owner(pages,index,kind)
    if kind=="header" and index%2 and owner.get("header_alternate"):
        return owner.get("header_even",owner.get("header"))
    return owner.get(kind)


def migrate_titles(state):
    """Turn legacy page and template titles into normal heading text boxes."""
    from .model import title_object
    pages=state["pages"]
    legacy=state["settings"].get("title") or any(o["kind"]=="title" for o in state["settings"]["objects"])
    if not legacy and not any("title" in pg for pg in pages):return
    for i,pg in enumerate(pages):
        title=title_object(state,i)
        if title:
            pg["objects"].append(dict(title,kind="text",level=1))
    state["settings"].pop("title",None)
    state["settings"]["objects"]=[o for o in state["settings"]["objects"] if o["kind"]!="title"]
    for pg in pages:pg.pop("title",None)
