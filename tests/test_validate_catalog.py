"""Regression tests against copies of the real catalog; no third-party dependencies.

Symbolic-link coverage is guarded by an actual capability probe: on hosts where
creating a symlink fails (e.g. Windows without developer mode or the
SeCreateSymbolicLink privilege), only the tests that truly require symlinks
skip, each with the probe's reason. Every other check always runs.
"""
import csv
import errno
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def _ignore_runtime(directory, names):
    ignored = {'.git', '__pycache__', '.venv', 'node_modules'} & set(names)
    if Path(directory) == ROOT:
        ignored.update({'work'} & set(names))
    if Path(directory) == ROOT / 'data':
        ignored.update({'music'} & set(names))
    return ignored


def _probe_symlink_support():
    """Return (supported, reason) by really creating and reading one symlink.

    This function must be called before any test monkeypatches Path.symlink_to.
    Only genuine "symlinks not permitted/available" outcomes are reported as
    unsupported; any other OSError propagates so it is visible as a test error.
    """
    base = Path(tempfile.mkdtemp(prefix='symlink-probe-'))
    try:
        source = base / 'probe-source.md'
        source.write_text('probe', encoding='utf8')
        link = base / 'probe-link.md'
        try:
            link.symlink_to(source.name)
        except NotImplementedError:
            return False, 'os.symlink is not implemented on this platform'
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314 or exc.errno in (errno.EPERM, errno.EACCES):
                return False, 'creating symbolic links is not permitted on this host: ' + str(exc)
            raise
        link.read_text(encoding='utf8')
        return True, ''
    finally:
        shutil.rmtree(base, ignore_errors=True)


