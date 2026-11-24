from copy import deepcopy
from PyQt6.QtCore import Qt,QTimer
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QFormLayout,QLabel,QComboBox,QDoubleSpinBox,
    QSpinBox,QCheckBox,QLineEdit,QPlainTextEdit,QHBoxLayout,QPushButton,QFontComboBox,QSizePolicy)
from .widgets import ColorButton,WheelGuard
from src.core.model import content_box,footer_box,object_box,boxes,title_object

LABELS={"paper":"纸型","landscape":"横向","count":"每页张数","direction":"排列","align":"水平对齐",
        "gap":"幻灯片间距","slide_area":"原稿宽度比例","text":"内容","font":"字体","size":"字号",
        "angle":"旋转角度","enabled":"显示","background":"背景色","border":"边框色","color":"文字颜色",
        "style":"批注样式","spacing":"线间距","bold":"加粗","italic":"斜体","underline":"下划线",
        "start":"页码起始值","chapter":"一级编号","separator":"编号分隔符","substart":"二级起始值",
        "sub":"本页二级编号","n":"本页普通编号","label":"本页页码格式","hidden":"隐藏页码","valign":"垂直对齐"}
CHOICES={"paper":[("A4","A4"),("A3","A3"),("Letter","Letter"),("Custom","自定义")],
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
    def build(self):
        while self.outer.count():
            item=self.outer.takeAt(0)
            if item.widget():item.widget().deleteLater()
        self.text_field=None;self.inherit=None
        e=self.editor
        self.setProperty("inherit",e.sel==("title",0) and e.pg.get("title") is None)
        self.style().unpolish(self);self.style().polish(self)
        fields=deepcopy(e.obj())
        if fields.get("kind"):fields.setdefault("enabled",True)
        if not e.sel or e.sel[0]=="settings":
            fields["content_box"]=content_box(e.settings)
            names=["paper","landscape","custom","margins","content_box","gap","count","direction","align","background"]
            groups=[("纸张",names[:4]),("Slides 内容区域",names[4:9]),("页面背景",["background"])]
        else:
            if e.sel[0]=="title":
                self.inherit=QCheckBox("与上一页保持一致")
                self.inherit.setChecked(e.pg.get("title") is None)
                self.inherit.toggled.connect(e.set_title_inheritance)
                self.outer.addWidget(self.inherit)
            if e.sel[0]=="slides":
                fields["box"]=boxes(e.settings,e.pg,e.source)[e.sel[1]]
            elif e.sel[0]=="number":fields["box"]=footer_box(e.settings)
            elif fields.get("kind")=="notes":fields["box"]=object_box(e.settings,fields)
            if e.sel[0]=="numbering":
                fields={"hidden":False,"chapter":None,"sub":None,"n":None,"label":"",**fields}
            if fields.get("kind") in ("text","title"):fields.setdefault("valign","top")
            groups=[("内容",["enabled","text","hidden","chapter","sub","n","label"]),
                    ("位置与尺寸",["box","angle"]),("文字格式",["font","size","bold","italic","underline","align","valign","color"]),
                    ("外观",["background","border","style","spacing"])]
            if e.sel[0]=="number":
                fields.update({k:e.settings[k] for k in ("start","chapter","substart","separator")})
                groups.insert(0,("编号",["start","chapter","substart","separator"]))
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
                form.addRow(label,control)
            if "content_box" in present:
                reset=QPushButton("恢复自动区域")
                reset.clicked.connect(lambda:e.edit_property("content_box",None,rebuild=True));form.addRow("",reset)
                hint=QLabel("单位为点（72 点 = 1 英寸）。间距控制自动布局，手动定位可用“恢复本页自动布局”。")
                hint.setWordWrap(True);hint.setStyleSheet("color:#819087;font-size:11px;")
                form.addRow(hint)
        self.outer.addStretch()
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
                    spin.setValue(value[j]);spin.setKeyboardTracking(True);spin.setMinimumWidth(65)
                    spin.installEventFilter(self.guard);layout.addWidget(spin)
                    controls.append(spin)
                form.addRow(row)
            for spin in controls:
                spin.valueChanged.connect(lambda v:commit([c.value() for c in controls]))
            return container
        if key in CHOICES:
            combo=QComboBox()
            for data,label in CHOICES[key]:combo.addItem(label,data)
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
        if key=="font":
            combo=QFontComboBox();combo.setCurrentText(value);combo.installEventFilter(self.guard)
            combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
            combo.setMinimumContentsLength(7);combo.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Fixed)
            combo.currentFontChanged.connect(lambda font:commit(font.family()));return combo
        if key=="text":
            text=QPlainTextEdit(value);text.setFixedHeight(65)
            text.textChanged.connect(lambda:commit(text.toPlainText()))
            self.text_field=text;return text
        if isinstance(value,(int,float)) or key in ("n","sub","chapter"):
            integral=key in ("count","start","chapter","substart","n","sub")
            spin=QSpinBox() if integral else QDoubleSpinBox()
            spin.setRange(-10000,10000)
            if key in ("count","size","spacing"):spin.setMinimum(1)
            if key=="gap":spin.setMinimum(0)
            if not integral:spin.setDecimals(2)
            if value is None:
                spin.setSpecialValueText("自动");spin.setValue(spin.minimum())
            else:spin.setValue(value)
            spin.setKeyboardTracking(True);spin.installEventFilter(self.guard)
            spin.valueChanged.connect(lambda v:commit(None if key in ("n","sub","chapter") and v==-10000 else v))
            return spin
        field=QLineEdit(str(value));field.textEdited.connect(commit)
        return field
