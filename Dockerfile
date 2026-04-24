FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
      build-essential libpq-dev \
      libcairo2 libpango-1.0-0 libpangocairo-1.0-0 libpangoft2-1.0-0 \
      libgdk-pixbuf-2.0-0 libffi-dev libjpeg62-turbo libopenjp2-7 \
      libharfbuzz0b libharfbuzz-subset0 shared-mime-info fontconfig fonts-dejavu-core \
      poppler-utils \
      ffmpeg \
      tesseract-ocr tesseract-ocr-spa \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/

EXPOSE 8000

RUN chmod +x /app/start.sh

# Render/Heroku-style platforms provide $PORT at runtime. Default to 8000 for local Docker usage.
CMD ["/app/start.sh"]
