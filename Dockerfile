# Akira — Fargate batch container
# Python 3.12 + Node.js (Brave Search MCP) + uv (analytics-mcp を uvx で実行)

FROM python:3.12-slim

# Node.js 22.x (npx for Brave Search MCP stdio)
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl && \
    curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y --no-install-recommends nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# uv / uvx (GA4 analytics-mcp 用)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

# MCP Toolbox (BigQuery MCP 用)
RUN curl -fL https://storage.googleapis.com/genai-toolbox/v0.10.0/linux/amd64/toolbox -o /usr/local/bin/toolbox && \
    chmod +x /usr/local/bin/toolbox

WORKDIR /app

# 依存インストール（uv.lock で再現性を担保）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# アプリケーションコード
COPY main.py settings.py budget.py config_store.py tools.py prompts.py report.py ./
COPY gcp-workload-config-template.json ./

# npx の Brave Search MCP と Firecrawl MCP を事前キャッシュ
RUN npx -y @brave/brave-search-mcp-server --help 2>/dev/null || true
RUN npx -y firecrawl-mcp --help 2>/dev/null || true

ENV PATH="/app/.venv/bin:$PATH" \
    GCP_WORKLOAD_IDENTITY_TEMPLATE="/app/gcp-workload-config-template.json" \
    BYPASS_TOOL_CONSENT=true

# APIキーは実行時にSecrets Managerから取得（イメージに含めない）
ENTRYPOINT ["python", "main.py"]
