FROM python:3.12-alpine

WORKDIR /app

RUN apk add --no-cache \
    bash \
    curl \
    openssl \
    bind-tools \
    iputils \
    tailscale \
    sudo

COPY web/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/

EXPOSE 29485

CMD ["python", "web/app.py"]
