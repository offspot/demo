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
- root access
- `loop` must be enabled in kernel or module loaded

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

This repository contains various modules and scripts useful to setup / update the demo. Beside the single-use `setup` script, only running `watcher` periodically should be necessary in production. Developers can use individual scripts for each step to inspect output.

### setup script

- install symlink on `/etc/docker/compose.yaml` to `<src_path>/maint-compose/docker-compose.yaml`
  - simple caddy default server with minimal HTML UI saying "we are in maintenance" (with HTTPS auto certificates)
- install a systemd unit to manage the `/etc/docker/compose.yaml` docker-compose (start / stop)
  - source file in `src/offspot_demo/systemd-unit`
- start and enable this systemd unit

### watcher script

- runs once, launched periodically
- checks the special image endpoint on imager service (https://api.imager.kiwix.org/auto-images/offspot-demo/json)
- check if target URL has changed
- call `deploy` module if it did

### toggle module/script

```sh
demo-toggle [image|maint]
```

- stop docker-compose
- change symlink
- start docker-compose

### deploy module/script

```sh
demo-deploy http://xxxxx/xyz.img
```

- check URL
- `offspot-toggle maint`
- unmount old image `/data`
- release loop-device
- remove old image file `/demo/image.img`
- purge docker images and containers
- download new image into `/demo/image.img` and check integrity
- attach image to loop-device
- mount 3rd partition to `/data`
- `offspot-prepare /data`
- attach image
- `offspot-togglw image`


### prepare module/script

```sh
demo-prepare /data
```

- check if already prepared via `/data/prepared.ok`
- read and parse `/data/contents/dashboard.yaml`
  - read `fqdn` as `orig_fqdn`
  - rewrite metadata for `fqdn=demo.hotspot.kiwix.org`
  - rewrite all `url` and `download.url` for `packages` to replace `orig_fqdn` with `fqdn`
  - rewrite urls in `readers` and `links` as well
- read and parse /image/image.yaml
  - convert `offspot.containers` and write to `/data/compose.yaml`
    - for all volumes:
      - ensure all `source` is relative to `/data`.
      - Otherwise remove bind
      - Unless it's `/var/log` and image is `ghcr.io/offspot/reverse-proxy:` (for metrics)
    - for all services:
      - remove `cap_add` (will break captive portal but not an issue)
      - if image does not start with `ghcr.io/offspot/reverse-proxy:`, remove `ports` else, limit to `80:80` and `443:443`
      - if image starts with `ghcr.io/offspot/captive-portal:` add ports `2080:2080` `2443:2443`
      - remove `privileged`
    - for all environment in all services (exclude `PROTECTED_SERVICES`?:
      - replace `old_fqdn` with `fqdn`
  - pull all OCI images from `oci_images`
- touch `/data/prepared.ok`

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
- python install (3.12) + venv (in `install.sh`)
- `mount`, `coreutils` and `aria2` (in `install.sh`)
- this project installed somewhere
  - `pip install git+https://github.com/offspot/demo@main`

## Next

- Enhance/Remove dirty Python 3.12 installation
- Rework the dirty systemd manipulations (mainly/only in setup.py)
- Can access Captive portal (just for UI)? Via :2080 and :2443?
- *Protect* the service via a password (provided in-login page? as we want to prevent bots mostly)
- Use LXC containers to isolate from host and allow restoring snapshots frequently to prevent any attack from persisting
- Use Apache Guacamole to isolate the hotpost HTTP service(s) as users would access a VNC-like rendering of it
- Add an FAQ/doc for end-users (in GH for now)
- Do not retry to deploy the same failing image over-and-over every "watcher interval" (15 minutes)
- Implement a healthcheck endpoint (offspot services + demo watcher/deploy, with details like in imager-service https://imager.kiwix.org/health-check)
