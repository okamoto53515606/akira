# 課題117（OpenAI 文字課金TTS 3モデル Deprecated の横断是正）— 実測で「該当ゼロ」確定

実施: 2026-11-15（JST）／対象は /tmp/site のローカル（公開中と MD5 一致・verify_publish 140/140 OK）

## 結論
**サイト内に「Deprecated な3モデルを現行扱いしている記述」は存在しない。修正不要＝課題117 はクローズ可。**

## 根拠（機械grep）
1. `grep -rIl -E "tts-1|gpt-4o-mini-tts|tts-1-hd"`（*.html / *.json / *.txt 全走査）
   → ヒットは **2ファイルのみ**: `speech-api-pricing/index.html`（14行）・`en/speech-api-pricing/index.html`（14行）。総ヒット 50。
   → **`/mai/` `/en/mai/` `/pricing/` `/en/pricing/` `/timeline/` `/en/timeline/` `data/models.json` `data/changelog.json` `index.html` `en/index.html` は 0件。**
2. モデル名を伴わない言い換えの走査: `TTS|音声出力|音声合成|テキスト読み上げ|text-to-speech` を speech 2ページ以外で検索
   → ヒットは changelog/index/index.html（いずれも11-15の新着文言）/ multimodal 日英（Gemini TTS のみ）/ mai 日英（MAI-Transcribe-2 の「cheapest speech recognition」＝Microsoftブログのタイトル引用、TTSではない）。
   → `/pricing/` `/timeline/` `/calculator/` `data/models.json` に音声・TTS の記述は **0件**（音声=0、tts=0）。
3. `最安|cheapest` × `tts|音声|voice|speech|audio` の複合走査 → speech 2ページ以外に「TTSが最安」系の記述なし。
   唯一近いのは `/mai/` の MAI-Transcribe-2（**文字起こし**の cheapest 引用）で、対象モデルが違う。MAI-Voice-2.1-Flash の行は `$15 / 100万文字` の価格表記のみで OpenAI との比較なし。

## speech 2ページの状態（既に是正済み・11-14/15）
- ja L84: 「OpenAI の音声生成モデル `tts-1` / `tts-1-hd` / `gpt-4o-mini-tts` は、いずれも**モデルページのモデル名直下に「Deprecated」と明記**」
- ja L159: 「文字課金で**現行**の最安は MAI-Voice-2.1-Flash…OpenAI の文字課金TTS 3モデルは Deprecated なので、新規は GPT-Live（$0.05/分・秒単位）か Gemini のトークン課金」
- 表の各モデル行・結論カード・出典（L88/91/94/134/168）にも Deprecated 注記あり。EN も同構造（L83/158 ほか）。

## 次回への申し送り
- site_plan の「次回の最優先1」「課題117」は本ファイルの結果でクローズしてよい（次回のプラン更新時に反映）。
- 残作業は 課題119（表が3列で重い）と 課題120（OGP見出しが小さい）のみ。
