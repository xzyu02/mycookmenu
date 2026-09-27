import base64
import html
import io
import json
import os
import re
import sys

import pandas as pd

# --- 配置 ---
CSV_FILE = 'menu.csv'  # 你的CSV文件名
HTML_OUTPUT_FILE = 'mymenu.html'
TITLE = "Xizheng's Bistro"
FONT_FILE = 'assets/OzCarame.ttf'  # 标题用的手写字体；只截取标题用到的字内嵌，文件很小
SHOW_RECIPES = True  # 菜品详情里显示做法；设为False则只显示菜名、视频和点单
IMAGE_WIDTH = 360  # 猫咪图片压缩后的最大宽度（像素），保持网页轻量

# 分类显示顺序（按分类名开头匹配），没列出的分类按CSV顺序排在最后
CATEGORY_ORDER = ['牛', '猪', '羊', '鸡', '鸭', '鱼', '海鲜', '蔬菜', '凉菜', '饭', '面', '米粉', '带馅',
                  '咸粥', '甜粥', '早餐', '甜品', '冰激凌', '饮品', '豆浆机', '酱汁']

# 从Video列（小红书分享文字、B站链接等）中提取链接
URL_RE = re.compile(r'https?://[\w\-./?=&%#~+:@]+|(?:[a-z0-9-]+\.)+[a-z]{2,}/[\w\-./?=&%#~+:@]*',
                    re.ASCII | re.IGNORECASE)
LINK_LABELS = {'xhslink.com': '小红书', 'xiaohongshu.com': '小红书', 'b23.tv': 'B站', 'bilibili.com': 'B站'}


def category_rank(category):
    return next((i for i, prefix in enumerate(CATEGORY_ORDER) if category.startswith(prefix)), len(CATEGORY_ORDER))


def load_menu():
    """读取CSV，返回 {分类: [菜品]}，分类按 CATEGORY_ORDER 排序"""
    try:
        df = pd.read_csv(CSV_FILE, encoding='utf-8', dtype=str, keep_default_na=False)
    except FileNotFoundError:
        print(f"错误: 找不到文件 '{CSV_FILE}'。请确保文件名正确且文件在同一目录下。")
        sys.exit(1)

    menu = {}
    for _, row in df.iterrows():
        name = ' '.join(row['Name'].split())  # 去掉菜名里的换行和多余空格
        if not name:
            continue  # 跳过空行
        # 和PDF一样：去掉"还没做"，用剩下的第一个类型作为分类；"还没做"改为在菜名旁标注
        types = [t.strip() for t in row['Type'].split(',') if t.strip()]
        category = next((t for t in types if '还没做' not in t), '其他')
        video = row['Video'].strip()
        links = find_links(video)
        menu.setdefault(category, []).append({
            'name': name,
            'cat': category,
            'todo': any('还没做' in t for t in types),
            'recipe': row['做法'].strip() if SHOW_RECIPES else '',
            'links': links,
            'videoText': '' if links else video,  # Video列里没有链接时，原样显示文字
        })
    return dict(sorted(menu.items(), key=lambda item: category_rank(item[0])))


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
        print(f"提示: 找不到字体文件 '{FONT_FILE}'，标题将使用系统字体。")
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
    return f"@font-face {{ font-family: 'BrandFont'; src: url(data:font/woff;base64,{data}) format('woff'); }}"


PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>{{title}}</title>
<style>
{{font_face}}
:root {
  color-scheme: light;
  --bg: #faf7f2; --surface: #ffffff; --surface-2: #f3eee6; --text: #1f1b16; --muted: #6f675e;
  --border: #ebe4da; --accent: #d9480f; --accent-text: #ffffff; --soft: #fff0e6;
  --shadow: 0 1px 2px rgba(31, 27, 22, .05), 0 6px 20px rgba(31, 27, 22, .06);
  --font: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', 'Noto Sans SC', system-ui, sans-serif;
}
@media (prefers-color-scheme: dark) {
  :root {
    color-scheme: dark;
    --bg: #15120f; --surface: #211d18; --surface-2: #2a251f; --text: #f2ede6; --muted: #a79e93;
    --border: #353029; --accent: #ff8a4c; --accent-text: #1a0f08; --soft: #33241a; --shadow: none;
  }
}
* { box-sizing: border-box; }
[hidden] { display: none !important; }
html { -webkit-text-size-adjust: 100%; }
body { margin: 0; background: var(--bg); color: var(--text); font: 15px/1.5 var(--font); padding-bottom: 96px; }
body:has(dialog[open]) { overflow: hidden; }
button, input, textarea { font: inherit; color: inherit; }
button { cursor: pointer; }
:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
.wrap { max-width: 1100px; margin: 0 auto; padding: 0 16px; }

