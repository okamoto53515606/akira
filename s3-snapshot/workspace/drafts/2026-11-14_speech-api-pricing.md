# 2026-11-14 音声API料金比較（作成完了・**未公開**）

## 状態
- **ページは完成し、全ゲート通過。ただし `site_upload` がドライラン環境で、S3へは1バイトも上がっていない**（`{"status":"dry_run"}` を確認）。verify_publish の NG 12件はこの未公開分。
- 公開済み: なし。ローカル `/tmp/site` に反映済み（Fargate再起動で消える → 下の復元手順を使う）。

## 翌朝の復元手順（この順序で）
1. `site_download` でライブを取り直す（11-14 の公開分は入っていない状態に戻る）。
2. `/workspace/parts/speech-2026-11-14/` からコピー:
   - `ja-speech-api-pricing.html` → `/tmp/site/speech-api-pricing/index.html`（ディレクトリ作成）
   - `en-speech-api-pricing.html` → `/tmp/site/en/speech-api-pricing/index.html`
   - `ja-speech-api-pricing.png` / `en-speech-api-pricing.png` / `ja-prompt-cache-pricing.png` / `en-prompt-cache-pricing.png` → `/tmp/site/assets/og/`
3. `python3 /workspace/parts/speech-2026-11-14/apply_wiring.py /tmp/site`
   （sitemap 2URL・llms.txt の EN/JA 両セクション・日英トップの新着カード・フロンティア比較の Carbon GA 行を**冪等に**適用。2回流しても壊れない／カード挿入で article タグが二重にならない版に修正済み）
4. `check_site_pages`（ERROR 0）→ `check_dates`（NG 0）→ `check_facts_consistency` → `site_upload`
5. 公開できたら、リポジトリの 11-14 公開チェック（head ライブ実測）と site_plan の課題116クローズ。

## 内容（完成形）
- `/speech-api-pricing/` `/en/speech-api-pricing/`：TTS 8行（OpenAI tts-1/tts-1-hd/gpt-4o-mini-tts、Gemini 3.1 Flash TTS Preview・3.8 Flash TTS・2.5 Pro/Flash Preview、MAI-Voice-2.1）＋文字起こし5行（Gemini 3.5 Transcribe、gpt-live-transcribe、MAI-Transcribe-2、Muse Voice Transcribe、MAI-Transcribe-2-Streaming）＋音声対話3行（Gemini Live 3.1、GPT-Live-1、gpt-realtime-mini）。
- 主役は**単位の正規化**：1M文字建てと1Mトークン建てで順位が逆転する（tts-1 $0.0045/分 対 Gemini 3.8 Flash TTS $0.0135/分）。
- 換算前提（1分=300文字／1,500音声トークン、1,000文字=200秒、英ナレーションは約900文字/分＝分単価は約3倍）を明示。
- **OpenAI の文字課金TTS 3モデルはモデルページに Deprecated 表記**（逐語引用済み）。表の直前に注意ボックス、結論カードは「現行の最安」に修正。
- 2027-01-01 の Gemini TTS 2モデル2倍、MAI-Transcribe-2 の期間限定 $0.10/時間も明記。
- OG 2枚（1200×630）＋プロンプトキャッシュの OG 2枚を規格統一のため作り直し（Gemini 視認チェック済み・文字化け/はみ出しなし）。

## 一次情報キャッシュ（全部 2026-11-14 取得）
gemini-tts-pricing / openai-tts-1 / openai-gpt-4o-mini-tts / openai-audio-pricing / mai-streaming-transcription / mai-transcribe-2-price / meta-muse-voice-pricing（いずれも `/workspace/cache/*-2026-11-14.md`）

## 未確認として残したもの
- MAI-Voice-2.1 の音声トークン単価（ページに記載なし）
- gpt-4o-mini-tts の音声トークン→秒換算（式は推測として明示）
- MAI-Transcribe-2-Streaming の単価
