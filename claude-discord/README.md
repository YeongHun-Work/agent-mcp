# claude-discord

Discord 봇과 Claude CLI를 연결한 프로젝트입니다.  
채널별 대화 컨텍스트를 SQLite에 저장하고, 채널에서 활성화한 MCP 스킬 설명을 프롬프트에 주입하여 Claude CLI에 전달합니다.

**대상 환경:** Odroid-XU4 (`linux/arm/v7`), Docker

## 파일 구성

```text
claude-discord/
├── bot.mjs               # 메인 봇 프로세스
├── deploy-commands.mjs   # 슬래시 명령어 수동 등록 스크립트
├── mcp-skills.json       # MCP 스킬 레지스트리
├── package.json
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── data/
    └── sessions.db       # SQLite 데이터베이스
```

## 동작 구조

```text
Discord
  -> bot.mjs (discord.js v14)
      -> SQLite (sessions, channel_skills)
      -> mcp-skills.json (name, description)
      -> spawn('claude', ['-p', prompt, '--no-session-persistence'])
```

현재 구현 기준 동작은 다음과 같습니다.

- 슬래시 명령어, 멘션, DM 메시지는 모두 같은 `askClaude()` 흐름으로 처리합니다.
- `mcp-skills.json`에 적힌 스킬은 이 봇 프로세스에서 실시간 MCP 연결을 수행하지 않습니다.
- 현재는 채널별로 활성화한 스킬의 `description`을 프롬프트 앞에 붙이는 방식입니다.
- Claude CLI가 빈 응답으로 끝나면 정상 응답으로 처리하지 않고 오류로 간주합니다.
- `--dangerously-skip-permissions` 옵션은 제거했습니다.

## 슬래시 명령어

| 명령어 | 설명 |
|---|---|
| `/ask question:<text>` | Claude에게 질문합니다. 주제, 히스토리, 활성 스킬 설명이 함께 전달됩니다. |
| `/topic set:<text>` | 현재 채널의 주제를 설정합니다. |
| `/history show` | 현재 채널의 대화 히스토리를 조회합니다. |
| `/history clear` | 현재 채널의 대화 히스토리를 초기화합니다. |
| `/skill list` | 사용 가능한 스킬 목록과 현재 채널의 활성 상태를 표시합니다. |
| `/skill on <name>` | 현재 채널에서 스킬을 활성화합니다. |
| `/skill off <name>` | 현재 채널에서 스킬을 비활성화합니다. |

멘션(`@ClaudeBot 질문`)과 DM도 `/ask`와 동일하게 처리됩니다.

## MCP 스킬 레지스트리

예시 `mcp-skills.json`:

```json
[
  {
    "name": "agent-auto-memo",
    "url": "http://{server_url}:8000/sse",
    "transport": "sse",
    "description": "Obsidian 메모 자동 저장. 사용자가 메모/기록을 요청하면 save_memo 툴 사용."
  }
]
```

현재 기준 참고사항:

- 런타임에서는 `name`, `description`을 사용합니다.
- `url`, `transport`는 운영 참고용 메타데이터입니다.
- `mcp-skills.json` 수정 후에는 재빌드 없이 `docker compose restart`만 하면 됩니다.

스킬 동작 흐름:

1. `/skill on agent-auto-memo`
2. 해당 채널의 `channel_skills` 테이블에 스킬 이름 저장
3. `/ask` 실행 시 해당 스킬의 설명을 Claude 프롬프트 앞에 주입

## 환경변수

`.env`:

```env
DISCORD_TOKEN=
CLIENT_ID=
GUILD_ID=
```

- `DISCORD_TOKEN`: Discord 봇 토큰
- `CLIENT_ID`: Discord 애플리케이션 ID
- `GUILD_ID`: 선택값. 설정하면 해당 길드에 슬래시 명령어가 즉시 등록됩니다.

## 영속 저장소

`docker-compose.yml` 기준으로 두 가지 저장소를 사용합니다.

- `./data:/app/data`
  SQLite 데이터베이스와 봇 데이터 저장
