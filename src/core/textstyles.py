import re
from .model import page_objects
from .structure import format_number

FORMATS={"decimal":"阿拉伯数字","I":"大写罗马数字","i":"小写罗马数字","A":"大写字母","a":"小写字母"}
NUMBER_PRESETS={
    "word_decimal_dot":{"name":"1.  2.  3.","style":"decimal","separator":"."},
    "word_decimal_paren":{"name":"1)  2)  3)","style":"decimal","separator":")"},
    "word_roman_upper":{"name":"I.  II.  III.","style":"I","separator":"."},
    "word_roman_lower":{"name":"i.  ii.  iii.","style":"i","separator":"."},
    "word_letter_upper":{"name":"A.  B.  C.","style":"A","separator":"."},
    "word_letter_lower":{"name":"a.  b.  c.","style":"a","separator":"."},
    "word_letter_paren":{"name":"a)  b)  c)","style":"a","separator":")"},
}
NUMBER_PRESETS={key:{"prefix":"","spacing":1,**value} for key,value in NUMBER_PRESETS.items()}
PRESETS={
    "body":{"name":"正文","level":0,"size":14,"bold":False},
    "heading1":{"name":"一级标题","level":1,"size":22,"bold":True},
    "heading2":{"name":"二级标题","level":2,"size":18,"bold":True},
    "heading3":{"name":"三级标题","level":3,"size":16,"bold":True},
}
DEFAULT_FONTS={"font":"SimSun","latin_font":"Times New Roman"}

def text_styles(settings):
    return settings.get("text_styles",PRESETS)

def number_formats(settings):
    saved=settings.get("number_formats",{})
    return saved if settings.get("number_presets_initialized") else NUMBER_PRESETS | saved

def style_id(settings,obj):
    styles=text_styles(settings)
    if obj.get("text_style") in styles:return obj["text_style"]
    return next((key for key,style in styles.items() if style["level"]==obj.get("level",0)),next(iter(styles)))

def styled(settings,obj):
    key=obj.get("text_style")
    if not key:return obj
    preset=text_styles(settings).get(style_id(settings,obj),{})
    result=obj | DEFAULT_FONTS | settings.get("text_fonts",{}) | {k:v for k,v in preset.items() if k!="name"}
    return result | obj.get("text_overrides",{})

def numbered_pages(state,index):
    settings=state["settings"]
    groups=settings.get("number_groups",{})
    if not groups:return page_objects(state,index)
    formats=number_formats(settings)
    current={name:group["start"] for name,group in groups.items()}
    def replace(match):
        name,star=match.groups()
        if name not in groups:return match[0]
        group=groups[name]
        rule=formats.get(group["format"],{"style":group["format"]})
        label=format_number(current[name],rule.get("style","decimal"))
        if star:return label
        current[name]+=group["step"]
        spacing=rule.get("spacing",group.get("spacing",0))
        return rule.get("prefix","")+label+rule.get("separator","")+(" "*spacing)
    objects=[]
    for page in range(index+1):
        objects=[]
        for obj in page_objects(state,page):
            if "text" not in obj or not obj.get("enabled",True):
                objects.append(obj)
                continue
            objects.append(obj | {"text":re.sub(r"<([^<>*]+)(\*)?>",replace,obj["text"])})
    return objects
