FROM python:3.12-slim

# System deps for Playwright (chromium) and psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright chromium with its OS-level dependencies
RUN playwright install --with-deps chromium

COPY . .

EXPOSE 5001

CMD ["python", "web/app.py"]
