FROM python:3.11-slim

# Prevent Python from writing .pyc files & enable unbuffered stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies required for cryptography, mariadb, netmiko
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    mariadb-client \
    libmariadb-dev \
    pkg-config \
    openssh-client \
    && rm -rf /var/lib/apt/lists/*

# Copy and install python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy backend source code
COPY . /app

RUN groupadd --gid 10001 omnieye && \
    useradd --uid 10001 --gid omnieye --create-home --shell /usr/sbin/nologin omnieye && \
    mkdir -p /home/omnieye/.ssh && \
    chown -R omnieye:omnieye /home/omnieye

USER 10001:10001

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
