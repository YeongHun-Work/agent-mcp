# 경량 Debian 기반 Python 3.11 이미지 (ARM 환경 패키지 설치 호환성 보장)
FROM python:3.11-slim

# 컨테이너 내 작업 디렉토리 설정
WORKDIR /app

# 파이썬 출력 버퍼링 비활성화 (stdio 통신 시 딜레이 방지)
ENV PYTHONUNBUFFERED=1

# 필요 패키지 명세 복사 및 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 서버 핵심 로직 파일 복사
COPY server.py .

# 컨테이너 구동 기본 커맨드
# OpenClaw(Docker CLI 연동)이든 Docker-Compose(SSE)이든 동일하게 실행됩니다.
CMD ["python", "server.py"]
