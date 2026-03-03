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

echo "Done! B-TWIN installed successfully."
echo ""
echo "Add the following to your project's .mcp.json:"
echo ""
echo '{
  "mcpServers": {
    "btwin": {
      "command": "'"$BTWIN_HOME/serve.sh"'",
      "args": []
    }
  }
}'
echo ""
