# Obsidian-mcp-tools (Linux Docker 기반)

## 프로젝트 개요
이 프로젝트는 URL과 내용(Content)을 입력받아 마크다운 형태의 파일로 자동 포맷팅한 뒤, `OBSIDIAN_LOCAL_REST_API`를 통해 로컬 Obsidian Vault의 지정된 폴더(기본값: `Memo`)에 즉시 저장해 주는 Python 기반 Obsidian-mcp-tools 입니다.

> 📝 **폴더 지정 팁:** 저장할 대상 폴더는 `.env`의 `OBSIDIAN_TARGET_FOLDER`를 통해 전역으로 지정할 수 있으며, AI 에이전트가 `save_memo` 도구를 호출할 때 `folder` 인자를 추가로 넘겨줘서 동적으로 다른 폴더에 저장하게 만들 수도 있습니다!

## 핵심 특징
- **미니멀 Linux (Alpine) 컨테이너**: 가장 가벼운 `python:3.11-alpine` 이미지를 기반으로 불필요한 OS 기능은 모두 제외하고 핵심 라이브러리만 담은 `Dockerfile` 구성을 완료했습니다.
- **Linux 네이티브 네트워크 대응**: 마련해둔 `docker-compose.yml`에는 `host-gateway` 설정이 들어가 있어, 최신 Linux용 Docker 환경에서도 Host 머신의 다른 포트(Obsidian 플러그인 등)에 원활히 접근할 수 있습니다.
- **듀얼 통신 (SSE & stdio) 지원**: OpenClaw 등 데스크톱 클라이언트에 직접 바이너리 파이프로 연결하는 `stdio` 모드와, 백그라운드 웹서버로 올려서 원격 통신하는 `SSE` 모드를 `.env` 파일 만으로 손쉽게 스위칭할 수 있습니다.

## 초기 설정 방법
1. 배포할 Linux 서버 디렉토리에서 `.env.example`을 복사해 `.env` 파일을 만듭니다.
2. Obsidian의 Local REST API 키(`OBSIDIAN_API_KEY`)를 복사해 넣습니다.
3. **네트워크 설정 팁**: Obsidian 플러그인이 같은 Linux Host 안에서 돌고 있다면 Base URL의 `host.docker.internal` 부분을 그대로 쓰시면 연결이 가능합니다. (만약 Obsidian은 윈도우 랩탑에 있고 Docker 서버만 별도의 리눅스에 위치한 상황이라면 해당 노트북의 고정 IP를 적어주시고 랩탑 방화벽에서 27124 포트를 열어야 합니다)
4. Obsidian 플러그인의 `Interface to listen on` 값이 `0.0.0.0`으로 개방되어 있는지 꼭 확인해주세요.

## 통합 실행 가이드

### 1. Docker Compose (추천! 가장 깔끔한 SSE 서버 상시 구동)
리눅스 쉘에서 아래 커맨드 하나면 빌드와 함께 백그라운드 상시 구동이 이루어집니다:
```bash
docker-compose up -d --build
```
컨테이너가 정상적으로 올라오면 OpenClaw나 원격 클라이언트에서 `http://<리눅스IP/로컬>:8000/sse` 엔드포인트로 MCP에 연결할 수 있게 됩니다.

### 2. 표준 입출력 (stdio) 모드로 Docker 직접 런타임 파이프 연결
원격지의 특정 AI 에이전트나 OpenClaw가 직접 명령어 라인에서 `stdio` 통신을 파이핑하도록 만드려면 다음과 같은 커맨드 프로필을 구성하면 됩니다. (단 이 경우 사전에 `docker build -t obsidian-mcp-tools .` 로 이미지가 빌드되어 있어야 합니다.)

- **Command**: `docker`
- **Args**: `run -i --rm --env-file ./.env obsidian-mcp-tools`

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

### 4. AI 에이전트 연동 및 사용 가이드 (OpenClaw 등)
서버가 구동되고 AI 클라이언트(OpenClaw, Claude Desktop 등)에 MCP 서버로 등록되었다면, 채팅창에서 자연어 명령만으로 메모를 저장할 수 있습니다.

**대화 요청 예시:**
> "다음 유튜브 링크를 요약해서 Obsidian에 저장해줘: https://youtu.be/..."
> "이 인프런 강의 링크(url)의 핵심 내용을 정리하고, `Memo/Inflearn` 폴더에 넣어줄래?"

**동작 결과:**
1. AI가 사용자의 요청과 URL 내용을 훌륭한 마크다운 문서로 분석/요약합니다.
2. AI가 백그라운드에서 `save_memo` 도구를 호출하며 `title`, `content`, `folder`(선택) 등의 데이터를 전달합니다.
3. 로컬 Obsidian Vault의 지정된 위치에 실시간으로 `.md` 파일이 생성되며 즉시 에디터에서 확인할 수 있습니다!
