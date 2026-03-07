#!/bin/bash
set -e

BTWIN_HOME="$HOME/.btwin"

echo "=== B-TWIN Installation ==="
echo ""

# 1. Check / install uv
if ! command -v uv &> /dev/null; then
    echo "uv not found. Installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    echo ""
fi

# 2. Install btwin as a global tool
echo "Installing btwin..."
cd "$(dirname "$0")"
uv tool install . --force
echo ""

# 3. Create ~/.btwin directory
mkdir -p "$BTWIN_HOME"

# 4. Generate serve.sh wrapper (MCP server for direct usage)
cat > "$BTWIN_HOME/serve.sh" << 'EOF'
#!/usr/bin/env bash
exec btwin serve
EOF
chmod +x "$BTWIN_HOME/serve.sh"

# 5. Generate proxy.sh wrapper (MCP proxy for per-project usage)
cat > "$BTWIN_HOME/proxy.sh" << 'EOF'
#!/usr/bin/env bash
exec btwin mcp-proxy "$@"
EOF
chmod +x "$BTWIN_HOME/proxy.sh"

echo ""
echo "Done! B-TWIN installed successfully."
echo ""
echo "Quick start:"
echo ""
echo "  1. Start the API server:"
echo "       btwin serve-api"
echo ""
echo "  2. In your project directory, run:"
echo "       btwin init"
echo ""
echo "     This creates .mcp.json so Claude Code auto-connects via the MCP proxy."
echo ""
echo "To uninstall:"
echo "       uv tool uninstall btwin && rm -rf ~/.btwin"
echo ""
