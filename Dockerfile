# Stage 1: Build releaser-pleaser from source
FROM golang:1.24-alpine AS builder
RUN apk add --no-cache git
RUN git clone --depth 1 --branch v0.7.1 https://github.com/apricote/releaser-pleaser.git /src
WORKDIR /src
RUN go build -o /go/bin/rp ./cmd/rp

# Stage 2: Main image
FROM gitlab/gitlab-runner:latest

# Install Python3, Supervisor, Node.js 20, and git (needed by npm/releaser-pleaser)
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 supervisor curl ca-certificates gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Copy the compiled rp binary from the builder stage
COPY --from=builder /go/bin/rp /usr/local/bin/rp

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
COPY dashboard/ /opt/dashboard/

RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
