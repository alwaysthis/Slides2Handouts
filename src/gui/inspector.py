from copy import deepcopy
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QLabel,QComboBox,QDoubleSpinBox,
    QSpinBox,QCheckBox,QLineEdit,QPlainTextEdit,QHBoxLayout,QPushButton,QSizePolicy,QToolButton,QButtonGroup)
from PyQt6.QtCore import QSize
from src.core.textstyles import styled,text_styles,style_id
from .widgets import ColorButton,FontPicker,WheelGuard,line_icon,emphasis_buttons
from src.core.model import content_box,footer_box,object_box,boxes,title_object

LABELS={"paper":"纸型","landscape":"纸张方向","count":"每页张数","direction":"排列","align":"水平对齐",
        "gap":"幻灯片间距","slide_area":"原稿宽度比例","text":"内容","font":"字体","size":"字号",
        "angle":"旋转角度","enabled":"显示","background":"背景色","border":"边框色","color":"文字颜色",
        "style":"批注样式","spacing":"线间距","bold":"加粗","italic":"斜体","underline":"下划线",
        "start":"页码起始值","chapter":"一级编号","separator":"编号分隔符","substart":"二级起始值",
        "sub":"本页二级编号","n":"本页普通编号","label":"本页页码格式","hidden":"隐藏页码","valign":"垂直对齐"}
CHOICES={"landscape":[(False,"纵向"),(True,"横向")],"division":[("none","不划分"),("horizontal","左右划分"),("vertical","上下划分")],
         "odd_side":[("left","Slides 靠左"),("right","Slides 靠右")],
         "even_side":[("left","Slides 靠左"),("right","Slides 靠右")],
         **{key:[("decimal","阿拉伯数字"),("I","大写罗马数字"),("i","小写罗马数字"),("A","大写字母"),("a","小写字母")] for key in ("page_style","section_style")},"paper":[("A4","A4"),("A3","A3"),("Letter","Letter"),("Custom","自定义")],
         "direction":[("vertical","纵向"),("horizontal","横向"),("grid","网格")],
         "align":[("left","左对齐"),("center","居中"),("right","右对齐")],
         "valign":[("top","顶部"),("center","居中"),("bottom","底部")],
         "style":[("blank","空白"),("lines","横线"),("grid","方格")]}
