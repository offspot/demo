# Kiwix Hotspot Demo


This repo allows setting up online replicas of Kiwix Hotspot Web Access from Hotspot-image (imager-service built).
Those replicas (called *demos* or *deployments*) are configured in the `demos.yaml` file at the root of this repo.

The tool automatically monitors this file and adjusts on changes.

Kiwix Hotspot Demo adheres to openZIM's [Contribution Guidelines](https://github.com/openzim/overview/wiki/Contributing).

Kiwix Hotspot Demo has implemented openZIM's [Python bootstrap, conventions and policies](https://github.com/openzim/_python-bootstrap/docs/Policy.md) **v1.0.0**.

## Managing live demo

Adding, removing or reordering demos is done by editing (via a PR) [`demo.offspot.yaml`](https://github.com/kiwix/operations/blob/main/demos/demo.offspot.yaml) file on [`kiwix/operations`](https://github.com/kiwix/operations) repository.

- The `ident` key must match the imager-service ident of the auto-image.
- The `name` key is an optionnal user-friendly label for the homepage.
- The `alias` key is an optionnal user-friendly replacement of `ident` for the demo's sub-domain (`xxx.demo.hotspot.kiwix.org`)
- The icon can be added/updated via a PR on this repository (files are named after `ident` in `/src/offspot_demo/multi-proxy/assets`)

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
- install the services and required aria2

```sh
# download and install aria2 (used for downloads)
wget -O /tmp/aria2.zip https://github.com/abcfy2/aria2-static-build/releases/download/1.37.0/aria2-x86_64-linux-musl_libressl_static.zip \
	&& unzip -d /tmp /tmp/aria2.zip \
	&& mv /tmp/aria2c /usr/local/bin \
	&& rm /tmp/aria2.zip \
	&& aria2c -v

# this folder must exists
mkdir -p /var/log/demo

# install systend units
cp src/offspot_demo/systemd-unit/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now multi-proxy.service demo-watcher.service demo-watcher.timer
```

## How it works

- always-running caddy web server named `multi-proxy` that responds to the FQDN and links to individual demos
- one script runs *always* (restarted every 15mn) running two scripts one after the other
  - config-watcher that checks [`demo.offspot.yaml`](https://github.com/kiwix/operations/blob/main/demos/demo.offspot.yaml) file in kiwix/operations repo and updates `/etc/demo/environment` accordingly
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

- `demo.hotspot.kiwix.org A 51.158.55.51`
- `*.demo.hotspot.kiwix.org CNAME demo.hotspot.kiwix.org`

### Machine

- Scaleway EM-A116X-SSD (Elastic Metal) with 32GB RAM and 2TB SSD disk for €28/m
- Debian
- node-like setup with bastion
- docker install (comes with compose)
- configuration at `/etc/demo/environment`. Files in `/data/demo`. Virtual devices mounted in `/loop-data`


```sh
apt install python3.13-venv unzip mount coreutils
wget -O /tmp/aria2.zip https://github.com/abcfy2/aria2-static-build/releases/download/1.37.0/aria2-x86_64-linux-musl_static.zip \
  && unzip -d /tmp /tmp/aria2.zip  \
  && mv /tmp/aria2c /usr/local/bin \
  && rm /tmp/aria2.zip \
  && aria2c -v
mkdir -p /var/log/demo
mkdir -p /etc/demo
mkdir -p /loop-data
mkdir -p /data/demo/{data,images,compose}
python3 -m venv /data/demo/env
source /data/demo/env/bin/activate
vim /etc/demo/environment
git clone https://github.com/offspot/demo.git /data/demo/repo
pip install -e /data/demo/repo
vim ~/.bashrc
echo "loop" >> /etc/modules-load.d/modules.conf
modprobe loop
cp /data/demo/repo/src/offspot_demo/systemd-unit/* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now multi-proxy.service demo-watcher.service demo-watcher.timer
```

**`~/.bashrc`**

```sh
set -o allexport
source /etc/demo/environment
source /data/demo/env/bin/activate
env | grep OFFSPOT_DEMO
```

**`/etc/demo/environment`**

```sh
# Configuration file (this very one file)
OFFSPOT_CONFIGURATION="/etc/demo/environment"

# FQDN which will be used by the demo, e.g. demo.hotspot.kiwix.org
OFFSPOT_DEMO_FQDN="demo.hotspot.kiwix.org"
OFFSPOT_DEMO_HOST_IP="51.158.55.51"

# comma-separated demo info
# format is {ident}:{alias}:
# alias can be empty.
# last semicolon is mandatory so keep a single format between light config (this)
# and rich config with subdomains that is only known upon deployment.
OFFSPOT_DEMOS_LIST="preppers:preppers:Preppers Package:,premium-preppers:premium-preppers:Preppers Premium Package:,computers:compsci:Computer Science Package:,medical:medical:Medical package:,wikipedia-en:wikipedia:Wikipedia Package:"

# Root folder where everything will be deployed (in per-demo subfolder)
#OFFSPOT_DEMO_TARGET_ROOT_DIR="/data/demo/data"
OFFSPOT_DEMO_TARGET_ROOT_DIR="/loop-data"

# Location of the images on disk
OFFSPOT_DEMO_IMAGES_ROOT_DIR="/data/demo/images"
OFFSPOT_DEMO_COMPOSE_ROOT_DIR="/data/demo/compose"

# OCI plateform to use (by default, offspot is linux/aarch64 but usually demo will run on linux/amd64)
OFFSPOT_DEMO_OCI_PLATFORM="linux/amd64"

# Email adress for acme to receive notifications about expiring/expired certificates
OFFSPOT_DEMO_TLS_EMAIL="dev@kiwix.org"

OFFSPOT_DEMO_SRC_DIR="/data/demo/repo/src/offspot_demo"
OFFSPOT_ENV_DIR="/data/demo/env"
OFFSPOT_DEMO_PROXY_CONTAINER_NAME="multi-proxy"
OFFSPOT_DEMO_PROXY_IMAGE_NAME="multi-proxy"
STARTUP_DURATION="15"

IMAGER_SERVICE_API_USERNAME="xxxxx"
IMAGER_SERVICE_API_PASSWORD="xxxxx"
MULTI_CONFIG_URL="https://raw.githubusercontent.com/kiwix/operations/main/demos/demo.offspot.yaml"
```


## Next

- *Protect* the service via a password (provided in-login page? as we want to prevent bots mostly)
- Use LXC containers to isolate from host and allow restoring snapshots frequently to prevent any attack from persisting
- Use Apache Guacamole to isolate the hotpost HTTP service(s) as users would access a VNC-like rendering of it
- Add an FAQ/doc for end-users (in GH for now)
- Do not retry to deploy the same failing image over-and-over every "watcher interval" (15 minutes)
- Implement a healthcheck endpoint (offspot services + demo watcher/deploy, with details like in imager-service https://imager.kiwix.org/health-check)
- Use a private auto-image so users cant download this special image
