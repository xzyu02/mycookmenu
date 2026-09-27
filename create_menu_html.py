import base64
import html
import io
import os
import re
import sys
import urllib.parse
from string import Template

import pandas as pd

# --- 配置 ---
CSV_FILE = 'menu.csv'  # 你的CSV文件名
HTML_OUTPUT_FILE = 'mymenu.html'
TITLE = "Xizheng's Bistro"
FONT_FILE = 'assets/OzCarame.ttf'  # 和PDF同一个字体；只截取网页用到的字内嵌，文件很小
WEB_FONT = 'ZCOOL KuaiLe'  # 找不到字体文件或字体缺字时使用的Google网络字体
SHOW_RECIPES = True  # 点击菜名展开做法和视频链接；设为False则和PDF一样只显示菜名
IMAGE_WIDTH = 360  # 猫咪图片压缩后的最大宽度（像素），保持网页轻量

# 分类标题的背景色，和PDF一致
COLORS = [(255, 228, 225), (224, 255, 255), (240, 255, 240), (255, 250, 205), (230, 230, 250), (255, 240, 245)]

# 从Video列（小红书分享文字、B站链接等）中提取链接
URL_RE = re.compile(r'https?://[\w\-./?=&%#~+:@]+|(?:[a-z0-9-]+\.)+[a-z]{2,}/[\w\-./?=&%#~+:@]*',
                    re.ASCII | re.IGNORECASE)
LINK_LABELS = {'xhslink.com': '小红书', 'xiaohongshu.com': '小红书', 'b23.tv': 'B站', 'bilibili.com': 'B站'}


def load_menu():
    """读取CSV，返回 {分类: [菜品]}，分类按在CSV中第一次出现的顺序排列"""
    try:
        df = pd.read_csv(CSV_FILE, encoding='utf-8', dtype=str, keep_default_na=False)
    except FileNotFoundError:
        print(f"错误: 找不到文件 '{CSV_FILE}'。请确保文件名正确且文件在同一目录下。")
        sys.exit(1)

    menu = {}
    for _, row in df.iterrows():
        name = row['Name'].strip()
        if not name:
            continue  # 跳过空行
        # 和PDF一样：去掉"还没做"，用剩下的第一个类型作为分类；"还没做"改为在菜名旁标注
        types = [t.strip() for t in row['Type'].split(',') if t.strip()]
        category = next((t for t in types if '还没做' not in t), '其他')
        menu.setdefault(category, []).append({
            'name': name,
            'todo': any('还没做' in t for t in types),
            'recipe': row['做法'].strip(),
            'video': row['Video'].strip(),
        })
    return menu


def find_links(text):
    """返回 [(标签, 链接)]"""
    links = []
    for url in URL_RE.findall(text):
        url = url.rstrip('.')
        if not url.lower().startswith(('http://', 'https://')):
            url = 'https://' + url
        label = next((v for k, v in LINK_LABELS.items() if k in url.lower()), '视频')
        links.append((label, url))
    return links


def image_tag(path, css_class):
    """压缩后以base64内嵌图片，网页单文件即可分享；找不到图片时省略"""
    if not os.path.exists(path):
        print(f"警告: 找不到图片 '{path}'，网页中将省略它。")
        return ''
    from PIL import Image  # fpdf2 已依赖 Pillow

    with Image.open(path) as img:
        # 保留RGB颜色配置（如iPhone/Mac导出的Display P3），否则颜色会变淡；PDF也保留了它
        icc = img.info.get('icc_profile') if img.mode in ('RGB', 'RGBA', 'P') else None
        img = img.convert('RGBA')
        img.thumbnail((IMAGE_WIDTH, IMAGE_WIDTH * 10))
        buf = io.BytesIO()
        img.save(buf, 'WEBP', quality=85, icc_profile=icc)
    data = base64.b64encode(buf.getvalue()).decode()
    return f'<img class="{css_class}" src="data:image/webp;base64,{data}" alt="">'


