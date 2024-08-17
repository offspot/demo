#!/usr/bin/env python3

""" Generates multi-proxy configuration fron SERVICES environ.
    Generates static homepage

    Dependencies:
    - Jinja2
"""
import argparse
import dataclasses
import os
import sys
import traceback
from pathlib import Path

from jinja2 import Template

debug: bool = bool(os.getenv("DEBUG", ""))
caddyfile_fpath = Path("/etc/caddy/Caddyfile")
homepage_fpath = Path("/var/www/index.html")
FQDN = os.getenv("FQDN", "") or "notset"


def port_from(ident: str) -> int:
    return 1024 + sum([ord(char) for char in ident.strip().lower()])


def captive_port_from(ident: str) -> int:
    return 10000 + port_from(ident)


@dataclasses.dataclass
class Demo:
    ident: str
    dns_alias: str
    name: str
    port: int
    captive_port: int
    subdomains: list[str]

    @classmethod
    def from_line(cls, text: str):
        """Demo from ident:[alias]:subdomains format"""
        ident, dns_alias, name, subdomains = text.strip().split(":", 3)
        if not dns_alias:
            dns_alias = ident

        return cls(
            ident=ident,
            dns_alias=dns_alias,
            name=name.strip(),
            port=port_from(ident),
            captive_port=captive_port_from(ident),
            subdomains=[sd for sd in subdomains.strip().split("|") if sd],
        )


caddy_template: Template = Template(
    """
{
    admin :2020
    {% if debug %}debug{% endif %}
    auto_https disable_redirects

    http_port 80
    https_port 443
}

# home page on domain, with prefix redirects
http://{$FQDN}, https://{$FQDN} {
    tls {$TLS_EMAIL}
    log

    root * /var/www
    file_server


    handle_errors {
        respond "multi-proxy HTTP {http.error.status_code} Error ({http.error.message})"
    }
}

{% for demo in demos.values() %}
http://{{demo.dns_alias}}.{$FQDN}, https://{{demo.dns_alias}}.{$FQDN}, http://*.{{demo.dns_alias}}.{$FQDN}, https://*.{{demo.dns_alias}}.{$FQDN}{% if demo.subdomains %}{% for subdomain in demo.subdomains %}, http://{{ subdomain }}.{{demo.dns_alias}}.{$FQDN}, https://{{ subdomain }}.{{demo.dns_alias}}.{$FQDN}{% endfor %}{% endif %} {
    tls {$TLS_EMAIL}
    log

    reverse_proxy http://{$HOST_IP}:{{demo.port}}

    handle_errors 502 {
        respond "The “{{demo.ident}}” demo is not available or ready. \
Please retry later.\n\n\
HTTP {http.error.status_code}: {http.error.message}" 502
    }

    handle_errors {
        respond "HTTP {http.error.status_code} for ”{{ident}}”: {http.error.message}" {http.error.status_code}
    }
}

http://_captive.{{demo.dns_alias}}.{$FQDN}, https://_captive.{{demo.dns_alias}}.{$FQDN} {
    tls {$TLS_EMAIL}
    redir http://{{demo.dns_alias}}.{$FQDN}:{{demo.captive_port}}
}
{% endfor %}

http://*.{$FQDN}, https://*.{$FQDN} {
    tls {$TLS_EMAIL}
    log
    respond "Not found! This address is not for a configured demo" 404
}

"""
)

