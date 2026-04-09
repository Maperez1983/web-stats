FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

# Render/Heroku-style platforms provide $PORT at runtime. Default to 8000 for local Docker usage.
CMD ["sh", "-c", "gunicorn webstats.wsgi:application --bind 0.0.0.0:${PORT:-8000}"]
