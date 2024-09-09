# Kiwix Hotspot Demo


This repo allows setting up online replicas of Kiwix Hotspot Web Access from Hotspot-image (imager-service built).
Those replicas (called *demos* or *deployments*) are configured in the `demos.yaml` file at the root of this repo.

The tool automatically monitors this file and adjusts on changes.

Kiwix Hotspot Demo adheres to openZIM's [Contribution Guidelines](https://github.com/openzim/overview/wiki/Contributing).

Kiwix Hotspot Demo has implemented openZIM's [Python bootstrap, conventions and policies](https://github.com/openzim/_python-bootstrap/docs/Policy.md) **v1.0.0**.

## Pre-requisites

Installing this demo requires:

- a Linux machine (or VM)
- with Docker (compose is required as well but it is now parted of docker)
- with Python 3.11, preferably in a venv
- root access
- `loop` must be enabled in kernel or module loaded

If you start from a bare machine, you can:

- install Docker by following instructions at https://docs.docker.com/engine/install/debian/
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

## How it works

- always-running caddy web server named `multi-proxy` that responds to the FQDN and links to individual demos
- one script runs *always* (restarted every 15mn) running two scripts one after the other
  - config-watcher that checks [`demos.yaml`](https://github.com/kiwix/operations/blob/main/demos/demo.offspot.yaml) file in kiwix/operations repo and updates `/etc/demo/environment` accordingly
  - update-watcher removes deployments (not in config anymore), deploys new or updated ones (images are updated periodically so it checks online if a new version is available)
- deploy script (ran for an indiv demo) downloads the image file then:
  - turn that demo off (switch to maintenance mode)
  - undeploys (unmount, release loop, removes stuff)
  - gets a loop device, mounts third partition of file
  - runs prepare script: fixes in-images variables for use with that demo's FQDN, writes fixed compose file, informs multi-proxy of new domain(s)
  - switch from maintenance mode to image mode (launch the new compose file.

Check the source code starting from the `config_watcher` and `update-watcher` to discover the various steps.

## Kiwix instance

Kiwix is running a demo instance at https://demo.hotspot.kiwix.org

### Domain names

- `demo.hotspot.kiwix.org A 62.210.206.65`
- `*.demo.hotspot.kiwix.org CNAME demo.hotspot.kiwix.org`

### Machine

- Scaleway Start-1-L-SATA (dedibox) with 16GB RAM and 2TB disk for €20/m
- Debian
- node-like setup with bastion
- docker install (comes with compose)
- python install (3.12) + venv (in `install.sh`)
- `mount`, `coreutils` and `aria2` (in `install.sh`)
- this project installed in `/root/demo/env`
  - `pip install git+https://github.com/offspot/demo@main`
- configuration at `/etc/demo/environment`. Files in `/data/demo`

## Next

- *Protect* the service via a password (provided in-login page? as we want to prevent bots mostly)
- Use LXC containers to isolate from host and allow restoring snapshots frequently to prevent any attack from persisting
- Use Apache Guacamole to isolate the hotpost HTTP service(s) as users would access a VNC-like rendering of it
- Add an FAQ/doc for end-users (in GH for now)
- Do not retry to deploy the same failing image over-and-over every "watcher interval" (15 minutes)
- Implement a healthcheck endpoint (offspot services + demo watcher/deploy, with details like in imager-service https://imager.kiwix.org/health-check)
- Use a private auto-image so users cant download this special image