class CatalogValidationTests(unittest.TestCase):
    invocations = 0
    symlink_support = None

    @classmethod
    def tearDownClass(cls):
        print(f"Validator subprocess invocations: {cls.invocations} (normal and -O)")

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'repo'
        shutil.copytree(ROOT, self.root, ignore=_ignore_runtime)

    def require_symlinks(self):
        if type(self).symlink_support is None:
            type(self).symlink_support = _probe_symlink_support()
        supported, reason = self.symlink_support
        if not supported:
            self.skipTest('host does not support creating symbolic links: ' + reason)

    def read_json(self):
        return json.loads((self.root / 'data/projects.json').read_text(encoding='utf8'))

    def write_json(self, data, sync=False):
        (self.root / 'data/projects.json').write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
        if sync:
            self.write_csv('projects.csv', data['projects'][0].keys(),
                           [{k: ' | '.join(v) if k == 'sources' else str(v) for k, v in p.items()}
                            for p in data['projects']])

    def read_csv(self, name):
        with (self.root / 'data' / name).open(encoding='utf-8-sig', newline='') as handle:
            reader = csv.DictReader(handle)
            return reader.fieldnames, list(reader)

    def write_csv(self, name, fields, rows):
        with (self.root / 'data' / name).open('w', encoding='utf-8-sig', newline='') as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)

    def run_validator(self, good=False, contains=None):
        for flag in ([], ['-O']):
            with self.subTest(mode=flag or 'normal'):
                type(self).invocations += 1
                result = subprocess.run([sys.executable, *flag, str(self.root / 'scripts/validate_catalog.py')],
                                        cwd=self.temp.name, capture_output=True, text=True, timeout=15)
                output = result.stdout + result.stderr
                self.assertEqual(result.returncode, 0 if good else 1, output)
                self.assertNotIn('Traceback', output)
                self.assertIn('PASS:' if good else 'FAIL:', output)
                if contains:
                    self.assertIn(contains, output)
        return output

    def add_markdown(self, text, name='fixture.md'):
        target = self.root / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding='utf8')

    def test_real_catalog(self):
        self.run_validator(good=True)

    def test_top_level_shapes(self):
        original = self.read_json()
        cases = [None, [], 'catalog', 1, {}, {**original, 'extra': 1}]
        for value in cases:
            with self.subTest(value=value if not isinstance(value, dict) else list(value)):
                self.write_json(value)
                self.run_validator(contains='top-level')

    def test_schema_versions(self):
        original = self.read_json()
        for value in (True, False, None, '1', 1.0, 2):
            with self.subTest(value=value):
                self.write_json({**original, 'schema_version': value})
                self.run_validator(contains='schema_version')

    def test_top_metadata(self):
        original = self.read_json()
        for field, value in [('scope', ''), ('scope', ' '), ('scope', None), ('scope', []),
                             ('checked_at', '2026-02-30'), ('checked_at', '2026-1-01'),
                             ('checked_at', None), ('checked_at', 20261009)]:
            with self.subTest(field=field, value=value):
                self.write_json({**original, field: value})
                self.run_validator()

    def test_project_list_shapes_and_counts(self):
        original = self.read_json()
        for value in (None, {}, 'projects', [], original['projects'][:-1], original['projects'] * 2):
            self.write_json({**original, 'projects': value})
            self.run_validator(contains='list of 19')

    def test_project_object_shapes(self):
        original = self.read_json()
        first = original['projects'][0]
        for value in (None, [], 'project', {}, {**first, 'extra': 1}, {k: v for k, v in first.items() if k != 'name'}):
            original['projects'][0] = value
            self.write_json(original)
            self.run_validator(contains='incorrect fields/object')

    def test_text_field_types_and_empty_values(self):
        original = self.read_json()
        for field in original['projects'][0]:
            if field in ('sources', 'runtime_tested', 'commit_pinned'):
                continue
            for value in (None, '', '  ', 42, [], {}):
                with self.subTest(field=field, value=value):
                    data = json.loads(json.dumps(original))
                    data['projects'][0][field] = value
                    self.write_json(data)
                    self.run_validator(contains=field + ' must be a nonempty string')

    def test_project_bad_values(self):
        original = self.read_json()
        cases = [('id', 'Bad ID'), ('id', '-'), ('id', original['projects'][1]['id']),
                 ('checked_at', '2026-02-30'), ('checked_at', '2026-13-01'),
                 ('checked_at', '2026-1-01'), ('research_group', 'other'), ('evidence_level', 'unknown'),
                 ('runtime_tested', 0), ('runtime_tested', 'False'), ('commit_pinned', None),
                 ('sources', None), ('sources', 'https://example.com'), ('sources', []),
                 ('sources', [None]), ('sources', [{}]), ('sources', ['https://example.com'] * 2)]
        for field, value in cases:
            with self.subTest(field=field, value=value):
                data = json.loads(json.dumps(original))
                data['projects'][0][field] = value
                self.write_json(data)
                self.run_validator()

    def test_invalid_urls(self):
        original = self.read_json()
        for url in ('http://example.com', 'https://', 'https://[oops', 'https://example.com:bad',
                    'https://example.com:99999', 'https://example.com/a b', 'https://user:pass@example.com',
                    'https://example.com\\escape'):
            with self.subTest(url=url):
                original['projects'][0]['repository'] = url
                self.write_json(original)
                self.run_validator(contains='malformed repository URL')

    def test_detail_paths(self):
        """Path rejections that never need symlinks; they always run on any host."""
        original = self.read_json()
        external = Path(self.temp.name) / 'outside.md'
        external.write_text('# Outside', encoding='utf8')
        for path in (str(external), '../outside.md', 'docs/../README.md', 'C:/outside.md',
                     'C:\\outside.md', 'docs\\\\ai-generation.md', 'docs', 'missing.md'):
            with self.subTest(path=path):
                original['projects'][0]['detail_document'] = path
                self.write_json(original, sync=True)
                self.run_validator()

    def test_detail_symlink_escape_and_cycle(self):
        """Symlink-based escapes require real symlink support; otherwise skip with reason."""
        self.require_symlinks()
        original = self.read_json()
        external = Path(self.temp.name) / 'outside.md'
        external.write_text('# Outside', encoding='utf8')
        (self.root / 'escape.md').symlink_to(external)
        (self.root / 'cycle.md').symlink_to('cycle.md')
        for path in ('escape.md', 'cycle.md'):
            with self.subTest(path=path):
                original['projects'][0]['detail_document'] = path
                self.write_json(original, sync=True)
                self.run_validator()

    def test_bad_json_and_encoding(self):
        path = self.root / 'data/projects.json'
        for data in (b'{bad', b'{"schema_version":1,"schema_version":1}', b'\xff'):
            path.write_bytes(data)
            self.run_validator()

    def test_missing_files(self):
        for name in ('data/projects.json', 'data/projects.csv', 'data/sources.csv', 'docs/ai-generation.md'):
            path = self.root / name
            saved = path.read_bytes()
            path.unlink()
            self.run_validator()
            path.write_bytes(saved)

    def test_bad_csv_headers_and_widths(self):
        for name in ('projects.csv', 'sources.csv'):
            path = self.root / 'data' / name
            saved = path.read_bytes()
            for data in (b'', b'wrong,header\na,b\n', b'url,url,source_kind,checked_at\na,b,c,d\n',
                         saved + b'one,two\n', saved + b'"unterminated\n', saved + b'\xff'):
                with self.subTest(name=name, data=data[:50]):
                    path.write_bytes(data)
                    self.run_validator()
            path.write_bytes(saved)

    def test_json_csv_mismatch(self):
        data = self.read_json()
        data['projects'][0]['name'] = 'Changed'
        self.write_json(data)
        self.run_validator(contains='JSON/CSV contents differ')

    def test_source_ownership_and_metadata(self):
        fields, original = self.read_csv('sources.csv')
        for field, value in [('project_ids', ''), ('project_ids', 'heartmula'),
                             ('project_ids', 'lmms | heartmula'), ('project_ids', 'lmms | lmms'),
                             ('project_ids', 'unknown'), ('checked_at', '2026-02-30'),
                             ('source_kind', ''), ('source_kind', 'unknown'), ('url', 'https://example.com')]:
            with self.subTest(field=field, value=value):
                rows = [dict(row) for row in original]
                rows[0][field] = value
                self.write_csv('sources.csv', fields, rows)
                self.run_validator()
        for rows in (original[:-1], original + original[:1]):
            self.write_csv('sources.csv', fields, rows)
            self.run_validator()

    def test_shared_url_requires_exact_owners(self):
        data = self.read_json()
        url = data['projects'][0]['sources'][0]
        data['projects'][1]['sources'].append(url)
        self.write_json(data, sync=True)
        fields, rows = self.read_csv('sources.csv')
        self.run_validator(contains='incorrect project ownership')
        row = next(r for r in rows if r['url'] == url)
        row['project_ids'] += ' | heartmula'
        self.write_csv('sources.csv', fields, rows)
        self.run_validator(good=True)

    def test_broken_markdown(self):
        for text in ('[x](missing.md)', '[](missing.md)', '![](missing.png)', '```inline code```\n\n[x](missing.md)', '`<!--`\n\n[x](missing.md)', '```html <!--\nexample\n```\n[x](missing.md)', '```html\n<!--\n```\n[x](missing.md)', '[x][ref]\n\n[ref]: missing.md', '[ref][]\n\n[ref]: missing.md',
                     '[ref]\n\n[ref]: missing.md', '[x][undefined]', '[undefined][]',
                     '[x](README.md#missing)', '[x](#missing)', '[x](../outside.md)',
                     '[x](%2e%2e/outside.md)', '[x](/etc/passwd)', '[x](README.md#%E4%B8%8D%E5%AD%98%E5%9C%A8)'):
            with self.subTest(text=text):
                self.add_markdown(text)
                self.run_validator()

    def test_markdown_code_and_comments_ignored(self):
        self.add_markdown('''# Example
`[x](missing.md)` and ``[x][undefined]``
<!-- [x](missing.md) -->
<!--
```
[x](missing.md)
-->
```md
[x](missing.md)
# Not a heading
```
~~~
[x][undefined]
~~~
    [x](missing.md)
\t[x](missing.md)
- ```md
  [x](missing.md)
  ```
> ```md
> [x](missing.md)
> ```
Ordinary [brackets] and \\[x](missing.md)
''')
        self.run_validator(good=True)

    def test_markdown_anchors_references_and_titles(self):
        self.add_markdown('''# Hello, World!
# _Emphasized_
# `_Hello_`
# __hello_world__
# _hello_world_
# [Linked][guide]
# 中文 标题
# Repeat
# Repeat
Setext title
============
[x](#_hello_) [x](#hello_world) [x](#hello_world-1) [x](#emphasized) [x](#linked) [x](#hello-world) [x](#中文-标题) [x](#repeat-1) [x](#setext-title)
[x][ Guide ] [guide][] [guide]
[guide]: README.md "A title"
[x](README.md "Title (with parentheses)")
[x](<docs/file space.md>)
[x](docs/file(name).md#nested)
[x](docs/file%20space.md#space)
''')
        self.add_markdown('# Space', 'docs/file space.md')
        self.add_markdown('# Nested', 'docs/file(name).md')
        self.run_validator(good=True)

    def test_nested_internal_markdown_document_accepted(self):
        """A Markdown file in a nested directory must be scanned on Windows too.

        rglob() yields backslash separators there; the validator converts them
        to POSIX form before its portability checks. The two links inside the
        nested document raise the baseline link count by two, proving
        the file was actually discovered and validated instead of skipped.
        """
        baseline = self.run_validator(good=True)
        count = int(re.search(r'(\d+) internal links', baseline).group(1))
        self.add_markdown('# Nested Guide\n\nSee [self](#nested-guide) and [top](../../README.md).\n',
                          'docs/nested/guide.md')
        self.run_validator(good=True, contains=f'{count + 2} internal links')

    def test_markdown_symlink_escape(self):
        self.require_symlinks()
        external = Path(self.temp.name) / 'outside.md'
        external.write_text('# Outside', encoding='utf8')
        (self.root / 'escape.md').symlink_to(external)
        self.run_validator(contains='escaping file')

    def test_valid_leap_day_checked_at(self):
        """Leap-day dates are always valid; this check never depends on symlinks."""
        data = self.read_json()
        data['projects'][0]['checked_at'] = '2024-02-29'
        self.write_json(data, sync=True)
        self.run_validator(good=True)

    def test_valid_local_symlink_to_internal_markdown(self):
        """An in-repo symlink as detail_document is accepted (needs symlink support)."""
        self.require_symlinks()
        data = self.read_json()
        data['projects'][0]['checked_at'] = '2024-02-29'
        (self.root / 'detail.md').symlink_to('docs/ai-generation.md')
        data['projects'][0]['detail_document'] = 'detail.md'
        self.write_json(data, sync=True)
        self.run_validator(good=True)


