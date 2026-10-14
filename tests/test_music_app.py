"""Local protocol simulation only: these tests never generate real music."""
import concurrent.futures
import http.client
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import struct
import threading
import time
import unittest
import wave
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

try:
    from app.adapter import AceClient, UpstreamError
    from app.server import MusicApp, make_server
    from app.storage import StoreError
except ImportError:
    AceClient = MusicApp = make_server = None


def wav_bytes():
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(8000)
        stream.writeframes(b'\x00\x00' * 800)
    return buf.getvalue()


def float_wav_bytes(extensible=False):
    audio = struct.pack('<8f', 0, .1, -.1, .5, -.5, .9, -.9, 0)
    fmt = struct.pack('<HHIIHH', 65534 if extensible else 3, 1, 8000, 32000, 4, 32)
    if extensible:
        fmt += struct.pack('<HHI', 22, 32, 0) + struct.pack('<I', 3) + bytes.fromhex('00001000800000aa00389b71')
    body = b'WAVEfmt ' + struct.pack('<I', len(fmt)) + fmt + b'data' + struct.pack('<I', len(audio)) + audio
    return b'RIFF' + struct.pack('<I', len(body)) + body


class FakeAce(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def respond(self, data, code=200):
        body = json.dumps({'data': data, 'code': code, 'error': None}).encode()
        self.send_response(code)
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def do_GET(self):
        if self.path == '/health':
            self.server.health_requests += 1
            if self.server.health_truncated:
                self.send_response(200)
                self.send_header('Transfer-Encoding', 'chunked')
                self.end_headers()
                self.wfile.write(b'ff\r\n{"data":')
                self.close_connection = True
                return
            return self.respond({'status': 'ok', 'models_initialized': self.server.models_initialized, 'llm_initialized': self.server.llm_initialized})
        if self.path.startswith('/v1/audio?'):
            if self.server.redirect:
                self.send_response(302)
                self.send_header('Location', 'http://127.0.0.1:1/private')
                self.end_headers()
                return
            self.send_response(200)
            self.send_header('Content-Length', str(len(self.server.audio)))
            self.end_headers()
            self.wfile.write(self.server.audio)
            return
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        self.server.events.append(self.path)
        if self.path == '/release_task':
            self.server.submissions.append(body)
            if self.server.submit_delay:
                time.sleep(self.server.submit_delay)
            return self.respond({'task_id': 'upstream-1'})
        if self.path == '/query_result':
            self.server.queries.append(body)
            if self.server.query_delay:
                time.sleep(self.server.query_delay)
            result = [{'file': self.server.file, 'lyrics': '测试歌词', 'prompt': 'test', 'seed_value': 42, 'dit_model': 'turbo'}]
            return self.respond([{'task_id': 'upstream-1', 'status': self.server.status, 'result': json.dumps(result)}])
        if self.path == '/v1/create_sample':
            self.server.lyric_requests.append(body)
            if self.server.lyric_delay:
                time.sleep(self.server.lyric_delay)
            return self.respond({'lyrics': self.server.lyrics, 'caption': '温暖的中文民谣'})
        self.send_error(404)


class MusicTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(MusicApp, '后端尚未实现')
        scratch = Path(__file__).resolve().parents[1] / 'work'
        scratch.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=scratch)
        self.ace = ThreadingHTTPServer(('127.0.0.1', 0), FakeAce)
        self.ace.submissions, self.ace.queries = [], []
        self.ace.events = []
        self.ace.lyric_requests = []
        self.ace.lyrics = '[Verse]\n夜空中有一颗星'
        self.ace.lyric_delay = 0
        self.ace.status = 1
        self.ace.models_initialized = self.ace.llm_initialized = True
        self.ace.health_requests = 0
        self.ace.health_truncated = False
        self.ace.audio = wav_bytes()
        self.ace.file = '/v1/audio?path=generated.wav'
        self.ace.redirect = False
        self.ace.submit_delay = self.ace.query_delay = 0
        threading.Thread(target=self.ace.serve_forever, daemon=True).start()
        self.client = AceClient(f'http://127.0.0.1:{self.ace.server_port}', timeout=.15)
        self.app = MusicApp(self.tmp.name, self.client, pair_code='123456', poll_interval=.03)
        self.server = make_server(self.app, '127.0.0.1', 0)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.cookie = ''
        self.request('POST', '/api/session', {'code': '123456'})

    def tearDown(self):
        if hasattr(self, 'server'):
            self.server.shutdown()
            self.server.server_close()
            self.app.close()
            self.app.store.db.close()
            self.ace.shutdown()
            self.ace.server_close()
            self.tmp.cleanup()

    def request(self, method, path, data=None, headers=None, auth=True):
        conn = http.client.HTTPConnection('127.0.0.1', self.server.server_port, timeout=3)
        hdr = {'Content-Type': 'application/json'}
        if auth:
            hdr['Cookie'] = self.cookie
        hdr.update(headers or {})
        conn.request(method, path, json.dumps(data) if data is not None else None, hdr)
        response = conn.getresponse()
        raw = response.read()
        status, result_headers = response.status, dict(response.getheaders())
        if result_headers.get('Set-Cookie'):
            self.cookie = result_headers['Set-Cookie'].split(';')[0]
        conn.close()
        try:
            value = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            value = raw
        return status, value, result_headers

    def payload(self, request_id='test-1'):
        return {'request_id': request_id, 'mode': 'song', 'title': '测试', 'description': '温暖', 'style': '民谣', 'mood': '平静', 'duration': 30, 'lyrics': '夜空中有一颗星', 'lyric_mode': 'manual'}

    def wait_job(self, job_id, states=('completed', 'failed', 'unknown'), timeout=3):
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            job = self.app.store.get(job_id)
            if job['status'] in states:
                return job
            time.sleep(.02)
        self.fail(f'任务未到达{states}: {job}')

    def test_async_protocol_and_range(self):
        status, result, _ = self.request('POST', '/api/jobs', self.payload())
        self.assertEqual(status, 202)
        job = self.wait_job(result['job']['id'])
        self.assertEqual(job['status'], 'completed')
        self.assertEqual(job['metadata']['seed_value'], 42)
        self.assertEqual(job['metadata']['dit_model'], 'turbo')
        submitted = self.ace.submissions[0]
        self.assertEqual(submitted['lyrics'], '夜空中有一颗星')
        self.assertEqual(submitted['vocal_language'], 'zh')
        self.assertEqual(submitted['batch_size'], 1)
        self.assertTrue(submitted['thinking'])
        self.assertTrue(submitted['prompt'].startswith('A vocal song with a lead singer clearly singing the provided Mandarin Chinese lyrics from the beginning; '))
        self.assertIn('Clear Mandarin diction', submitted['prompt'])
        self.assertIn('natural syllabic phrasing and breaths', submitted['prompt'])
        self.assertIn('quieter accompaniment', submitted['prompt'])
        self.assertEqual(self.ace.queries[0], {'task_id_list': ['upstream-1']})
        status, body, headers = self.request('GET', f'/audio/{job["id"]}.wav', headers={'Range': 'bytes=0-11'})
        self.assertEqual(status, 206)
        self.assertEqual(body, self.ace.audio[:12])
        self.assertTrue(headers['Content-Range'].startswith('bytes 0-11/'))
        self.assertEqual(self.request('GET', f'/audio/{job["id"]}.wav', headers={'Range': 'bytes=999999-'})[0], 416)
        public = self.request('GET', f'/api/jobs/{job["id"]}')[1]['job']
        self.assertNotIn('upstream_id', public)
        self.assertNotIn(str(Path(self.tmp.name)), json.dumps(public))

    def test_upstream_failure(self):
        self.ace.status = 2
        _, result, _ = self.request('POST', '/api/jobs', self.payload())
        self.assertEqual(self.wait_job(result['job']['id'])['status'], 'failed')
        self.assertEqual(len(self.ace.submissions), 1)

    def test_voice_and_instruments_reach_model_and_public_record(self):
        payload = self.payload()
        payload.update(voice_gender='female', voice_tone='warm', instruments=['piano', 'acoustic_guitar'])
        status, result, _ = self.request('POST', '/api/jobs', payload)
        self.assertEqual(status, 202)
        job = self.wait_job(result['job']['id'])
        public = self.request('GET', f'/api/jobs/{job["id"]}')[1]['job']
        self.assertEqual(public['voice_gender'], 'female')
        self.assertEqual(public['voice_tone'], 'warm')
        self.assertEqual(public['instruments'], ['acoustic_guitar', 'piano'])
        prompt = self.ace.submissions[0]['prompt']
        for value in ('female lead vocals', 'warm mellow vocal timbre', 'featured instruments: acoustic guitar, piano'):
            self.assertIn(value, prompt)
        self.assertEqual(self.ace.submissions[0]['lyrics'], payload['lyrics'])

    def test_bgm_discards_voice_but_keeps_instruments(self):
        payload = self.payload()
        payload.update(mode=' bgm ', voice_gender='male', voice_tone='husky', instruments=['guzheng'])
        _, result, _ = self.request('POST', '/api/jobs', payload)
        job = self.wait_job(result['job']['id'])
        self.assertEqual(job['voice_gender'], 'auto')
        self.assertEqual(job['voice_tone'], 'auto')
        body = self.ace.submissions[0]
        self.assertIn('featured instruments: guzheng', body['prompt'])
        self.assertIn('no vocals', body['prompt'])
        self.assertNotIn('male lead vocals', body['prompt'])
        self.assertNotIn('husky', body['prompt'])
        self.assertEqual(body['lyrics'], '[Instrumental]')
        self.assertFalse(body['thinking'])
        self.assertNotIn('A vocal song', body['prompt'])
        self.assertNotIn('Mandarin diction', body['prompt'])

    def test_preference_validation_and_idempotency(self):
        invalid = [{'voice_gender': 'other'}, {'voice_tone': None}, {'instruments': 'piano'},
                   {'instruments': ['unknown']}, {'instruments': ['piano', 'piano']},
                   {'instruments': ['piano', 'drums', 'bass', 'strings']}, {'instruments': [{}]}]
        for values in invalid:
            with self.subTest(values=values):
                self.assertEqual(self.request('POST', '/api/jobs', dict(self.payload(), **values))[0], 400)
        self.assertEqual(self.ace.submissions, [])
        payload = dict(self.payload(), instruments=['piano', 'drums'])
        _, first, _ = self.request('POST', '/api/jobs', payload)
        self.wait_job(first['job']['id'])
        payload['instruments'].reverse()
        _, replay, _ = self.request('POST', '/api/jobs', payload)
        self.assertEqual(first['job']['id'], replay['job']['id'])
        payload['voice_gender'] = 'male'
        self.assertEqual(self.request('POST', '/api/jobs', payload)[0], 409)
        self.assertEqual(len(self.ace.submissions), 1)

    def test_legacy_request_replay_and_defaults(self):
        self.app.close()
        payload = self.payload()
        job, _ = self.app.store.create(payload)
        legacy = dict(payload)
        fingerprint = hashlib.sha256(json.dumps(legacy, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        with self.app.store.db:
            self.app.store.db.execute('UPDATE jobs SET payload=?,fingerprint=? WHERE id=?',
                                      (json.dumps(legacy), fingerprint, job['id']))
        replay, created = self.app.store.create(payload)
        self.assertFalse(created)
        self.assertEqual(replay['id'], job['id'])
        public = self.app.store.public(replay)
        self.assertEqual((public['voice_gender'], public['voice_tone'], public['instruments']), ('auto', 'auto', []))
        self.assertNotIn('featured instruments', self.client.payload(replay)['prompt'])
        with self.assertRaises(StoreError):
            self.app.store.create(dict(payload, instruments=['piano']))

    def test_query_timeout_recovers_without_resubmit(self):
        self.ace.query_delay = .3
        _, result, _ = self.request('POST', '/api/jobs', self.payload())
        job = self.wait_job(result['job']['id'], ('waiting',))
        self.assertEqual(job['upstream_id'], 'upstream-1')
        self.ace.query_delay = 0
        self.assertEqual(self.wait_job(job['id'])['status'], 'completed')
        self.assertEqual(len(self.ace.submissions), 1)

    def test_ambiguous_submit_is_never_retried(self):
        self.ace.submit_delay = .3
        _, result, _ = self.request('POST', '/api/jobs', self.payload())
        self.assertEqual(self.wait_job(result['job']['id'])['status'], 'unknown')
        time.sleep(.2)
        self.assertEqual(len(self.ace.submissions), 1)

    def test_restart_recovers_known_id_and_marks_unknown_submit(self):
        self.app.close()
        one, _ = self.app.store.create(self.payload('recover'))
        two, _ = self.app.store.create(self.payload('unknown'))
        self.app.store.update(one['id'], status='running', upstream_id='upstream-1')
        self.app.store.update(two['id'], status='submitting')
        self.app.store.db.close()
        self.app = MusicApp(self.tmp.name, self.client, pair_code='123456', poll_interval=.03)
        self.server.app = self.app
        self.assertEqual(self.wait_job(one['id'])['status'], 'completed')
        self.assertEqual(self.app.store.get(two['id'])['status'], 'unknown')
        self.assertEqual(len(self.ace.submissions), 0)

    def test_idempotency_is_atomic_and_conflict_detected(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.app.store.create(self.payload()), range(12)))
        self.assertEqual(len({x[0]['id'] for x in results}), 1)
        self.assertEqual(sum(x[1] for x in results), 1)
        payload = self.payload()
        payload['duration'] = 60
        self.assertEqual(self.request('POST', '/api/jobs', payload)[0], 409)

    def test_auth_csrf_and_pair_limit(self):
        self.assertEqual(self.request('GET', '/api/jobs', auth=False)[0], 401)
        self.assertEqual(self.request('GET', '/audio/no.wav', auth=False)[0], 401)
        self.assertEqual(self.request('POST', '/api/jobs', self.payload(), {'Origin': 'https://evil.test'})[0], 403)
        self.assertEqual(self.request('POST', '/api/session', {'code': '123456'}, {'Sec-Fetch-Site': 'cross-site'})[0], 403)
        self.assertEqual(self.request('POST', '/api/jobs', self.payload(), {'Content-Type': 'text/plain'})[0], 415)
        for _ in range(8):
            status = self.request('POST', '/api/session', {'code': '000000'})[0]
        self.assertEqual(status, 429)

    def test_download_rejects_external_and_redirect_and_nonwav(self):
        for url in ('http://evil.test/v1/audio?path=x', '/other?path=x', '//evil.test/v1/audio?path=x'):
            with self.subTest(url=url), self.assertRaises(UpstreamError):
                self.client.download(url, Path(self.tmp.name) / 'reject.wav')
        self.ace.redirect = True
        with self.assertRaises(UpstreamError):
            self.client.download(self.ace.file, Path(self.tmp.name) / 'redirect.wav')
        self.ace.redirect = False
        self.ace.audio = b'not an audio file'
        with self.assertRaises(UpstreamError):
            self.client.download(self.ace.file, Path(self.tmp.name) / 'invalid.wav')
        self.assertFalse((Path(self.tmp.name) / 'invalid.wav').exists())

    def test_download_accepts_float_wav_and_extensible_but_rejects_truncation(self):
        for extensible in (False, True):
            with self.subTest(extensible=extensible):
                self.ace.audio = float_wav_bytes(extensible)
                target = Path(self.tmp.name) / f'float-{extensible}.wav'
                self.client.download(self.ace.file, target)
                self.assertEqual(target.read_bytes(), self.ace.audio)
        self.ace.audio = float_wav_bytes()[:-1]
        with self.assertRaises(UpstreamError):
            self.client.download(self.ace.file, Path(self.tmp.name) / 'truncated.wav')
        self.ace.audio = float_wav_bytes().replace(b'data\x20\x00\x00\x00', b'data\xff\xff\xff\x7f')
        with self.assertRaises(UpstreamError):
            self.client.download(self.ace.file, Path(self.tmp.name) / 'oversized-chunk.wav')

    def test_manual_end_waiting_releases_queue_without_cancel_or_resubmit(self):
        self.ace.status = 0
        _, first, _ = self.request('POST', '/api/jobs', self.payload('expired-upstream'))
        job_id = first['job']['id']
        self.wait_job(job_id, ('running',))
        _, second, _ = self.request('POST', '/api/jobs', self.payload('next-song'))
        route = f'/api/jobs/{job_id}/resolve-waiting'
        self.assertEqual(self.request('POST', route, {'confirmed': False})[0], 400)
        self.assertEqual(self.app.store.get(job_id)['status'], 'running')
        self.app.generation_lock.acquire()
        try:
            self.assertEqual(self.request('POST', route, {'confirmed': True})[0], 409)
        finally:
            self.app.generation_lock.release()
        status, result, _ = self.request('POST', route, {'confirmed': True})
        self.assertEqual(status, 200)
        self.assertEqual(result['job']['status'], 'failed')
        self.assertIn('未取消', result['job']['error'])
        self.ace.status = 1
        self.assertEqual(self.wait_job(second['job']['id'])['status'], 'completed')
        self.assertEqual(len(self.ace.submissions), 2)
        self.assertEqual(self.app.store.get(job_id)['status'], 'failed')

    def test_bgm_and_auto_generation_rejected(self):
        payload = self.payload()
        payload.update(mode='bgm', lyrics='ignored')
        body = self.client.payload(payload)
        self.assertEqual(body['lyrics'], '[Instrumental]')
        self.assertEqual(body['vocal_language'], 'unknown')
        self.assertIn('instrumental', body['prompt'].lower())
        payload.update(mode='song', lyric_mode='auto', lyrics='')
        self.assertEqual(self.request('POST', '/api/jobs', payload)[0], 400)

    def test_queue_limit_and_input_validation(self):
        self.app.close()
        for number in range(5):
            self.assertEqual(self.request('POST', '/api/jobs', self.payload(str(number)))[0], 202)
        self.assertEqual(self.request('POST', '/api/jobs', self.payload('sixth'))[0], 429)
        self.assertEqual(self.request('POST', '/api/jobs', self.payload('0'))[0], 200)
        invalid = self.payload('bad')
        invalid['duration'] = 45
        self.assertEqual(self.request('POST', '/api/jobs', invalid)[0], 400)

    def test_resume_existing_task_precedes_five_queued_jobs(self):
        self.ace.query_delay = .3
        _, response, _ = self.request('POST', '/api/jobs', self.payload('paused'))
        job = self.wait_job(response['job']['id'], ('paused',), timeout=6)
        for number in range(5):
            status, queued_response, _ = self.request('POST', '/api/jobs', self.payload(str(number)))
            self.assertEqual(status, 202)
        self.assertEqual(len(self.ace.submissions), 1)
        event_count = len(self.ace.events)
        self.ace.query_delay = 0
        status, result, _ = self.request('POST', f'/api/jobs/{job["id"]}/resume', {})
        self.assertEqual(status, 200)
        self.assertEqual(result['job']['status'], 'waiting')
        self.assertEqual(self.wait_job(job['id'])['status'], 'completed')
        self.assertEqual(self.wait_job(queued_response['job']['id'])['status'], 'completed')
        self.assertEqual(self.ace.events[event_count], '/query_result')
        self.assertEqual(len(self.ace.submissions), 6)

    def test_session_logout_host_and_request_size(self):
        self.assertTrue(self.request('GET', '/api/session')[1]['authenticated'])
        self.assertEqual(self.request('GET', '/api/jobs', headers={'Host': 'evil.test'})[0], 403)
        self.assertEqual(self.request('POST', '/api/jobs', {'description': 'a' * 70000})[0], 413)
        self.request('DELETE', '/api/session')
        self.assertFalse(self.request('GET', '/api/session')[1]['authenticated'])
        self.assertEqual(self.request('GET', '/api/jobs')[0], 401)

    def test_lyrics_protocol_editability_and_busy_guard(self):
        status, body, _ = self.request('POST', '/api/lyrics', {'description': '夜空和星星', 'style': '民谣', 'mood': '平静', 'duration': 30})
        self.assertEqual(status, 200)
        self.assertIn('夜空', body['lyrics'])
        self.assertEqual(self.ace.lyric_requests[0]['vocal_language'], 'zh')
        self.assertFalse(self.ace.lyric_requests[0]['instrumental'])
        self.app.generation_lock.acquire()
        try:
            self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[0], 409)
        finally:
            self.app.generation_lock.release()
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[0], 200)
        self.assertEqual(len(self.ace.lyric_requests), 2)
        job, _ = self.app.store.create(self.payload('manual-edited'))
        self.assertEqual(self.client.payload(job)['lyrics'], '夜空中有一颗星')
        self.assertNotIn('sample_query', self.client.payload(job))

    def test_lyric_failure_releases_lock_and_does_not_fake_content(self):
        self.ace.lyrics = ''
        status, data, _ = self.request('POST', '/api/lyrics', self.payload())
        self.assertEqual(status, 502)
        self.assertNotIn('lyrics', data)
        self.ace.lyrics = '词' * 6001
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[0], 502)
        self.ace.lyrics = '已修复的真实模拟响应'
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[1]['lyrics'], self.ace.lyrics)
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload(), auth=False)[0], 401)
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload(), {'Origin': 'http://evil.test'})[0], 403)

    def test_second_worker_cannot_open_same_queue(self):
        with self.assertRaises(StoreError):
            duplicate = MusicApp(self.tmp.name, self.client, pair_code='123456', poll_interval=.03)
            duplicate.close()

    def test_restart_prioritizes_existing_tasks_over_full_new_queue(self):
        self.app.close()
        for number in range(3):
            job, _ = self.app.store.create(self.payload(f'paused-{number}'))
            self.app.store.update(job['id'], status='paused', upstream_id='upstream-1')
        for number in range(5):
            self.app.store.create(self.payload(str(number)))
        self.app.store.recover()
        pending = self.app.store.pending()
        self.assertEqual(len(pending), 8)
        self.assertTrue(all(job['upstream_id'] for job in pending[:3]))
        self.assertTrue(all(job['status'] == 'queued' for job in pending[3:]))

    def test_music_jobs_submit_serially_until_first_completed(self):
        self.ace.status = 0
        _, first, _ = self.request('POST', '/api/jobs', self.payload('first'))
        _, second, _ = self.request('POST', '/api/jobs', self.payload('second'))
        self.wait_job(first['job']['id'], ('running',))
        time.sleep(.2)
        self.assertEqual(len(self.ace.submissions), 1)
        self.assertEqual(self.app.store.get(second['job']['id'])['status'], 'queued')
        self.ace.status = 1
        self.assertEqual(self.wait_job(second['job']['id'])['status'], 'completed')
        self.assertEqual(len(self.ace.submissions), 2)

    def test_unknown_job_requires_explicit_confirmation(self):
        self.app.close()
        job, _ = self.app.store.create(self.payload())
        self.app.store.update(job['id'], status='unknown')
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[0], 409)
        route = f'/api/jobs/{job["id"]}/resolve-unknown'
        self.assertEqual(self.request('POST', route, {'confirmed': False})[0], 400)
        self.assertEqual(self.request('POST', route, {'confirmed': True})[0], 200)
        self.assertEqual(self.app.store.get(job['id'])['status'], 'failed')
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[0], 200)
        self.assertEqual(len(self.ace.submissions), 0)

    def test_health_requires_music_model_readiness_and_reports_lyric_readiness(self):
        self.ace.models_initialized = False
        status, body, _ = self.request('GET', '/api/status')
        self.assertEqual(status, 200)
        self.assertFalse(body['connected'])
        self.assertIn('音乐模型', body['message'])
        payload = self.payload('bgm-without-llm')
        payload.update(mode='bgm', lyrics='')
        _, response, _ = self.request('POST', '/api/jobs', payload)
        time.sleep(.12)
        self.assertEqual(self.app.store.get(response['job']['id'])['status'], 'queued')
        self.assertEqual(self.ace.submissions, [])
        self.ace.health_truncated = True
        self.assertFalse(self.request('GET', '/api/status')[1]['connected'])
        time.sleep(1.05)
        self.assertEqual(self.app.store.get(response['job']['id'])['status'], 'queued')
        self.assertEqual(self.ace.submissions, [])
        self.ace.health_truncated = False
        self.ace.models_initialized = True
        self.ace.llm_initialized = False
        _, body, _ = self.request('GET', '/api/status')
        self.assertTrue(body['connected'])
        self.assertFalse(body['lyrics_ready'])
        self.assertIn('歌词模型', body['message'])
        self.assertEqual(self.wait_job(response['job']['id'])['status'], 'completed')

    def test_uncertain_lyrics_persists_and_blocks_submission_until_ack(self):
        # Shorten the timeout, but use an actual delayed HTTP response from fake ACE.
        self.ace.lyric_delay = .3
        original_open = self.client._open
        def short_timeout(path, body=None, timeout=None):
            return original_open(path, body, timeout=.05 if path == '/v1/create_sample' else timeout)
        with patch.object(self.client, '_open', side_effect=short_timeout):
            self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[0], 502)
        self.assertFalse(self.app.lyrics_active)
        self.assertTrue(self.request('GET', '/api/status')[1]['model_uncertain'])
        self.assertEqual(self.request('POST', '/api/lyrics', self.payload())[0], 409)
        _, result, _ = self.request('POST', '/api/jobs', self.payload('waiting-for-lm'))
        time.sleep(.15)
        self.assertEqual(len(self.ace.submissions), 0)
        self.app.close()
        self.app.store.db.close()
        self.app = MusicApp(self.tmp.name, self.client, pair_code='123456', poll_interval=.03)
        self.server.app = self.app
        self.request('POST', '/api/session', {'code': '123456'})
        self.assertTrue(self.app.store.model_uncertain())
        self.assertEqual(self.request('POST', '/api/resolve-model', {'confirmed': False})[0], 400)
        self.assertEqual(self.request('POST', '/api/resolve-model', {'confirmed': True})[0], 200)
        self.assertEqual(self.wait_job(result['job']['id'])['status'], 'completed')
        self.assertEqual(len(self.ace.submissions), 1)
        self.assertEqual(len(self.ace.lyric_requests), 1)

    def test_active_lyrics_status_skips_health_and_hides_uncertainty(self):
        self.ace.lyric_delay = .4
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            writing = pool.submit(self.request, 'POST', '/api/lyrics', self.payload())
            deadline = time.monotonic() + 2
            while not self.ace.lyric_requests and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(self.ace.lyric_requests)
            status, body, _ = self.request('GET', '/api/status')
            self.assertEqual(status, 200)
            self.assertTrue(body['processing_lyrics'])
            self.assertFalse(body['model_uncertain'])
            self.assertFalse(body['connected'])
            self.assertFalse(body['lyrics_ready'])
            self.assertTrue(self.app.store.model_uncertain())
            self.assertEqual(self.ace.health_requests, 0)
            self.assertEqual(writing.result()[0], 200)
        self.assertFalse(self.app.lyrics_active)
        self.assertFalse(self.app.store.model_uncertain())
        self.assertTrue(self.request('GET', '/api/status')[1]['connected'])
        self.assertEqual(self.ace.health_requests, 1)


if __name__ == '__main__':
    unittest.main()
