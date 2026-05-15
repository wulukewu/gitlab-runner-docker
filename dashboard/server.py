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

import threading
import time

STATE = {
    'health': {},
    'runners': [],
    'jobs': [],
    'last_updated': 0,
    'error': None,
    'ready': False,
    'sync_generation': 0
}
STATE_LOCK = threading.Lock()
POLL_EVENT = threading.Event()

def fetch_gitlab_api(path, fetch_all=False, max_pages=1):
    results = []
    page = 1
    while page <= max_pages or fetch_all:
        sep = '&' if '?' in path else '?'
        url = f"{GITLAB_URL}/api/v4{path}{sep}page={page}&per_page=100"
        
        req = urllib.request.Request(url)
        if GITLAB_API_TOKEN:
            req.add_header('PRIVATE-TOKEN', GITLAB_API_TOKEN)
        
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read())
                if not data:
                    break
                if isinstance(data, list):
                    results.extend(data)
                else:
                    return data
                
                x_next = resp.getheader('X-Next-Page')
                if not x_next:
                    break
                page = int(x_next)
        except Exception as e:
            if not results:
                raise e
            break
            
    return results

def poll_gitlab():
    while True:
        try:
            health = {
                'concurrent': int(os.environ.get('RUNNER_CONCURRENT', '4')),
                'executor': os.environ.get('RUNNER_EXECUTOR', 'shell'),
                'gitlab_url': GITLAB_URL,
                'runner_name': os.environ.get('RUNNER_NAME', 'gitlab-runner'),
                'group_id': GITLAB_GROUP_ID or None,
            }
            
            runners = []
            if GITLAB_GROUP_ID:
                for rtype in ('group_type', 'project_type'):
                    path = f"/groups/{GITLAB_GROUP_ID}/runners?type={rtype}"
                    try:
                        runners.extend(fetch_gitlab_api(path, fetch_all=True))
                    except:
                        pass
                seen = set()
                unique = []
                for r in runners:
                    if r.get('id') not in seen:
                        seen.add(r.get('id'))
                        unique.append(r)
                runners = unique
            else:
                runners = fetch_gitlab_api('/runners?', fetch_all=True)
                
            all_jobs = []
            for r in runners:
                r_id = r.get('id')
                try:
                    managers = fetch_gitlab_api(f"/runners/{r_id}/managers?", fetch_all=True)
                    r['_managers'] = managers
                except:
                    r['_managers'] = []
                    
                try:
                    r_jobs = fetch_gitlab_api(f"/runners/{r_id}/jobs?order_by=id", fetch_all=False, max_pages=5)
                    runner_name = r.get('description') or f"#{r_id}"
                    for j in r_jobs:
                        j['_runner'] = runner_name
                    all_jobs.extend(r_jobs)
                except:
                    pass
                    
            seen_jobs = set()
            unique_jobs = []
            for j in all_jobs:
                if j.get('id') not in seen_jobs:
                    seen_jobs.add(j.get('id'))
                    unique_jobs.append(j)
            
            unique_jobs.sort(key=lambda x: x.get('id', 0), reverse=True)
            
            with STATE_LOCK:
                STATE['health'] = health
                STATE['runners'] = runners
                STATE['jobs'] = unique_jobs
                STATE['error'] = None
                STATE['ready'] = True
                STATE['last_updated'] = time.time()
                STATE['sync_generation'] += 1
                
        except Exception as e:
            print(f"Poller error: {e}")
            with STATE_LOCK:
                STATE['error'] = str(e)
                STATE['sync_generation'] += 1
                
        POLL_EVENT.wait(15)
        POLL_EVENT.clear()


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DASHBOARD_DIR, **kwargs)

    def do_GET(self):
        if self.path == '/health':
            self._health()
        elif self.path.startswith('/api/state'):
            self._state()
        elif self.path.startswith('/api/'):
            self._proxy_gitlab()
        else:
            super().do_GET()

    def _health(self):
        info = {
            'concurrent': int(os.environ.get('RUNNER_CONCURRENT', '4')),
            'executor': os.environ.get('RUNNER_EXECUTOR', 'shell'),
            'gitlab_url': GITLAB_URL,
            'runner_name': os.environ.get('RUNNER_NAME', 'gitlab-runner'),
            'group_id': GITLAB_GROUP_ID or None,
        }
        self._json_response(200, info)

    def _state(self):
        if 'force=true' in self.path:
            with STATE_LOCK:
                target_gen = STATE.get('sync_generation', 0) + 1
            POLL_EVENT.set()
            
            # Wait until the background poller finishes its next cycle (timeout 30s)
            start_time = time.time()
            while time.time() - start_time < 30:
                with STATE_LOCK:
                    if STATE.get('sync_generation', 0) >= target_gen:
                        break
                time.sleep(0.2)
                
        with STATE_LOCK:
            self._json_response(200, STATE)
    def _proxy_gitlab(self):
        api_path = self.path[4:]  # strip leading /api

        # Route /runners to group-scoped endpoint when GITLAB_GROUP_ID is set
        # Fetch both group and project runners, exclude instance (shared) runners
        if GITLAB_GROUP_ID and api_path.startswith('/runners') and '/runners/' not in api_path:
            # Make two calls: group_type + project_type, merge results
            results = []
            for rtype in ('group_type', 'project_type'):
                group_path = api_path.replace('/runners', f'/groups/{GITLAB_GROUP_ID}/runners', 1)
                sep = '&' if '?' in group_path else '?'
                typed_path = f'{group_path}{sep}type={rtype}'
                url = f'{GITLAB_URL}/api/v4{typed_path}'
                req = urllib.request.Request(url)
                req.add_header('PRIVATE-TOKEN', GITLAB_API_TOKEN)
                try:
                    with urllib.request.urlopen(req, timeout=15) as resp:
                        results.extend(json.loads(resp.read()))
                except Exception:
                    pass
            # Deduplicate by runner ID
            seen = set()
            unique = []
            for r in results:
                if r.get('id') not in seen:
                    seen.add(r.get('id'))
                    unique.append(r)
            self._json_response(200, unique)
            return

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
            try:
                body = e.read() if e.fp else b'{}'
                self.send_response(e.code)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionResetError):
                pass
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception as e:
            self._json_response(502, {'error': str(e)})

    def _json_response(self, code, obj):
        try:
            self.send_response(code)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(obj).encode())
        except (BrokenPipeError, ConnectionResetError):
            pass

    def log_message(self, fmt, *args):
        if args and str(args[1]).startswith('5'):
            super().log_message(fmt, *args)


if __name__ == '__main__':
    threading.Thread(target=poll_gitlab, daemon=True).start()
    if GITLAB_GROUP_ID:
        print(f'Dashboard scoped to group {GITLAB_GROUP_ID}')
    with http.server.HTTPServer(('0.0.0.0', PORT), Handler) as srv:
        print(f'Dashboard listening on :{PORT}')
        srv.serve_forever()