def font_face(text):
    """把字体截取为只含 text 中的字符，以WOFF内嵌；找不到字体文件时返回空字符串"""
    if not os.path.exists(FONT_FILE):
        print(f"提示: 找不到字体文件 '{FONT_FILE}'，将使用网络字体 {WEB_FONT}。")
        return ''
    from fontTools import subset  # fpdf2 已依赖 fontTools

    options = subset.Options()
    options.flavor = 'woff'
    options.hinting = False  # 网页显示不需要hinting，去掉后体积小一半以上
    font = subset.load_font(FONT_FILE, options)
    subsetter = subset.Subsetter(options)
    subsetter.populate(text=text)
    subsetter.subset(font)
    buf = io.BytesIO()
    subset.save_font(font, buf, options)
    data = base64.b64encode(buf.getvalue()).decode()
    return f"@font-face {{ font-family: 'MenuFont'; src: url(data:font/woff;base64,{data}) format('woff'); }}"


def render_dish(dish):
    name = html.escape(dish['name'])
    if dish['todo']:
        name += ' <span class="todo">还没做</span>'

    body = []
    if SHOW_RECIPES:
        if dish['recipe']:
            body.append(f'<p>{html.escape(dish["recipe"])}</p>')
        links = find_links(dish['video'])
        if links:
            body.append('<p class="links">' + ''.join(
                f'<a href="{html.escape(url)}" target="_blank" rel="noopener">{label} ↗</a>'
                for label, url in links) + '</p>')
        elif dish['video']:
            body.append(f'<p>{html.escape(dish["video"])}</p>')

    if not body:
        return f'<div class="dish">{name}</div>'
    return f'<details class="dish"><summary>{name}</summary><div class="recipe">{"".join(body)}</div></details>'


PAGE = Template("""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<!-- 网络字体异步加载，网络不通时页面也不会卡住 -->
<link rel="stylesheet" href="$web_font_url" media="print" onload="this.media='all'">
<noscript><link rel="stylesheet" href="$web_font_url"></noscript>
<style>
$font_face
:root {
  color-scheme: light;
  --menu-font: 'MenuFont', '$web_font', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  --text-font: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', sans-serif;
  --grid: rgb(200, 200, 200);
}
* { box-sizing: border-box; }
body {
  margin: 0;
  color: #000;
  font-family: var(--menu-font);
  /* 和PDF一样的米色网格纸背景，格子5mm */
  background-color: rgb(250, 253, 243);
  background-image: linear-gradient(var(--grid) 1px, transparent 1px),
                    linear-gradient(90deg, var(--grid) 1px, transparent 1px);
  background-size: 5mm 5mm;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
}
.page { max-width: 210mm; margin: 0 auto; padding: 5mm 10mm 10mm; }
header { display: grid; grid-template-columns: 1fr auto 1fr; align-items: center; gap: 4mm; }
header h1 { margin: 0; font-size: 20pt; font-weight: normal; text-align: center; }
header img, footer img { display: block; height: auto; }
.cat-left { width: min(35mm, 24vw); }
.cat-right { width: min(45mm, 30vw); margin-left: auto; }
.cat-footer { width: min(35mm, 24vw); margin-left: auto; }
nav { display: flex; flex-wrap: wrap; gap: 2mm; margin: 6mm 0; }
nav a { padding: 1mm 3mm; border-radius: 3mm; color: inherit; text-decoration: none; font-size: 12pt; }
section { margin-bottom: 5mm; scroll-margin-top: 4mm; }
h2 { margin: 0 0 4mm; padding: 0 1mm; font-size: 24pt; font-weight: normal; line-height: 12mm; }
.dishes { display: grid; grid-template-columns: 1fr 1fr; column-gap: 4mm; font-size: 16pt; }
div.dish, summary { position: relative; padding: 1.5mm 0 1.5mm 8mm; line-height: 1.35; }
div.dish::before, summary::before { position: absolute; left: 2.5mm; content: '-'; }
summary { cursor: pointer; list-style: none; }
summary::-webkit-details-marker { display: none; }
summary::before { content: '▸'; color: #b07a4f; }
details[open] { grid-column: 1 / -1; }
details[open] > summary::before { content: '▾'; }
.todo {
  padding: 0 .5em; border: 1px dashed currentColor; border-radius: 1em;
  color: #8a6d3b; font-family: var(--text-font); font-size: 9pt; vertical-align: middle; white-space: nowrap;
}
.recipe {
  margin: 0 0 3mm 8mm; padding: 3mm 4mm;
  background: rgba(255, 255, 255, .92); border: 1px solid var(--grid); border-radius: 2mm;
  font-family: var(--text-font); font-size: 11pt; line-height: 1.7;
}
.recipe p { margin: 0 0 2mm; white-space: pre-line; overflow-wrap: anywhere; }
.recipe p:last-child { margin-bottom: 0; }
.links a {
  display: inline-block; margin-right: 2mm; padding: 0 3mm; border-radius: 3mm;
  background: rgb(255, 228, 225); color: inherit; text-decoration: none;
}
@media (max-width: 480px) {
  .page { padding: 4mm 16px 8mm; }
  header { gap: 2mm; }
  .cat-left, .cat-right { width: 22vw; }
  header h1 { font-size: 18pt; }
  h2 { font-size: 18pt; line-height: 10mm; }
  .dishes { column-gap: 2mm; font-size: 13pt; }
  div.dish, summary { padding-left: 6mm; }
  div.dish::before, summary::before { left: 1.5mm; }
  .recipe { margin-left: 0; }
}
@media print { nav { display: none; } h2 { break-after: avoid; } }
</style>
</head>
<body>
<div class="page">
<header>
<div>$left_cat</div>
<h1>$title</h1>
<div>$right_cat</div>
</header>
<nav>
$nav
</nav>
<main>
$sections
</main>
<footer>$footer_cat</footer>
</div>
</body>
</html>
""")


