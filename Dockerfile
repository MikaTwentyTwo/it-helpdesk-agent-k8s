FROM python:3.13-slim

WORKDIR /app

COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock

COPY app app
COPY prompts prompts
COPY skills skills
COPY knowledge knowledge

RUN useradd --uid 10001 --create-home agent \
    && mkdir -p /app/data \
    && chown agent:agent /app/data

USER 10001

EXPOSE 8080

CMD ["python", "-m", "uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8080"]
