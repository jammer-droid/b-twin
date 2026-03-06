#!/bin/bash
set -e

BTWIN_HOME="$HOME/.btwin"
SERVICE_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== B-TWIN Installation ==="
echo ""

# 1. Check / install uv
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
fi

# 2. Install dependencies
echo "Installing dependencies..."
cd "$SERVICE_DIR"
uv sync
echo ""

# 3. Create ~/.btwin directory
mkdir -p "$BTWIN_HOME"

# 4. Generate serve.sh wrapper
cat > "$BTWIN_HOME/serve.sh" << EOF
#!/bin/bash
uv --directory "$SERVICE_DIR" run btwin serve
EOF
chmod +x "$BTWIN_HOME/serve.sh"

# 5. Generate proxy.sh wrapper (MCP proxy for per-project usage)
cat > "$BTWIN_HOME/proxy.sh" << EOF
#!/usr/bin/env bash
# B-TWIN MCP Proxy launcher
exec uv --directory "$SERVICE_DIR" run btwin mcp-proxy "\$@"
EOF
chmod +x "$BTWIN_HOME/proxy.sh"
echo "Created $BTWIN_HOME/proxy.sh"

echo ""
echo "Done! B-TWIN installed successfully."
echo ""
echo "Quick start for a project:"
echo ""
echo "  1. Start the API server:"
echo "       btwin serve-api"
echo ""
echo "  2. In your project directory, run:"
echo "       btwin init"
echo ""
echo "     This creates .mcp.json so Claude Code auto-connects via the MCP proxy."
echo ""
echo "Or manually add the following to your project's .mcp.json:"
echo ""
echo '{
  "mcpServers": {
    "btwin": {
      "command": "'"$BTWIN_HOME/proxy.sh"'",
      "args": ["--project", "<your-project-name>"]
    }
  }
}'
echo ""
