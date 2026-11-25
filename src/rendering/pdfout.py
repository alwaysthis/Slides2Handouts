import html
import math
import os
import re
import pymupdf as pdf
from src.rendering.fonts import font_css
from src.core.textstyles import styled,numbered_pages
from src.core.model import paper, boxes, footer_box, object_box, page_objects

def color(value):
    return tuple(int(value[i:i+2],16)/255 for i in (1,3,5))
def rect(box):
    x,y,w,h=box
    return pdf.Rect(x,y,x+w,y+h)
def draw(page,o):
    r=rect(o["box"])
    if o.get("enabled") is False: return
    if o["kind"]!="notes" and not o.get("text"):return
    bg=o.get("background")
    border=o.get("border")
    if o["kind"]=="notes":
        page.draw_rect(r,color=color(border) if border else None,fill=color(bg) if bg else None)
        step=o["spacing"]
        if step<=0: raise ValueError("间距必须为正数")
        if o["style"] in ("lines","grid"):
            for i in range(1,math.ceil(r.height/step)):
                y=r.y0+i*step
                page.draw_line((r.x0,y),(r.x1,y),color=(.8,.8,.8),width=.4)
        if o["style"]=="grid":
            for i in range(1,math.ceil(r.width/step)):
                x=r.x0+i*step
                page.draw_line((x,r.y0),(x,r.y1),color=(.8,.8,.8),width=.4)
        return
    with pdf.open() as layer:
        lp=layer.new_page(width=r.width,height=r.height)
        if bg or border: lp.draw_rect(lp.rect,color=color(border) if border else None,fill=color(bg) if bg else None)
        faces=font_css(o["font"])
        family="Handout" if faces else o["font"]
        style=f"font-family:'{family}';font-size:{o['size']}pt;color:{o['color']};text-align:{o['align']}"
        content=html.escape(o["text"]).replace("\n","<br>")
        if o.get("latin_font"):
            latin=font_css(o["latin_font"],"HandoutLatin")
            if latin:
                faces+=latin
                content="".join(f'<span style="font-family:HandoutLatin">{html.escape(part)}</span>'
                                if part.isascii() and part!="\n" else html.escape(part).replace("\n","<br>")
                                for part in re.findall(r"[ -~]+|[^ -~]",o["text"]))
        style+=";white-space:pre-wrap"
        for key,tag in (("bold","b"),("italic","i"),("underline","u")):
            if o[key]: content=f"<{tag}>{content}</{tag}>"
        markup=f'<div style="{style}">{content}</div>'
        css=faces+"body{margin:0}"
        archive=pdf.Archive(os.path.join(os.environ["WINDIR"],"Fonts"))
        target=pdf.Rect(lp.rect)
        valign=o.get("valign","top")
        if valign!="top":
            story=pdf.Story(html=markup,user_css=css,archive=archive)
            _,filled=story.place(pdf.Rect(0,0,target.width,100000))
            remaining=max(0,target.height-pdf.Rect(filled).height)
            target.y0+=remaining/2 if valign=="center" else remaining
        lp.insert_htmlbox(target,markup,css=css,archive=archive)
        angle=o["angle"]
        c,s=abs(math.cos(math.radians(angle))),abs(math.sin(math.radians(angle)))
        w,h=r.width*c+r.height*s,r.width*s+r.height*c
        cx,cy=(r.x0+r.x1)/2,(r.y0+r.y1)/2
        page.show_pdf_page(pdf.Rect(cx-w/2,cy-h/2,cx+w/2,cy+h/2),layer,0,rotate=angle)

def render(doc,source,state,index):
    from src.core.structure import contents,DisplayNumber,section_start
    start=section_start(state["pages"],index)
    s=state["settings"] | state["pages"][start].get("layout",{}) | state["pages"][index].get("page_layout",{}) | {"_page_index":index}
    p=state["pages"][index]
    out=doc.new_page(width=paper(s)[0],height=paper(s)[1])
    out.draw_rect(out.rect,color=None,fill=color(s["background"]))
    objects=[styled(s,obj) for obj in numbered_pages(state,index)]
    for o in objects:
        if o["kind"]=="notes" and s.get("division")!="none": draw(out,dict(o,box=object_box(s,o)))
    for item,box in zip(p["slides"],boxes(s,p,source)):
        if item["source"] is None:continue
        out.show_pdf_page(rect(box),source,item["source"])
        if s.get("slide_border"):out.draw_rect(rect(box),color=(.35,.4,.37),width=.6)
    for o in objects:
        if o["kind"]!="notes": draw(out,dict(o,box=object_box(s,o),text=contents(state) if o.get("toc") else o["text"]))
    chapter,sub,n=s["chapter"],s["substart"],s["start"]
    for pg in state["pages"][:index+1]:
        if pg.get("section"):
            chapter+=1
            sub=s["substart"]
        rule=pg["numbering"]
        chapter=rule.get("chapter",chapter)
        sub=rule.get("sub",sub)
        n=rule.get("n",n)
        sub+=1
        n+=1
    if s.get("number_enabled",True) and not rule.get("hidden"):
        num=dict(s["number"],box=footer_box(s))
        num["text"]=rule.get("label",num["text"]).format(n=DisplayNumber(n-1,s.get("page_style","decimal")),chapter=DisplayNumber(chapter,s.get("section_style","decimal")),sub=DisplayNumber(sub-1,s.get("page_style","decimal")),sep=s["separator"])
        draw(out,num)
    return out

def footer_issue(settings,page,source,title=None):
    if page["numbering"].get("hidden") or settings["number"].get("enabled") is False:
        return ""
    area=rect(footer_box(settings))
    def bounds(area,angle):
        if not angle:return area
        turned=area*pdf.Matrix(angle)
        x,y=(area.x0+area.x1)/2,(area.y0+area.y1)/2
        return pdf.Rect(x-turned.width/2,y-turned.height/2,x+turned.width/2,y+turned.height/2)
    area=bounds(area,settings["number"]["angle"])
    if not pdf.Rect(0,0,*paper(settings)).contains(area):return "页码框超出纸张"
    for obj in [o for o in settings["objects"] if o["kind"]!="title"]+page["objects"]+([title] if title else []):
        if obj.get("enabled",True) and area.intersects(bounds(rect(object_box(settings,obj)),obj.get("angle",0))):
            return "页码框与批注区或文字框重叠"
    if any(area.intersects(rect(b)) for b in boxes(settings,page,source)):
        return "页码框与幻灯片重叠"
    return ""
