#!/usr/bin/env python3
"""Generate a privacy-preserving star-history SVG from GitHub GraphQL data.

Only each current stargazer's ``starredAt`` timestamp is requested. Usernames,
profile URLs, and other account data are neither requested nor written.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from html import escape
import json
import math
import os
from pathlib import Path
import re
import urllib.request


GRAPHQL_URL = 'https://api.github.com/graphql'
OUTPUT_PATH = (
    Path(__file__).resolve().parents[1] / 'docs' / 'assets' /
    'star-history.svg'
)
RENDER_VERSION = '2'

QUERY = '''
query StarHistory($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    stargazerCount
    stargazers(
      first: 100
      after: $cursor
      orderBy: {field: STARRED_AT, direction: ASC}
    ) {
      edges { starredAt }
      pageInfo { hasNextPage endCursor }
    }
  }
}
'''


def graphql(token: str, variables: dict) -> dict:
    payload = json.dumps({'query': QUERY, 'variables': variables}).encode()
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=payload,
        headers={
            'Accept': 'application/vnd.github+json',
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'User-Agent': 'ALOS-Unified-AV-Downloader-star-history',
        },
        method='POST',
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.load(response)
    if result.get('errors'):
        messages = '; '.join(
            str(item.get('message', 'GraphQL error'))
            for item in result['errors'])
        raise RuntimeError(messages)
    return result['data']['repository']


def fetch_star_times(token: str, repository: str) -> tuple[int, list[str]]:
    try:
        owner, name = repository.split('/', 1)
    except ValueError as exc:
        raise ValueError('GITHUB_REPOSITORY must be owner/name') from exc

    cursor = None
    timestamps = []
    total = None
    while True:
        data = graphql(token, {'owner': owner, 'name': name, 'cursor': cursor})
        total = int(data['stargazerCount'])
        connection = data['stargazers']
        timestamps.extend(
            edge['starredAt'] for edge in connection['edges']
            if edge.get('starredAt'))
        page_info = connection['pageInfo']
        if not page_info['hasNextPage']:
            break
        cursor = page_info['endCursor']

    if total != len(timestamps):
        raise RuntimeError(
            f'Incomplete star data: expected {total}, received {len(timestamps)}')
    return total, timestamps


def daily_series(timestamps: list[str], today: date | None = None):
    today = today or datetime.now(timezone.utc).date()
    days = [datetime.fromisoformat(value.replace('Z', '+00:00')).date()
            for value in timestamps]
    if not days:
        return [(today, 0)]

    counts = Counter(days)
    current = min(days)
    end = max(today, max(days))
    cumulative = 0
    series = []
    while current <= end:
        cumulative += counts[current]
        series.append((current, cumulative))
        current += timedelta(days=1)
    return series


def nice_upper(value: int) -> int:
    if value <= 4:
        return 4
    magnitude = 10 ** math.floor(math.log10(value))
    normalized = value / magnitude
    if normalized <= 2:
        step = 2
    elif normalized <= 2.5:
        step = 2.5
    elif normalized <= 5:
        step = 5
    else:
        step = 10
    return int(step * magnitude)


def history_hash(timestamps: list[str]) -> str:
    payload = RENDER_VERSION + '\n' + '\n'.join(timestamps)
    return sha256(payload.encode()).hexdigest()[:20]


def render_svg(repository: str, total: int, timestamps: list[str]) -> str:
    width, height = 1200, 480
    left, top, right, bottom = 82, 98, 48, 64
    plot_w = width - left - right
    plot_h = height - top - bottom
    series = daily_series(timestamps)
    y_max = nice_upper(max(total, 1))

    def x_at(index: int) -> float:
        return left if len(series) == 1 else left + plot_w * index / (len(series) - 1)

    def y_at(value: int) -> float:
        return top + plot_h * (1 - value / y_max)

    points = ' '.join(
        f'{x_at(index):.1f},{y_at(value):.1f}'
        for index, (_day, value) in enumerate(series))
    area = (f'M {left},{top + plot_h} L {points.replace(" ", " L ")} '
            f'L {left + plot_w},{top + plot_h} Z')

    y_grid = []
    for tick in range(5):
        value = round(y_max * tick / 4)
        y = y_at(value)
        y_grid.append(
            f'<line class="grid" x1="{left}" y1="{y:.1f}" '
            f'x2="{left + plot_w}" y2="{y:.1f}"/>'
            f'<text class="axis" x="{left - 16}" y="{y + 5:.1f}" '
            f'text-anchor="end">{value}</text>')

    indexes = sorted({
        0,
        (len(series) - 1) // 4,
        (len(series) - 1) // 2,
        3 * (len(series) - 1) // 4,
        len(series) - 1,
    })
    x_labels = ''.join(
        f'<text class="axis" x="{x_at(index):.1f}" y="{height - 28}" '
        f'text-anchor="middle">{series[index][0].isoformat()}</text>'
        for index in indexes)

    updated = datetime.now(timezone.utc).date().isoformat()
    repo_label = escape(repository)
    digest = history_hash(timestamps)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}"
  viewBox="0 0 {width} {height}" role="img"
  aria-labelledby="title description" data-history-hash="{digest}">
  <title id="title">GitHub star history for {repo_label}</title>
  <desc id="description">{total} current stargazers grouped by the date each star was added. Updated {updated}.</desc>
  <defs>
    <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="#ff5263" stop-opacity="0.34"/>
      <stop offset="1" stop-color="#ff5263" stop-opacity="0.02"/>
    </linearGradient>
  </defs>
  <rect x="1" y="1" width="1198" height="478" rx="18" fill="#0d1117" stroke="#30363d"/>
  <text x="42" y="48" fill="#f0f6fc" font-family="Segoe UI, sans-serif" font-size="24" font-weight="700">Star history</text>
  <text x="42" y="75" fill="#8b949e" font-family="Segoe UI, sans-serif" font-size="14">Current stargazers grouped by starredAt · updated {updated}</text>
  <text x="1158" y="52" fill="#ff6374" font-family="Segoe UI, sans-serif" font-size="30" font-weight="700" text-anchor="end">{total} stars</text>
  <g font-family="Segoe UI, sans-serif" font-size="13">
    {''.join(y_grid)}
    {x_labels}
  </g>
  <path d="{area}" fill="url(#area)"/>
  <polyline points="{points}" fill="none" stroke="#ff5263" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="{x_at(len(series) - 1):.1f}" cy="{y_at(series[-1][1]):.1f}" r="6" fill="#ff5263" stroke="#0d1117" stroke-width="3"/>
  <style>.grid{{stroke:#21262d;stroke-width:1}}.axis{{fill:#8b949e}}</style>
</svg>
'''


def main() -> None:
    token = os.environ.get('GITHUB_TOKEN', '').strip()
    repository = os.environ.get('GITHUB_REPOSITORY', '').strip()
    if not token or not repository:
        raise SystemExit('GITHUB_TOKEN and GITHUB_REPOSITORY are required')

    total, timestamps = fetch_star_times(token, repository)
    digest = history_hash(timestamps)
    if OUTPUT_PATH.exists():
        current = OUTPUT_PATH.read_text(encoding='utf-8')
        match = re.search(r'data-history-hash="([0-9a-f]+)"', current)
        if match and match.group(1) == digest:
            print(f'Star history unchanged ({total} stars).')
            return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        render_svg(repository, total, timestamps), encoding='utf-8')
    print(f'Updated {OUTPUT_PATH.name} ({total} stars).')


if __name__ == '__main__':
    main()
