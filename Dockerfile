FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY harness/ ./harness/
COPY llm/ ./llm/
COPY pipeline/ ./pipeline/
COPY cases/ ./cases/
COPY evalsets/ ./evalsets/
COPY reports/ ./reports/
COPY webapp/ ./webapp/
COPY scripts/ ./scripts/

# 以非 root 运行:即使容器被攻破也难以篡改宿主机文件;
# 数据卷由 compose 挂载,宿主目录需对 UID 1000 可写
RUN useradd --uid 1000 --create-home harness && chown -R harness:harness /app
USER harness

ENV HOST=0.0.0.0 PORT=8765 PYTHONUNBUFFERED=1
EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/api/health', timeout=4).status == 200 else 1)"

# 建议运行时注入:AUTH_TOKEN=<强随机串>(公网必须开启 API 令牌鉴权)
CMD ["python", "webapp/app.py"]
