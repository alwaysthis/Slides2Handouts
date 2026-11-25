from copy import deepcopy
from math import ceil, sqrt

TEXT = dict(kind="text", text="文字", box=[30,30,240,36], font="Microsoft YaHei", size=14,
            color="#202020", background="", border="", bold=False, italic=False,
            underline=False, align="left", valign="top", angle=0)
DEFAULT = dict(paper="A4", custom=[595,842], landscape=False, margins=[28,28,28,42],
               count=3, direction="vertical", align="center", gap=12, slide_area=0.52,
               background="#ffffff", objects=[dict(kind="notes", box=[320,28,246,770],
               enabled=True, background="#ffffff", border="#bbbbbb", style="blank", spacing=18)],
               number=dict(TEXT, text="{n}", box=[28,806,539,25], align="center", size=10),
               start=1, chapter=1, substart=1, separator=".")
def paper(s):
    w,h = {"A4":(595.28,841.89),"A3":(841.89,1190.55),"Letter":(612,792)}.get(s["paper"],s["custom"])
    return (h,w) if s["landscape"] else (w,h)
def page(indices=()):
    return dict(slides=[dict(source=i,box=None) for i in indices],objects=[], numbering={})
def group(indices,count):
    return [page(indices[i:i+count]) for i in range(0,len(indices),count)] or [page()]
def boxes(s,p,source):
    x,y,width,height=content_box(s)
    n=max(1,s["count"],len(p["slides"]))
    cols={"vertical":1,"horizontal":n,"grid":ceil(sqrt(n))}[s["direction"]]
    cols=s.get("columns") or cols
    rows=ceil(n/cols)
    gap=s["gap"]
    cw=(width-(cols-1)*gap)/cols
    ch=(height-(rows-1)*gap)/rows
    if min(cw,ch)<=0: raise ValueError("页面空间不足，请缩小边距或间隔")
    result=[]
    if not p["slides"]:return []
    aspects=[source[item["source"] if item["source"] is not None else 0].rect for item in p["slides"]]
    cell_height=min(ch,min(cw/r.width*r.height for r in aspects))
    for i,(item,rect) in enumerate(zip(p["slides"],aspects)):
        scale=min(cw/rect.width,cell_height/rect.height)
        a,bh=rect.width*scale,rect.height*scale
        offset={"left":0,"center":0.5,"right":1}[s["align"]]
        result.append(item["box"] or [x+i%cols*(cw+gap)+(cw-a)*offset,
                      y+i//cols*(cell_height+gap)+(cell_height-bh)/2,a,bh])
    return result
def move(pages, p, i, dest, slot):
    slide=pages[p]["slides"].pop(i)
    slide["box"]=None
    pages[dest]["slides"].insert(slot-int(p==dest and i<slot),slide)

def regroup(pages,p,i,count):
    tail=[slide for k,pg in enumerate(pages[p:]) for slide in pg["slides"][i if k==0 else 0:]]
    prefix=pages[p]["slides"][:i]
    for pg in pages[p:]: pg["slides"]=[]
    pages[p]["slides"]=prefix
    for slide in tail:
        if len(pages[p]["slides"])>=count:
            p+=1
            if p==len(pages): pages.append(page())
        slide["box"]=None
        pages[p]["slides"].append(slide)
def footer_box(settings):
    """The original template coordinates identify the automatic footer in v1 files."""
    number=settings["number"]
    if number["box"] != DEFAULT["number"]["box"]:
        return list(number["box"])
    width,height=paper(settings)
    left,_,right,_=settings["margins"]
    text_height=max(18,number["size"]*1.6)
    return [left,height-16-text_height,width-left-right,text_height]

def object_box(settings,obj):
    if obj["kind"]=="notes" and (obj.get("auto_box") or ("division" in settings and obj["box"]==DEFAULT["objects"][0]["box"])):
        from .structure import boundaries
        return boundaries(settings,settings.get("_page_index",0))[1] or obj["box"]
    if obj["kind"]=="notes" and obj["box"]==DEFAULT["objects"][0]["box"]:
        width,height=paper(settings)
        left,top,right,bottom=settings["margins"]
        x=left+(width-left-right)*settings["slide_area"]+12
        limit=min(height-bottom,footer_box(settings)[1]-10) if settings["number"]["box"]==DEFAULT["number"]["box"] else height-bottom
        return [x,top,max(1,width-right-x),max(1,limit-top)]
    return list(obj["box"])

def content_box(settings):
    if "division" in settings:
        from .structure import boundaries
        return boundaries(settings,settings.get("_page_index",0))[0]
    if settings.get("content_box") is not None:
        return list(settings["content_box"])
    width,height=paper(settings)
    left,top,right,bottom=settings["margins"]
    end=min(height-bottom,footer_box(settings)[1]-10)
    return [left,top,(width-left-right)*settings["slide_area"],max(1,end-top)]

def title_object(state,index):
    for pg in reversed(state["pages"][:index+1]):
        if pg.get("title") is not None:
            return deepcopy(pg["title"])
    if state["settings"].get("title") is not None:
        return deepcopy(state["settings"]["title"])
    return deepcopy(next((o for o in state["settings"]["objects"] if o["kind"]=="title"),None))

def page_objects(state,index):
    settings=state["settings"]
    from .structure import section_start
    start=section_start(state["pages"],index)
    section=state["pages"][start]
    objects=[o for o in settings["objects"] if o["kind"]!="title"]+section.get("section_objects",[])+state["pages"][index]["objects"]
    from .structure import section_band
    for kind in ("header","footer"):
        band=section_band(state["pages"],index,kind)
        if band:objects.append(band)
    title=title_object(state,index)
    return objects+([title] if title else [])
