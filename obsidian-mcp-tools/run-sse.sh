#!/bin/bash
echo "Starting Obsidian Memo MCP in SSE mode..."
export MCP_TRANSPORT=sse
source venv/bin/activate
python server.py