home_template: Template = Template(
    """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Kiwix Hotspot Demo</title>
<link rel="icon" type="image/svg+xml" href="https://raw.githubusercontent.com/offspot/offspot-config/main/src/offspot_config/branding/square-logo.svg">
<meta http-equiv="X-UA-Compatible" content="IE=edge">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="canonical" href="https://{{FQDN}}/">
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet" integrity="sha384-QWTKZyjpPEjISv5WaRU9OFeRpok6YctnYmDr5pNlyT2bRjXh0JMhjY6hW+ALEwIH" crossorigin="anonymous">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Roboto:wght@400;500&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
<style>
*, html, body {
  font-family: "Roboto", sans-serif;
   font-style: normal;
}
header {
    margin-top: 1rem;
}
.icon {
    height: 100%;
    max-height: 3em;
}
a {
    color: inherit;
    text-decoration: none;
}
a:hover {
    text-decoration: underline;
}
.col {
    font-size: 2em;
}
.row {
    margin-bottom: 2em;
    position: relative;
}
</style>
</head>
<body>
  <div class="container">
    <header><img src="https://raw.githubusercontent.com/offspot/offspot-config/main/src/offspot_config/branding/horizontal-logo-light.png" style="width: 22rem; height: 4rem" /></header>
    <hr />
    <section>
        <p>The following links replicates what Hotspot users would be faced with once they've connected to a running <strong><a href="https://kiwix.org/en/wifi-hotspot/">Kiwix Hotspot</a></strong> network running the macthing pre-packaged image.</p>
    {% if demos %}
    {% for demo in demos.values() %}
    <div class="row">
            <div class="col-2 col-md-1"><a href="//{{demo.dns_alias}}.{{FQDN}}"><img class="icon" onerror="this.style.display='none'" src="assets/{{demo.ident}}.png" /></a></div>
            <div class="col"><a href="//{{demo.dns_alias}}.{{FQDN}}">{{demo.name}}</a></div>
        </div>
    {% endfor %}
    {% else %}
    <p>There's no demo configured at the moment 🤷‍♂️</p>
    {% endif %}
    <p>The Imager-service (“<em>Build your own</em>” option) allows you to create one such Hotspot with your own set of contents.</p>
        <p><a href="https://kiwix.org/en/wifi-hotspot/" class="btn btn-primary">Kiwix Hotspot Shop <i class="bi bi-bag"></i></a></p>
    </section>
  </div>
</body>
</html>

    """
)


def gen_caddyfile(demos: dict[str, Demo]) -> int:
    try:
        caddyfile_fpath.parent.mkdir(parents=True, exist_ok=True)
        caddyfile_fpath.write_text(
            caddy_template.render(
                debug=debug,
                demos=demos,
                nb_demos=len(demos),
            )
        )
    except Exception as exc:
        print("[ERROR] unable to gen Caddyfile", flush=True)
        traceback.print_exception(exc)
        return 1

    print(f"Generated Caddyfile for: {demos=}", flush=True)
    return 0


def gen_homepage(demos: dict[str, Demo]) -> int:
    try:
        homepage_fpath.parent.mkdir(parents=True, exist_ok=True)
        homepage_fpath.write_text(
            home_template.render(
                debug=debug,
                FQDN=FQDN,
                demos=demos,
                nb_demos=len(demos),
            )
        )
    except Exception as exc:
        print("[ERROR] unable to gen homepage", flush=True)
        traceback.print_exception(exc)
        return 1

    print(f"Generated Homepage for: {demos.keys()}", flush=True)
    return 0


def entrypoint():
    parser = argparse.ArgumentParser(
        prog="gen-server", description="Generate Caddyfile and homepage"
    )

    parser.add_argument(
        "--demos",
        dest="demos_string",
        default=os.getenv("DEMOS") or "",
        help="Specify custom demos string (use DEMOS environ otherwise)",
    )

    args = parser.parse_args()

    demos: dict[str, Demo] = (
        {
            Demo.from_line(demo).ident: Demo.from_line(demo)
            for demo in args.demos_string.split(",")
        }
        if args.demos_string
        else {}
    )

    if rc := gen_caddyfile(demos=demos):
        sys.exit(rc)

    if debug:
        print(caddyfile_fpath.read_text(), flush=True)

    if rc := gen_homepage(demos=demos):
        sys.exit(rc)

    if debug:
        print(Path(homepage_fpath).read_text(), flush=True)


if __name__ == "__main__":
    sys.exit(entrypoint())
