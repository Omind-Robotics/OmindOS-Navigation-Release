"""Add a migration notice to known releases while retaining all original content."""
import json
import os
from pathlib import Path
import urllib.request

def api(repo, suffix, payload=None):
    req = urllib.request.Request(
        'https://api.github.com/repos/' + repo + '/' + suffix,
        data=None if payload is None else json.dumps(payload).encode(),
        headers={'Authorization': 'Bearer ' + os.environ['GH_TOKEN'],
                 'Accept': 'application/vnd.github+json',
                 'X-GitHub-Api-Version': '2022-11-28',
                 'Content-Type': 'application/json'},
        method='GET' if payload is None else 'PATCH')
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)

def asset_records(release, include_ids=False):
    keys = ['name', 'size', 'digest']
    if include_ids:
        keys.append('id')
    return sorted([tuple(asset.get(k) for k in keys) for asset in release['assets']])

def main():
    plan = json.loads(Path('migration-notice/releases.json').read_text())
    repo = os.environ['GITHUB_REPOSITORY']
    assert repo == plan['source']
    checked = []
    for item in plan['releases']:
        before = api(repo, 'releases/' + str(item['id']))
        target = api(plan['destination'], 'releases/tags/' + item['tag'])
        assert before['tag_name'] == target['tag_name'] == item['tag']
        assert not before['draft'] and not target['draft']
        assert asset_records(before) == asset_records(target), 'Mirrored assets differ'
        wanted = item['notice'] + item['original_body']
        assert before['body'] in (item['original_body'], wanted), 'Concurrent note edit; stopped'
        checked.append((item, before, wanted))
    for item, before, wanted in checked:
        endpoint = 'releases/' + str(item['id'])
        fresh = api(repo, endpoint)
        assert fresh['body'] == before['body'] and fresh['updated_at'] == before['updated_at'], 'Concurrent change'
        if fresh['body'] != wanted:
            api(repo, endpoint, {'body': wanted})
        after = api(repo, endpoint)
        assert after['body'] == wanted
        assert asset_records(after, True) == asset_records(before, True)
        for field in ('id', 'tag_name', 'name', 'draft', 'prerelease', 'target_commitish', 'published_at'):
            assert after[field] == before[field], field
        print(json.dumps({'release': after['html_url'], 'notice_added': True,
                          'original_content_preserved': True,
                          'assets_unchanged': len(after['assets'])}, ensure_ascii=False))

if __name__ == '__main__':
    main()
