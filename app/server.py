"""Run with python -m app.server [--lan] [--port 8765] [--data-dir data/music]."""
import argparse
from collections import defaultdict, deque
import hmac
from http.cookies import SimpleCookie, CookieError
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
import socket
import threading
import time
from urllib.parse import urlsplit

from .adapter import AceClient, UpstreamError
from .storage import JobStore, StoreError

LOG = logging.getLogger('music_creator')
JOB_ID = re.compile(r'^[a-f0-9]{32}$')


class MusicApp:
    def __init__(self, data_dir, client=None, pair_code=None, poll_interval=3):
        self.store = JobStore(data_dir)
        self.client = client or AceClient()
        self.pair_code = pair_code or os.environ.get('MUSIC_PAIR_CODE') or f'{secrets.randbelow(1000000):06d}'
        if not re.fullmatch(r'\d{6}', self.pair_code):
            raise ValueError('MUSIC_PAIR_CODE 必须为 6 位数字。')
        self.store.claim_worker()
        self.poll_interval = poll_interval
        self.sessions = {}
        self.failures = defaultdict(deque)
        self.session_lock = threading.Lock()
        self.generation_lock = threading.Lock()
        self.lyrics_active = False
        self.stop = threading.Event()
        self.store.recover()
        self.worker = threading.Thread(target=self._worker, name='music-worker', daemon=True)
        self.worker.start()

    def close(self):
        self.stop.set()
        self.worker.join(timeout=self.client.timeout + 2)
        if not self.worker.is_alive():
            self.store.release_worker()

    def _worker(self):
        retry_at, errors = {}, {}
        while not self.stop.is_set():
            for job in self.store.pending():
                if self.stop.is_set():
                    break
                job_id = job['id']
                if time.monotonic() < retry_at.get(job_id, 0):
                    continue
                if not self.generation_lock.acquire(blocking=False):
                    continue
                submitting = job['status'] == 'queued'
                try:
                    # A manual resolution may have changed a row since pending() was read.
                    job = self.store.get(job_id)
                    if not job or job['status'] not in ('queued', 'running', 'waiting'):
                        continue
                    submitting = job['status'] == 'queued'
                    if submitting:
                        if self.store.model_busy():
                            continue
                        try:
                            self.client.health()
                        except UpstreamError as exc:
                            # A read-only readiness failure has not submitted any work.
                            self.store.update(job_id, error=str(exc) + ' 作品仍在队列中，模型就绪后会开始。')
                            retry_at[job_id] = time.monotonic() + max(1, self.poll_interval)
                            continue
                        self.store.update(job_id, status='submitting', error='')
                        upstream_id = self.client.submit(job)
                        self.store.update(job_id, status='running', upstream_id=upstream_id)
                        retry_at[job_id] = time.monotonic() + self.poll_interval
                        continue
                    result = self.client.query(job['upstream_id'])
                    if result is None:
                        self.store.update(job_id, status='running', error='')
                    else:
                        self.client.download(result['file'], self.store.audio_dir / f'{job_id}.wav')
                        # Never expose upstream URLs, model paths or credentials to browsers.
                        metadata = {'lyrics': result.get('lyrics', '') if isinstance(result.get('lyrics', ''), str) else ''}
                        seed = result.get('seed_value')
                        if type(seed) is int or (isinstance(seed, str) and re.fullmatch(r'-?\d{1,24}', seed)):
                            metadata['seed_value'] = seed
                        for key in ('dit_model', 'lm_model'):
                            name = result.get(key)
                            if isinstance(name, str):
                                name = name.replace('\\', '/').rsplit('/', 1)[-1][:120]
                                if re.fullmatch(r'[\w .+-]{1,120}', name):
                                    metadata[key] = name
                        self.store.update(job_id, status='completed', error='', metadata=metadata)
                    errors.pop(job_id, None)
                    retry_at[job_id] = time.monotonic() + self.poll_interval
                except UpstreamError as exc:
                    if submitting:
                        # Even HTTP errors can follow acceptance: never auto-resubmit.
                        self.store.update(job_id, status='unknown', error=str(exc) + ' 提交结果无法确认，已保留记录，不会自动重发。')
                    elif exc.retryable:
                        errors[job_id] = errors.get(job_id, 0) + 1
                        paused = errors[job_id] >= 5
                        self.store.update(job_id, status='paused' if paused else 'waiting', error=str(exc) + (' 已暂停查询；恢复时只查询原任务。' if paused else ' 已保留任务编号，稍后继续查询。'))
                        retry_at[job_id] = time.monotonic() + min(30, self.poll_interval * 2 ** errors[job_id])
                    else:
                        self.store.update(job_id, status='failed', error=str(exc))
                except Exception:
                    LOG.exception('本地任务处理异常，任务 %s', job_id)
                    self.store.update(job_id, status='unknown' if submitting else 'paused', error='本地任务处理异常，已保留记录；请查看电脑端日志。')
                finally:
                    self.generation_lock.release()
            self.stop.wait(min(self.poll_interval, 1))

    def authenticate(self, cookie):
        parsed = SimpleCookie()
        try:
            parsed.load(cookie or '')
            token = parsed['music_session'].value if 'music_session' in parsed else ''
        except CookieError:
            return False
        with self.session_lock:
            now = time.monotonic()
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            return token in self.sessions

    def login(self, address, code):
        with self.session_lock:
            now = time.monotonic()
            # Prevent unbounded memory use from many LAN addresses.
            for key in list(self.failures):
                attempts = self.failures[key]
                while attempts and attempts[0] < now - 300:
                    attempts.popleft()
                if not attempts:
                    del self.failures[key]
            if len(self.failures[address]) >= 6 or sum(map(len, self.failures.values())) >= 30:
                raise StoreError('配对尝试过多，请 5 分钟后再试。', 429)
            if not isinstance(code, str) or not hmac.compare_digest(code.encode(), self.pair_code.encode()):
                self.failures[address].append(now)
                raise StoreError('配对码不正确，请查看电脑端窗口。', 401)
            self.failures.pop(address, None)
            self.sessions = {key: expiry for key, expiry in self.sessions.items() if expiry > now}
            if len(self.sessions) >= 32:
                oldest = min(self.sessions, key=self.sessions.get)
                del self.sessions[oldest]
            token = secrets.token_urlsafe(32)
            self.sessions[token] = now + 86400
            return token

    def logout(self, cookie):
        parsed = SimpleCookie()
        try:
            parsed.load(cookie or '')
            if 'music_session' in parsed:
                with self.session_lock:
                    self.sessions.pop(parsed['music_session'].value, None)
        except CookieError:
            pass


