FROM caddy:2.8.4-alpine
LABEL org.opencontainers.image.source=https://github.com/offspot/container-images

RUN \
    # openssl required to generate cert when CAPTIVE_PORTAL is on
    apk add --no-cache dumb-init python3 \
    && python3 -m venv /usr/local/proxy-env \
    && /usr/local/proxy-env/bin/pip3 install --no-cache-dir -U pip \
    && /usr/local/proxy-env/bin/pip3 install --no-cache-dir Jinja2==3.1.2

COPY Caddyfile /etc/caddy/
COPY gen-server.py /src/
COPY entrypoint.sh /usr/local/bin/entrypoint
COPY assets /var/www/assets

# FQDN to reverse for (main domain)
ENV FQDN "demo.hotspot.kiwix.org"
# email for letsencrypt
ENV TLS_EMAIL "dev@kiwix.org"
# comma-separated idents. here idents can be composed of ident:alias (being the DNS subdomain)
ENV DEMOS ""
# host IP. used as destination for reverse (with port). must be reachable from container
ENV HOST_IP "notset"

# store python bytecode in image
RUN /usr/local/proxy-env/bin/python3 -m compileall /src/gen-server.py \
    && mv /src/__pycache__/*.pyc /usr/local/lib/ \
    && printf '#!/bin/sh\nexec /usr/local/proxy-env/bin/python3 /usr/local/lib/gen-server.cpython-312.pyc "$@"\n' > /usr/local/bin/gen-server \
    && chmod +x /usr/local/bin/gen-server \
    && printf '#!/bin/sh\nexec caddy reload --config /etc/caddy/Caddyfile --adapter caddyfile "$@"\n' > /usr/local/bin/caddy-reload \
    && chmod +x /usr/local/bin/caddy-reload

ENTRYPOINT ["/usr/bin/dumb-init", "--", "entrypoint"]
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile"]
