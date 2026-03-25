import os
import re
import asyncio
from datetime import datetime
from dotenv import load_dotenv

from mcp.server import Server
import mcp.types as types
from mcp.server.stdio import stdio_server

import httpx

# FastAPI imports for SSE
from fastapi import FastAPI
from mcp.server.sse import SseServerTransport
import uvicorn
from starlette.requests import Request

# 환경변수 로드
load_dotenv()

# Configuration
OBSIDIAN_API_KEY = os.getenv("OBSIDIAN_API_KEY", "")
OBSIDIAN_BASE_URL = os.getenv("OBSIDIAN_BASE_URL", "https://127.0.0.1:27124").rstrip("/")
OBSIDIAN_TARGET_FOLDER = os.getenv("OBSIDIAN_TARGET_FOLDER", "Memo").strip("/")
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()
SSE_PORT = int(os.getenv("SSE_PORT", "8000"))

# Obsidian-mcp-tools 
server = Server("Obsidian-mcp-tools")

def sanitize_filename(title: str) -> str:
    # 특수문자 제거 및 공백을 하이픈으로 대체
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    safe_title = safe_title.replace(" ", "-")
    return safe_title

@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="save_memo",
            description="URL의 내용을 마크다운 형태로 Obsidian Memo 버킷에 저장합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "원본 URL"
                    },
                    "title": {
                        "type": "string",
                        "description": "저장할 메모의 제목 (파일명과 메인 타이틀에 사용됨)"
                    },
                    "content": {
                        "type": "string",
                        "description": "포맷팅이 완료된 마크다운 내용 (Frontmatter 포함 권장)"
                    },
                    "folder": {
                        "type": "string",
                        "description": "저장할 대상 폴더명 (옵션). 제공하지 않으면 기본 폴더를 사용합니다. 예: 'Memo/IT'"
                    }
                },
                "required": ["url", "title", "content"]
            }
        )
    ]

@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    if name != "save_memo":
        raise ValueError(f"Unknown tool: {name}")

    if not OBSIDIAN_API_KEY or OBSIDIAN_API_KEY == "your_api_key_here":
        return [types.TextContent(type="text", text="Error: OBSIDIAN_API_KEY가 .env 파일에 올바르게 설정되지 않았습니다.")]

    title = arguments["title"]
    url = arguments["url"]
    content = arguments["content"]
    folder = arguments.get("folder", "")

    # 폴더 결정 로직
    target_folder = folder.strip("/") if folder else OBSIDIAN_TARGET_FOLDER

    # 파일명 생성: YYYYMMDD-HHmmss-title.md
    now_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_title = sanitize_filename(title)
    filename = f"{now_str}-{safe_title}.md"
    
    # 파일 내 원본 URL 명시 (Frontmatter가 없다면 하단에 추가)
    final_content = content
    if url not in final_content:
        final_content += f"\n\n---\n**Source:** {url}"

    # Local REST API 엔드포인트 생성: PUT /vault/{target_folder}/{filename}
    if target_folder:
        endpoint = f"{OBSIDIAN_BASE_URL}/vault/{target_folder}/{filename}"
    else:
        # 타겟 폴더가 비어있으면 볼트 루트(/vault/)에 직접 저장
        endpoint = f"{OBSIDIAN_BASE_URL}/vault/{filename}"
    
    headers = {
        "Authorization": f"Bearer {OBSIDIAN_API_KEY}",
        "Content-Type": "text/markdown"
    }

    try:
        # Local REST API 플러그인은 기본적으로 self-signed 인증서를 사용하므로 verify=False 처리
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.put(endpoint, content=final_content, headers=headers)
            response.raise_for_status()
            
            return [types.TextContent(
                type="text", 
                text=f"성공적으로 메모가 저장되었습니다! 폴더: '{target_folder or 'Vault Root'}', 파일명: '{filename}'"
            )]
    except httpx.HTTPStatusError as e:
        return [types.TextContent(type="text", text=f"Obsidian API 통신 에러: {e.response.status_code} - {e.response.text}")]
    except Exception as e:
        return [types.TextContent(type="text", text=f"메모 저장 실패: {str(e)}")]

# ==========================================
# Transport Runners
# ==========================================
async def run_stdio():
    print("Starting Obsidian-mcp-tools with stdio transport...", flush=True)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())

# SSE 통신을 위한 FastAPI 설정
app = FastAPI()
sse = SseServerTransport("/messages")

@app.get("/sse")
async def handle_sse(request: Request):
    async with sse.connect_sse(request.scope, request.receive, request._send) as streams:
        await server.run(streams[0], streams[1], server.create_initialization_options())

@app.post("/messages")
async def handle_messages(request: Request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

def main():
    if MCP_TRANSPORT == "sse":
        print(f"Starting Obsidian-mcp-tools with SSE transport on port {SSE_PORT}...")
        uvicorn.run(app, host="0.0.0.0", port=SSE_PORT)
    else:
        # 기본값: stdio
        asyncio.run(run_stdio())

if __name__ == "__main__":
    main()
