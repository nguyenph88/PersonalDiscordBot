FROM python:3.10-slim
LABEL maintainer="AlexFlipnote <root@alexflipnote.dev>"

LABEL build_date="2022-04-25"

# Install system dependencies
RUN apt-get update && apt-get upgrade -y && \
    apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /discord_bot

# Copy requirements first for better caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

CMD ["python", "-u", "index.py"]
