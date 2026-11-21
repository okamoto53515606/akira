# 2026-11-21 計算機データ欠落の真因（Gemini 4 Neon / Claude Fable 5.2）

- 症状: verify_published_contracts が「台帳はGAだが公開中の計算機データに無い」を2件。
- 真因1: `render_site.py` の render_models_json が**追加のみ**で、台帳に無い行を作るだけで
  既存行を更新しなかった → Neon は render すれば入るが未公開のまま。
- 真因2: 台帳 claude-fable-5-2 の `price.provider` が表示名 "Anthropic"（他は slug）。
  さらに `names.ja` が "Claude Fable 5.2 / Mythos 5.2" で C5 ゲート（names で照合）が
  models.json の name "Claude Fable 5.2" と一致せず「無い」と誤判定。
- 対処: 台帳の provider→anthropic、names→"Claude Fable 5.2" に統一。生成器に
  provider_slug() を追加し、**既存行も** slug に正規化するようにした（未知 provider は触らない）。
- 注意: /app/tools.py の render_site ツール呼び出し直後に models.json が直っていない例を観測。
  確実に効かせたいときは `python3 tools/render_site.py --site /tmp/site --workspace /workspace`
  を直接叩き、data/models.json の中身を読んで確認する（ツールの戻り値の changed だけ信じない）。
