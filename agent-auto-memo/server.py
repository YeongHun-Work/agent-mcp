import os
import sys
import re
import asyncio
import collections
import contextlib
from datetime import datetime
from dotenv import load_dotenv
from uuid import UUID

from mcp.server import Server
import mcp.types as types
from mcp.server.stdio import stdio_server

import aiofiles

# Starlette imports for raw ASGI SSE
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import JSONResponse
from starlette.requests import Request
from mcp.server.sse import SseServerTransport

# Option A: MCP Streamable HTTP
from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

import uvicorn

# 최근 저장 이력 (최대 20건, 메모리)
_save_history: collections.deque = collections.deque(maxlen=20)

# 환경변수 로드
load_dotenv()

# Configuration
OBSIDIAN_VAULT_PATH = os.getenv("OBSIDIAN_VAULT_PATH", "/data/workspace/obsidian/").rstrip("/")
OBSIDIAN_TARGET_FOLDER = os.getenv("OBSIDIAN_TARGET_FOLDER", "Memo").strip("/")
MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "stdio").lower()
SSE_PORT = int(os.getenv("SSE_PORT", "8000"))

# agent-auto-memo
server = Server("agent-auto-memo")

def sanitize_filename(title: str) -> str:
    safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
    safe_title = safe_title.replace(" ", "-")
    return safe_title


# ==========================================
# 공통 저장 로직 (MCP 툴 + REST API 공유)
# ==========================================
async def _do_save_memo(title: str, url: str, content: str, folder: str = "") -> dict:
    """
    실제 파일 저장 + 검증 수행.
    반환: {"ok": True, ...} 또는 {"ok": False, "error": "..."}
    """
    if not OBSIDIAN_VAULT_PATH or OBSIDIAN_VAULT_PATH == "/path/to/your/obsidian/vault":
        return {"ok": False, "error": "OBSIDIAN_VAULT_PATH가 .env 파일에 올바르게 설정되지 않았습니다."}

    target_folder = folder.strip("/") if folder else OBSIDIAN_TARGET_FOLDER
    now_str = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_title = sanitize_filename(title)
    filename = f"{now_str}-{safe_title}.md"

    final_content = content
    if url not in final_content:
        final_content += f"\n\n---\n**Source:** {url}"

    target_dir = os.path.join(OBSIDIAN_VAULT_PATH, target_folder) if target_folder else OBSIDIAN_VAULT_PATH
    file_path = os.path.join(target_dir, filename)

    print(f"[save_memo] writing to: {file_path}", file=sys.stderr, flush=True)
    try:
        os.makedirs(target_dir, exist_ok=True)
        expected_size = len(final_content.encode("utf-8"))

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(final_content)
            await f.flush()

        if not os.path.exists(file_path):
            raise IOError(f"파일이 존재하지 않음 (write 후): {file_path}")

        file_size = os.path.getsize(file_path)
        if file_size == 0:
            raise IOError(f"파일이 비어있음 (0 bytes): {file_path}")
        if file_size < expected_size * 0.9:
            raise IOError(f"파일 크기 불일치: 기대={expected_size}, 실제={file_size}")

        async with aiofiles.open(file_path, "r", encoding="utf-8") as f:
            head = await f.read(80)
        if head != final_content[:80]:
            raise IOError("파일 내용 불일치 (read-back 실패)")

        print(f"[save_memo] verified: {file_path} ({file_size} bytes)", file=sys.stderr, flush=True)

        record = {
            "filename": filename,
            "path": file_path,
            "folder": target_folder,
            "size": file_size,
            "saved_at": now_str,
            "title": title,
            "url": url,
        }
        _save_history.appendleft(record)
        return {"ok": True, **record}

    except Exception as e:
        print(f"[save_memo] ERROR: {e}", file=sys.stderr, flush=True)
        return {"ok": False, "error": str(e)}


# ==========================================
# MCP 툴 정의
# ==========================================
@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="save_memo",
            description="URL의 내용을 마크다운 형태로 Obsidian Memo 버킷에 저장합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "원본 URL"},
                    "title": {"type": "string", "description": "저장할 메모의 제목 (파일명과 메인 타이틀에 사용됨)"},
                    "content": {"type": "string", "description": "포맷팅이 완료된 마크다운 내용 (Frontmatter 포함 권장)"},
                    "folder": {"type": "string", "description": "저장할 대상 폴더명 (옵션). 예: 'Memo/IT'"},
                },
                "required": ["url", "title", "content"],
            },
        ),
        types.Tool(
            name="get_last_save",
            description="가장 최근에 저장된 메모 정보를 반환합니다. save_memo 호출 후 실제 저장 여부를 확인할 때 사용합니다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "count": {"type": "integer", "description": "조회할 최근 저장 건수 (기본값: 1, 최대: 20)", "default": 1},
                },
                "required": [],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    print(f"[call_tool] name={name}, title={arguments.get('title','')}, folder={arguments.get('folder','')}", file=sys.stderr, flush=True)

    if name == "get_last_save":
        count = min(int(arguments.get("count", 1)), 20)
        if not _save_history:
            return [types.TextContent(type="text", text="저장 이력이 없습니다. (서버 재시작 후 저장된 항목 없음)")]
        items = list(_save_history)[:count]
        lines = [f"📋 최근 저장 이력 ({len(items)}건)"]
        for i, item in enumerate(items, 1):
            lines.append(
                f"\n[{i}] {item['saved_at']}\n"
                f"  - 파일명: {item['filename']}\n"
                f"  - 경로: {item['path']}\n"
                f"  - 크기: {item['size']} bytes\n"
                f"  - 제목: {item['title']}"
            )
        return [types.TextContent(type="text", text="\n".join(lines))]

    if name != "save_memo":
        raise ValueError(f"Unknown tool: {name}")

    result = await _do_save_memo(
        title=arguments["title"],
        url=arguments["url"],
        content=arguments["content"],
        folder=arguments.get("folder", ""),
    )

    if result["ok"]:
        text = (
            f"✅ 메모 저장 완료\n"
            f"- 파일명: {result['filename']}\n"
            f"- 저장 경로: {result['path']}\n"
            f"- 폴더: {result['folder']}\n"
            f"- 파일 크기: {result['size']} bytes\n"
            f"- 저장 시각: {result['saved_at']}"
        )
    else:
        text = f"❌ 메모 저장 실패: {result['error']}"

    return [types.TextContent(type="text", text=text)]


