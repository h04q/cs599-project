FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 系统依赖（git 用于 git_diff 工具）
RUN apt-get update && apt-get install -y --no-install-recommends \
        git \
        && rm -rf /var/lib/apt/lists/*

# 先装依赖以利用缓存层
COPY requirements.txt ./
RUN pip install -r requirements.txt

# 拷贝源码
COPY src ./src
COPY examples ./examples

# 非 root 用户运行
RUN useradd -m sentinel && chown -R sentinel:sentinel /app
USER sentinel

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--help"]
