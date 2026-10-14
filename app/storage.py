"""SQLite queue with atomic idempotency and durable upstream task identifiers."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import threading
import uuid
from .preferences import normalize_preferences


class StoreError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def normalize(data):
    if not isinstance(data, dict):
        raise StoreError('请提交 JSON 对象。')
    values = {}
    for name, limit in [('request_id', 128), ('title', 80), ('description', 2000), ('style', 120), ('mood', 120), ('lyrics', 6000), ('mode', 10), ('lyric_mode', 10)]:
        value = data.get(name, 'manual' if name == 'lyric_mode' else '')
        if not isinstance(value, str) or len(value) > limit or '\x00' in value:
            raise StoreError(f'{name} 内容格式或长度不正确。')
        values[name] = value.strip()
    if not values['request_id']:
        raise StoreError('缺少请求编号，请刷新页面重试。')
    if values['lyric_mode'] != 'manual':
        raise StoreError('请先生成歌词草稿并确认或修改，再提交歌曲。')
    if values['mode'] not in ('song', 'bgm'):
        raise StoreError('创作模式或歌词模式不正确。')
    if type(data.get('duration')) is not int or data['duration'] not in (30, 60, 90, 120):
        raise StoreError('时长请选择 30、60、90 或 120 秒。')
    values['duration'] = data['duration']
    if not values['description']:
        raise StoreError('请填写想创作的音乐。')
    if values['mode'] == 'song' and values['lyric_mode'] == 'manual' and not values['lyrics']:
        raise StoreError('请填写歌词，或先生成歌词草稿并确认。')
    if values['mode'] == 'bgm':
        values.update(lyrics='', lyric_mode='manual')
    try:
        values.update(normalize_preferences(dict(data, mode=values['mode'])))
    except ValueError as exc:
        raise StoreError(str(exc)) from exc
    values['title'] = values['title'] or ('未命名歌曲' if values['mode'] == 'song' else '未命名配乐')
    return values


class JobStore:
    def __init__(self, directory):
        self.directory = Path(directory).resolve()
        self.directory.mkdir(parents=True, exist_ok=True)
        self.audio_dir = self.directory / 'audio'
        self.audio_dir.mkdir(exist_ok=True)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.directory / 'music.sqlite3', check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, request_id TEXT UNIQUE NOT NULL, fingerprint TEXT NOT NULL, payload TEXT NOT NULL, status TEXT NOT NULL, upstream_id TEXT, created_at TEXT NOT NULL, error TEXT NOT NULL DEFAULT \'\', metadata TEXT NOT NULL DEFAULT \'{}\')')
        self.db.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
        self.db.commit()
        self.worker_lock = None

    def claim_worker(self):
        handle = (self.directory / '.worker.lock').open('a+b')
        try:
            handle.seek(0, 2)
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            if os.name == 'nt':
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.worker_lock = handle
        except OSError as exc:
            handle.close()
            self.db.close()
            raise StoreError('该作品目录已经由另一实例使用，请关闭重复启动窗口。', 409) from exc

    def release_worker(self):
        if self.worker_lock is not None:
            self.worker_lock.close()
            self.worker_lock = None

    @staticmethod
    def _row(row):
        if row is None:
            return None
        result = dict(row)
        result.update(json.loads(result.pop('payload')))
        result['metadata'] = json.loads(result['metadata'])
        return result

    def create(self, data):
        payload = normalize(data)
        fingerprint = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.lock, self.db:
            previous = self.db.execute('SELECT * FROM jobs WHERE request_id=?', (payload['request_id'],)).fetchone()
            if previous:
                if previous['fingerprint'] != fingerprint and normalize(json.loads(previous['payload'])) != payload:
                    raise StoreError('同一请求编号对应的内容发生变化，请重新发起创作。', 409)
                return self._row(previous), False
            pending = self.db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','submitting','running','waiting')").fetchone()[0]
            if pending >= 5:
                raise StoreError('已有 5 个待完成任务，请等待后再提交。', 429)
            job_id = uuid.uuid4().hex
            self.db.execute('INSERT INTO jobs (id,request_id,fingerprint,payload,status,created_at) VALUES (?,?,?,?,?,?)', (job_id, payload['request_id'], fingerprint, json.dumps(payload, ensure_ascii=False), 'queued', datetime.now(timezone.utc).isoformat()))
            return self.get(job_id), True

    def get(self, job_id):
        with self.lock:
            return self._row(self.db.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone())

    def list(self):
        with self.lock:
            return [self._row(row) for row in self.db.execute('SELECT * FROM jobs ORDER BY created_at DESC LIMIT 200')]

    def pending(self):
        with self.lock:
            return [self._row(row) for row in self.db.execute("SELECT * FROM jobs WHERE status IN ('queued','running','waiting') ORDER BY CASE WHEN upstream_id IS NOT NULL THEN 0 ELSE 1 END, created_at")]

    def update(self, job_id, **fields):
        if not fields or set(fields) - {'status', 'upstream_id', 'error', 'metadata'}:
            raise ValueError('invalid update')
        if 'metadata' in fields:
            fields['metadata'] = json.dumps(fields['metadata'], ensure_ascii=False)
        with self.lock, self.db:
            self.db.execute('UPDATE jobs SET ' + ','.join(f'{name}=?' for name in fields) + ' WHERE id=?', [*fields.values(), job_id])

    def recover(self):
        with self.lock, self.db:
            self.db.execute("UPDATE jobs SET status='unknown', error='程序在提交期间退出，无法确认模型是否接单；为避免重复生成，不会自动重发。' WHERE status='submitting' AND upstream_id IS NULL")
            # Existing upstream work must remain recoverable even if five new jobs await it.
            self.db.execute("UPDATE jobs SET status='waiting', error='正在恢复模型任务查询。' WHERE upstream_id IS NOT NULL AND status IN ('running','submitting','waiting','paused')")

    def resume(self, job_id):
        with self.lock, self.db:
            job = self.get(job_id)
            if not job or job['status'] != 'paused' or not job['upstream_id']:
                raise StoreError('此任务无法恢复查询。提交结果未知的任务不会自动重发。', 409)
            self.update(job_id, status='waiting', error='正在恢复原任务查询。')
            return self.get(job_id)

    def model_busy(self):
        with self.lock:
            return self.model_uncertain() or self.db.execute("SELECT 1 FROM jobs WHERE status IN ('submitting','running','waiting','paused','unknown') LIMIT 1").fetchone() is not None

    def model_uncertain(self):
        with self.lock:
            row = self.db.execute("SELECT value FROM settings WHERE key='model_uncertain'").fetchone()
            return row is not None and row['value'] == '1'

    def set_model_uncertain(self, uncertain):
        with self.lock, self.db:
            self.db.execute("INSERT OR REPLACE INTO settings (key,value) VALUES ('model_uncertain', ?)", ('1' if uncertain else '0',))

    def resolve_unknown(self, job_id):
        with self.lock, self.db:
            job = self.get(job_id)
            if not job or job['status'] != 'unknown':
                raise StoreError('只有提交结果未知的任务需要此确认。', 409)
            self.update(job_id, status='failed', error='已由用户确认上游任务已停止或结束；本地记录关闭，未重新提交。')
            return self.get(job_id)

    def resolve_waiting(self, job_id):
        with self.lock, self.db:
            job = self.get(job_id)
            if not job or job['status'] not in ('running', 'waiting', 'paused') or not job['upstream_id']:
                raise StoreError('只有已取得模型任务编号且仍在等待的任务才能结束本地等待。', 409)
            self.update(job_id, status='failed', error='用户已确认上游停止或结束，人工结束本地等待；未取消上游任务，也未重新提交。')
            return self.get(job_id)

    def public(self, job):
        fields = ('id', 'status', 'title', 'mode', 'description', 'style', 'mood', 'duration', 'lyrics', 'lyric_mode', 'created_at', 'error')
        result = {key: job[key] for key in fields}
        result.update(voice_gender=job.get('voice_gender', 'auto'), voice_tone=job.get('voice_tone', 'auto'), instruments=job.get('instruments', []))
        result['audio_url'] = f'/audio/{job["id"]}.wav' if job['status'] == 'completed' else None
        result['download_url'] = result['audio_url'] + '?download=1' if result['audio_url'] else None
        result['generated_lyrics'] = job['metadata'].get('lyrics', '')
        return result
