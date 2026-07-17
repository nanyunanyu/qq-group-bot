FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY qq_bot/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && useradd --create-home --uid 10001 bot

COPY room_bot /app/room_bot
COPY qq_bot /app/qq_bot

USER bot

CMD ["python", "-m", "qq_bot"]