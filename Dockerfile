# Solo la aplicacion Flask se ejecuta en Docker. Oracle XE queda en Windows.
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY . ./
EXPOSE 5000
CMD ["python", "server.py"]
