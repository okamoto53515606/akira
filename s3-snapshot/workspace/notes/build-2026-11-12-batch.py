# -*- coding: utf-8 -*-
import os, re, io, urllib.request
from PIL import Image, ImageDraw, ImageFont

SITE='/tmp/site'
TODAY='2026-11-12'
OGDIR=SITE+'/assets/og'
FONTDIR='/tmp/ogfonts'
os.makedirs(OGDIR, exist_ok=True); os.makedirs(FONTDIR, exist_ok=True)
FONT_URLS={'bold':'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf',
           'reg':'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf'}
def get_font(kind,size):
    p=os.path.join(FONTDIR,'NotoSansJP-%s.otf'%('Bold' if kind=='bold' else 'Regular'))
    if not os.path.exists(p) or os.path.getsize(p)<500000:
        urllib.request.urlretrieve(FONT_URLS[kind],p)
    return ImageFont.truetype(p,size)

# ---------------- OG images (1200x630 fixed) ----------------
W,H=1200,630
def wrap(d,text,font,maxw):
    words=list(text) if ' ' not in text else text.split(' ')
    lines=[];cur=''
    for w in words:
        t=(cur+(' ' if (' ' in text and cur) else '')+w)
        if d.textlength(t,font=font)<=maxw: cur=t
        else: lines.append(cur); cur=w
    if cur: lines.append(cur)
    return lines

def make_og(fn,kicker,title,facts,url,accent=(15,118,110)):
    im=Image.new('RGB',(W,H),(9,17,28)); d=ImageDraw.Draw(im)
    for y in range(H):
        t=y/H; d.line([(0,y),(W,y)],fill=(int(9+15*t),int(17+22*t),int(28+26*t)))
    d.rectangle([0,0,14,H],fill=accent)
    fb=get_font('bold',54); fk=get_font('bold',26); ff=get_font('reg',30); fu=get_font('reg',22)
    d.text((58,52),kicker,font=fk,fill=accent)
    y=104
    for ln in wrap(d,title,fb,W-120)[:2]:
        d.text((58,y),ln,font=fb,fill=(232,240,248)); y+=68
    y+=18
    for f in facts:
        d.ellipse([62,y+11,72,y+21],fill=accent)
        d.text((86,y),f,font=ff,fill=(196,212,228)); y+=52
    d.text((58,H-52),url,font=fu,fill=(140,162,182))
    im.save(os.path.join(OGDIR,fn),'PNG',optimize=True)
    chk=Image.open(os.path.join(OGDIR,fn))
    print('OG',fn,chk.size)
    assert chk.size==(1200,630), chk.size

make_og('ja-batch-api-pricing.png','LLM Data Hub / Batch API 割引',
        'Batch API割引の横断比較',
        ['OpenAI・Anthropic・Google は 50%減（通常比）',
         'xAI は 20%減、Moonshot は標準の60%、DeepSeek はオフピーク半額',
         '締切・保持期間・上限を公式ページの逐語で整理（2026-11-12確認）'],
        'llm.okamomedia.tokyo/batch-api-pricing/')
make_og('en-batch-api-pricing.png','LLM Data Hub / Batch API discounts',
        'Batch API discounts compared',
        ['OpenAI, Anthropic and Google: 50% off standard rates',
         'xAI: 20% off. Moonshot: 60% of standard. DeepSeek: off-peak half price',
         'Turnaround, retention and limits, taken verbatim (checked Nov 12, 2026)'],
        'llm.okamomedia.tokyo/en/batch-api-pricing/')
