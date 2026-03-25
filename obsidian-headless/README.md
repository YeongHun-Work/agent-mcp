# Obsidian Headless CLI 서버 설정

이 디렉토리는 Obsidian을 Headless(GUI 없이 CLI/백그라운드 전용) 모드로 실행하기 위한 Docker 설정을 포함하고 있습니다.

## 주요 기능
- **공식 CLI (가정)**: 백그라운드에서 노트를 주기적으로 동기화 
- **Local REST API 연동**: 외부(다른 컨테이너, n8n, AI Agent 등)에서 HTTP API로 Vault의 노트를 읽고 쓸 수 있도록 개방
- **호스트 마운트**: 호스트 서버의 `/data/workspace/obsidian/` 경로를 Vault로 사용하여 안전하게 관리

## 디렉토리 구조
```text
obsidian-headless/
├── docker-compose.yml       # 컨테이너 실행 설정 파일
├── .env.example             # 환경 변수 템플릿 (본인의 정보로 .env 파일 생성 필요)
├── plugin-config-example/   # Local REST API 플러그인 설정 예시
└── README.md                # 설명서
```

## 시작하기

1. **환경 변수 설정**: `.env.example` 파일을 복사하여 `.env` 파일을 만들고, 필요한 정보를 입력합니다.
   ```bash
   cp .env.example .env
   # .env 파일 편집
   ```

2. **컨테이너 실행**:
   ```bash
   docker compose up -d
   ```

## ⚠️ Local REST API 바인딩 호스트 설정 (중요)

기본적으로 `obsidian-local-rest-api` 플러그인은 보안을 위해 `127.0.0.1`에서만 접근 스크립트를 허용합니다. Docker 환경에서는 외부에서 API에 접근해야 하므로, 이 값을 반드시 `0.0.0.0`으로 변경해야 합니다.

플러그인 설정 파일 경로 (호스트 기준):
`/data/workspace/obsidian/.obsidian/plugins/obsidian-local-rest-api/data.json`

설정 파일 내용 예시 (위 경로가 없다면 폴더 생성 후 아래의 형식으로 저장):
```json
{
  "port": 27123,
  "insecurePort": 27124,
  "enableInsecureServer": false,
  "apiKey": "본인의_보안_API키_입력",
  "crypto": {
    "cert": "인증서_내용",
    "publicKey": "공개키_내용",
    "privateKey": "비밀키_내용"
  },
  "host": "0.0.0.0"  // <-- 이 부분을 반드시 추가/변경해야 합니다!
}
```

## 사용 시나리오 논의
현재 이 설정에 MCP(Model Context Protocol) 서버를 연동할지, n8n 등의 자동화 툴과 연결할지, 아니면 자체 AI 에이전트와 통신할지에 따라 최적화 방법(예: 같은 Docker 네트워크로 묶기 등)이 달라질 수 있습니다. 

원하시는 특정 시나리오가 있다면 추가로 알려주시면 맞춤 설정을 안내해 드릴 수 있습니다.
