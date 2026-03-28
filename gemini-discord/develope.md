# gemini-discord 개발 문서

## 프로젝트 개요
Discord 봇 + Gemini CLI + MCP 스킬 통합 시스템.
채널별 대화 컨텍스트를 SQLite로 유지하고, MCP 서버(자체 개발)를 스킬로 등록해 Gemini가 툴로 활용할 수 있도록 구성.

**실행 환경:** Odroid-XU4 (linux/arm/v7), Docker

---

## 파일 구조

```
gemini-discord/
├── bot.mjs               # 메인 봇 코드
├── deploy-commands.mjs   # 슬래시 명령어 수동 등록 스크립트
├── mcp-skills.json       # 사용 가능한 MCP 스킬 목록 정의
├── package.json          # Node.js 의존성
├── Dockerfile            # Docker 이미지 빌드 설정
├── docker-compose.yml    # 컨테이너 실행 설정
├── .env                  # 환경변수 (Git 제외)
├── .env.example          # 환경변수 템플릿
├── plan.md               # 설계 문서
└── data/                 # 볼륨 마운트 (SQLite DB 저장)
    └── sessions.db
```

---

## 아키텍처

```
Discord
  │
  ▼
bot.mjs (discord.js v14)
  │
  ├── SQLite (better-sqlite3)
  │     ├── sessions        — 채널별 topic, context
  │     └── channel_skills  — 채널별 활성 MCP 스킬
  │
  ├── mcp-skills.json       — 스킬 레지스트리 (name, url, description)
  │
  └── Gemini CLI (spawn, shell:false)
        │
        └── ~/.gemini/settings.json의 mcpServers로 MCP 서버 직접 호출
```

### 프롬프트 구성 순서
```
[활성 MCP 툴 지침]   ← /skill on 으로 활성화된 스킬
[topic]              ← /topic set 으로 설정된 주제
[이전 대화 context]  ← SQLite에 누적된 대화 히스토리
[질문]
```

---

## SQLite 스키마

```sql
CREATE TABLE sessions (
  channel_id  TEXT PRIMARY KEY,
  topic       TEXT,
  context     TEXT DEFAULT '',
  updated_at  INTEGER
);

CREATE TABLE channel_skills (
  channel_id  TEXT NOT NULL,
  skill_name  TEXT NOT NULL,
  PRIMARY KEY (channel_id, skill_name)
);
```

- context 60줄 초과 시 Gemini로 12줄 요약 압축

---

## 슬래시 명령어

| 명령어 | 설명 |
|--------|------|
| `/ask question:<text>` | Gemini에게 질문 (컨텍스트 + 활성 스킬 포함) |
| `/topic set:<text>` | 채널 대화 주제 설정 |
| `/history` | 채널 대화 히스토리 조회 |
| `/skill list` | 스킬 목록 및 이 채널의 활성화 상태 조회 |
| `/skill on <name>` | 채널에 MCP 스킬 활성화 |
| `/skill off <name>` | 채널에서 MCP 스킬 비활성화 |

멘션(`@봇 질문`) 및 DM도 `/ask`와 동일하게 처리됨.

---

## MCP 스킬 시스템

### 스킬 등록 (mcp-skills.json)
새로운 MCP 서버를 스킬로 추가하려면 `mcp-skills.json`에 항목 추가 후 컨테이너 재시작:
```json
[
  {
    "name": "agent-auto-memo",
    "url": "http://192.168.0.100:8000/sse",
    "description": "Obsidian 메모 자동 저장. 사용자가 메모/기록을 요청하면 save_memo 툴 사용."
  }
]
```

### Gemini CLI MCP 설정 (서버 ~/.gemini/settings.json)
Gemini CLI가 실제로 MCP 툴을 호출하려면 settings.json에 mcpServers 등록 필요:
```json
{
  "security": {
    "auth": { "selectedType": "oauth-personal" }
  },
  "mcpServers": {
    "agent-auto-memo": {
      "url": "http://192.168.0.100:8000/sse"
    }
  }
}
```

### 스킬 동작 흐름
1. `/skill on agent-auto-memo` → `channel_skills` 테이블에 저장
2. 사용자 질문 시 → 활성 스킬의 description을 프롬프트 앞에 주입
3. Gemini CLI가 settings.json의 mcpServers를 통해 실제 툴 호출

---