class SymlinkProbeTests(unittest.TestCase):
    """The guard itself: unsupported hosts must skip with a reason, other
    failures must surface as errors instead of being misread as skips."""

    def test_unsupported_probe_reports_nonempty_reason(self):
        original = Path.symlink_to

        def denied(self, target, *args, **kwargs):
            raise OSError(errno.EACCES, 'injected symlink denial')

        Path.symlink_to = denied
        try:
            supported, reason = _probe_symlink_support()
        finally:
            Path.symlink_to = original
        self.assertFalse(supported)
        self.assertTrue(reason.strip(), 'a skip on an unsupported host must carry a nonempty reason')

    def test_unexpected_probe_errors_propagate(self):
        original = Path.symlink_to

        def broken(self, target, *args, **kwargs):
            raise OSError(errno.EIO, 'injected I/O error')

        Path.symlink_to = broken
        try:
            with self.assertRaises(OSError):
                _probe_symlink_support()
        finally:
            Path.symlink_to = original

    def test_unexpected_symlink_read_errors_propagate(self):
        with patch.object(Path, 'symlink_to', return_value=None), patch.object(
                Path, 'read_text', side_effect=OSError(errno.EIO, 'injected read failure')):
            with self.assertRaises(OSError) as caught:
                _probe_symlink_support()
        self.assertEqual(caught.exception.errno, errno.EIO)

    def test_probe_errors_do_not_block_unrelated_catalog_tests(self):
        suite = unittest.TestSuite(CatalogValidationTests(name) for name in (
            'test_detail_paths', 'test_valid_leap_day_checked_at',
            'test_detail_symlink_escape_and_cycle'))
        result = unittest.TestResult()
        with patch(__name__ + '._probe_symlink_support',
                   side_effect=OSError(errno.EIO, 'injected probe failure')), patch.object(
                       CatalogValidationTests, 'symlink_support', None):
            suite.run(result)
        self.assertEqual(result.testsRun, 3)
        self.assertEqual(result.failures, [])
        self.assertEqual(result.skipped, [])
        self.assertEqual(len(result.errors), 1)
        self.assertEqual(result.errors[0][0]._testMethodName, 'test_detail_symlink_escape_and_cycle')


if __name__ == '__main__':
    unittest.main()
