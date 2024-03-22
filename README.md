# Kiwix Hotspot Demo

Kiwix Hotspot Demo adheres to openZIM's [Contribution Guidelines](https://github.com/openzim/overview/wiki/Contributing).

Kiwix Hotspot Demo has implemented openZIM's [Python bootstrap, conventions and policies](https://github.com/openzim/_python-bootstrap/docs/Policy.md) **v1.0.0**.

http://demo.hotspot.kiwix.org

- Arrive on home page
- Can access Captive portal (just for UI)? Via :2080 and :2443?
- Can browse content

## Domain names

- `demo.hotspot.kiwix.org A 51.159.6.102`
- `*.demo.hotspot.kiwix.org CNAME demo.hotspot.kiwix.org`

## Machine

- Scaleway Start-2-M-SATA (dedibox) with 16GB RAM and 1TB disk for €17/m
- Debian
- node-like setup with bastion
- docker install (comes with compose)
- python install (3.12) + venv
- this project installed somewhere
  - pip install git+https://github.com/offspot/demo@main

## setup script

- install symlink on `/etc/docker/compose.yaml` to `<src_path>/maint-compose/docker-compose.yaml`
  - simple caddy default server with minimal HTML UI saying "we are in maintenance" (with HTTPS auto certificates)
- install a systemd unit to manage the `/etc/docker/compose.yaml` docker-compose (start / stop)
  - source file in `src/offspot_demo/systemd-unit`
- start and enable this systemd unit

## watcher script

- runs forever
- checks the special image endpoint on imager service (https://api.imager.kiwix.org/auto-images/demo/json)
- check if target URL has changed
- call `deploy-script` if it did, otherwise sleeps

## toggle script

```sh
toggle-compose [image|maint]
```

- check symlink for active one (and docker ps?)
- down docker-compose
- change symlink
- up docker-compose

## deploy script

```sh
deploy-demo-for http://xxxxx/xyz.img
```

- check URL
- `toggle-compose maint`
- unmount old image `/data`
- release loop-device
- remove old image file `/demo/image.img`
- purge docker images and containers for image
- download new image `/demo/image.img`
- prepare-image `/demo/image.img`
- `toggle-compose image`


## prepare script

```sh
prepare-image /demo/image.img
```

- setup loop-device
- mount part3 onto `/data` (allows reusing all fs paths directly)
- check if already prepared via `/data/demo_prepared`
- read and parse `/data/contents/dashboard.yaml`
  - read `fqdn` as `orig_fqdn`
  - rewrite metadata for `fqdn=demo.hotspot.kiwix.org`
  - rewrite all `url` and `download.url` for `packages` to replace `orig_fqdn` with `fqdn`
  - rewrite urls in `readers` and `links` as well
- read and parse /image/image.yaml
  - pull all OCI images from `oci_images`
  - read timezome from `offspot.timezone`
  - set timezone on host????
  - convert `offspot.containers` and write to `/data/compose.yaml`
    - for all volumes:
      - ensure all `source` is relative to `/data`.
      - Otherwise remove bind
      - Unless it's `/var/log` and image is `ghcr.io/offspot/reverse-proxy:` (for metrics)
    - for all services:
      - remove `cap_add` (will break captive portal but not an issue)
      - if image doesnot start with `ghcr.io/offspot/reverse-proxy:`, remove `ports` else, limit to `80:80` and `443:443`
      - if image starts with `ghcr.io/offspot/captive-portal:` add ports `2080:2080` `2443:2443`
      - remove `privileged`
    - for all environment in all services (exclude `PROTECTED_SERVICES`?:
      - replace `old_fqdn` with `fqdn`
    - remove any secu-related option that we don't set?
- touch `/data/demo_prepared`

## Next

- _Protect_ the service via a password (provided in-login page? as we want to prevent bots mostly)
- Use LXC containers to isolate from host and allow restoring snapshots frequently to prevent any attack from persisting
- Use Apache Guacamole to isolate the hotpost HTTP service(s) as users would access a VNC-like rendering of it
- Add an FAQ/doc for end-users (in GH for now)