def main():
    menu = load_menu()

    nav, sections = [], []
    for i, (category, dishes) in enumerate(menu.items()):
        r, g, b = COLORS[i % len(COLORS)]
        color = f'rgb({r}, {g}, {b})'
        name = html.escape(category)
        nav.append(f'<a href="#c{i}" style="background: {color}">{name}</a>')
        items = '\n'.join(render_dish(d) for d in dishes)
        sections.append(f'<section id="c{i}">\n<h2 style="background: {color}">--- {name} ---</h2>\n'
                        f'<div class="dishes">\n{items}\n</div>\n</section>')

    # 用手写字体显示的文字：标题、分类、菜名
    menu_text = TITLE + '-▸▾' + ''.join(menu) + ''.join(d['name'] for ds in menu.values() for d in ds)
    # 网络字体也只请求用到的字（text参数），几十KB而不是整套字体
    web_font_url = ('https://fonts.googleapis.com/css2?family=' + WEB_FONT.replace(' ', '+')
                    + '&text=' + urllib.parse.quote(''.join(sorted(set(menu_text)))) + '&display=swap')
    page = PAGE.substitute(
        title=html.escape(TITLE),
        font_face=font_face(menu_text),
        web_font=WEB_FONT,
        web_font_url=html.escape(web_font_url),
        left_cat=image_tag('assets/pipi3.png', 'cat-left'),
        right_cat=image_tag('assets/pipi4.png', 'cat-right'),
        footer_cat=image_tag('assets/pipi2.png', 'cat-footer'),
        nav='\n'.join(nav),
        sections='\n'.join(sections),
    )
    with open(HTML_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f"菜谱网页 '{HTML_OUTPUT_FILE}' 已成功生成！（{os.path.getsize(HTML_OUTPUT_FILE) / 1024:.0f} KB）")


if __name__ == '__main__':
    main()
