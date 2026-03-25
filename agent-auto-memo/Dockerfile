# 경량 Debian 기반 Python 3.11 이미지 (ARM 환경 패키지 설치 호환성 보장)
FROM python:3.11-slim

# 컨테이너 내 작업 디렉토리 설정
WORKDIR /app

# 파이썬 출력 버퍼링 비활성화 (stdio 통신 시 딜레이 방지)
ENV PYTHONUNBUFFERED=1

# ODROID(armv7l 등 32/64비트 ARM) 빌드 에러 방지를 위한 핵심 빌드 툴 사전 설치
# gcc, cffi 통과를 위한 libffi-dev, 그리고 Rust 기반 패키지(pydantic-core 등)를 위한 rustc/cargo 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libffi-dev \
    python3-dev \
    make \
    rustc \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# 필요 패키지 명세 복사 및 설치
COPY requirements.txt .

# ARM 기기에서 빌드 시간을 획기적으로 줄이고 호환성을 높이기 위해 라즈베리파이(piwheels) 인덱스 교차 사용
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --extra-index-url https://www.piwheels.org/simple -r requirements.txt

# 서버 핵심 로직 파일 복사
COPY server.py .

# 컨테이너 구동 기본 커맨드
CMD ["python", "server.py"]