.hero { background: linear-gradient(180deg, var(--soft), transparent); }
.hero-inner { display: flex; flex-wrap: wrap; align-items: center; gap: 12px 16px; padding-top: 20px; padding-bottom: 12px; }
.logo { display: block; height: 64px; width: auto; }
.brand { margin: 0; font-family: 'BrandFont', var(--font); font-size: 32px; font-weight: 600; line-height: 1.1; }
.tagline { margin: 4px 0 0; color: var(--muted); font-size: 14px; }
#random { margin-left: auto; }

.btn { border: 1px solid transparent; border-radius: 999px; padding: 8px 16px; font-weight: 600; white-space: nowrap; }
.btn-primary { background: var(--accent); color: var(--accent-text); }
.btn-soft { background: var(--soft); color: var(--accent); border-color: color-mix(in srgb, var(--accent) 25%, transparent); }
.btn-ghost { background: transparent; border-color: var(--border); }

.toolbar {
  position: sticky; top: 0; z-index: 5;
  background: color-mix(in srgb, var(--bg) 88%, transparent); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid var(--border);
}
.search-row { display: flex; gap: 8px; padding-top: 10px; }
#search {
  flex: 1; min-width: 0; height: 40px; padding: 0 14px; border: 1px solid var(--border); border-radius: 12px;
  background: var(--surface);
}
.toggle { height: 40px; padding: 0 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); white-space: nowrap; }
.toggle[aria-pressed="true"] { background: var(--soft); border-color: var(--accent); color: var(--accent); font-weight: 600; }
.chips { display: flex; gap: 8px; overflow-x: auto; padding: 10px 0; scrollbar-width: none; }
.chips::-webkit-scrollbar { display: none; }
.chip {
  flex: none; display: inline-flex; align-items: center; gap: 6px; padding: 6px 12px;
  border: 1px solid var(--border); border-radius: 999px; background: var(--surface); white-space: nowrap;
}
.chip-count { color: var(--muted); font-size: 12px; }
.chip[aria-pressed="true"] { background: var(--text); border-color: var(--text); color: var(--bg); }
.chip[aria-pressed="true"] .chip-count { color: inherit; opacity: .7; }

