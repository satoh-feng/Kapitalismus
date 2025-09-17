# app.py
from flask import Flask, request, jsonify, send_from_directory
import re, json, shutil, os
from datetime import datetime

app = Flask(__name__, static_url_path='', static_folder='.')

# <<< 需要时改这里 >>>
TARGET_FILE = r'./main.py'
BACKUP_DIR = os.path.join(os.path.dirname(TARGET_FILE), '.backups')

# 更宽松的正则：匹配  query = "..."  /  query='...'
QUERY_PATTERN = re.compile(r'query\s*=\s*(["\'])(.*?)\1', re.S)

def ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)

def read_file_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def write_file_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

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

if __name__ == '__main__':
    # 本地访问：http://127.0.0.1:5000
    app.run(host='127.0.0.1', port=5000, debug=True)
