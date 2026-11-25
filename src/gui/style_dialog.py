from copy import deepcopy
import re
import html
from uuid import uuid4
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QDialog,QFormLayout,QHBoxLayout,
    QLabel,QFrame,QListWidget,QStackedWidget,QWidget,QVBoxLayout,QLineEdit,QSpinBox,QCheckBox,QComboBox,QPushButton)
from .widgets import Dialog, FontPicker, emphasis_buttons, prompt, message
from src.core.textstyles import FORMATS,DEFAULT_FONTS,text_styles,number_formats

def format_combo(options,value):
    control=QComboBox()
    for key,label in options.items():control.addItem(label,key)
    control.setCurrentIndex(max(0,control.findData(value)))
    return control

def settings_divider():
    divider=QFrame()
    divider.setObjectName("settingsDivider")
    divider.setFixedWidth(1)
    return divider


class RecordList(QWidget):
    def __init__(self,dialog,records,defaults,fields,token_names=False,fonts=None):
        super().__init__()
        self.setObjectName("settingsPage")
        self.records=records
        row=QHBoxLayout(self)
        left=QVBoxLayout();row.addLayout(left)
        self.list=QListWidget();self.list.setObjectName("presetList");self.list.setFixedWidth(135);left.addWidget(self.list)
        actions=QHBoxLayout();left.addLayout(actions)
        for label,callback in (("新增",self.add),("删除",self.delete)):
            button=QPushButton(label);button.clicked.connect(callback);actions.addWidget(button)
        row.addWidget(settings_divider())
        panel=QFrame();panel.setObjectName("settingsContent")
        self.form=QFormLayout(panel);self.form.setContentsMargins(12,10,12,10)
        row.addWidget(panel,1)
        self.fonts=fonts
        self.preview=None
        self.defaults=defaults;self.fields=fields;self.dialog=dialog;self.token_names=token_names
        self.list.currentRowChanged.connect(self.select)
        self.refresh()

    def refresh(self,key=None):
        self.list.clear()
        for value in self.records.values():self.list.addItem(value["name"])
        if self.records:self.list.setCurrentRow(list(self.records).index(key) if key in self.records else 0)

    def select(self,index):
        self.preview=None
        while self.form.rowCount():self.form.removeRow(0)
        if index<0:return
        key=list(self.records)[index]
        record=self.records[key]
        if self.fonts is not None:
            for field,label in (("font","默认中文字体"),("latin_font","默认英文字体")):
                font=FontPicker(self.fonts[field])
                font.currentIndexChanged.connect(lambda _,f=field,w=font:self.set_default_font(f,w.currentData()))
                self.form.addRow(label,font)
        name=QLineEdit(record["name"])
        def rename():
            proposed=name.text().strip()
            if not proposed or (self.token_names and any(c in proposed for c in "<>*")) or any(k!=key and v["name"]==proposed for k,v in self.records.items()):
                name.setText(record["name"])
                return
            record["name"]=proposed
            self.list.item(index).setText(proposed)
        name.editingFinished.connect(rename)
        self.form.addRow("名称",name)
        for field,label,options in self.fields:
            value=record.get(field,self.defaults.get(field))
            if field in ("font","latin_font"):
                control=FontPicker(value or self.fonts[field])
                control.insertItem(0,"跟随默认字体",None)
                if not value:control.setCurrentIndex(0)
                control.currentIndexChanged.connect(lambda _,f=field,w=control:self.set_value(record,f,w.currentData()))
            elif isinstance(options,dict):
                control=format_combo(options,value)
                control.currentIndexChanged.connect(lambda _,f=field,w=control:record.update({f:w.currentData()}))
            elif isinstance(options,tuple):
                control=QSpinBox();control.setRange(*options);control.setValue(int(value));control.setKeyboardTracking(False)
                control.valueChanged.connect(lambda v,f=field:self.set_value(record,f,v))
            elif isinstance(value,bool):
                control=QCheckBox();control.setChecked(value)
                control.toggled.connect(lambda v,f=field:record.update({f:v}))
            else:
                control=QLineEdit(value or "")
                control.textChanged.connect(lambda v,f=field:record.update({f:v}))
            self.form.addRow(label,control)

        if self.fonts is not None:
            self.form.addRow("字形",emphasis_buttons(self,record,lambda field,value:self.set_value(record,field,value)))
            self.preview=QLabel()
            self.preview.setObjectName("stylePreview");self.preview.setWordWrap(True)
            self.form.addRow("预览",self.preview)
            self.update_preview()

    def set_value(self,record,field,value):
        if value is None:record.pop(field,None)
        else:record[field]=value
        self.update_preview()

    def set_default_font(self,field,value):
        self.fonts[field]=value
        self.update_preview()

    def update_preview(self):
        if self.preview is None:return
        record=list(self.records.values())[self.list.currentRow()]
        fonts=self.fonts | record
        size=record.get("size",14)
        common=f"font-size:{size}pt"
        if record.get("bold"):common+=";font-weight:bold"
        if record.get("italic"):common+=";font-style:italic"
        if record.get("underline"):common+=";text-decoration:underline"
        chinese=html.escape(fonts["font"],quote=True)
        latin=html.escape(fonts["latin_font"],quote=True)
        self.preview.setText(f'<span style="{common};font-family:{chinese}">中文样式预览</span><br>'
                             f'<span style="{common};font-family:{latin}">The quick brown fox</span>')

    def add(self):
        name=prompt(self.dialog,"新增","名称")
        if not name or not name.strip():return
        name=name.strip()
        if self.token_names and any(c in name for c in "<>*"):
            message(self.dialog,"名称无效","编号组名称不能包含 <、> 或 *")
            return
        if any(value["name"]==name for value in self.records.values()):
            message(self.dialog,"名称重复","请使用不同的名称")
            return
        key=uuid4().hex
        self.records[key]=self.defaults | {"name":name}
        self.refresh(key)

    def delete(self):
        index=self.list.currentRow()
        if index>=0:
            del self.records[list(self.records)[index]]
            self.refresh()

