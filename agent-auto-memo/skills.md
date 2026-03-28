# agent-auto-memo — Skills Guide

AI 에이전트(openclaw, Claude Code 등)가 이 MCP 서버를 올바르게 사용하는 방법을 정리한 가이드입니다.

---

## 제공 도구 (MCP Tools)

| 도구 이름 | 역할 |
|---|---|
| `save_memo` | 마크다운 내용을 파일로 저장 |
| `get_last_save` | 최근 저장 이력 조회 (저장 성공 여부 검증용) |

---

## 1. save_memo

### 파라미터

| 이름 | 타입 | 필수 | 설명 |
|---|---|---|---|
| `url` | string | ✅ | 원본 URL (내용이 없으면 `"internal"` 등 임의값 사용 가능) |
| `title` | string | ✅ | 파일명과 H1 제목으로 사용됨 |
| `content` | string | ✅ | 저장할 마크다운 전문 (Frontmatter 포함 권장) |
| `folder` | string | ❌ | 저장할 하위 폴더 (미지정 시 `.env`의 `OBSIDIAN_TARGET_FOLDER` 사용) |

### 호출 예시

```json
{
  "url": "https://example.com/article",
  "title": "React 18 핵심 정리",
  "content": "---\ntags: [react, frontend]\ndate: 2026-03-28\n---\n\n# React 18 핵심 정리\n\n## 주요 변경사항\n- Concurrent Mode 기본 활성화\n- Automatic Batching 개선\n",
  "folder": "개발/React"
}
```

### 성공 응답 형태

```
✅ 메모 저장 완료
- 파일명: 20260328-153000-React-18-핵심-정리.md
- 저장 경로: /data/workspace/obsidian/개발/React/20260328-153000-React-18-핵심-정리.md
- 폴더: 개발/React
- 파일 크기: 312 bytes
- 저장 시각: 20260328-153000
```

### 실패 응답 형태

```
❌ 메모 저장 실패: 파일이 비어있음 (0 bytes): ...
```

**중요:** 응답에 `✅ 메모 저장 완료`가 포함되어 있어야 실제로 파일이 기록된 것입니다.
`❌`로 시작하거나 응답이 없다면 저장되지 않은 것입니다.

---

## 2. get_last_save

`save_memo` 호출 직후 실제 저장 여부를 클라이언트 측에서 이중 확인할 때 사용합니다.

### 파라미터

| 이름 | 타입 | 기본값 | 설명 |
|---|---|---|---|
| `count` | integer | 1 | 조회할 최근 저장 건수 (최대 20) |

### 호출 예시

```json
{ "count": 1 }
```

### 응답 예시

```
📋 최근 저장 이력 (1건)

[1] 20260328-153000
  - 파일명: 20260328-153000-React-18-핵심-정리.md
  - 경로: /data/workspace/obsidian/개발/React/20260328-153000-React-18-핵심-정리.md
  - 크기: 312 bytes
  - 제목: React 18 핵심 정리
```

서버 재시작 후 저장 이력이 없으면 다음 메시지가 반환됩니다:
```
저장 이력이 없습니다. (서버 재시작 후 저장된 항목 없음)
```

---

## 3. 권장 사용 패턴

### 패턴 A — 기본 (단순 저장)

```
1. 콘텐츠 수집/정리
2. save_memo 호출
3. 응답에서 "✅ 메모 저장 완료" 확인 → 완료
```

### 패턴 B — 이중 검증 (신뢰성이 중요한 경우)

```
1. 콘텐츠 수집/정리
2. save_memo 호출
3. 응답에서 "✅ 메모 저장 완료" 확인
4. get_last_save 호출 → 파일명/크기 일치 여부 확인
5. 불일치 시 save_memo 재시도
```

### 패턴 C — 여러 건 분할 저장

URL 하나당 `save_memo` 한 번. 내용이 많아도 하나의 호출로 처리합니다.
여러 URL을 묶어서 저장할 때는 각각 호출하거나 하나의 통합 문서로 작성합니다.

---

## 4. content 작성 가이드

### 기본 구조 (Frontmatter 포함 권장)

```markdown
---
tags: [태그1, 태그2]
source: https://원본URL
date: 2026-03-28
---

# 제목

## 섹션 1
내용...

## 섹션 2
내용...
```

### content에 포함해야 할 것

- 원본 내용의 핵심 정보 (요약, 중요 포인트)
- 출처 URL (Frontmatter `source` 또는 본문에 명시)
- 적절한 마크다운 구조 (헤더, 리스트, 코드블럭 등)

### content에서 피해야 할 것

- 빈 문자열 또는 너무 짧은 내용 (검증 실패 가능성)
- HTML 태그 그대로 포함 (마크다운으로 변환해야 함)
- 인코딩 깨짐 방지를 위해 특수 제어문자 제외

---

## 5. 폴더 경로 규칙

- 슬래시(`/`)로 하위 폴더 구분: `"개발/Python/FastAPI"`
- 앞뒤 슬래시는 자동으로 제거됩니다
- 폴더가 없으면 자동 생성됩니다
- 미지정 시 서버의 `OBSIDIAN_TARGET_FOLDER` 환경변수 값 사용 (기본: `Memo`)

---

## 6. 파일명 생성 규칙

파일명은 서버가 자동 생성합니다:

```
{YYYYMMDD}-{HHmmss}-{title-sanitized}.md
```

- `title`의 공백 → 하이픈(`-`)으로 변환
- 특수문자 `\ / * ? : " < > |` → 제거
- 예: `title="React 18: 핵심 정리"` → `20260328-153000-React-18-핵심-정리.md`

