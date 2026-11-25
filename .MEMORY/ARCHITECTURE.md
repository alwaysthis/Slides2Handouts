# 架构 · 0.6.0

main.py 建立 PyQt6 应用、加载主题与中文翻译，并记录 Python 与底层错误。gui/theme.py 使用 CrystalX 的控件和菜单样式规则，assets 保存对应步进和下拉箭头。GUI 直接由 Qt 绘制圆角，无窗口遮罩。

gui/editor.py 管理工程状态、选择、历史、原稿与页面树。gui/inspector.py 构建即时属性表单。gui/widgets.py 提供标题栏、对话框、颜色选择和滚轮转发。gui/canvas.py 处理选中、拖动、Shift 约束、缩放和异步预览请求。

预览由 rendering/preview_worker.py 独立进程完成，维护三页 PDF 缓存，输出当前视口图像。GUI 只保留最新待处理请求，旧请求结果不覆盖新页面。UTF-8 通信支持中文内容。窗口退出时回收预览进程。

PPTX 导入由 rendering/worker.py 与 PowerPoint PowerShell 导出脚本完成。Qt QProcess 在居中弹窗中显示进度；取消会结束本次导入进程树。源文件指纹检查成功后替换当前工程。

core/model.py 计算 content_box、自动原稿框、批注框和页脚。settings.content_box 为空时使用纸张与边距计算。pages[].title 为空或缺省时继承前页，第一段使用 settings.title 或旧 settings.objects 中的 title。独立标题保存完整文字对象。文字 valign 为 top、center、bottom，旧文件默认 top。

rendering/pdfout.py 共用于预览与最终输出，以 show_pdf_page 保留源页矢量，叠加批注、文字、继承标题与页码。configuration/store.py 提供版本化 JSON 和原稿 SHA-256，同目录临时文件替换保存。

## UI 组件约定

应用内弹窗使用 gui/widgets.py 的 Dialog。外框、标题栏与居中逻辑在该类维护，确认、取消和继续按钮通过 add_buttons 创建；需要校验的弹窗传入接受回调。Windows 文件选择继续使用 QFileDialog 原生入口。

gui/theme.py 维护全局样式和圆角表面绘制。主窗口、应用弹窗及下拉列表共用绘制函数，并各自指定颜色和半径。BIU 与字体选择控件供属性面板和样式设置复用。样式与编号器共用预设列表和设置面板结构。

## 工程内嵌原稿

导入时建立 PPTX 临时快照，转换与保存共用该快照。工程保存将原稿以 Base64 写入 source.embedded_pptx，SHA-256 用于校验。打开内嵌工程时解包至临时目录，载荷不进入编辑历史或预览进程请求。旧工程按原路径和指纹定位原稿。
