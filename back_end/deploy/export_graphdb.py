"""Read-only export of all explicit RDF statements, including named graphs."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import dotenv_values


def main():
    root = Path(__file__).resolve().parents[1]
    values = dotenv_values(root / '.env')
    base = (values.get('GRAPHDB_URL') or 'http://26.118.79.77:7200').rstrip('/')
    repo = values.get('GRAPHDB_REPO') or 'Project'
    output = root / 'backups' / datetime.now(timezone.utc).strftime('graphdb-%Y%m%dT%H%M%S%fZ')
    output.mkdir(parents=True, exist_ok=False)
    partial = output / 'data.trig.partial'
    try:
        version = requests.get(base + '/rest/info/version', timeout=15)
        version.raise_for_status()
        digest = hashlib.sha256()
        size = 0
        with requests.get(
            base + '/repositories/' + quote(repo, safe='') + '/statements',
            params={'infer': 'false'}, headers={'Accept': 'application/x-trig'},
            stream=True, timeout=(15, 120),
        ) as response:
            response.raise_for_status()
            media_type = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
            if media_type not in {'application/trig', 'application/x-trig'}:
                raise ValueError('Unexpected export content type; export not accepted')
            with partial.open('xb') as target:
                for chunk in response.iter_content(1024 * 1024):
                    if chunk:
                        target.write(chunk)
                        digest.update(chunk)
                        size += len(chunk)
        if size == 0:
            raise ValueError('Empty export; check source repository')
        partial.rename(output / 'data.trig')
        (output / 'manifest.json').write_text(json.dumps({
            'repository': repo, 'version': version.json(),
            'exported_at_utc': datetime.now(timezone.utc).isoformat(),
            'bytes': size, 'sha256': digest.hexdigest(),
            'scope': 'All explicit statements and named graphs; inferred statements excluded',
            'remaining': 'Export repository configuration/ruleset and check licence separately',
        }, indent=2), encoding='utf-8')
        print('Export saved:', output.relative_to(root))
        print('Bytes:', size)
        print('Repository configuration and restore verification are still required.')
    except (requests.RequestException, ValueError, OSError) as error:
        print('Export incomplete:', type(error).__name__)
        print('Do not import .partial files. Check connection, permissions and repository.')
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