## 환경변수 (.env)

```env
DISCORD_TOKEN=   # Discord Developer Portal > Bot > Token
CLIENT_ID=       # Discord Developer Portal > General Information > Application ID
GUILD_ID=        # (선택) 길드 ID — 설정 시 해당 서버에만 즉시 명령어 등록
```

---

## Docker 구성

### Dockerfile 주요 설정
- 베이스: `node:22-bookworm-slim` (linux/arm/v7)
- 빌드 도구: `python3`, `make`, `g++`, `sqlite3` (better-sqlite3 네이티브 빌드용)
- Gemini CLI: `@google/gemini-cli@0.35.1` 전역 설치
- 실행 유저: `node` (비루트)

### docker-compose.yml 보안 설정
```yaml
read_only: true          # 루트 파일시스템 읽기 전용
tmpfs: [/tmp]            # 임시 파일용 tmpfs
cap_drop: [ALL]          # 모든 Linux Capabilities 제거
security_opt:
  - no-new-privileges:true  # 권한 상승 차단
volumes:
  - ./data:/app/data                      # SQLite DB 영속화
  - ~/.gemini:/home/node/.gemini          # Gemini OAuth 인증 마운트 (쓰기 가능 — 토큰 자동 갱신)
  - ./mcp-skills.json:/app/mcp-skills.json:ro  # MCP 스킬 목록 (재빌드 없이 수정 반영)
```

> **주의:** `~/.gemini` 볼륨은 `:ro` 없이 마운트해야 합니다. OAuth access_token 만료 시 CLI가 refresh_token으로 자동 갱신하며 파일에 씁니다. `:ro`이면 갱신 실패로 인증 오류 발생.

---

## 배포 절차

### 최초 배포
```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 편집 (DISCORD_TOKEN, CLIENT_ID, GUILD_ID)

# 2. 데이터 디렉토리 생성
mkdir -p data

# 3. Gemini 인증 (로컬 Windows에서)
gemini -p "hello"   # 인증 및 토큰 갱신
scp C:\Users\{user}\.gemini\oauth_creds.json root@192.168.0.100:/root/.gemini/
scp C:\Users\{user}\.gemini\google_accounts.json root@192.168.0.100:/root/.gemini/
scp C:\Users\{user}\.gemini\installation_id root@192.168.0.100:/root/.gemini/
scp C:\Users\{user}\.gemini\settings.json root@192.168.0.100:/root/.gemini/

# 4. 서버 ~/.gemini/settings.json에 mcpServers 추가

# 5. 빌드 및 실행
docker compose up -d --build

# 6. 슬래시 명령어 등록 (최초 1회)
docker exec gemini-discord node deploy-commands.mjs
```

### 코드 업데이트 후
```bash
docker compose up -d --build
```

### 로그 확인
```bash
docker compose logs -f
docker logs gemini-discord --tail 50
```

---

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `SQLITE_CANTOPEN` | `data/` 디렉토리 없거나 권한 없음 | `mkdir -p data && chown odroid:odroid data` |
| `Please set an Auth method` | settings.json 버전 불일치 또는 `"model":{"name":"--persist"}` 오염 | 서버에서 settings.json을 auth 항목만 남기고 재작성 |
| OAuth 토큰 자동 갱신 안 됨 | 볼륨이 `:ro`로 마운트됨 | docker-compose.yml에서 `:ro` 제거 |
| `ModelNotFoundError` | settings.json에 잘못된 model 항목 있음 | settings.json에서 `"model"` 키 제거 후 컨테이너 재시작 |
| 슬래시 명령어 미등록 | CLIENT_ID 미설정 또는 등록 미실행 | `.env`에 CLIENT_ID 추가 후 `docker exec gemini-discord node deploy-commands.mjs` |
| MCP 툴이 호출 안 됨 | settings.json에 mcpServers 미등록 | 서버 `~/.gemini/settings.json`에 mcpServers 추가 |
| Gemini 응답 타임아웃 | 응답 생성 시간이 10초 초과 | `GEMINI_TIMEOUT_MS` 값 확인 (현재 180,000ms = 3분) |

---

## 연관 프로젝트

| 프로젝트 | 위치 | 역할 |
|----------|------|------|
| agent-auto-memo | `../agent-auto-memo` | Obsidian 메모 저장 MCP 서버 (SSE, port 8000) |