def style_dialog(editor):
    settings=editor.settings
    styles=deepcopy(text_styles(settings));formats=deepcopy(number_formats(settings))
    fonts=DEFAULT_FONTS | settings.get("text_fonts",{})
    dialog=Dialog(editor,"样式设置");dialog.resize(650,430);dialog.setMinimumSize(630,380)
    content=QHBoxLayout()
    tabs=QListWidget();tabs.setObjectName("presetList");tabs.addItems(["文本","编号"]);tabs.setFixedWidth(96)
    stack=QStackedWidget();stack.setObjectName("settingsStack")
    records=RecordList(dialog,styles,{"level":0,"size":14,"bold":False,"italic":False,"underline":False},
                       [("level","目录级别（0 为正文）",(0,9)),("size","字号",(1,200)),
                        ("font","中文字体",None),("latin_font","英文字体",None)],fonts=fonts)
    stack.addWidget(records)
    stack.addWidget(RecordList(dialog,formats,{"style":"decimal","prefix":"","separator":".","spacing":1},
                               [("style","数字样式",FORMATS),("prefix","前缀",None),("separator","分隔符",None),
                                ("spacing","编号后空格",(0,20))]))
    tabs.currentRowChanged.connect(stack.setCurrentIndex);tabs.setCurrentRow(0)
    content.addWidget(tabs);content.addWidget(settings_divider());content.addWidget(stack,1);dialog.body.addLayout(content)
    dialog.add_buttons()
    if dialog.exec()==QDialog.DialogCode.Accepted:
        editor.change(lambda:settings.update(text_styles=styles,text_fonts=fonts,number_formats=formats,
                                            number_presets_initialized=True))

def numbering_dialog(editor):
    settings=editor.settings
    original=settings.get("number_groups",{})
    groups={key:{"name":key,**value} for key,value in deepcopy(original).items()}
    options=FORMATS | {key:fmt["name"] for key,fmt in number_formats(settings).items()}
    dialog=Dialog(editor,"编号器");dialog.setMinimumSize(535,340)
    dialog.body.addWidget(RecordList(dialog,groups,{"format":"word_decimal_dot","start":1,"step":1},
                          [("format","编号格式",options),("start","起始编号",(1,10000)),
                           ("step","编号步长",(1,10000))],token_names=True))
    dialog.add_buttons()
    if dialog.exec()==QDialog.DialogCode.Accepted:
        def apply():
            renamed={key:record["name"] for key,record in groups.items() if key in original and key!=record["name"]}
            if renamed:
                objects=list(settings["objects"])
                for page in editor.pages:
                    objects.extend(page["objects"]+page.get("section_objects",[]))
                    objects.extend(page[key] for key in ("header","footer","title") if page.get(key))
                for obj in objects:
                    if "text" in obj:
                        obj["text"]=re.sub(r"<([^<>*]+)(\*)?>",
                            lambda m:"<"+renamed.get(m[1],m[1])+(m[2] or "")+">",obj["text"])
            settings["number_groups"]={v["name"]:{k:x for k,x in v.items() if k!="name"} for v in groups.values()}
        editor.change(apply)