- `claude_auth:/home/node/.claude`
  Claude CLI 인증 정보를 Docker named volume으로 저장

이 프로젝트는 더 이상 Claude 인증 정보를 호스트 홈 디렉터리에서 bind mount 하지 않습니다.

## Claude CLI 인증 방법

이 프로젝트는 컨테이너 내부에서 Claude CLI OAuth 로그인 방식으로 인증합니다.

### 최초 인증

```bash
# 1. 원격 서버에 SSH 접속
ssh <사용자>@<서버IP>

# 2. 프로젝트 디렉터리로 이동
cd /data/volumes/agent-mcp-tools/claude-discord

# 3. 컨테이너 빌드 및 실행
docker compose up -d --build

# 4. 실행 중인 컨테이너 내부로 접속
docker exec -it claude-discord sh

# 5. Claude CLI 로그인 시작
claude
```

이후 동작:

- 브라우저가 자동으로 열리면 그 브라우저에서 로그인합니다.
- 서버가 headless 환경이면 Claude CLI가 로그인 URL을 출력합니다.
- 그 URL을 복사해서 로컬 PC 브라우저에서 열고 로그인하면 됩니다.
- 인증이 끝나면 컨테이너 안의 Claude CLI가 인증 상태를 유지합니다.

SSH 환경 기준으로 보면:

1. 로컬 PC 터미널에서 서버로 `ssh` 접속
2. 서버 셸에서 `docker exec -it claude-discord sh` 실행
3. 컨테이너 내부에서 `claude` 실행
4. 출력된 로그인 URL을 로컬 PC 브라우저에 붙여넣어 인증
5. 인증 완료 후 다시 SSH 세션으로 돌아와 계속 사용

### 인증 확인

컨테이너 내부에서 아래 명령으로 확인합니다.

```bash
claude -p "안녕"
```

정상이라면:

- Claude가 텍스트 응답을 출력해야 합니다.
- `stdout: 0` 상태로 끝나면 안 됩니다.

### 재인증

인증이 꼬였거나 만료된 경우:

```bash
docker exec -it claude-discord sh
claude
```

Claude 인증 볼륨을 완전히 초기화해야 하는 경우:

```bash
docker compose down
docker volume rm claude-discord_claude_auth
docker compose up -d --build
docker exec -it claude-discord sh
claude
```

## 배포 절차

### 1. 환경변수 설정

```bash
cp .env.example .env
```

`.env`에 다음 값을 입력합니다.

- `DISCORD_TOKEN`
- `CLIENT_ID`
- `GUILD_ID` 선택

### 2. 컨테이너 빌드 및 실행

```bash
docker compose up -d --build
```

### 3. Claude CLI 인증

```bash
docker exec -it claude-discord sh
claude
```

### 4. 로그 확인

```bash
docker compose logs -f
```

## 업데이트 방법

### 코드 변경 후

```bash
docker compose up -d --build
```

### 스킬 목록 변경 후

```bash
docker compose restart
```

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

현재 동작:

- 채널별로 대화 히스토리를 누적합니다.
- 컨텍스트가 60줄을 넘으면 Claude에게 12줄 요약을 요청합니다.
- Claude가 빈 응답을 반환하면 히스토리에 저장하지 않습니다.

## 트러블슈팅

| 증상 | 원인 | 조치 |
|---|---|---|
| `Claude CLI가 빈 응답으로 종료되었습니다` | 컨테이너 내부 인증 상태 누락 또는 손상 | `docker exec -it claude-discord sh` 후 `claude` 재로그인 |
| `claude -p "안녕"` 실행 시 아무 응답이 없음 | Claude 인증 볼륨 상태가 깨졌거나 만료됨 | 컨테이너 내부에서 재인증 |
| 슬래시 명령어가 바로 보이지 않음 | 전역 등록 지연 | `GUILD_ID`를 설정하고 재시작 |
| `SQLITE_CANTOPEN` | `data/` 권한 문제 | `./data` 권한 확인 |
| 멘션에 반응하지 않음 | Discord Message Content Intent 문제 | Discord Developer Portal에서 Message Content Intent 확인 |
