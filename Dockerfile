FROM python:3.13-slim
WORKDIR /app
COPY app /app/app
USER 65534:65534
EXPOSE 8080
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HUB_MODE=demo
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"
CMD ["python", "-m", "app.server", "--host", "0.0.0.0", "--port", "8080"]
