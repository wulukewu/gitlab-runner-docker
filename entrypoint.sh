#!/bin/sh
set -e

# ── Required ──
if [ -z "$RUNNER_TOKEN" ]; then
  echo "ERROR: RUNNER_TOKEN is required"
  exit 1
fi

# ── Defaults ──
GITLAB_URL="${GITLAB_URL:-https://gitlab.com}"
RUNNER_NAME="${RUNNER_NAME:-gitlab-runner}"
RUNNER_EXECUTOR="${RUNNER_EXECUTOR:-shell}"
RUNNER_DOCKER_IMAGE="${RUNNER_DOCKER_IMAGE:-docker:24.0.5}"
RUNNER_DOCKER_PRIVILEGED="${RUNNER_DOCKER_PRIVILEGED:-true}"
RUNNER_CONCURRENT="${RUNNER_CONCURRENT:-4}"
RUNNER_CHECK_INTERVAL="${RUNNER_CHECK_INTERVAL:-0}"
RUNNER_DOCKER_VOLUMES="${RUNNER_DOCKER_VOLUMES:-/var/run/docker.sock:/var/run/docker.sock,/cache,/certs/client}"
RUNNER_DOCKER_SHM_SIZE="${RUNNER_DOCKER_SHM_SIZE:-0}"
RUNNER_TLS_VERIFY="${RUNNER_TLS_VERIFY:-false}"

CONFIG_FILE="/etc/gitlab-runner/config.toml"
mkdir -p /etc/gitlab-runner

# ── Build Docker volumes array ──
VOLUMES=""
OLD_IFS="$IFS"
IFS=','
for vol in $RUNNER_DOCKER_VOLUMES; do
  VOLUMES="${VOLUMES}\"${vol}\", "
done
IFS="$OLD_IFS"
VOLUMES="[${VOLUMES%, }]"

# ── Write config header ──
cat > "$CONFIG_FILE" <<EOF
concurrent = ${RUNNER_CONCURRENT}
check_interval = ${RUNNER_CHECK_INTERVAL}
shutdown_timeout = 0

[session_server]
  session_timeout = 1800
EOF

# ── Write [[runners]] sections ──
# Supports comma-separated tokens: RUNNER_TOKEN=glrt-aaa,glrt-bbb,glrt-ccc
COUNTER=1
OLD_IFS="$IFS"
IFS=','
for token in $RUNNER_TOKEN; do
  # Trim whitespace
  token=$(echo "$token" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

  cat >> "$CONFIG_FILE" <<EOF

[[runners]]
  name = "${RUNNER_NAME}-${COUNTER}"
  url = "${GITLAB_URL}"
  token = "${token}"
  executor = "${RUNNER_EXECUTOR}"
EOF

  # Docker executor settings
  if [ "$RUNNER_EXECUTOR" = "docker" ]; then
    cat >> "$CONFIG_FILE" <<EOF
  [runners.docker]
    tls_verify = ${RUNNER_TLS_VERIFY}
    image = "${RUNNER_DOCKER_IMAGE}"
    privileged = ${RUNNER_DOCKER_PRIVILEGED}
    disable_entrypoint_overwrite = false
    oom_kill_disable = false
    disable_cache = false
    volumes = ${VOLUMES}
    shm_size = ${RUNNER_DOCKER_SHM_SIZE}
EOF
  fi

  cat >> "$CONFIG_FILE" <<EOF
  [runners.cache]
    MaxUploadedArchiveSize = 0
EOF

  COUNTER=$((COUNTER + 1))
done
IFS="$OLD_IFS"

echo "========== Generated config.toml =========="
cat "$CONFIG_FILE"
echo "============================================"

# ── Export RUNNER_SYSTEM_ID to keep it consistent ──
export RUNNER_SYSTEM_ID="runner-$(echo "${RUNNER_NAME}-${DASHBOARD_PORT:-8080}" | md5sum | cut -c1-12)"

# ── Start supervisord (manages runner + dashboard) ──
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
