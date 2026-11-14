# -*- coding: utf-8 -*-
"""課題120: 音声API料金比較のOGP（ja/en）を見出し20%拡大で再生成。1200x630固定。"""
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
TITLE=92          # 旧76 → +21%（見出し20%拡大）
SPECS=[
 ('ja-speech-api-pricing.png','LLM Data Hub · 2026\u5e7411\u6708\u7248','\u97f3\u58f0API\u6599\u91d1\u6bd4\u8f03',
  ['TTS\u306f\u300c1\u5206\u300d\u3001\u6587\u5b57\u8d77\u3053\u3057\u306f\u300c1\u6642\u9593\u300d\u306b\u7d71\u4e00',
   'MAI-Voice-2.1-Flash $0.0045/\u5206',
   'MAI-Transcribe-2 $0.10/\u6642\u9593\uff08\u5e74\u672b\u307e\u3067\u306e\u671f\u9593\u9650\u5b9a\uff09'],
  'llm.okamomedia.tokyo/speech-api-pricing/'),
 ('en-speech-api-pricing.png','LLM Data Hub · Nov 2026','Speech API Pricing',
  ['TTS normalised to one minute, STT to one hour',
   'MAI-Voice-2.1-Flash $0.0045/min',
   'MAI-Transcribe-2 $0.10/hour (promo to year end)'],
  'llm.okamomedia.tokyo/en/speech-api-pricing/'),
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
    d.text((70,58),kicker,font=F('bold',34),fill=(120,214,206))
    y=118
    lines=wrap(d,title,F('bold',TITLE),W-160)
    for ln in lines:
        d.text((70,y),ln,font=F('bold',TITLE),fill=TEXT); y+=112
    y+=10
    d.rectangle([70,y,150,y+6],fill=ACC); y+=30
    for f in facts:
        for i,ln in enumerate(wrap(d,f,F('reg',31),W-210)):
            d.text((70 if i==0 else 100,y), ('\u2022  ' if i==0 else '')+ln, font=F('reg',31), fill=MUTED); y+=44
        y+=6
    d.text((70,H-70),url,font=F('reg',28),fill=(110,146,152))
    p=os.path.join(OGDIR,fn); img.save(p,'PNG',optimize=True)
    im=Image.open(p)
    print('saved',fn,'size',im.size,'bytes',os.path.getsize(p),'title_lines',len(lines))
