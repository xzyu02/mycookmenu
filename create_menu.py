import pandas as pd
from fpdf import FPDF
import sys # 引入 sys 模块用于退出
import re # 引入正则表达式模块用于处理emoji

# --- 配置 ---
CSV_FILE = 'menu.csv'  # 你的CSV文件名
PDF_OUTPUT_FILE = 'mymenu.pdf'
TITLE = "Xizheng's Bistro"

# --- PDF生成 ---
class PDF(FPDF):
    def header(self):
        # 绘制网格背景
        self.draw_grid()
        
        # 添加猫咪图片到左上角，保持原始尺寸
        try:
            self.image('assets/pipi3.png', 10, 5, w=35)  # top left
            self.image('assets/pipi4.png', self.w - 50, 5, w=45)  # top right
        except Exception as e:
            print(f"警告: 无法加载图片 'pipi3.png': {e}")
        
        # 需要在添加字体后才能设置
        if self.font_family:
            self.set_font(self.font_family, '', 20)
            self.cell(0, 10, TITLE, 0, 1, 'C')
            self.ln(10)

    def draw_grid(self):

        self.set_fill_color(250, 253, 243)
        self.rect(0, 0, self.w, self.h, 'F')  # 填充整个页面
        
        # 设置网格线颜色（浅灰色）
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.1)
        
        # 网格间距（毫米）
        grid_size = 5
        
        # 绘制垂直线
        x = 0
        while x <= self.w:
            self.line(x, 0, x, self.h)
            x += grid_size
        
        # 绘制水平线
        y = 0
        while y <= self.h:
            self.line(0, y, self.w, y)
            y += grid_size
        
        # 重置线条颜色为黑色
        self.set_draw_color(0, 0, 0)
        self.set_line_width(0.2)

    def footer(self):
        # 添加pipi2图片到右下角
        try:
            # 计算右下角位置 (页面宽度 - 图片宽度 - 右边距, 页面底部 - 图片高度 - 底边距)
            self.image('assets/pipi2.png', self.w - 45, self.h - 45, w=35)  # bottom right
        except Exception as e:
            print(f"警告: 无法加载图片 'pipi2.png': {e}")
        
        # 设置页脚
        self.set_y(-15)
        if self.font_family:
            self.set_font(self.font_family, '', 8)
            self.cell(0, 10, f'第 {self.page_no()} 页', 0, 0, 'C')

# 读取CSV数据
try:
    # 关键改动：使用 read_csv 并指定 utf-8 编码
    df = pd.read_csv(CSV_FILE, encoding='utf-8')
    expanded_rows = []
    for index, row in df.iterrows():
        
                    
        types = [t.strip() for t in str(row['Type']).split(',')]  # 按逗号分割并去除空格
        if len(types) == 1:
            continue
        
        # 过滤掉包含"还没做"的类型
        types = [t for t in types if '还没做' not in t]
        row['Type'] = types[0]  # 更新类型列
    
except FileNotFoundError:
    print(f"错误: 找不到文件 '{CSV_FILE}'。请确保文件名正确且文件在同一目录下。")
    sys.exit() # 找不到文件则退出程序
except Exception as e:
    print(f"读取CSV文件时发生错误: {e}")
    sys.exit()

# 按“Type”列进行分组 (你的分类列)
# 关键改动：使用 'Type' 作为分类的列名
grouped = df.groupby('Type')

# 创建PDF对象
pdf = PDF()

# 添加支持中文的字体
# 确保你有一个中文字体文件（.ttf），比如思源黑体、微软雅黑等
# 这里假设你有一个名为 'msyh.ttf' 的字体文件在脚本同目录下
try:
    pdf.add_font('chinese', '', 'assets/OzCarame.ttf')
except RuntimeError:
    print("错误: 找不到字体文件 'msyh.ttf'。")
    print("请从网上搜索 '思源黑体 ttf' 或 '微软雅黑 ttf' 下载，并将其放在和脚本相同的文件夹中。")
    sys.exit()

# 设置默认字体，这样页眉页脚才能正常显示
pdf.set_font('chinese', '', 12)
pdf.set_auto_page_break(auto=True, margin=15)

# 定义一些颜色，用于不同分类的标题背景
colors = [(255, 228, 225), (224, 255, 255), (240, 255, 240), (255, 250, 205), (230, 230, 250), (255, 240, 245)]
color_index = 0

# 添加首页
pdf.add_page()

# 遍历每个分类
for category_name, group in grouped:
    # --- 打印分类标题 ---
    pdf.set_font('chinese', '', 24)
    # 设置标题背景色
    current_color = colors[color_index % len(colors)]
    pdf.set_fill_color(current_color[0], current_color[1], current_color[2])
    pdf.cell(0, 12, f'--- {category_name} ---', 0, 1, 'L', fill=True)
    pdf.ln(4)
    color_index += 1
    
    # --- 打印该分类下的所有菜名 ---
    pdf.set_font('chinese', '', 16)
    
    # 将菜名列表转换为列表
    dishes = [row['Name'] for index, row in group.iterrows()]
    
    # 两列布局
    column_width = 95  # 每列的宽度
    for i in range(0, len(dishes), 2):
        # 左列
        left_dish = f'  - {dishes[i]}'
        pdf.cell(column_width, 10, left_dish, 0, 0, 'L')
        
        # 右列（如果存在）
        if i + 1 < len(dishes):
            right_dish = f'  - {dishes[i + 1]}'
            pdf.cell(column_width, 10, right_dish, 0, 1, 'L')
        else:
            pdf.ln()  # 如果没有右列内容，换行
    
    # 添加分类之间的间距
    pdf.ln(5)

# 保存PDF文件
try:
    pdf.output(PDF_OUTPUT_FILE)
    print(f"菜谱 '{PDF_OUTPUT_FILE}' 已成功生成！")
except Exception as e:
    print(f"生成PDF时发生错误: {e}")