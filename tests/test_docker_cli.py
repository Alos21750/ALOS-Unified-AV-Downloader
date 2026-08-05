import sys

import docker_cli


def test_docker_worker_limit_is_forwarded_to_each_video(monkeypatch, tmp_path):
    captured = []

    class _FakeSite:
        def is_url_vaildate(self):
            return True

        def start_download(self):
            return True

    def _create(url, dest, max_workers=None):
        captured.append((url, dest, max_workers))
        return _FakeSite()

    monkeypatch.setattr(
        sys, 'argv', ['docker_cli.py', 'https://jable.tv/videos/example/'])
    monkeypatch.setenv('DOWNLOAD_DIR', str(tmp_path))
    monkeypatch.setenv('MAX_WORKERS_PER_VIDEO', '3')
    monkeypatch.delenv('URLS', raising=False)
    monkeypatch.delenv('URL', raising=False)
    monkeypatch.setattr(docker_cli.M3U8Sites, 'CreateSite', _create)

    assert docker_cli.main() == 0
    assert captured == [
        ('https://jable.tv/videos/example/', str(tmp_path), 3),
    ]
