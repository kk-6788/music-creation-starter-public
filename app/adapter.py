"""Bounded, authenticated ACE-Step REST transport; no generation fallback."""
import http.client
import json
import os
from pathlib import Path
import socket
import struct
import urllib.error
import urllib.parse
import urllib.request
from .preferences import caption_preferences


class UpstreamError(Exception):
    def __init__(self, message, retryable=False, uncertain=False):
        super().__init__(message)
        self.retryable = retryable
        self.uncertain = uncertain


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def validate_wave(path, max_bytes):
    """Validate bounded RIFF structure without decoding or rewriting PCM/float samples."""
    size = path.stat().st_size
    invalid = '模型返回的 WAV 容器无效、截断或音频格式不受支持。'
    if not 44 <= size <= max_bytes:
        raise UpstreamError(invalid)
    with path.open('rb') as stream:
        header = stream.read(12)
        if header[:4] != b'RIFF' or header[8:] != b'WAVE' or struct.unpack_from('<I', header, 4)[0] + 8 != size:
            raise UpstreamError(invalid)
        block_align = None
        audio_bytes = 0
        chunks = 0
        while stream.tell() < size:
            chunks += 1
            chunk_header = stream.read(8)
            if len(chunk_header) != 8 or chunks > 10000:
                raise UpstreamError(invalid)
            kind, length = struct.unpack('<4sI', chunk_header)
            next_offset = stream.tell() + length + (length & 1)
            if length > max_bytes or next_offset > size:
                raise UpstreamError(invalid)
            if kind == b'fmt ':
                if block_align is not None or not 16 <= length <= 4096:
                    raise UpstreamError(invalid)
                fmt = stream.read(length)
                code, channels, rate, byte_rate, alignment, bits = struct.unpack_from('<HHIIHH', fmt)
                if code == 65534:
                    if length < 40:
                        raise UpstreamError(invalid)
                    extra, valid_bits = struct.unpack_from('<HH', fmt, 16)
                    if extra < 22 or 18 + extra > length or not 0 < valid_bits <= bits or fmt[28:40] != bytes.fromhex('00001000800000aa00389b71'):
                        raise UpstreamError(invalid)
                    code = struct.unpack_from('<I', fmt, 24)[0]
                if (code == 1 and bits not in (8, 16, 24, 32)) or (code == 3 and bits not in (32, 64)) or code not in (1, 3):
                    raise UpstreamError(invalid)
                if not 1 <= channels <= 64 or not 1 <= rate <= 768000 or alignment != channels * (bits // 8) or byte_rate != rate * alignment:
                    raise UpstreamError(invalid)
                block_align = alignment
            elif kind == b'data':
                if block_align is None or length % block_align:
                    raise UpstreamError(invalid)
                audio_bytes += length
            stream.seek(next_offset)
        if block_align is None or audio_bytes < block_align:
            raise UpstreamError(invalid)


class AceClient:
    def __init__(self, base_url=None, api_key=None, timeout=15, max_audio_bytes=200 * 1024 * 1024):
        self.base_url = (base_url or os.environ.get('MUSIC_ACESTEP_URL', 'http://127.0.0.1:8001')).rstrip('/')
        parsed = urllib.parse.urlsplit(self.base_url)
        if parsed.scheme not in ('http', 'https') or parsed.hostname not in ('127.0.0.1', 'localhost', '::1') or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('MUSIC_ACESTEP_URL 必须是本机 ACE-Step 服务地址，例如 http://127.0.0.1:8001')
        self.origin = (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
        self.api_key = api_key if api_key is not None else os.environ.get('ACESTEP_API_KEY', '')
        self.timeout = timeout
        self.max_audio_bytes = max_audio_bytes
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def _open(self, path, body=None, timeout=None):
        headers = {'Accept': 'application/json'}
        if self.api_key:
            headers['Authorization'] = 'Bearer ' + self.api_key
        raw = None
        if body is not None:
            headers['Content-Type'] = 'application/json'
            raw = json.dumps(body, ensure_ascii=False).encode('utf-8')
        request = urllib.request.Request(self.base_url + path, data=raw, headers=headers)
        try:
            return self.opener.open(request, timeout=self.timeout if timeout is None else timeout)
        except urllib.error.HTTPError as exc:
            if exc.code in (401, 403):
                message = 'ACE-Step 认证失败，请检查电脑端 ACESTEP_API_KEY。'
            elif 300 <= exc.code < 400:
                message = 'ACE-Step 返回了不允许的跳转。'
            else:
                message = f'ACE-Step 请求失败（HTTP {exc.code}）。自动写词还需要服务端已加载语言模型。'
            raise UpstreamError(message, retryable=exc.code >= 500, uncertain=exc.code not in (400, 401, 403, 422, 503)) from exc
        except (http.client.HTTPException, urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
            raise UpstreamError('暂时无法连接 ACE-Step 或请求超时，请检查电脑端模型服务。', retryable=True, uncertain=True) from exc

    def _json(self, path, body=None, timeout=None):
        try:
            with self._open(path, body, timeout=timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
            if len(raw) > 2 * 1024 * 1024:
                raise UpstreamError('ACE-Step 响应超过允许大小。', uncertain=True)
            result = json.loads(raw)
            if not isinstance(result, dict) or result.get('code') != 200 or result.get('error'):
                raise UpstreamError('ACE-Step 返回失败。使用自动写词时，请确认服务端已加载语言模型；可改为手动歌词。', uncertain=True)
            return result.get('data')
        except (ValueError, UnicodeDecodeError) as exc:
            raise UpstreamError('ACE-Step 返回的数据格式无法识别。', uncertain=True) from exc
        except (http.client.HTTPException, TimeoutError, OSError) as exc:
            raise UpstreamError('读取 ACE-Step 响应超时。', retryable=True, uncertain=True) from exc

    def health(self):
        data = self._json('/health')
        if not isinstance(data, dict) or data.get('models_initialized') is not True:
            raise UpstreamError('ACE-Step 服务已响应，但音乐模型尚未完成加载或初始化失败，请查看电脑端模型日志。')
        return {'models_initialized': True, 'llm_initialized': data.get('llm_initialized') is True}

    def create_lyrics(self, description, style, mood, duration):
        query = f'请写一首中文歌曲的完整歌词，主题：{description}。风格：{style}。情绪：{mood}。时长约{duration}秒。'
        result = self._json('/v1/create_sample', {'query': query, 'vocal_language': 'zh', 'instrumental': False}, timeout=180)
        if not isinstance(result, dict) or not isinstance(result.get('lyrics'), str) or not result['lyrics'].strip():
            raise UpstreamError('语言模型未返回歌词；请确认 ACE-Step 已加载语言模型，或直接手写歌词。')
        if len(result['lyrics']) > 6000:
            raise UpstreamError('模型歌词超过 6000 字，请缩短创作描述后重试。')
        caption = result.get('caption', '')
        if not isinstance(caption, str) or len(caption) > 4000:
            caption = ''
        return {'lyrics': result['lyrics'].strip(), 'caption': caption}

    @staticmethod
    def payload(job):
        prompt = '；'.join(x for x in (job['description'], job['style'], job['mood'], caption_preferences(job)) if x)
        if job['mode'] == 'song':
            prompt = ('A vocal song with a lead singer clearly singing the provided Mandarin Chinese lyrics from the beginning; '
                      'Clear Mandarin diction, crisp consonants and vowels, natural syllabic phrasing and breaths; '
                      'upfront solo vocal, light reverb, quieter accompaniment; ' + prompt)
        body = {'prompt': prompt, 'lyrics': job['lyrics'], 'audio_duration': job['duration'], 'batch_size': 1, 'audio_format': 'wav', 'thinking': job['mode'] == 'song', 'use_cot_caption': False, 'use_cot_language': False, 'vocal_language': 'zh'}
        if job['mode'] == 'bgm':
            body.update(prompt=prompt + '; instrumental, no vocals', lyrics='[Instrumental]', vocal_language='unknown')
        return body

    def submit(self, job):
        result = self._json('/release_task', self.payload(job))
        task_id = result.get('task_id') if isinstance(result, dict) else None
        if not isinstance(task_id, str) or not task_id or len(task_id) > 512:
            raise UpstreamError('模型服务未返回任务编号，提交结果未知，请勿重复提交。')
        return task_id

    def query(self, task_id):
        result = self._json('/query_result', {'task_id_list': [task_id]})
        if not isinstance(result, list):
            raise UpstreamError('模型任务查询格式无法识别。', retryable=True)
        matches = [item for item in result if isinstance(item, dict) and item.get('task_id') == task_id]
        if len(matches) != 1:
            raise UpstreamError('模型服务暂未返回该任务，保留编号稍后查询。', retryable=True)
        item = matches[0]
        if item.get('status') == 0:
            return None
        if item.get('status') == 2:
            raise UpstreamError('ACE-Step 生成失败。自动写词需要服务端语言模型；请检查模型日志。')
        if item.get('status') != 1:
            raise UpstreamError('模型任务状态无法识别。', retryable=True)
        try:
            outputs = json.loads(item['result'])
            if not isinstance(outputs, list) or not outputs or not isinstance(outputs[0], dict) or not isinstance(outputs[0].get('file'), str):
                raise ValueError('missing output')
            return outputs[0]
        except (KeyError, TypeError, ValueError) as exc:
            raise UpstreamError('模型已结束，但没有可读取的音频结果。') from exc

    def download(self, source, destination):
        try:
            parsed = urllib.parse.urlsplit(source)
            origin = (parsed.scheme, parsed.hostname, parsed.port or (443 if parsed.scheme == 'https' else 80))
        except ValueError as exc:
            raise UpstreamError('模型音频地址不合法。') from exc
        if (parsed.scheme or parsed.netloc) and origin != self.origin:
            raise UpstreamError('拒绝从本机模型服务以外的地址下载音频。')
        if parsed.path != '/v1/audio' or parsed.username or parsed.password or parsed.fragment or '\\' in source or any(ord(c) < 32 for c in source):
            raise UpstreamError('仅接受模型服务的 /v1/audio 下载地址。')
        query = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
        if set(query) != {'path'} or len(query['path']) != 1 or not query['path'][0]:
            raise UpstreamError('模型音频下载参数不合法。')
        # The file path is supplied by ACE-Step only, never by the browser.
        route = urllib.parse.urlunsplit(('', '', '/v1/audio', parsed.query, ''))
        destination = Path(destination)
        temporary = destination.with_suffix('.part')
        try:
            with self._open(route) as response, temporary.open('wb') as output:
                length = response.headers.get('Content-Length')
                if length and (not length.isdigit() or int(length) > self.max_audio_bytes):
                    raise UpstreamError('模型音频大小超过 200 MB 限制。')
                size = 0
                while True:
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_audio_bytes:
                        raise UpstreamError('模型音频大小超过 200 MB 限制。')
                    output.write(chunk)
                if length and size != int(length):
                    raise UpstreamError('音频下载不完整，稍后重新读取。', retryable=True)
            validate_wave(temporary, self.max_audio_bytes)
            os.replace(temporary, destination)
        except (http.client.HTTPException, TimeoutError, OSError) as exc:
            raise UpstreamError('保存音频失败或下载超时，任务编号已保留。', retryable=True) from exc
        finally:
            temporary.unlink(missing_ok=True)