---

## 7. 흔한 실수 & 주의사항

### ❌ 실수 1 — content 없이 호출

```json
{ "url": "...", "title": "..." }
// content 누락 → required 파라미터 오류
```

### ❌ 실수 2 — 응답 확인 없이 성공으로 간주

`save_memo`를 호출했다고 파일이 저장된 것이 아닙니다.
반드시 응답 텍스트에서 `✅ 메모 저장 완료`를 확인해야 합니다.
응답이 없거나 `❌`로 시작하면 저장 실패입니다.

### ❌ 실수 3 — SSE 클라이언트가 initialize 직후 연결을 닫음

MCP SSE 방식은 `initialize` → 응답 수신 → `tools/list` → `call_tool` 전체 과정에서 SSE 연결을 유지해야 합니다.
일부 클라이언트(구버전 OpenClaw 등)가 initialize POST 직후 SSE를 끊으면 `[call_tool]` 로그가 전혀 찍히지 않고 저장도 되지 않습니다.

**해결:** MCP Streamable HTTP(`/mcp`) 또는 REST API(`/api/save-memo`) 방식으로 전환하세요.

### ❌ 실수 4 — 대용량 content를 여러 번 쪼개서 저장 시도

하나의 완성된 마크다운 문서를 한 번에 `content`로 전달해야 합니다.
부분 내용을 여러 번 나눠서 append하는 방식은 지원되지 않습니다.

### ❌ 실수 5 — folder를 절대 경로로 지정

```json
// 잘못된 예
{ "folder": "/data/workspace/obsidian/Memo" }

// 올바른 예
{ "folder": "Memo" }
```

`folder`는 Obsidian vault 루트 기준의 **상대 경로**입니다.

---

## 8. 연결 방식 선택 가이드

클라이언트 종류에 따라 연결 방식을 선택하세요.

| 방식 | 엔드포인트 | 적합한 클라이언트 |
|------|-----------|-----------------|
| MCP Streamable HTTP | `POST http://<IP>:8000/mcp` | OpenClaw 등 최신 MCP 클라이언트 |
| MCP SSE (기존) | `GET http://<IP>:8000/sse` | Claude Desktop, 구버전 MCP 클라이언트 |
| REST API | `POST http://<IP>:8000/api/save-memo` | HTTP 툴 직접 호출 |
| stdio | `docker exec -i agent-auto-memo python server.py --stdio` | 네트워크 없이 로컬 연결 |

### REST API 호출 예시 (Option B)

**POST /api/save-memo**
```json
{
  "title": "React 18 핵심 정리",
  "url": "https://example.com/article",
  "content": "# React 18\n\n내용...",
  "folder": "개발/React"
}
```

응답:
```json
{
  "ok": true,
  "filename": "20260328-153000-React-18-핵심-정리.md",
  "path": "/data/workspace/obsidian/개발/React/...",
  "size": 312,
  "saved_at": "20260328-153000"
}
```

**GET /api/last-save?count=1**
```json
{
  "ok": true,
  "count": 1,
  "items": [{ "filename": "...", "size": 312, ... }]
}
```

---

## 9. 서버 상태 확인 (HTTP)

MCP 도구 외에도 HTTP로 서버 상태를 직접 확인할 수 있습니다.

```
GET http://<서버IP>:8000/status
```

응답 예시:
```json
{
  "status": "ok",
  "server": "agent-auto-memo",
  "total_saves": 3,
  "recent_saves": [
    {
      "filename": "20260328-153000-React-18-핵심-정리.md",
      "path": "/data/workspace/obsidian/개발/React/...",
      "folder": "개발/React",
      "size": 312,
      "saved_at": "20260328-153000",
      "title": "React 18 핵심 정리",
      "url": "https://example.com/article"
    }
  ]
}
```

`total_saves`가 `save_memo` 호출 후 증가했다면 저장 성공입니다.

---

## 10. Claude와 다른 AI 에이전트의 동작 차이

### Claude (openclaw 포함)
- SSE 세션 1개로 `initialize` → `tool_call` → 응답 → 세션 종료 흐름
- `content` 파라미터에 정제된 마크다운을 직접 생성해서 전달
- Frontmatter를 포함한 구조화된 문서 작성 경향

### 다른 에이전트 (Codex 계열 등)
- 세션 수명이 더 짧을 수 있음 → 응답 수신 전 세션 종료 위험
- `content`를 URL만 전달하거나 매우 짧게 작성하는 경향
- Frontmatter 없이 단순 텍스트만 전달하는 경우 있음

**핵심:** `content`는 최종 저장될 마크다운 전문이어야 합니다.
URL만 전달하면 서버는 URL을 읽지 않습니다 — AI가 직접 읽고 정리해서 전달해야 합니다.

---

## 11. openclaw 전용 확인 절차

openclaw가 `save_memo` 사용 후 반드시 수행해야 할 확인 흐름:

```
1. save_memo 호출
2. 응답 대기 (세션 유지 필수)
3. 응답 텍스트에서 확인:
   - "✅ 메모 저장 완료" 포함 여부
   - "파일명: ..." 줄 파싱
   - "파일 크기: ... bytes" 확인 (0이면 실패)
4. (선택) get_last_save { "count": 1 } 호출로 이중 확인
5. 사용자에게 파일명과 저장 경로 포함해서 보고
```

서버 로그(`[call_tool] verified: ...`)가 남았다면 파일은 반드시 디스크에 존재합니다.
