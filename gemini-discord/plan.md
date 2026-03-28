# Discord + Gemini CLI Bot Plan

## 1. 목표
- 슬래시/멘션/DM 지원 대화형 봇
- 채널별 주제·히스토리·MCP 스킬 유지 (SQLite)
- Gemini CLI 사용, Docker로 Odroid-XU4에서 경량·보안 실행
- MCP 서버(자체 개발)를 채널별로 활성화하여 Gemini가 툴로 활용

## 2. 명령 설계
- `/ask question:<text>` — Gemini에게 질문 (채널 컨텍스트 + 활성 스킬 포함)
- `/topic set:<text>` — 채널 대화 주제 설정
- `/history` — 채널 대화 히스토리 조회
- `/skill list` — 사용 가능한 MCP 스킬 목록 및 활성화 상태 조회
- `/skill on <name>` — 채널에 스킬 활성화
- `/skill off <name>` — 채널에서 스킬 비활성화
- 멘션/DM: `@봇 질문` 또는 DM 메시지 (Message Content Intent 없음)
- 추후 명령어 추가/수정 예정

## 3. 데이터 모델 (SQLite)

```sql
-- 채널별 대화 세션
sessions (
  channel_id  TEXT PRIMARY KEY,
  topic       TEXT,
  context     TEXT DEFAULT '',
  updated_at  INTEGER
)

-- 채널별 활성화된 MCP 스킬
channel_skills (
  channel_id  TEXT NOT NULL,
  skill_name  TEXT NOT NULL,
  PRIMARY KEY (channel_id, skill_name)
)
```

- 히스토리 60줄 초과 시 Gemini로 12줄 요약 압축

## 4. MCP 스킬 시스템

### 스킬 등록 (mcp-skills.json)
사용 가능한 MCP 스킬은 `mcp-skills.json`에 정적 정의:
```json
[
  {
    "name": "agent-auto-memo",
    "url": "http://192.168.0.100:8000/sse",
    "description": "Obsidian 메모 자동 저장. 사용자가 메모나 기록을 요청하면 save_memo 툴 사용."
  }
]
```

### 스킬 활성화 흐름
1. `/skill on agent-auto-memo` → `channel_skills` 테이블에 저장
2. `/ask` 또는 멘션 시 → 활성 스킬 목록 조회 → 프롬프트에 지침 주입
3. Gemini CLI가 `settings.json`에 등록된 MCP 서버 툴을 실제 호출

### Gemini CLI MCP 설정 (서버 ~/.gemini/settings.json)
```json
{
  "security": { "auth": { "selectedType": "oauth-personal" } },
  "mcpServers": {
    "agent-auto-memo": {
      "url": "http://192.168.0.100:8000/sse"
    }
  }
}
```

### 프롬프트 구성 순서
```
[활성 MCP 툴 지침]  ← 스킬 활성화 시 주입
[topic]
[이전 대화 context]
[질문]
```

## 5. 코드 구조

### bot.mjs
- intents: Guilds, GuildMessages, DirectMessages, MessageContent
- DB: sessions + channel_skills 테이블
- `loadSkills()` — mcp-skills.json 로드
- `getChannelSkills(channelId)` — 채널 활성 스킬 조회
- `setChannelSkill(channelId, name, enabled)` — 스킬 on/off
- `callGemini(prompt)` — spawn('gemini', ['--model', MODEL, '-p', prompt]) 10s timeout
- `askGemini(channelId, question)` — 스킬 지침 + 컨텍스트 포함 프롬프트 빌드
- `appendContext()` — 60줄 초과 시 Gemini로 12줄 압축
- handlers: InteractionCreate(/ask, /topic, /history, /skill), MessageCreate(멘션/DM)

### deploy-commands.mjs
- 슬래시 명령어 수동 등록 스크립트 (최초 1회 또는 명령어 변경 시)

## 6. 보안 조치
- Gemini CLI 버전 고정, spawn shell:false, 입력 4000자 제한
- Docker: USER node, read_only root fs, tmpfs:/tmp, cap_drop:ALL, no-new-privileges
- 비밀: .env → env_file로 주입
- Gemini 인증: OAuth (~/.gemini/ 볼륨 마운트, 쓰기 가능)

## 7. Docker 구성
- Dockerfile: node:22-bookworm-slim (arm/v7), sqlite3/python3/g++ 설치, @google/gemini-cli@0.35.1
- compose: read_only, volumes ./data:/app/data + ~/.gemini:/home/node/.gemini, env_file .env, tmpfs:/tmp, cap_drop:ALL

## 8. 운영 절차
1. `.env` 작성 (DISCORD_TOKEN, CLIENT_ID, GUILD_ID)
2. `~/.gemini/settings.json`에 mcpServers 등록 (서버)
3. `mcp-skills.json` 편집 (사용할 MCP 서버 추가)
4. `docker compose up -d --build`
5. `docker exec gemini-discord node deploy-commands.mjs` (최초 1회)
6. Discord에서 `/skill on <name>`으로 채널별 스킬 활성화

## 9. 권한
- 봇 코드에는 권한 설정 없음
- 초대 URL의 permissions 값과 서버 역할/채널 설정에서 관리
