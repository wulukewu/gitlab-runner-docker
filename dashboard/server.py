#!/usr/bin/env python3
"""GitLab Runner Dashboard — lightweight API proxy + static file server."""

import http.server
import json
import os
import urllib.request
import urllib.error
from pathlib import Path

GITLAB_URL = os.environ.get('GITLAB_URL', 'https://gitlab.com').rstrip('/')
GITLAB_API_TOKEN = os.environ.get('GITLAB_API_TOKEN', '')
GITLAB_GROUP_ID = os.environ.get('GITLAB_GROUP_ID', '')
PORT = int(os.environ.get('DASHBOARD_PORT', os.environ.get('PORT', '8080')))
DASHBOARD_DIR = str(Path(__file__).parent)


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_GET(self):
        if self.path == '/health':
            self._health()
        elif self.path.startswith('/api/'):
            self._proxy_gitlab()
        else:
            super().do_GET()

    def _health(self):
        """Return local config info for the dashboard."""
        info = {
            'concurrent': int(os.environ.get('RUNNER_CONCURRENT', '4')),
            'executor': os.environ.get('RUNNER_EXECUTOR', 'shell'),
            'gitlab_url': GITLAB_URL,
            'gitlab_group_id': GITLAB_GROUP_ID,
            'runner_name': os.environ.get('RUNNER_NAME', 'gitlab-runner'),
        }
        self._json_response(200, info)

    def _proxy_gitlab(self):
        """Forward /api/... to GitLab REST API."""
        api_path = self.path[4:]  # strip leading /api

        # If GITLAB_GROUP_ID is set, redirect /runners to /groups/{id}/runners
        if GITLAB_GROUP_ID and api_path.startswith('/runners'):
            query = ''
            if '?' in api_path:
                api_path, query = api_path.split('?', 1)
                query = '?' + query
            
            if api_path == '/runners':
                api_path = f'/groups/{GITLAB_GROUP_ID}/runners{query}'
            else:
                # keep original path for /runners/{id} etc.
                api_path = api_path + query

        url = f'{GITLAB_URL}/api/v4{api_path}'

        req = urllib.request.Request(url)
        req.add_header('PRIVATE-TOKEN', GITLAB_API_TOKEN)

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = resp.read()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(data)
        except urllib.error.HTTPError as e:
            body = e.read() if e.fp else b'{}'
            self.send_response(e.code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self._json_response(502, {'error': str(e)})

    def _json_response(self, code, obj):
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(obj).encode())

    def log_message(self, fmt, *args):
        # Keep logs minimal — only errors
        if args and str(args[1]).startswith('5'):
            super().log_message(fmt, *args)


if __name__ == '__main__':
    with http.server.HTTPServer(('0.0.0.0', PORT), Handler) as srv:
        print(f'Dashboard listening on :{PORT}')
        srv.serve_forever()
