# -*- coding: utf-8 -*-
"""OGP images for /kimi-k3-1-pro/ (ja/en). 1200x630."""
import os, urllib.request
from PIL import Image, ImageDraw, ImageFont
OGDIR='/tmp/site/assets/og'; FONTDIR='/tmp/ogfonts'
os.makedirs(OGDIR,exist_ok=True); os.makedirs(FONTDIR,exist_ok=True)
URLS={'bold':'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Bold.otf',
      'reg':'https://raw.githubusercontent.com/googlefonts/noto-cjk/main/Sans/SubsetOTF/JP/NotoSansJP-Regular.otf'}
def F(kind,size):
    p=os.path.join(FONTDIR,'NotoSansJP-%s.otf'%('Bold' if kind=='bold' else 'Regular'))
    if not os.path.exists(p) or os.path.getsize(p)<500000:
        urllib.request.urlretrieve(URLS[kind],p)
    return ImageFont.truetype(p,size)
W,H=1200,630
BG1=(6,20,24); BG2=(12,42,48); ACC=(16,148,140); TEXT=(235,244,246); MUTED=(186,208,212)
SPECS=[
 ('ja-kimi-k3-1-pro.png','Moonshot AI · Kimi K3.1 Pro','入力 $2.00 / 出力 $10.00',
  ['1,048,576トークン（約104万）のコンテキスト','キャッシュ入力 $0.20・書込 5分$2.00/1時間$4.00','前世代 Kimi K3 の $3/$15 より安い',
   'Batch API は標準の60%・公式料金ページで確認'],
  'llm.okamomedia.tokyo/kimi-k3-1-pro/'),
 ('en-kimi-k3-1-pro.png','Moonshot AI · Kimi K3.1 Pro','$2.00 in / $10.00 out',
  ['1,048,576-token context window','Cached input $0.20 · writes $2.00 (5m) / $4.00 (1h)','Cheaper than Kimi K3 ($3/$15)',
   'Batch API at 60% of standard rates'],
  'llm.okamomedia.tokyo/en/kimi-k3-1-pro/'),
]
def bg():
    img=Image.new('RGB',(W,H),BG1); d=ImageDraw.Draw(img)
    for y in range(H):
        t=y/H
        d.line([(0,y),(W,y)],fill=(int(BG1[0]+(BG2[0]-BG1[0])*t),int(BG1[1]+(BG2[1]-BG1[1])*t),int(BG1[2]+(BG2[2]-BG1[2])*t)))
    d.rectangle([0,0,14,H],fill=ACC)
    d.rectangle([70,H-96,W-70,H-94],fill=(40,80,86))
    return img,d
def wrap(d,text,font,maxw):
    out=[]; cur=''
    for ch in text:
        if d.textlength(cur+ch,font=font)<=maxw: cur+=ch
        else: out.append(cur); cur=ch
    if cur: out.append(cur)
    return out
for fn,kicker,title,facts,url in SPECS:
    img,d=bg()
    d.text((70,64),kicker,font=F('bold',34),fill=(120,214,206))
    y=126
    for ln in wrap(d,title,F('bold',76),W-160):
        d.text((70,y),ln,font=F('bold',76),fill=TEXT); y+=92
    y+=14
    d.rectangle([70,y,150,y+6],fill=ACC); y+=34
    for f in facts:
        for i,ln in enumerate(wrap(d,f,F('reg',32),W-200)):
            d.text((70 if i==0 else 100,y), ('•  ' if i==0 else '')+ln, font=F('reg',32), fill=MUTED); y+=46
        y+=6
    d.text((70,H-70),url,font=F('reg',28),fill=(110,146,152))
    p=os.path.join(OGDIR,fn); img.save(p,'PNG',optimize=True)
    print('saved',p,os.path.getsize(p))
