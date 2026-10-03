"""Validate a reviewed edition and publish the latest pointer and archive."""
import datetime as dt
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
REGIONS = {'Americas', 'Europe', 'Middle East and North Africa', 'Sub-Saharan Africa', 'Asia-Pacific'}

def validate(edition):
    for key in ('id', 'published_at', 'information_cutoff', 'title', 'summary', 'disclosure', 'coverage'):
        if not isinstance(edition.get(key), str) or not edition[key].strip():
            raise ValueError(f'Missing {key}')
    if edition.get('status') != 'published':
        raise ValueError('Only reviewed editions marked published may be published')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}', edition['id']):
        raise ValueError('Invalid edition ID')
    if edition['id'] in {'latest', 'index'}:
        raise ValueError('Edition ID is reserved')
    stamp = dt.datetime.fromisoformat(edition['published_at'].replace('Z', '+00:00'))
    if stamp.tzinfo is None or stamp > dt.datetime.now(dt.timezone.utc):
        raise ValueError('Publication time must include timezone and cannot be in the future')
    cutoff = dt.datetime.fromisoformat(edition['information_cutoff'].replace('Z', '+00:00'))
    if cutoff.tzinfo is None or cutoff > stamp:
        raise ValueError('Information cutoff must include timezone and cannot follow publication')
    sources = edition.get('sources')
    if not isinstance(sources, list) or not sources:
        raise ValueError('Sources are required')
    ids = set()
    for source in sources:
        if not all(isinstance(source.get(k), str) and source[k].strip() for k in ('id', 'name', 'url', 'published', 'accessed')):
            raise ValueError('Incomplete source')
        url = urlparse(source['url'])
        if url.scheme != 'https' or not url.hostname or url.hostname == 'example.com':
            raise ValueError('Source must have a real HTTPS URL')
        if source['id'] in ids:
            raise ValueError('Duplicate source ID')
        ids.add(source['id'])
        for key in ('published', 'accessed'):
            date = dt.date.fromisoformat(source[key])
            if date > stamp.date():
                raise ValueError('Source dates cannot follow publication')
        if source['published'] > source['accessed']:
            raise ValueError('Source cannot be accessed before publication')
    entries = edition.get('developments')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Developments are required')
    for entry in entries:
        if entry.get('region') not in REGIONS:
            raise ValueError('Invalid region')
        for key in ('title', 'facts', 'response', 'effects', 'outlook', 'horizon', 'confidence', 'indicators'):
            if not isinstance(entry.get(key), str) or not entry[key].strip():
                raise ValueError(f'Missing development {key}')
        refs = entry.get('source_ids')
        if not isinstance(refs, list) or not refs or any(ref not in ids for ref in refs):
            raise ValueError('Unknown or missing source reference')

def publish(path):
    edition = json.loads(Path(path).read_text(encoding='utf-8'))
    validate(edition)
    folder = ROOT / 'docs/data/outlook'
    folder.mkdir(parents=True, exist_ok=True)
    archive = folder / f"{edition['id']}.json"
    if archive.exists():
        raise ValueError('Edition ID already exists; use a new ID for corrections')
    existing = sorted(folder.glob('*.json'))
    editions = [json.loads(p.read_text(encoding='utf-8')) for p in existing if p.name not in {'latest.json', 'index.json'}]
    editions.append(edition)
    editions.sort(key=lambda e: dt.datetime.fromisoformat(e['published_at'].replace('Z', '+00:00')), reverse=True)
    content = json.dumps(edition, ensure_ascii=False, indent=2) + '\n'
    archive.write_text(content, encoding='utf-8')
    temporary = folder / 'latest.tmp'
    temporary.write_text(json.dumps(editions[0], ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(folder / 'latest.json')
    index = [{'id': e['id'], 'title': e['title'], 'published_at': e['published_at']} for e in editions]
    temporary = folder / 'index.tmp'
    temporary.write_text(json.dumps({'editions': index}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(folder / 'index.json')
    print(f"Published {edition['id']}")

if __name__ == '__main__':
    try:
        publish(sys.argv[1])
    except (ValueError, KeyError, TypeError, IndexError, OSError) as error:
        sys.exit(f'Publication failed: {error}')
