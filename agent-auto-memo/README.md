# agent-auto-memo (Linux Docker 기반)

## 프로젝트 개요
이 프로젝트는 URL과 내용(Content)을 입력받아 마크다운 형태의 파일로 자동 포맷팅한 뒤, 권한이 부여된 지정 폴더(Volume Mount 또는 로컬 경로) 내의 대상 폴더(기본값: `memo`)에 직접 `.md` 파일을 생성하고 저장해 주는 Python 기반 agent-auto-memo 입니다.

> 📝 **폴더 지정 팁:** 저장할 대상 폴더는 `.env`의 `OBSIDIAN_TARGET_FOLDER`를 통해 전역으로 지정할 수 있으며, AI 에이전트가 `save_memo` 도구를 호출할 때 `folder` 인자를 추가로 넘겨줘서 동적으로 다른 하위 폴더에 저장하게 만들 수도 있습니다!

## 핵심 특징
- **미니멀 Linux (Alpine) 컨테이너**: 가장 가벼운 `python:3.11-alpine` 이미지를 기반으로 불필요한 OS 기능은 모두 제외하고 핵심 라이브러리만 담은 `Dockerfile` 구성을 완료했습니다.
- **다이렉트 파일 시스템 로직 설계**: 불안정한 API 통신이나 복잡한 인증 절차 대신 호스트 디렉토리를 볼륨으로 매핑하여 즉각적이고 안정적인 파일 쓰기를 지원합니다.
- **듀얼 통신 (SSE & stdio) 지원**: OpenClaw 등 데스크톱 클라이언트에 직접 바이너리 파이프로 연결하는 `stdio` 모드와, 백그라운드 웹서버로 올려서 원격 통신하는 `SSE` 모드를 `.env` 파일 만으로 손쉽게 스위칭할 수 있습니다.

## 초기 설정 방법
1. 배포할 Linux 서버 디렉토리에서 `.env.example`을 복사해 `.env` 파일을 만듭니다.
2. 마크다운 파일이 직접 저장될 상위 디렉토리(보통 옵시디언 볼트 루트)의 절대 경로를 `OBSIDIAN_VAULT_PATH`에 기록합니다.
3. `docker-compose.yml` 파일을 열고, `volumes` 영역의 `/path/to/your/obsidian/vault` 부분을 `.env`에 적었던 실제 절대 경로와 일치시켜 마운트해 줍니다. (예: `/data/workspace/obsidian:/data/workspace/obsidian`)

## 통합 실행 가이드

### 1. Docker Compose (추천! 가장 깔끔한 SSE 서버 상시 구동)
리눅스 쉘에서 아래 커맨드 하나면 빌드와 함께 백그라운드 상시 구동이 이루어집니다:
```bash
docker compose up -d --build
```
컨테이너가 정상적으로 올라오면 클라이언트에서 아래 엔드포인트 중 하나로 연결할 수 있습니다.

### 2. 연결 방식 선택

#### 방식 A: MCP Streamable HTTP (신규 — 최신 클라이언트 권장)
OpenClaw 등 최신 MCP 클라이언트는 SSE 대신 단일 HTTP 트랜잭션 방식을 사용합니다.
- **URL**: `http://<서버IP>:8000/mcp`
- SSE 연결을 유지할 필요 없음, 요청/응답이 하나의 HTTP 요청으로 처리

#### 방식 B: MCP SSE (기존 — Claude Desktop 등 호환)
- **URL**: `http://<서버IP>:8000/sse`

#### 방식 C: REST API (HTTP 툴로 직접 호출)
MCP 없이 HTTP 툴로 직접 저장 가능합니다.
```bash
# 메모 저장
POST http://<서버IP>:8000/api/save-memo
Content-Type: application/json
{ "title": "제목", "url": "https://...", "content": "내용", "folder": "폴더명" }

# 최근 저장 조회
GET http://<서버IP>:8000/api/last-save?count=1
```

#### 방식 D: STDIO 파이프 (네트워크 없이 직접 연결)
컨테이너가 실행 중일 때 stdio 프로세스로 직접 연결:
- **Command**: `docker`
- **Args**: `exec -i agent-auto-memo python server.py --stdio`

### 3. (옵션) 순수 Linux 로컬 구동 (가상환경 활용)
만약 모종의 이유로 컨테이너를 올리지 않고 바로 Linux 쉘 환경에서 돌려보고 싶다면 아래 스크립트들을 사용하세요:
```bash
# 실행 권한 부여
chmod +x *.sh

# 설치 (최초 1회 설정 시 venv 생성 및 pip 인스톨 동작)
./install.sh

# 실행
./run-sse.sh  # (또는 ./run-stdio.sh)
```

### 4. AI 에이전트 연동 이후 활용 가이드 🤖 (프롬프트 예시)
이 MCP 서버가 클라이언트(OpenClaw, Claude Desktop 등)에 정상적으로 연결되면, AI는 내부적으로 `save_memo`라는 단일 도구를 갖게 됩니다. 이제부터 복잡한 클릭 없이 **"채팅창에 자연어로 치기만 하면"** AI가 알아서 옵시디언(Obsidian) 폴더에 예쁘게 포맷팅된 마크다운 파일을 생성해 줍니다!

#### 💡 활용 모델 및 프롬프트(명령어) 예시 모음
아래 예시들처럼 AI에게 지시해 보세요. AI가 URL을 읽고 분석한 뒤 알아서 도구를 호출해 파일을 저장합니다.

* **1. 유튜브/강의 요약 노트 작성 필기봇**
  * > "다음 유튜브 링크의 내용을 핵심 요약하고, `강의노트/유튜브` 폴더에 마크다운으로 저장해 줘: https://youtu.be/..."
  * > "이 인프런 강의 링크를 읽고, 중요한 내용만 테이블 형태로 정리해서 `공부/개발/Python` 경로에 저장해 줄래?"

* **2. 웹스크랩 및 북마크 자동 아카이빙**
  * > "내가 던져주는 뉴스 기사 URL들을 읽고, 가장 중요한 세 줄 요약과 본문 링크를 `스크랩/뉴스` 폴더에 스크랩해 줘. (주소: https://n.news.naver.com/...)"
  * > "이 사이트(URL)의 공식 문서를 한글로 번역한 뒤에, 예제 코드만 뽑아서 파일로 만들어줘."

* **3. 리서치 조사 자료 자동 정리**
  * > "아래 3개의 블로그 링크들을 싹 다 읽은 다음에, 'React vs Vue 장단점 비교'라는 주제로 하나의 완벽한 마크다운 리포트를 작성해서 내 옵시디언에 생성해 놔."

#### 🛠️ AI 내부 동작 프로세스
1. **이해 & 정보 수집:** AI가 사용자의 지시를 받고, 해당 웹 주소의 텍스트(강의, 뉴스, 블로그 등)를 스스로 읽어냅니다.
2. **포맷팅 (Markdown):** 수집한 텍스트를 가장 가독성 좋은 구조(제목, 목록, 코드블럭 등)의 마크다운 내용(`content`)으로 재가공합니다.
3. **도구 호출 (MCP `save_memo`):** AI가 스스로 재가공한 데이터와 함께 파일 제목(`title`), 저장할 위치(`folder`) 정보를 담아 `agent-auto-memo` 서버에 전송합니다.
4. **결과 확인:** 내 PC의 옵시디언 지정 폴더(`OBSIDIAN_VAULT_PATH`)에 파일이 **실시간으로 툭!** 하고 자동으로 생성됩니다.


