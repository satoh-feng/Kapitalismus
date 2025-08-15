# app.py
from flask import Flask, request, jsonify, send_from_directory, abort
import re, json, shutil, os, sys, signal, subprocess, time
from datetime import datetime

app = Flask(__name__, static_url_path='', static_folder='.')

# <<< 需要时改这里 >>>
TARGET_FILE = r'/Users/satoh/Desktop/Spider_XHS-master3/main7.31 copy.py'
BACKUP_DIR = os.path.join(os.path.dirname(TARGET_FILE), '.backups')

# 运行与日志
RUN_DIR = os.path.join(os.path.dirname(TARGET_FILE), '.run')
PID_PATH = os.path.join(RUN_DIR, 'main.pid')
LOG_PATH = os.path.join(RUN_DIR, 'main.log')

# 更宽松的正则：匹配  query = "..."  /  query='...'
QUERY_PATTERN = re.compile(r'query\s*=\s*(["\'])(.*?)\1', re.S)

def ensure_run_dir():
    os.makedirs(RUN_DIR, exist_ok=True)


def read_pid():
    try:
        with open(PID_PATH, 'r', encoding='utf-8') as f:
            return int(f.read().strip())
    except Exception:
        return None


def write_pid(pid: int):
    ensure_run_dir()
    with open(PID_PATH, 'w', encoding='utf-8') as f:
        f.write(str(pid))


def clear_pid():
    try:
        os.remove(PID_PATH)
    except FileNotFoundError:
        pass


def is_running(pid: int) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        # The process might exist but we don't have permission; assume running
        return True


def start_main():
    if not os.path.exists(TARGET_FILE):
        return False, f'Target file not found: {TARGET_FILE}'

    # Already running?
    existing = read_pid()
    if existing and is_running(existing):
        return False, f'Already running with PID {existing}'

    ensure_run_dir()

    # Open log file (append) and spawn subprocess
    log_fh = open(LOG_PATH, 'a', encoding='utf-8')
    log_fh.write(f'\n===== START {datetime.now().isoformat()} =====\n')
    log_fh.flush()

    # Use sys.executable to ensure same Python on macOS; pass args as a list to handle spaces
    try:
        proc = subprocess.Popen(
            [sys.executable, TARGET_FILE],
            cwd=os.path.dirname(TARGET_FILE),
            stdout=log_fh,
            stderr=subprocess.STDOUT,
            bufsize=1,
            universal_newlines=True
        )
    except Exception as e:
        log_fh.write(f'Failed to start: {e}\n')
        log_fh.flush()
        log_fh.close()
        return False, f'Failed to start: {e}'

    write_pid(proc.pid)
    return True, proc.pid


def stop_main(timeout=8.0):
    pid = read_pid()
    if not pid:
        return False, 'No PID file; not running?'
    if not is_running(pid):
        clear_pid()
        return False, f'Process {pid} not running'

    try:
        os.kill(pid, signal.SIGTERM)
        # wait up to timeout seconds
        t0 = time.time()
        while time.time() - t0 < timeout:
            if not is_running(pid):
                clear_pid()
                return True, f'Stopped PID {pid}'
            time.sleep(0.2)
        # force kill
        os.kill(pid, signal.SIGKILL)
        clear_pid()
        return True, f'Force-killed PID {pid}'
    except Exception as e:
        return False, f'Failed to stop PID {pid}: {e}'


def status_main():
    pid = read_pid()
    if pid and is_running(pid):
        return {'running': True, 'pid': pid, 'log': LOG_PATH}
    return {'running': False, 'pid': pid, 'log': LOG_PATH}


@app.route('/start', methods=['POST'])
def route_start():
    ok, msg = start_main()
    if ok:
        return jsonify({'ok': True, 'pid': msg, 'log': LOG_PATH})
    return jsonify({'ok': False, 'error': msg}), 400


@app.route('/stop', methods=['POST'])
def route_stop():
    ok, msg = stop_main()
    status = status_main()
    if ok:
        return jsonify({'ok': True, 'message': msg, 'status': status})
    return jsonify({'ok': False, 'error': msg, 'status': status}), 400


@app.route('/status', methods=['GET'])
def route_status():
    return jsonify({'ok': True, **status_main()})


@app.route('/logs', methods=['GET'])
def route_logs():
    # Optional query param: lines (default 200)
    lines = request.args.get('lines', default='200')
    try:
        n = max(1, min(5000, int(lines)))
    except ValueError:
        n = 200
    ensure_run_dir()
    if not os.path.exists(LOG_PATH):
        return jsonify({'ok': True, 'lines': [], 'log': LOG_PATH})
    try:
        with open(LOG_PATH, 'r', encoding='utf-8', errors='replace') as f:
            data = f.readlines()
        tail = data[-n:]
        return jsonify({'ok': True, 'log': LOG_PATH, 'lines': [line.rstrip('\n') for line in tail]})
    except Exception as e:
        return jsonify({'ok': False, 'error': f'Failed to read log: {e}', 'log': LOG_PATH}), 500


@app.route('/current', methods=['GET'])
def current():
    if not os.path.exists(TARGET_FILE):
        return jsonify({'ok': False, 'error': f'Target file not found: {TARGET_FILE}'}), 404
    text = read_file_text(TARGET_FILE)
    m = QUERY_PATTERN.search(text)
    return jsonify({'ok': True, 'query': (m.group(2) if m else None)})

@app.route('/update', methods=['POST'])
def update():
    data = request.get_json(silent=True) or {}
    new_query = data.get('query', '')
    if not isinstance(new_query, str) or new_query == '':
        return jsonify({'ok': False, 'error': 'query must be a non-empty string'}), 400

    if not os.path.exists(TARGET_FILE):
        return jsonify({'ok': False, 'error': f'Target file not found: {TARGET_FILE}'}), 404

    text = read_file_text(TARGET_FILE)
    if not QUERY_PATTERN.search(text):
        return jsonify({'ok': False, 'error': 'Could not find a line like: query = "..."'}), 400

    # 用 json.dumps 确保安全加引号与转义
    updated = QUERY_PATTERN.sub(lambda m: f'query = {json.dumps(new_query)}', text, count=1)

    ensure_backup_dir()
    ts = datetime.now().strftime('%Y%m%d-%H%M%S')
    backup_name = f'{os.path.basename(TARGET_FILE)}.{ts}.bak'
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    shutil.copy2(TARGET_FILE, backup_path)

    write_file_text(TARGET_FILE, updated)

    return jsonify({'ok': True, 'backup': backup_path, 'new_query': new_query})

@app.route('/')
def index():
    # 同目录下的 index.html
    return send_from_directory('.', 'index.html')

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def read_file_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

if __name__ == '__main__':
    # 本地访问：http://127.0.0.1:5000
    ensure_run_dir()
    app.run(host='127.0.0.1', port=5000, debug=True)