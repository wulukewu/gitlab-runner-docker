# GitLab Runner Docker with Dashboard

A highly customizable GitLab Runner setup packaged in a Docker container, featuring automatic configuration generation and a built-in status dashboard.

## Features

- **Multi-Token Support**: Register and run multiple GitLab Runners using a comma-separated list of tokens.
- **Auto-Configuration**: Generates `config.toml` dynamically from environment variables on startup.
- **Built-in Dashboard**: A lightweight Python-based dashboard to monitor runner status and jobs.
- **Supervisor Managed**: Ensures both the GitLab Runner and the dashboard stay running.
- **Docker-in-Docker Ready**: Pre-configured for Docker executor with socket mounting.
- **Cloud Ready**: Optimized for deployment on platforms like Render or local Docker environments.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/)
- [Docker Compose](https://docs.docker.com/compose/install/)
- GitLab Runner Registration Token (obtain from your GitLab project/group/instance settings)

## Quick Start

1. **Clone the repository:**
   ```bash
   git clone git@github.com:wulukewu/gitlab-runner-docker.git
   cd gitlab-runner-docker
   ```

2. **Configure Environment:**
   Copy the example environment file and fill in your details:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` and set at least the `RUNNER_TOKEN`.

3. **Start the Runner:**
   ```bash
   docker-compose up -d
   ```

4. **Access the Dashboard:**
   Open your browser and navigate to `http://localhost:8080`.

## Configuration

The following environment variables can be configured in your `.env` file:

| Variable | Description | Default |
|----------|-------------|---------|
| `RUNNER_TOKEN` | **Required**. One or more runner tokens (comma-separated). | - |
| `GITLAB_API_TOKEN` | Personal Access Token with `read_api` for the dashboard. | - |
| `GITLAB_URL` | Your GitLab instance URL. | `https://gitlab.com` |
| `RUNNER_NAME` | Base name for the runners. | `gitlab-runner` |
| `RUNNER_EXECUTOR` | Runner executor type (e.g., `shell`, `docker`). | `shell` |
| `RUNNER_CONCURRENT` | Maximum number of parallel jobs across all runners. | `4` |
| `DASHBOARD_PORT` | Port for the status dashboard. | `8080` |

### Docker Executor Settings
If `RUNNER_EXECUTOR=docker` is used:
- `RUNNER_DOCKER_IMAGE`: Default Docker image (default: `docker:24.0.5`).
- `RUNNER_DOCKER_PRIVILEGED`: Enable privileged mode (default: `true`).

## Dashboard

The dashboard provides a visual overview of your runner's status. It uses the GitLab API to fetch real-time data about the registered runners and their current activity.

To enable the dashboard's API features, ensure `GITLAB_API_TOKEN` is set with appropriate permissions.

## Architecture

- **`Dockerfile`**: Inherits from `gitlab/gitlab-runner:latest`, adds Python 3 and Supervisor.
- **`entrypoint.sh`**: The brain of the setup. It parses environment variables and templates the `config.toml`.
- **`supervisord.conf`**: Process manager that handles the lifecycle of both the runner and the dashboard.
- **`dashboard/`**: Contains the status page and the Python server.