.cat { padding-top: 20px; scroll-margin-top: 120px; }
.cat-title { display: flex; align-items: baseline; gap: 8px; margin: 0 0 12px; font-size: 20px; }
.cat-count { color: var(--muted); font-size: 13px; font-weight: 400; }
.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
.card {
  display: flex; flex-direction: column; justify-content: space-between; gap: 12px; padding: 14px;
  background: var(--surface); border: 1px solid var(--border); border-radius: 16px; box-shadow: var(--shadow);
}
.card-main { display: block; padding: 0; border: 0; background: none; text-align: left; }
.dish-name { display: block; font-size: 16px; font-weight: 600; overflow-wrap: anywhere; }
.card-main:hover .dish-name { color: var(--accent); }
.tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 6px; }
.tag { padding: 1px 8px; border-radius: 999px; background: var(--surface-2); color: var(--muted); font-size: 12px; }
.tag-todo { background: var(--soft); color: var(--accent); }
.card-actions { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.links { display: flex; flex-wrap: wrap; gap: 6px; }
.link-chip {
  padding: 4px 10px; border-radius: 999px; background: var(--surface-2); color: var(--text);
  font-size: 13px; text-decoration: none; white-space: nowrap;
}
.link-chip:hover { background: var(--soft); color: var(--accent); }

.qty-slot { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.add-btn, .step {
  display: grid; place-items: center; width: 32px; height: 32px; padding: 0; border-radius: 50%;
  font-size: 20px; line-height: 1;
}
.add-btn { border: 0; background: var(--accent); color: var(--accent-text); }
.step { border: 1.5px solid var(--accent); background: transparent; color: var(--accent); }
.qty-n { min-width: 1.5em; text-align: center; font-weight: 700; }
.qty-slot.big .add-btn { width: auto; height: 44px; padding: 0 22px; border-radius: 999px; font-size: 16px; font-weight: 600; }
.qty-slot.big .step { width: 40px; height: 40px; }

.empty { padding: 48px 16px; color: var(--muted); text-align: center; }
.footer { padding-top: 40px; color: var(--muted); font-size: 13px; text-align: center; }
.footer-cat { display: block; height: 96px; width: auto; margin: 0 auto 8px; }

.cartbar {
  position: fixed; left: 50%; bottom: calc(16px + env(safe-area-inset-bottom)); z-index: 6; transform: translateX(-50%);
  width: min(560px, calc(100% - 32px));
}
.cartbar-btn {
  display: flex; align-items: center; gap: 12px; width: 100%; padding: 10px 12px 10px 16px; border: 0; border-radius: 999px;
  background: var(--text); color: var(--bg); box-shadow: 0 10px 30px rgba(0, 0, 0, .25); text-align: left;
}
.cart-icon { position: relative; font-size: 22px; }
#cart-badge {
  position: absolute; top: -6px; right: -10px; min-width: 20px; height: 20px; padding: 0 5px; border-radius: 999px;
  background: var(--accent); color: var(--accent-text); font-size: 12px; font-weight: 700; line-height: 20px; text-align: center;
}
#cart-summary { flex: 1; font-weight: 600; }
.cartbar-cta { padding: 8px 16px; border-radius: 999px; background: var(--accent); color: var(--accent-text); font-weight: 600; }

dialog.sheet {
  width: min(560px, calc(100% - 32px)); max-width: none; padding: 0; border: 0; border-radius: 20px;
  background: var(--surface); color: var(--text); box-shadow: 0 20px 60px rgba(0, 0, 0, .3);
}
dialog.sheet::backdrop { background: rgba(20, 16, 12, .45); }
.sheet-inner { display: flex; flex-direction: column; max-height: min(85vh, 760px); outline: none; }
.sheet-head { display: flex; align-items: flex-start; gap: 12px; padding: 18px 20px 12px; }
.sheet-head h2 { margin: 0; font-size: 20px; overflow-wrap: anywhere; }
.eyebrow { margin: 0 0 2px; color: var(--muted); font-size: 13px; }
.icon-btn {
  flex: none; width: 34px; height: 34px; margin-left: auto; border: 0; border-radius: 50%;
  background: var(--surface-2); color: var(--muted); font-size: 15px;
}
.sheet-body { flex: 1; overflow: auto; padding: 0 20px 16px; }
.sheet-foot { display: flex; align-items: center; gap: 8px; padding: 12px 20px calc(16px + env(safe-area-inset-bottom)); border-top: 1px solid var(--border); }
.dish-links { margin-bottom: 12px; }
.recipe { margin: 0; padding: 14px 16px; border-radius: 12px; background: var(--surface-2); white-space: pre-line; overflow-wrap: anywhere; line-height: 1.7; }
.recipe.muted { color: var(--muted); }
.cart-list { margin: 0; padding: 0; list-style: none; }
.cart-list li { display: flex; align-items: center; gap: 12px; padding: 10px 0; border-bottom: 1px solid var(--border); }
.cart-item-name { font-weight: 600; overflow-wrap: anywhere; }
.cart-item-cat { display: block; color: var(--muted); font-size: 12px; font-weight: 400; }
.cart-empty { padding: 16px 0 24px; color: var(--muted); text-align: center; }
.empty-cat { display: block; width: 180px; max-width: 60%; height: auto; margin: 0 auto 8px; }
.note-label { display: block; margin: 16px 0 6px; color: var(--muted); font-size: 13px; }
#cart-note { width: 100%; padding: 10px 12px; border: 1px solid var(--border); border-radius: 12px; background: var(--surface); resize: vertical; }
.cart-actions .btn-primary { margin-left: auto; }

.toast {
  position: fixed; left: 50%; bottom: calc(88px + env(safe-area-inset-bottom)); z-index: 20; transform: translate(-50%, 8px);
  max-width: calc(100% - 32px); padding: 8px 16px; border-radius: 999px; background: var(--text); color: var(--bg);
  font-size: 14px; opacity: 0; pointer-events: none; transition: opacity .2s, transform .2s;
}
.toast.show { opacity: 1; transform: translate(-50%, 0); }

@media (max-width: 600px) {
  .logo { height: 48px; }
  .brand { font-size: 26px; }
  #random { margin-left: 0; }
  .grid { grid-template-columns: 1fr; gap: 10px; }
  dialog.sheet { width: 100%; margin: auto 0 0; border-radius: 20px 20px 0 0; }
  .sheet-inner { max-height: 88vh; }
}
@media print { .toolbar, .cartbar, #random, .qty-slot { display: none !important; } body { padding-bottom: 0; } }
</style>
</head>
<body>
<header class="hero">
  <div class="wrap hero-inner">
    {{logo}}
    <div>
      <h1 class="brand">{{title}}</h1>
      <p class="tagline">{{dish_count}} 道家常菜 · 今天想吃点什么？</p>
    </div>
    <button id="random" class="btn btn-soft" type="button">🎲 今天吃什么</button>
  </div>
</header>

<div class="toolbar">
  <div class="wrap">
    <div class="search-row">
      <input id="search" type="search" placeholder="搜索菜名、食材…" autocomplete="off" aria-label="搜索菜名、食材">
      <button class="toggle" type="button" data-filter="video" aria-pressed="false">▶ 视频</button>
      <button class="toggle" type="button" data-filter="recipe" aria-pressed="false" {{recipe_toggle}}>📖 做法</button>
    </div>
    <nav id="chips" class="chips" aria-label="菜品分类"></nav>
  </div>
</div>

<main id="menu" class="wrap"></main>
<p id="empty" class="empty" hidden>没有找到符合条件的菜 🐾</p>
<footer class="wrap footer">{{footer_img}}<p>{{title}} · 用心做好每一顿饭</p></footer>

<div id="cartbar" class="cartbar" hidden>
  <button id="open-cart" class="cartbar-btn" type="button">
    <span class="cart-icon" aria-hidden="true">🛒<span id="cart-badge"></span></span>
    <span id="cart-summary"></span>
    <span class="cartbar-cta">查看点单</span>
  </button>
</div>

<dialog id="dish-dialog" class="sheet" aria-labelledby="dish-name">
  <div class="sheet-inner" tabindex="-1" autofocus>
    <div class="sheet-head">
      <div><p id="dish-cat" class="eyebrow"></p><h2 id="dish-name"></h2><div id="dish-tags" class="tags"></div></div>
      <button class="icon-btn" type="button" data-close aria-label="关闭">✕</button>
    </div>
    <div class="sheet-body">
      <div id="dish-links" class="links dish-links"></div>
      <p id="dish-recipe" class="recipe"></p>
    </div>
    <div class="sheet-foot">
      <button id="reroll" class="btn btn-ghost" type="button" hidden>🎲 换一个</button>
      <div id="dish-qty" class="qty-slot big"></div>
    </div>
  </div>
</dialog>

<dialog id="cart-dialog" class="sheet" aria-labelledby="cart-title">
  <div class="sheet-inner" tabindex="-1" autofocus>
    <div class="sheet-head">
      <h2 id="cart-title">我的点单</h2>
      <button class="icon-btn" type="button" data-close aria-label="关闭">✕</button>
    </div>
    <div class="sheet-body">
      <div id="cart-empty" class="cart-empty">{{empty_img}}<p>还没有点菜哦，去菜单里挑挑吧</p></div>
      <ul id="cart-list" class="cart-list"></ul>
      <label class="note-label" for="cart-note">备注</label>
      <textarea id="cart-note" rows="2" placeholder="比如：少辣、晚上7点吃"></textarea>
    </div>
    <div class="sheet-foot">
      <button id="clear-cart" class="btn btn-ghost" type="button">清空</button>
      <button id="share-cart" class="btn btn-soft" type="button" hidden>分享</button>
      <button id="copy-cart" class="btn btn-primary" type="button">复制点单</button>
    </div>
  </div>
</dialog>

<div id="toast" class="toast" role="status" aria-live="polite"></div>

<script type="application/json" id="menu-data">{{data}}</script>
<script>
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('menu-data').textContent);
  const dishes = data.dishes;
  const byName = new Map(dishes.map(d => [d.name, d]));
  const $ = id => document.getElementById(id);
  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text != null) e.textContent = text;
    return e;
  };

  // 点单保存在浏览器本地；隐私模式等无法保存时照常使用
  const store = {
    get(key, fallback) { try { const v = localStorage.getItem(key); return v ? JSON.parse(v) : fallback; } catch (e) { return fallback; } },
    set(key, value) { try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* 忽略 */ } },
  };
  const CART_KEY = 'bistro-cart', NOTE_KEY = 'bistro-note';
  const cart = store.get(CART_KEY, {});
  for (const name of Object.keys(cart)) {
    if (!byName.has(name) || !(cart[name] > 0)) delete cart[name];  // 菜单更新后去掉已删除的菜
  }
  const state = { cat: 'all', q: '', video: false, recipe: false };

  // --- 分类标签 ---
  const chips = $('chips'), menuEl = $('menu'), toolbar = document.querySelector('.toolbar');
  const addChip = (key, label, count) => {
    const b = el('button', 'chip');
    b.type = 'button';
    b.dataset.cat = key;
    b.append(el('span', null, label), el('span', 'chip-count', count));
    b.addEventListener('click', () => {
      state.cat = key;
      apply();
      b.scrollIntoView({ block: 'nearest', inline: 'nearest' });
      const top = menuEl.getBoundingClientRect().top + scrollY - toolbar.offsetHeight;
      if (scrollY > top) scrollTo({ top, behavior: 'smooth' });
    });
    chips.append(b);
  };
  addChip('all', '全部', dishes.length);
  data.categories.forEach(c => addChip(c.name, c.name, c.count));

  // --- 菜品卡片 ---
  const linkChip = ([label, url]) => {
    const a = el('a', 'link-chip', '▶ ' + label);
    a.href = url;
    a.target = '_blank';
    a.rel = 'noopener';
    return a;
  };
  const tagsFor = d => {
    const tags = [];
    if (d.todo) tags.push(el('span', 'tag tag-todo', '还没做'));
    if (d.recipe) tags.push(el('span', 'tag', '📖 有做法'));
    return tags;
  };
  const qtySlot = (name, cls) => {
    const slot = el('div', cls || 'qty-slot');
    slot.dataset.qty = name;
    renderQty(slot);
    return slot;
  };
  function renderQty(slot) {
    const name = slot.dataset.qty, n = cart[name] || 0;
    const button = (cls, text, role, label, delta) => {
      const b = el('button', cls, text);
      b.type = 'button';
      b.dataset.role = role;
      b.setAttribute('aria-label', label + name);
      b.addEventListener('click', e => { e.stopPropagation(); change(name, delta); });
      return b;
    };
    slot.replaceChildren();
    if (!name) return;
    if (!n) {
      slot.append(button('add-btn', slot.classList.contains('big') ? '+ 加入点单' : '+', 'add', '加入点单：', 1));
    } else {
      slot.append(button('step', '−', 'minus', '减少一份：', -1), el('span', 'qty-n', n), button('step', '+', 'plus', '再加一份：', 1));
    }
  }

  const sections = new Map();
  data.categories.forEach(c => {
    const sec = el('section', 'cat');
    const count = el('span', 'cat-count');
    const title = el('h2', 'cat-title');
    title.append(el('span', null, c.name), count);
    const grid = el('div', 'grid');
    sec.append(title, grid);
    menuEl.append(sec);
    sections.set(c.name, { sec, grid, count, visible: 0 });
  });
  dishes.forEach(d => {
    d.search = (d.name + ' ' + d.cat + ' ' + d.recipe).toLowerCase();
    const card = el('article', 'card');
    const main = el('button', 'card-main');
    main.type = 'button';
    main.append(el('span', 'dish-name', d.name));
    const tags = tagsFor(d);
    if (tags.length) { const t = el('span', 'tags'); t.append(...tags); main.append(t); }
    main.addEventListener('click', () => openDish(d));
    const actions = el('div', 'card-actions');
    const links = el('div', 'links');
    links.append(...d.links.map(linkChip));
    actions.append(links, qtySlot(d.name));
    card.append(main, actions);
    d.card = card;
    sections.get(d.cat).grid.append(card);
  });

  // --- 筛选：分类、搜索、只看有视频/做法 ---
  function apply() {
    const q = state.q.trim().toLowerCase();
    let total = 0;
    sections.forEach(s => { s.visible = 0; });
    dishes.forEach(d => {
      d.visible = (state.cat === 'all' || d.cat === state.cat) && (!q || d.search.includes(q))
        && (!state.video || d.links.length > 0) && (!state.recipe || !!d.recipe);
      d.card.hidden = !d.visible;
      if (d.visible) { sections.get(d.cat).visible++; total++; }
    });
    sections.forEach(s => { s.sec.hidden = !s.visible; s.count.textContent = s.visible + ' 道'; });
    $('empty').hidden = total > 0;
    chips.querySelectorAll('.chip').forEach(c => c.setAttribute('aria-pressed', String(c.dataset.cat === state.cat)));
  }
  $('search').addEventListener('input', e => { state.q = e.target.value; apply(); });
  document.querySelectorAll('.toggle').forEach(b => b.addEventListener('click', () => {
    state[b.dataset.filter] = !state[b.dataset.filter];
    b.setAttribute('aria-pressed', String(state[b.dataset.filter]));
    apply();
  }));

  // --- 菜品详情 ---
  const dishDialog = $('dish-dialog');
  function openDish(d, fromRandom) {
    $('dish-cat').textContent = d.cat;
    $('dish-name').textContent = d.name;
    $('dish-tags').replaceChildren(...tagsFor(d).filter(t => t.classList.contains('tag-todo')));
    $('dish-links').replaceChildren(...d.links.map(linkChip));
    $('dish-links').hidden = !d.links.length;
    const recipe = $('dish-recipe');
    recipe.textContent = d.recipe || d.videoText || '还没有记录做法';
    recipe.classList.toggle('muted', !d.recipe && !d.videoText);
    recipe.hidden = !data.showRecipes && !d.videoText;
    $('dish-qty').dataset.qty = d.name;
    renderQty($('dish-qty'));
    $('reroll').hidden = !fromRandom;
    if (!dishDialog.open) dishDialog.showModal();
    dishDialog.querySelector('.sheet-body').scrollTop = 0;
  }
  const randomDish = () => {
    const pool = dishes.filter(d => d.visible);
    if (!pool.length) { toast('没有符合条件的菜'); return; }
    const current = $('dish-qty').dataset.qty;
    const choices = pool.length > 1 ? pool.filter(d => d.name !== current) : pool;
    openDish(choices[Math.floor(Math.random() * choices.length)], true);
  };
  $('random').addEventListener('click', randomDish);
  $('reroll').addEventListener('click', randomDish);

  // --- 点单 ---
  const cartDialog = $('cart-dialog'), noteEl = $('cart-note');
  noteEl.value = store.get(NOTE_KEY, '');
  noteEl.addEventListener('input', () => store.set(NOTE_KEY, noteEl.value));
  function change(name, delta) {
    const before = cart[name] || 0, after = Math.max(0, before + delta);
    if (after) cart[name] = after; else delete cart[name];
    store.set(CART_KEY, cart);
    refreshCart();
    if (!before && after) toast('已加入：' + name);
  }
  function refreshCart() {
    // 重新渲染后把焦点放回同一个菜的按钮上，方便键盘操作
    const active = document.activeElement;
    const slot = active && active.closest ? active.closest('[data-qty]') : null;
    const scope = slot ? (slot.id ? slot : slot.closest('[id]')) : null;
    const focus = slot && { name: slot.dataset.qty, role: active.dataset.role, scopeId: scope && scope.id };

    const names = Object.keys(cart);
    const list = $('cart-list');
    list.replaceChildren(...names.map(name => {
      const li = el('li'), label = el('div', 'cart-item-name', name);
      label.append(el('span', 'cart-item-cat', byName.get(name).cat));
      li.append(label, qtySlot(name));
      return li;
    }));
    document.querySelectorAll('[data-qty]').forEach(renderQty);
    const portions = names.reduce((sum, n) => sum + cart[n], 0);
    $('cartbar').hidden = !names.length;
    $('cart-badge').textContent = portions;
    $('cart-summary').textContent = '已点 ' + names.length + ' 道菜';
    $('cart-empty').hidden = names.length > 0;
    ['clear-cart', 'copy-cart', 'share-cart'].forEach(id => { $(id).disabled = !names.length; });

    if (focus && focus.scopeId) {
      const root = $(focus.scopeId);
      const target = root.matches('[data-qty]') ? root : root.querySelector('[data-qty="' + CSS.escape(focus.name) + '"]');
      const button = target && (target.querySelector('[data-role="' + focus.role + '"]') || target.querySelector('button'));
      if (button) button.focus();
    }
  }
  const orderText = () => {
    const names = Object.keys(cart);
    const lines = names.map((n, i) => (i + 1) + '. ' + n + (cart[n] > 1 ? ' ×' + cart[n] : ''));
    const note = noteEl.value.trim();
    return data.title + ' 点单（' + names.length + ' 道菜）\\n' + lines.join('\\n') + (note ? '\\n备注：' + note : '');
  };
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (e) { /* 退回旧方法 */ }
    const ta = el('textarea');
    ta.value = text;
    cartDialog.append(ta);  // 放在对话框里，避免被模态对话框挡住
    ta.select();
    let ok = false;
    try { ok = document.execCommand('copy'); } catch (e) { /* 忽略 */ }
    ta.remove();
    return ok;
  }
  $('open-cart').addEventListener('click', () => cartDialog.showModal());
  $('copy-cart').addEventListener('click', async () => {
    toast(await copyText(orderText()) ? '已复制，发给大厨吧 👨‍🍳' : '复制失败，请手动截图');
  });
  if (navigator.share) {
    $('share-cart').hidden = false;
    $('share-cart').addEventListener('click', () => navigator.share({ title: data.title, text: orderText() }).catch(() => {}));
  }
  $('clear-cart').addEventListener('click', () => {
    if (!confirm('确定清空点单吗？')) return;
    for (const name of Object.keys(cart)) delete cart[name];
    store.set(CART_KEY, cart);
    refreshCart();
  });

  // --- 对话框：点背景或✕关闭 ---
  document.querySelectorAll('dialog').forEach(dialog => {
    dialog.addEventListener('click', e => { if (e.target === dialog) dialog.close(); });
    dialog.querySelectorAll('[data-close]').forEach(b => b.addEventListener('click', () => dialog.close()));
  });
  dishDialog.addEventListener('close', () => { $('dish-qty').dataset.qty = ''; renderQty($('dish-qty')); });

  let toastTimer;
  function toast(message) {
    const t = $('toast');
    // 有对话框打开时，把提示放进对话框，才能显示在最上层
    const host = document.querySelector('dialog[open]') || document.body;
    if (t.parentNode !== host) host.append(t);
    t.textContent = message;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 1800);
  }

  apply();
  refreshCart();
})();
</script>
</body>
</html>
"""


def main():
    menu = load_menu()
    dishes = [d for ds in menu.values() for d in ds]
    data = {
        'title': TITLE,
        'showRecipes': SHOW_RECIPES,
        'categories': [{'name': c, 'count': len(ds)} for c, ds in menu.items()],
        'dishes': dishes,
    }
    values = {
        'title': html.escape(TITLE),
        'font_face': font_face(TITLE),
        'logo': image_tag('assets/pipi3.png', 'logo'),
        'empty_img': image_tag('assets/pipi4.png', 'empty-cat'),
        'footer_img': image_tag('assets/pipi2.png', 'footer-cat'),
        'dish_count': str(len(dishes)),
        'recipe_toggle': '' if SHOW_RECIPES else 'hidden',
        # "</" 转义后放进 <script>，菜名/做法里有 </script> 也不会破坏网页
        'data': json.dumps(data, ensure_ascii=False).replace('</', '<\\/'),
    }
    page = re.sub(r'\{\{(\w+)\}\}', lambda m: values[m.group(1)], PAGE)
    with open(HTML_OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(page)
    print(f"菜谱网页 '{HTML_OUTPUT_FILE}' 已成功生成！（{len(dishes)} 道菜，{os.path.getsize(HTML_OUTPUT_FILE) / 1024:.0f} KB）")


if __name__ == '__main__':
    main()