# ==========================================
# Transport Runners
# ==========================================
async def run_stdio():
    print("Starting agent-auto-memo with stdio transport...", file=sys.stderr, flush=True)
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


# ── Option: SSE (기존) ────────────────────────────────────────────────────────
sse = SseServerTransport("/messages")


class SSEHandler:
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return

        sessions_before: set[UUID] = set(sse._read_stream_writers.keys())
        new_session_id: UUID | None = None

        try:
            async with sse.connect_sse(scope, receive, send) as streams:
                new_ids = set(sse._read_stream_writers.keys()) - sessions_before
                if new_ids:
                    new_session_id = next(iter(new_ids))
                    print(f"[SSEHandler] Session started: {new_session_id.hex}", file=sys.stderr, flush=True)

                try:
                    await server.run(streams[0], streams[1], server.create_initialization_options())
                    print(f"[SSEHandler] server.run exited normally (session={new_session_id and new_session_id.hex})", file=sys.stderr, flush=True)
                except Exception as run_err:
                    print(f"[SSEHandler] server.run raised: {type(run_err).__name__}: {run_err}", file=sys.stderr, flush=True)
                    raise
        except Exception as e:
            print(f"[SSEHandler] connect_sse ended: {type(e).__name__}: {e}", file=sys.stderr, flush=True)
        finally:
            if new_session_id is not None:
                sse._read_stream_writers.pop(new_session_id, None)
                print(f"[SSEHandler] Session cleaned up: {new_session_id.hex}", file=sys.stderr, flush=True)


class MessageHandler:
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        try:
            await sse.handle_post_message(scope, receive, send)
        except Exception as e:
            print(f"[MessageHandler] Session expired or closed: {type(e).__name__}: {e}", file=sys.stderr, flush=True)


# ── Option A: MCP Streamable HTTP ────────────────────────────────────────────
session_manager = StreamableHTTPSessionManager(app=server, stateless=False)


class StreamableHTTPHandler:
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        await session_manager.handle_request(scope, receive, send)


# ── Option B: REST API ────────────────────────────────────────────────────────
async def api_save_memo(request: Request):
    """
    POST /api/save-memo
    Body: { "title": str, "url": str, "content": str, "folder": str (optional) }
    """
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"ok": False, "error": "Invalid JSON body"}, status_code=400)

    title = body.get("title", "").strip()
    url = body.get("url", "").strip()
    content = body.get("content", "").strip()
    folder = body.get("folder", "")

    if not title or not url or not content:
        return JSONResponse({"ok": False, "error": "title, url, content 필드가 필요합니다."}, status_code=400)

    result = await _do_save_memo(title=title, url=url, content=content, folder=folder)
    status_code = 200 if result["ok"] else 500
    return JSONResponse(result, status_code=status_code)


async def api_last_save(request: Request):
    """
    GET /api/last-save?count=1
    """
    try:
        count = min(int(request.query_params.get("count", 1)), 20)
    except ValueError:
        return JSONResponse({"ok": False, "error": "count must be an integer"}, status_code=400)

    history = list(_save_history)[:count]
    return JSONResponse({"ok": True, "count": len(history), "items": history})


# ── 상태 조회 ─────────────────────────────────────────────────────────────────
async def status_handler(_request: Request):
    history = list(_save_history)
    return JSONResponse({
        "status": "ok",
        "server": "agent-auto-memo",
        "total_saves": len(history),
        "recent_saves": history[:10],
    })


# ── Starlette 앱 (lifespan으로 session_manager 관리) ─────────────────────────
@contextlib.asynccontextmanager
async def lifespan(_app: Starlette):
    async with session_manager.run():
        yield


app = Starlette(
    debug=True,
    lifespan=lifespan,
    routes=[
        # 기존 SSE
        Route("/sse", endpoint=SSEHandler()),
        Route("/messages", endpoint=MessageHandler(), methods=["POST"]),
        # Option A: MCP Streamable HTTP
        Route("/mcp", endpoint=StreamableHTTPHandler(), methods=["GET", "POST", "DELETE"]),
        # Option B: REST API
        Route("/api/save-memo", endpoint=api_save_memo, methods=["POST"]),
        Route("/api/last-save", endpoint=api_last_save, methods=["GET"]),
        # 상태 조회
        Route("/status", endpoint=status_handler, methods=["GET"]),
    ],
)


def main():
    mode = MCP_TRANSPORT
    if len(sys.argv) > 1:
        if sys.argv[1] == "--stdio":
            mode = "stdio"
        elif sys.argv[1] == "--sse":
            mode = "sse"

    if mode == "sse":
        print(f"Starting agent-auto-memo with SSE transport on port {SSE_PORT}...", file=sys.stderr)
        uvicorn.run(app, host="0.0.0.0", port=SSE_PORT)
    else:
        asyncio.run(run_stdio())


if __name__ == "__main__":
    main()
