# coding: utf-8
"""One shared ssl.SSLContext for all requests-based HTTP, built once on the main
thread. Constructing SSLContexts concurrently across threads crashes OpenSSL on
some Windows builds (access violation); reusing ONE prebuilt context is safe."""
import ssl
import threading

import requests
from urllib3.poolmanager import PoolManager

_SHARED_SSL_CTX = None
_lock = threading.Lock()


def get_shared_ssl_context():
    global _SHARED_SSL_CTX
    if _SHARED_SSL_CTX is None:
        with _lock:
            if _SHARED_SSL_CTX is None:
                try:
                    import certifi
                    _SHARED_SSL_CTX = ssl.create_default_context(cafile=certifi.where())
                except Exception:
                    _SHARED_SSL_CTX = ssl.create_default_context()
    return _SHARED_SSL_CTX


class SharedSSLAdapter(requests.adapters.HTTPAdapter):
    def init_poolmanager(self, connections, maxsize, block=False, **kw):
        kw['ssl_context'] = get_shared_ssl_context()
        self.poolmanager = PoolManager(num_pools=connections, maxsize=maxsize, block=block, **kw)

    def proxy_manager_for(self, proxy, **kw):
        kw['ssl_context'] = get_shared_ssl_context()
        return super().proxy_manager_for(proxy, **kw)