class Inspector(QWidget):
    def __init__(self,editor):
        super().__init__()
        self.editor=editor;self.setObjectName("inspector")
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(6,2,6,8);self.outer.setSpacing(5)
        self.guard=WheelGuard(self)
        self.text_field=None
        self.inherit=None
    def build(self,preserve_scroll=True):
        scrollbar=self.editor.property_scroll.verticalScrollBar()
        position=scrollbar.value() if preserve_scroll else 0
        revision=getattr(self,"build_revision",0)+1
        self.build_revision=revision
        while self.outer.count():
            item=self.outer.takeAt(0)
            if item.widget():
                item.widget().hide()
                item.widget().deleteLater()
        self.text_field=None;self.inherit=None
        e=self.editor
        self.setProperty("inherit",e.sel==("title",0) and e.pg.get("title") is None)
        self.style().unpolish(self);self.style().polish(self)
        fields=deepcopy(styled(e.settings,e.obj()))
        if e.sel and e.sel[0] in ("header","footer"):
            from src.core.structure import section_start,band_owner
            fields["band_inherit"]=e.pages[section_start(e.pages,e.pi)].get(e.sel[0]+"_inherit",False)
            if e.sel[0]=="header":
                fields["header_alternate"]=band_owner(e.pages,e.pi,"header").get("header_alternate",False)
                self.editor.property_title.setText(("偶数页页眉" if e.pi%2 else "奇数页页眉") if fields["header_alternate"] else "页眉")
                LABELS["header_alternate"]="奇偶页不同"
        LABELS.update(slides_width_ratio="Slides 边界宽度比",slides_height_ratio="Slides 边界高度比",notes_width_ratio="批注边界宽度比",notes_height_ratio="批注边界高度比")
        LABELS.update(band_inherit="同上一节",slides_inset="Slides 区内边距",notes_inset="批注区内边距",slides_align="Slides 水平对齐",notes_align="批注水平对齐",slides_valign="Slides 垂直对齐",notes_valign="批注垂直对齐")
        LABELS.update(division="区域划分",notes_ratio="批注区比例",region_gap="区域间距",alternate="奇偶页不同",
                      odd_side="奇数页 Slides",even_side="偶数页 Slides",level="文本级别（0 为正文）",
                      columns="列数（0 为自动）",slide_border="幻灯片加框",page_style="页码样式",section_style="节编号样式",
                      header_space="页眉预留",footer_space="页脚预留")
        if fields.get("kind")=="text" and (not e.sel or e.sel[0]!="number"):
            fields["text_style"]=style_id(e.settings,fields)
            fields.setdefault("latin_font","Times New Roman")
        LABELS.update(text_style="文本级别",font="中文字体",latin_font="英文字体",emphasis="字形")
        if "bold" in fields:fields["emphasis"]=None
        if fields.get("kind"):fields.setdefault("enabled",True)
        if not e.sel or e.sel[0]=="settings":
            fields.update(e.effective_settings())
            fields["content_box"]=content_box(e.effective_settings())
            fields={**dict(division="horizontal",notes_ratio=.46,region_gap=12,alternate=False,odd_side="left",even_side="right",header_space=0,footer_space=0,slides_inset=0,notes_inset=0,slides_width_ratio=1.,slides_height_ratio=1.,notes_width_ratio=1.,notes_height_ratio=1.,slides_align="center",notes_align="right",slides_valign="center",notes_valign="center"),**fields}
            groups=[
                ("纸张",["paper","landscape","custom","margins"]),
                ("区域划分",["division","notes_ratio","region_gap","alternate","odd_side","even_side"]),
                ("Slides 内容区域",["content_box","count","direction","gap","align","slides_inset",
                                    "slides_align","slides_valign","slides_width_ratio","slides_height_ratio"]),
                ("批注区",["notes_inset","notes_align","notes_valign",
                           "notes_width_ratio","notes_height_ratio"]),
                ("页面背景",["background"]),
            ]
        else:
            if e.sel[0]=="title":
                self.inherit=QCheckBox("与上一页保持一致")
                self.inherit.setChecked(e.pg.get("title") is None)
                self.inherit.toggled.connect(e.set_title_inheritance)
                self.outer.addWidget(self.inherit)
            if e.sel[0]=="slides":
                fields["box"]=boxes(e.effective_settings(),e.pg,e.source)[e.sel[1]]
            elif e.sel[0]=="number":fields["box"]=footer_box(e.settings)
            elif fields.get("kind")=="notes":fields["box"]=object_box(e.effective_settings(),fields)
            if e.sel[0]=="numbering":
                fields={"hidden":False,"chapter":None,"sub":None,"n":None,"label":"",**fields}
            if fields.get("kind") in ("text","title"):fields.setdefault("valign","top")
            groups=[("内容",["band_inherit","header_alternate","enabled","text_style","text","hidden","chapter","sub","n","label"]),
                    ("位置与尺寸",["box","angle"]),("Slides 布局",["count","columns","direction","gap","slide_border"]),("文字格式",["font","latin_font","size","emphasis","align","valign","color"]),
                    ("外观",["background","border","style","spacing"])]
            if e.sel[0]=="number":
                fields.update({k:e.settings[k] for k in ("start","chapter","substart","separator")})
                fields.update(page_style=e.settings.get("page_style","decimal"),section_style=e.settings.get("section_style","decimal"))
                groups.insert(0,("编号",["start","chapter","substart","separator","page_style","section_style"]))
        if not fields.get("alternate"):
            fields.pop("even_side",None)
        if fields.get("division")=="none":
            for option in ("notes_ratio","notes_inset","notes_align","notes_valign",
                           "notes_width_ratio","notes_height_ratio"):
                fields.pop(option,None)
        shown=set()
        for title,keys in groups:
            present=[k for k in keys if k in fields and k not in shown]
            shown.update(present)
            if not present:continue
            section=QWidget();layout=QVBoxLayout(section);layout.setContentsMargins(0,0,0,0);layout.setSpacing(5)
            heading=QLabel(title);heading.setObjectName("section");layout.addWidget(heading)
            form=QFormLayout();form.setContentsMargins(0,0,0,0);form.setVerticalSpacing(5)
            form.setHorizontalSpacing(9);form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
            layout.addLayout(form);self.outer.addWidget(section)
            for key in present:
                value=fields[key]
                control=self.control(key,value)
                if key in ("box","margins","custom","content_box"):
                    label={"box":"位置 / 尺寸","margins":"页边距","custom":"自定义纸张","content_box":"区域位置 / 尺寸"}[key]
                else:label=LABELS.get(key,key)
                if key.endswith(("_width_ratio","_height_ratio")):
                    control.setToolTip("边界占对应区域宽度或高度的比例。1 表示占满，0.5 表示占一半。")
                form.addRow(label,control)
            if "content_box" in present:
                reset=QPushButton("恢复自动区域")
                reset.clicked.connect(lambda:e.edit_property("content_box",None,rebuild=True));form.addRow("",reset)
                hint=QLabel("单位为点（72 点 = 1 英寸）。间距控制自动布局，手动定位可用“恢复本页自动布局”。")
                hint.setWordWrap(True);hint.setStyleSheet("color:#819087;font-size:11px;")
                form.addRow(hint)
        self.outer.addStretch()
        def restore_scroll():
            if revision==self.build_revision:
                self.outer.activate()
                scrollbar.setValue(position)
        restore_scroll()
        # The scroll area updates its range after the rebuilt layout settles.
        QTimer.singleShot(0,restore_scroll)
    def control(self,key,value):
        e=self.editor
        def commit(v):e.edit_property(key,v)
        if isinstance(value,list):
            container=QWidget();form=QFormLayout(container);form.setContentsMargins(0,0,0,0);form.setVerticalSpacing(4)
            names={"margins":["左","上","右","下"],"box":["左","上","宽","高"],"content_box":["左","上","宽","高"],"custom":["宽","高"]}[key]
            controls=[]
            for i in range(0,len(value),2):
                row=QWidget();layout=QHBoxLayout(row);layout.setContentsMargins(0,0,0,0);layout.setSpacing(5)
                for j in range(i,min(i+2,len(value))):
                    layout.addWidget(QLabel(names[j]))
                    spin=QDoubleSpinBox();spin.setDecimals(2);spin.setRange(-10000,10000)
                    if key=="custom" or key in ("box","content_box") and j>=2:spin.setMinimum(1)
                    if key=="margins":spin.setMinimum(0)
                    spin.setValue(value[j]);spin.setKeyboardTracking(False);spin.setMinimumWidth(65)
                    spin.installEventFilter(self.guard);layout.addWidget(spin)
                    controls.append(spin)
                form.addRow(row)
            for spin in controls:
                spin.valueChanged.connect(lambda v:commit([c.value() for c in controls]))
            return container
        if key=="emphasis":
            return emphasis_buttons(self,styled(e.settings,e.obj()),e.edit_property)
        options=([(k,v["name"]) for k,v in text_styles(e.settings).items()] if key=="text_style" else CHOICES.get(key)) or CHOICES.get(key.split("_")[-1])
        alignment=key.split("_")[-1]
        if alignment in ("align","valign"):
            host=QWidget()
            row=QHBoxLayout(host);row.setContentsMargins(0,0,0,0);row.setSpacing(4)
            group=QButtonGroup(host)
            for data,label in options:
                symbol="middle" if alignment=="valign" and data=="center" else data
                button=QToolButton()
                button.setIcon(line_icon("align_"+symbol));button.setIconSize(QSize(18,18))
                button.setToolTip(label);button.setAccessibleName(label)
                button.setCheckable(True);button.setChecked(data==value)
                group.addButton(button);row.addWidget(button)
                button.clicked.connect(lambda checked,v=data:commit(v))
            row.addStretch()
            return host
        if options:
            combo=QComboBox()
            for data,label in options:combo.addItem(label,data)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(7);combo.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
            combo.setCurrentIndex(max(0,combo.findData(value)))
            combo.installEventFilter(self.guard)
            combo.currentIndexChanged.connect(lambda index:commit(combo.itemData(index)))
            return combo
        if key in ("color","background","border"):
            host=QWidget();row=QHBoxLayout(host);row.setContentsMargins(0,0,0,0)
            button=ColorButton(value)
            button.changed=commit;row.addWidget(button);row.addStretch()
            if key=="border" or key=="background" and "kind" in e.obj():
                clear=QPushButton("无");clear.setFixedWidth(32)
                clear.clicked.connect(lambda:(setattr(button,"value",""),button.refresh(),commit("")));row.addWidget(clear)
            return host
        if isinstance(value,bool):
            checkbox=QCheckBox();checkbox.setChecked(value);checkbox.toggled.connect(commit);return checkbox
        if key in ("font","latin_font"):
            combo=FontPicker(value);combo.installEventFilter(self.guard)
            combo.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
            combo.currentIndexChanged.connect(lambda _:commit(combo.currentData()))
            return combo
        if key=="text":
            text=QPlainTextEdit(value);text.setFixedHeight(65)
            text.textChanged.connect(lambda:commit(text.toPlainText()))
            self.text_field=text;return text
        if isinstance(value,(int,float)) or key in ("n","sub","chapter"):
            integral=key in ("count","start","chapter","substart","n","sub","level","columns")
            spin=QSpinBox() if integral else QDoubleSpinBox()
            spin.setRange(-10000,10000)
            if key in ("count","size","spacing"):spin.setMinimum(1)
            if key in ("gap","region_gap","header_space","footer_space","slides_inset","notes_inset","level"):spin.setMinimum(0)
            if key=="level":spin.setMaximum(9)
            if key=="columns":spin.setRange(0,99)
            if key=="notes_ratio":spin.setRange(.05,.95);spin.setSingleStep(.05)
            if key.endswith(("_width_ratio","_height_ratio")):spin.setRange(.05,1);spin.setSingleStep(.05)
            if not integral:spin.setDecimals(2)
            if value is None:
                spin.setSpecialValueText("自动");spin.setValue(spin.minimum())
            else:spin.setValue(value)
            spin.setKeyboardTracking(False);spin.installEventFilter(self.guard)
            spin.valueChanged.connect(lambda v:commit(None if key in ("n","sub","chapter") and v==-10000 else v))
            return spin
        field=QLineEdit(str(value));field.textEdited.connect(commit)
        return field
