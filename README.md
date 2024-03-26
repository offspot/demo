# Kiwix Hotspot Demo

This Hostpot Demo allows to run a demo hotspot on a regular machine / VM. This demo contains all the required tooling to transform a Hotspot image and a bare machine into a working Hotspot Demo.

Functionalities:
- Arrive on home page
- Browse hostpot content

Kiwix Hotspot Demo adheres to openZIM's [Contribution Guidelines](https://github.com/openzim/overview/wiki/Contributing).

Kiwix Hotspot Demo has implemented openZIM's [Python bootstrap, conventions and policies](https://github.com/openzim/_python-bootstrap/docs/Policy.md) **v1.0.0**.

## Pre-requisites

Installing this demo requires:
- a Linux machine (or VM)
- with Docker (compose is required as well but it is now parted of docker)
- with Python 3.12 and preferably a venv

If you start from a bare machine, you can:
- install Docker by following instructions at https://docs.docker.com/engine/install/debian/
- compile Python from sources by executing the install.sh script
  - tested on Debian Buster 10
  - prefer a package install if Python 3.12 is available on your distro
- create the venv and automatize its activation for your user:
  - `python -m venv env`
  - automatize the venv activation: `echo "source ~/env/bin/activate" | tee /etc/profile.d/python-venv.sh`

## Installation

To install the demo, you have to:
- install the demo Python tooling: run `pip install git+https://github.com/offspot/demo@main`
- customize the environment:
  - copy the `contrib/environment` file to `/etc/demo/environment`
    - could be any other appropriate location, but then you have to modify `<src_path>/systemd-unit/demo-offspot.service`
  - customize this file as needed
  - automatically load the environment data in your user session: `echo "export \$(grep -v '^#' /etc/demo/environment | xargs) && env | grep OFFSPOT_DEMO" | tee /etc/profile.d/demo-env.sh`
- setup the demo: run `demo-setup`

## Tooling

This repository contains various scripts useful to setup / update the demo

### setup script

- install symlink on `/etc/docker/compose.yaml` to `<src_path>/maint-compose/docker-compose.yaml`
  - simple caddy default server with minimal HTML UI saying "we are in maintenance" (with HTTPS auto certificates)
- install a systemd unit to manage the `/etc/docker/compose.yaml` docker-compose (start / stop)
  - source file in `src/offspot_demo/systemd-unit`
- start and enable this systemd unit

### watcher script

- runs forever
- checks the special image endpoint on imager service (https://api.imager.kiwix.org/auto-images/demo/json)
- check if target URL has changed
- call `deploy-script` if it did, otherwise sleeps

### toggle script

```sh
toggle-compose [image|maint]
```

- check symlink for active one (and docker ps?)
- down docker-compose
- change symlink
- up docker-compose

### deploy script

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


### prepare script

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

## Kiwix instance

Kiwix is running a demo instance at http://demo.hotspot.kiwix.org

### Domain names

- `demo.hotspot.kiwix.org A 51.159.6.102`
- `*.demo.hotspot.kiwix.org CNAME demo.hotspot.kiwix.org`

### Machine

- Scaleway Start-2-M-SATA (dedibox) with 16GB RAM and 1TB disk for €17/m
- Debian
- node-like setup with bastion
- docker install (comes with compose)
- python install (3.12) + venv
- few apt packages: mount coreutils aria2
  - `apt install -y mount coreutils aria2`
- this project installed somewhere
  - `pip install git+https://github.com/offspot/demo@main`

## Next

- Enhance/Remove dirty Python 3.12 installation
- Rework the dirty systemd manipulations (mainly/only in setup.py)
- Can access Captive portal (just for UI)? Via :2080 and :2443?
- _Protect_ the service via a password (provided in-login page? as we want to prevent bots mostly)
- Use LXC containers to isolate from host and allow restoring snapshots frequently to prevent any attack from persisting
- Use Apache Guacamole to isolate the hotpost HTTP service(s) as users would access a VNC-like rendering of it
- Add an FAQ/doc for end-users (in GH for now)
- Do not retry to deploy the same failing image over-and-over every "watcher interval" (15 minutes)
- Implement a healthcheck endpoint (offspot services + demo watcher/deploy, with details like in imager-service https://imager.kiwix.org/health-check)
