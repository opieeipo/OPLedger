# HTTPS and reverse proxy

OPLedger serves plain HTTP on port `8080` and makes **no localhost
assumptions** — the frontend talks to the backend over the REST API, so the app
works identically behind a TLS-terminating reverse proxy. For anything beyond
`http://localhost`, put a proxy in front and let it handle HTTPS.

This keeps OPLedger itself simple: it never needs certificates, and you get
automatic renewal, HTTP/2, and security headers from a battle-tested proxy.

> Exposing OPLedger beyond your own machine? Also review
> [Security and encryption](../README.md#security-and-encryption) — in
> particular, tighten `session_timeout` and keep the encryption passphrase off
> disk (don't set `OPLEDGER_PASSPHRASE` on an internet-facing host).

---

## Option A — Caddy (automatic HTTPS)

Caddy obtains and renews Let's Encrypt certificates automatically. Point a DNS
record at your host, then use [`deploy/Caddyfile.example`](../deploy/Caddyfile.example):

```caddyfile
books.example.com {
    reverse_proxy localhost:8080
}
```

Run it:

```bash
caddy run --config deploy/Caddyfile.example
```

That's the whole setup — Caddy provisions the certificate on first request and
renews it indefinitely.

---

## Option B — Nginx + Certbot

Use [`deploy/nginx.conf.example`](../deploy/nginx.conf.example) as a starting
point. Obtain a certificate with Certbot (`certbot --nginx -d books.example.com`),
then Nginx terminates TLS and proxies to OPLedger:

```nginx
server {
    listen 443 ssl;
    server_name books.example.com;

    ssl_certificate     /etc/letsencrypt/live/books.example.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/books.example.com/privkey.pem;

    location / {
        proxy_pass         http://127.0.0.1:8080;
        proxy_set_header   Host              $host;
        proxy_set_header   X-Real-IP         $remote_addr;
        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header   X-Forwarded-Proto $scheme;
    }
}

server {
    listen 80;
    server_name books.example.com;
    return 301 https://$host$request_uri;
}
```

---

## Running the proxy alongside the container

Keep OPLedger bound to localhost and let the proxy be the only public listener.
A minimal Compose overlay:

```yaml
services:
  opledger:
    ports:
      - "127.0.0.1:8080:8080"   # not exposed publicly; proxy reaches it locally

  caddy:
    image: docker.io/library/caddy:2
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./deploy/Caddyfile.example:/etc/caddy/Caddyfile:ro
      - caddy-data:/data
    restart: unless-stopped

volumes:
  caddy-data:
```

---

## Notes

- **Forwarded headers.** OPLedger doesn't build absolute URLs, so it needs no
  special forwarded-header configuration to function. The `X-Forwarded-*`
  headers above are good hygiene for logging and any future awareness of the
  external scheme.
- **WebSockets.** None are used; no upgrade handling required.
- **Large uploads.** QFX files are tiny, but if you proxy other things, note
  Nginx's default `client_max_body_size` (1 MB) is plenty here.
