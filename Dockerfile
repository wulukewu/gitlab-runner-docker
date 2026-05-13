FROM gitlab/gitlab-runner:latest

RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 supervisor && \
    rm -rf /var/lib/apt/lists/*

COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf
COPY entrypoint.sh /entrypoint.sh
COPY dashboard/ /opt/dashboard/

RUN chmod +x /entrypoint.sh

EXPOSE 8080

ENTRYPOINT ["/entrypoint.sh"]
