#!/usr/bin/env python3
"""Offline catalog validation (Python >= 3.9); no dependencies or HTTP requests.

Markdown support and deliberate limits are documented in docs/validation-report.md.
"""
from collections import defaultdict
import csv
from datetime import date
import html
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ('id', 'name', 'research_group', 'category', 'input_output', 'beginner_fit',
          'chinese_evidence', 'deployment', 'code_license', 'model_or_asset_license',
          'output_terms', 'commercial_caution', 'repository', 'checked_at',
          'evidence_level', 'runtime_tested', 'commit_pinned', 'detail_document', 'sources')
SOURCE_FIELDS = ('url', 'project_ids', 'source_kind', 'checked_at')
TOP_FIELDS = {'schema_version', 'checked_at', 'scope', 'projects'}
BOOL_FIELDS = {'runtime_tested', 'commit_pinned'}


class ValidationError(ValueError):
    """Invalid input, rendered by the CLI without a traceback."""


def require(condition, message):
    if not condition:
        raise ValidationError(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip()) and '\x00' not in value


def valid_date(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', value):
        return False
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        return False


def valid_url(value):
    if not nonempty(value) or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        parsed = urlsplit(value)
        # Access port to reject malformed/out-of-range port strings as well.
        port = parsed.port
        return (parsed.scheme == 'https' and bool(parsed.hostname)
                and not parsed.username and not parsed.password
                and '\\' not in value and (port is None or port > 0))
    except ValueError:
        return False


def contained_file(root, parent, target, strict_relative=False):
    require(nonempty(target), 'empty/invalid file path')
    require(not PurePosixPath(target).is_absolute()
            and not PureWindowsPath(target).drive and '\\' not in target,
            'absolute or non-portable file path: ' + target)
    if strict_relative:
        require('..' not in PurePosixPath(target).parts, 'parent traversal: ' + target)
    dest = (parent / target).resolve()
    require(dest.is_relative_to(root) and dest.is_file(), 'missing/escaping file: ' + target)
    return dest


def read_csv(path, fields):
    with path.open(encoding='utf-8-sig', newline='') as handle:
        reader = csv.reader(handle, strict=True)
        header = next(reader, None)
        require(header is not None and len(header) == len(fields)
                and len(set(header)) == len(header) and set(header) == set(fields),
                str(path.name) + ': incorrect/duplicate CSV headers')
        rows = []
        for row in reader:
            require(len(row) == len(header),
                    f'{path.name}:{reader.line_num}: incorrect CSV row width')
            rows.append(dict(zip(header, row)))
        return rows


def unique_object(pairs):
    obj = {}
    for key, value in pairs:
        require(key not in obj, 'duplicate JSON key: ' + key)
        obj[key] = value
    return obj


def validate_data(root):
    data = json.loads((root / 'data/projects.json').read_text(encoding='utf-8'),
                      object_pairs_hook=unique_object)
    require(isinstance(data, dict) and set(data) == TOP_FIELDS, 'incorrect catalog top-level fields')
    require(type(data['schema_version']) is int and data['schema_version'] == 1,
            'schema_version must be integer 1 (not boolean)')
    require(valid_date(data['checked_at']), 'invalid catalog checked_at date')
    require(nonempty(data['scope']), 'scope must be a nonempty string')
    projects = data['projects']
    require(isinstance(projects, list) and len(projects) == 19, 'projects must be a list of 19 entries')
    ids, urls = set(), set()
    owners = defaultdict(set)
    for index, project in enumerate(projects):
        context = f'projects[{index}]'
        require(isinstance(project, dict) and set(project) == set(FIELDS), context + ': incorrect fields/object')
        for key in FIELDS:
            value = project[key]
            if key in BOOL_FIELDS:
                require(type(value) is bool, context + ': ' + key + ' must be boolean')
            elif key == 'sources':
                require(isinstance(value, list) and value and all(valid_url(url) for url in value),
                        context + ': sources must be a nonempty list of HTTPS URLs')
                require(len(value) == len(set(value)), context + ': duplicate sources')
            else:
                require(nonempty(value), context + ': ' + key + ' must be a nonempty string')
        pid = project['id']
        require(re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', pid) and pid not in ids,
                context + ': duplicate/invalid id')
        ids.add(pid)
        require(valid_date(project['checked_at']), pid + ': invalid checked_at date')
        require(project['research_group'] in ('ai', 'ui'), pid + ': invalid research_group')
        require(project['evidence_level'] in ('official-document-review', 'official-access-blocked-secondary-history'),
                pid + ': invalid evidence_level')
        require(valid_url(project['repository']), pid + ': malformed repository URL')
        contained_file(root, root, project['detail_document'], strict_relative=True)
        urls.add(project['repository'])
        urls.update(project['sources'])
        for url in project['sources']:
            owners[url].add(pid)
    rows = read_csv(root / 'data/projects.csv', FIELDS)
    expected = [{k: (' | '.join(v) if k == 'sources' else str(v)) for k, v in p.items()} for p in projects]
    require(rows == expected, 'JSON/CSV contents differ')
    sources = read_csv(root / 'data/sources.csv', SOURCE_FIELDS)
    seen = set()
    for index, row in enumerate(sources, 2):
        context = f'sources.csv:{index}'
        url = row['url']
        require(valid_url(url) and url not in seen, context + ': invalid/duplicate URL')
        seen.add(url)
        pids = row['project_ids'].split(' | ')
        require(all(nonempty(pid) for pid in pids) and len(pids) == len(set(pids)),
                context + ': empty/duplicate project IDs')
        require(set(pids) == owners.get(url, set()), context + ': incorrect project ownership for ' + url)
        require(valid_date(row['checked_at']), context + ': invalid checked_at date')
        require(row['source_kind'] in ('primary-or-official-reference', 'secondary-community'),
                context + ': invalid source_kind')
    require(seen == set(owners), 'source index missing or extra URLs')
    return len(projects), len(seen), len(urls)


def prose_lines(text):
    """Mask block code/comments, preserving single-line inline-code literals."""
    result, fence, comment = [], None, False
    inline_or_comment = re.compile(r'(`+)(?!`)(.*?)(?<!`)\1(?!`)|<!--')
    for line in text.splitlines():
        if not fence and not comment:
            candidate = re.sub(r'^ {0,3}(?:[-+*]|[0-9]+[.)]) +', '', line)
            candidate = re.sub(r'^ {0,3}> ?', '', candidate)
            opening = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', candidate)
            if opening and not (opening[1][0] == '`' and '`' in opening[2]):
                fence = (opening[1][0], len(opening[1]))
                result.append('')
                continue
        if not fence:
            if not comment and line.startswith(('    ', '\t')):
                result.append('')
                continue
            clean, cursor = '', 0
            while cursor < len(line):
                if comment:
                    close = line.find('-->', cursor)
                    if close < 0:
                        break
                    cursor, comment = close + 3, False
                    continue
                token = inline_or_comment.search(line, cursor)
                if not token:
                    clean += line[cursor:]
                    break
                clean += line[cursor:token.start()]
                if token[0] == '<!--':
                    comment = True
                else:
                    clean += token[0]
                cursor = token.end()
            line = clean
        fence_line = re.sub(r'^ {0,3}(?:[-+*]|[0-9]+[.)]) +', '', line)
        fence_line = re.sub(r'^ {0,3}> ?', '', fence_line)
        match = re.match(r'^ {0,3}(`{3,}|~{3,})(.*)$', fence_line)
        if match and match[1][0] == '`' and '`' in match[2]:
            match = None  # Backticks cannot occur in a backtick fence's info string.
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= fence[1] and not match[2].strip():
                fence = None
            result.append('')
        elif match:
            fence = (match[1][0], len(match[1]))
            result.append('')
        else:
            result.append(line)
    return result


def mask_inline_code(text):
    return re.sub(r'(`+)(?!`)(.*?)(?<!`)\1(?!`)', lambda m: ' ' * len(m[0]), text, flags=re.S)


def label_key(label):
    return ' '.join(label.split()).casefold()


def unescape(text):
    return html.unescape(re.sub(r'\\([!"#$%&\'()*+,\-./:;<=>?@\[\]\\^_`{|}~])', r'\1', text))


def destination(text):
    """One-line destination with angle brackets or balanced parentheses and optional title."""
    text = text.strip()
    if text.startswith('<'):
        end = text.find('>')
        require(end != -1, 'unclosed angle-bracket link destination')
        target, rest = text[1:end], text[end + 1:].strip()
    else:
        depth, end = 0, len(text)
        escaped = False
        for i, char in enumerate(text):
            if escaped:
                escaped = False
                continue
            if char == '\\':
                escaped = True
            elif char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            elif char.isspace() and depth == 0:
                end = i
                break
        target, rest = text[:end], text[end:].strip()
        require(depth == 0, 'unbalanced link destination')
    require(not rest or ((rest[0], rest[-1]) in (('"', '"'), ("'", "'"), ('(', ')')) and len(rest) >= 2),
            'unsupported/malformed link title: ' + text)
    return unescape(target)


def markdown_info(text):
    lines = prose_lines(text)
    anchors, used = set(), set()
    for index, line in enumerate(lines):
        heading = re.match(r'^ {0,3}#{1,6}\s+(.+?)\s*#*\s*$', line)
        title = heading[1] if heading else None
        if not title and index + 1 < len(lines) and re.fullmatch(r' {0,3}(?:=+|-+)\s*', lines[index + 1]) and line.strip():
            title = line.strip()
        if title is not None:
            # Protect code-span text from emphasis/HTML cleanup (e.g. `_name_`).
            code = []
            def protect(match):
                code.append(match[2])
                return '\x00' + str(len(code) - 1) + '\x00'
            title = re.sub(r'(`+)(?!`)(.*?)(?<!`)\1(?!`)', protect, title)
            title = re.sub(r'!?\[([^\]]+)\]\([^)]*\)', r'\1', title)
            title = re.sub(r'!?\[([^\]]+)\](?:\[[^\]]*\])?', r'\1', title)
            title = re.sub(r'(?<!\w)(_{1,2})(?=\S)(.+?)(?<=\S)\1(?!\w)', r'\2', title)
            title = re.sub(r'<[^>]*>', '', title)
            title = unescape(title).replace('*', '')
            for index, span in enumerate(code):
                title = title.replace('\x00' + str(index) + '\x00', span)
            slug = ''.join(c for c in title.lower() if c in ' _-' or unicodedata.category(c)[0] in 'LNM')
            slug = slug.replace(' ', '-')
            base, suffix = slug, 0
            while slug in used:
                suffix += 1
                slug = f'{base}-{suffix}'
            used.add(slug)
            anchors.add(slug)
    body = '\n'.join(lines)
    definitions = {}
    definition = re.compile(r'^ {0,3}\[([^\]\n]+)\]:[ \t]*(.*)$', re.M)
    for match in definition.finditer(mask_inline_code(body)):
        key = label_key(unescape(match[1]))
        # CommonMark uses the first definition of a label.
        definitions.setdefault(key, destination(match[2]))
    body = definition.sub('', body)
    body = mask_inline_code(body)
    targets = []
    pattern = re.compile(r'(?<!\\)!?\[([^\]\n]*)\]')
    pos = 0
    while True:
        match = pattern.search(body, pos)
        if not match:
            break
        end = match.end()
        label = unescape(match[1])
        if body[end:end + 1] == '(':
            start, depth, cursor, quoted, angle = end + 1, 1, end + 1, None, False
            while cursor < len(body) and depth:
                char = body[cursor]
                if char == '\\':
                    cursor += 2
                    continue
                if quoted:
                    if char == quoted:
                        quoted = None
                elif angle:
                    if char == '>':
                        angle = False
                elif char == '<':
                    angle = True
                elif char in ('"', "'") and cursor > start and body[cursor - 1].isspace():
                    quoted = char
                elif char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                cursor += 1
            require(depth == 0, 'unclosed inline link after [' + label + ']')
            targets.append(destination(body[start:cursor - 1]))
            pos = cursor
        elif body[end:end + 1] == '[':
            close = body.find(']', end + 1)
            require(close != -1, 'unclosed reference link after [' + label + ']')
            key = label_key(unescape(body[end + 1:close]) or label)
            require(key in definitions, 'undefined reference link: ' + key)
            targets.append(definitions[key])
            pos = close + 1
        else:
            key = label_key(label)
            if key in definitions:
                targets.append(definitions[key])
            pos = end
    return anchors, targets


def validate_markdown(root):
    documents = {}
    for path in sorted(root.rglob('*.md')):
        if any(part.startswith('.') for part in path.relative_to(root).parts):
            continue
        relative = path.relative_to(root).as_posix()
        dest = contained_file(root, root, relative)
        try:
            documents[dest] = markdown_info(path.read_text(encoding='utf-8'))
        except ValidationError as exc:
            raise ValidationError(relative + ': ' + str(exc)) from exc
    count = 0
    for path, (_, targets) in documents.items():
        for target in targets:
            try:
                parsed = urlsplit(target)
                if parsed.scheme in ('https', 'http', 'mailto') or parsed.netloc:
                    continue
                require(not parsed.scheme, 'unsupported local link scheme: ' + target)
                dest = contained_file(root, path.parent, unquote(parsed.path)) if parsed.path else path
                if parsed.fragment:
                    require(dest in documents, 'anchors supported only in Markdown files: ' + target)
                    require(unquote(parsed.fragment) in documents[dest][0], 'missing heading anchor: ' + target)
                count += 1
            except (ValidationError, ValueError) as exc:
                raise ValidationError(path.relative_to(root).as_posix() + ': ' + str(exc)) from exc
    return count


def main(root=ROOT):
    try:
        root = Path(root).resolve()
        projects, sources, urls = validate_data(root)
        links = validate_markdown(root)
    except (ValidationError, OSError, UnicodeError, ValueError, csv.Error, RuntimeError) as exc:
        print('FAIL: ' + str(exc), file=sys.stderr)
        return 1
    print(f'PASS: {projects} unique projects; JSON/CSV consistent; {sources} indexed source URLs; {links} internal links')
    print(f'PASS: {urls} catalog URLs are syntactically valid (no HTTP checks performed)')
    print('LIMIT: no model execution, music quality, external reachability, or license compliance test')
    return 0


if __name__ == '__main__':
    sys.exit(main())