class Handler(BaseHTTPRequestHandler):
    server_version = 'MusicCreator'
    sys_version = ''

    @property
    def app(self):
        return self.server.app

    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, format, *args):
        # Query strings and request bodies can contain secrets; do not log them.
        pass

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('X-Frame-Options', 'DENY')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()

    def _json(self, status, value, headers=None):
        raw = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(raw)))
        for key, val in (headers or {}).items():
            self.send_header(key, val)
        self.end_headers()
        if self.command != 'HEAD':
            self.wfile.write(raw)

    def _host(self):
        host = self.headers.get('Host', '')
        try:
            parsed = urlsplit('http://' + host)
            hostname, port = parsed.hostname, parsed.port or 80
            if parsed.path or parsed.query or parsed.fragment or parsed.username or not hostname or port != self.server.server_port:
                raise ValueError('invalid host')
            if hostname != 'localhost':
                address = ipaddress.ip_address(hostname)
                if not (address.is_loopback or address.is_private) or address.is_unspecified:
                    raise ValueError('non-local host')
        except ValueError as exc:
            raise StoreError('请通过工具显示的本机或局域网地址访问。', 403) from exc
        return host.lower()

    def _write_guard(self):
        site = self.headers.get('Sec-Fetch-Site', '')
        origin = self.headers.get('Origin')
        host = self._host()
        if site not in ('', 'same-origin', 'none') or (origin is not None and origin.lower() != 'http://' + host):
            raise StoreError('已拒绝跨站请求，请直接打开创作工具。', 403)
        if self.headers.get('Transfer-Encoding'):
            raise StoreError('不支持此请求编码。', 400)
        if self.command != 'DELETE' and self.headers.get('Content-Type', '').split(';')[0].strip().lower() != 'application/json':
            raise StoreError('请求需要 JSON 格式。', 415)

    def _body(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 65536:
                raise StoreError('请求为空或超过 64 KB。', 413)
            raw = self.rfile.read(length)
            if len(raw) != length:
                raise StoreError('请求内容不完整。')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise StoreError('请提交 JSON 对象。')
            return result
        except (ValueError, UnicodeDecodeError) as exc:
            raise StoreError('请求 JSON 格式不正确。') from exc

    def _route(self):
        self._host()
        path = urlsplit(self.path).path
        if self.command in ('POST', 'DELETE'):
            self._write_guard()
        if path == '/api/session':
            if self.command in ('GET', 'HEAD'):
                return self._json(200, {'authenticated': self.app.authenticate(self.headers.get('Cookie'))})
            if self.command == 'POST':
                token = self.app.login(self.client_address[0], self._body().get('code'))
                return self._json(200, {'authenticated': True}, {'Set-Cookie': f'music_session={token}; HttpOnly; SameSite=Strict; Path=/; Max-Age=86400'})
            if self.command == 'DELETE':
                self.app.logout(self.headers.get('Cookie'))
                return self._json(200, {'authenticated': False}, {'Set-Cookie': 'music_session=; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'})
        if path.startswith(('/api/', '/audio/')) and not self.app.authenticate(self.headers.get('Cookie')):
            raise StoreError('请先输入电脑端配对码。', 401)
        if path == '/api/status' and self.command in ('GET', 'HEAD'):
            if self.app.lyrics_active:
                return self._json(200, {'processing_lyrics': True, 'model_uncertain': False, 'connected': False, 'lyrics_ready': False, 'message': '正在写歌词，完成后恢复连接检查。'})
            uncertain = self.app.store.model_uncertain()
            warning = '上次写词结果无法确认；请核实模型服务已停止或完成，再解除占用。'
            try:
                readiness = self.app.client.health()
                lyrics_ready = readiness['llm_initialized']
                message = '音乐模型已就绪。' if lyrics_ready else '音乐模型已就绪；歌词模型尚未就绪，可先手写歌词或生成 BGM。'
                return self._json(200, {'processing_lyrics': False, 'connected': True, 'model_uncertain': uncertain, 'lyrics_ready': lyrics_ready, **readiness, 'message': warning if uncertain else message})
            except UpstreamError as exc:
                return self._json(200, {'processing_lyrics': False, 'connected': False, 'model_uncertain': uncertain, 'lyrics_ready': False, 'message': warning + ' ' + str(exc) if uncertain else str(exc)})
        if path == '/api/resolve-model' and self.command == 'POST':
            if self._body().get('confirmed') is not True:
                raise StoreError('需要明确确认模型服务已停止或完成。')
            if not self.app.generation_lock.acquire(blocking=False):
                raise StoreError('模型请求仍在进行，请等待结束后确认。', 409)
            try:
                if not self.app.store.model_uncertain():
                    raise StoreError('当前没有需要确认的写词请求。', 409)
                self.app.store.set_model_uncertain(False)
                return self._json(200, {'model_uncertain': False, 'message': '已确认上游停止或结束；不会重新发送写词请求。'})
            finally:
                self.app.generation_lock.release()
        if path == '/api/lyrics' and self.command == 'POST':
            data = self._body()
            values = {}
            for name, limit in (('description', 2000), ('style', 120), ('mood', 120)):
                value = data.get(name, '')
                if not isinstance(value, str) or len(value) > limit or '\x00' in value:
                    raise StoreError('歌词描述格式或长度不正确。')
                values[name] = value.strip()
            duration = data.get('duration')
            if not values['description'] or type(duration) is not int or duration not in (30, 60, 90, 120):
                raise StoreError('请填写歌词主题，并选择 30、60、90 或 120 秒。')
            if not self.app.generation_lock.acquire(blocking=False):
                raise StoreError('模型正在处理其他请求，请稍后再写歌词。', 409)
            try:
                if self.app.store.model_busy():
                    raise StoreError('还有音乐任务正在处理或结果待确认，请先完成或恢复原任务。', 409)
                self.app.lyrics_active = True
                # Persist before sending: a crash during this synchronous call is ambiguous too.
                self.app.store.set_model_uncertain(True)
                result = self.app.client.create_lyrics(**values, duration=duration)
                self.app.store.set_model_uncertain(False)
                return self._json(200, result)
            except UpstreamError as exc:
                if not exc.uncertain:
                    self.app.store.set_model_uncertain(False)
                raise StoreError(str(exc), 502) from exc
            finally:
                self.app.lyrics_active = False
                self.app.generation_lock.release()
        if path == '/api/jobs':
            if self.command in ('GET', 'HEAD'):
                return self._json(200, {'jobs': [self.app.store.public(job) for job in self.app.store.list()]})
            if self.command == 'POST':
                job, created = self.app.store.create(self._body())
                return self._json(202 if created else 200, {'job': self.app.store.public(job)})
        match = re.fullmatch(r'/api/jobs/([a-f0-9]{32})(/resume|/resolve-unknown|/resolve-waiting)?', path)
        if match:
            job = self.app.store.get(match[1])
            if not job:
                raise StoreError('没有找到这个任务。', 404)
            if match[2] == '/resolve-waiting' and self.command == 'POST':
                if self._body().get('confirmed') is not True:
                    raise StoreError('需要明确确认上游任务已停止或结束；此操作不会取消上游任务。')
                if not self.app.generation_lock.acquire(blocking=False):
                    raise StoreError('正在查询或保存模型结果，请稍后再结束等待。', 409)
                try:
                    job = self.app.store.resolve_waiting(job['id'])
                    return self._json(200, {'job': self.app.store.public(job)})
                finally:
                    self.app.generation_lock.release()
            if match[2] == '/resolve-unknown' and self.command == 'POST':
                if self._body().get('confirmed') is not True:
                    raise StoreError('需要明确确认上游任务已停止或结束。')
                job = self.app.store.resolve_unknown(job['id'])
                return self._json(200, {'job': self.app.store.public(job)})
            if match[2] == '/resume' and self.command == 'POST':
                self._body()
                job = self.app.store.resume(job['id'])
                return self._json(200, {'job': self.app.store.public(job)})
            if not match[2] and self.command in ('GET', 'HEAD'):
                return self._json(200, {'job': self.app.store.public(job)})
        match = re.fullmatch(r'/audio/([a-f0-9]{32})\.wav', path)
        if match and self.command in ('GET', 'HEAD'):
            return self._audio(match[1], urlsplit(self.path).query == 'download=1')
        if self.command in ('GET', 'HEAD') and path in ('/', '/index.html', '/app.js', '/style.css'):
            name = 'index.html' if path == '/' else path[1:]
            file = Path(__file__).parent / 'static' / name
            if not file.is_file():
                raise StoreError('页面文件尚未准备好。', 404)
            body = file.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', {'index.html': 'text/html; charset=utf-8', 'app.js': 'text/javascript; charset=utf-8', 'style.css': 'text/css; charset=utf-8'}[name])
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            if self.command != 'HEAD':
                self.wfile.write(body)
            return
        raise StoreError('没有找到该页面或接口。', 404)

    def _audio(self, job_id, download):
        job = self.app.store.get(job_id)
        path = self.app.store.audio_dir / f'{job_id}.wav'
        if not job or job['status'] != 'completed' or not path.is_file():
            raise StoreError('音频尚未生成或文件已不存在。', 404)
        total = path.stat().st_size
        start, end, status = 0, total - 1, 200
        range_header = self.headers.get('Range')
        if range_header:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
            valid = bool(match and any(match.groups()))
            if valid:
                left, right = match.groups()
                if left:
                    start, end = int(left), min(int(right), total - 1) if right else total - 1
                else:
                    length = int(right)
                    start, end = max(0, total - length), total - 1
                    valid = length > 0
                valid = valid and 0 <= start <= end < total
            if not valid:
                return self._json(416, {'error': '播放范围无效。'}, {'Content-Range': f'bytes */{total}'})
            status = 206
        self.send_response(status)
        self.send_header('Content-Type', 'audio/wav')
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Content-Length', str(end - start + 1))
        if status == 206:
            self.send_header('Content-Range', f'bytes {start}-{end}/{total}')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="music-{job_id[:8]}.wav"')
        self.end_headers()
        if self.command != 'HEAD':
            with path.open('rb') as stream:
                stream.seek(start)
                remaining = end - start + 1
                while remaining:
                    chunk = stream.read(min(65536, remaining))
                    if not chunk:
                        break
                    self.wfile.write(chunk)
                    remaining -= len(chunk)

    def _handle(self):
        try:
            self._route()
        except StoreError as exc:
            self._json(exc.status, {'error': str(exc)})
        except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, TimeoutError):
            pass
        except Exception:
            LOG.exception('本地 HTTP 请求处理异常')
            self._json(500, {'error': '本地服务发生异常，请查看电脑端日志。'})

    do_GET = do_POST = do_DELETE = do_HEAD = _handle


def make_server(app, host='127.0.0.1', port=8765):
    server = ThreadingHTTPServer((host, port), Handler)
    server.app = app
    return server


def main():
    parser = argparse.ArgumentParser(description='ACE-Step 中文音乐创作工具')
    parser.add_argument('--lan', action='store_true', help='允许同一局域网的手机访问')
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--data-dir', default=str(Path(__file__).resolve().parents[1] / 'data' / 'music'))
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    app = MusicApp(args.data_dir)
    try:
        server = make_server(app, '0.0.0.0' if args.lan else '127.0.0.1', args.port)
    except OSError:
        app.close()
        raise
    print(f'电脑地址：http://127.0.0.1:{args.port}', flush=True)
    print(f'配对码：{app.pair_code}（仅供你自己的设备使用）', flush=True)
    if args.lan:
        try:
            for address in sorted(set(socket.gethostbyname_ex(socket.gethostname())[2])):
                if ipaddress.ip_address(address).is_private and not address.startswith('127.'):
                    print(f'手机地址：http://{address}:{args.port}（需连接同一 Wi-Fi）', flush=True)
        except OSError:
            print('请在电脑网络设置中查看局域网 IPv4 地址。', flush=True)
        print('局域网访问使用普通 HTTP，请只在信任的家庭网络中使用。', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        app.close()
        server.server_close()


if __name__ == '__main__':
    main()
