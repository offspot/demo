from dataclasses import dataclass, field
from pathlib import Path

import requests

from offspot_demo import logger
from offspot_demo.constants import (
    DEFAULT_HTTP_TIMEOUT_SECONDS,
    IMAGER_SERVICE_API_PASSWORD,
    IMAGER_SERVICE_API_USERNAME,
    OFFSPOT_DEMO_COMPOSE_ROOT_DIR,
    OFFSPOT_DEMO_IMAGES_ROOT_DIR,
    OFFSPOT_DEMO_MAIN_FQDN,
    OFFSPOT_DEMO_TARGET_ROOT_DIR,
    OFFSPOT_DEMOS_LIST,
)


def port_from(ident: str) -> int:
    return 1024 + sum([ord(char) for char in ident.strip().lower()])


def captive_port_from(ident: str) -> int:
    return 10000 + port_from(ident)


@dataclass
class Deployment:
    ident: str
    alias: str
    name: str
    http_port: int
    captive_http_port: int
    _download_url: str = ""
    _subdomains: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.ident or not self.alias:
            raise ValueError(f"Invalid Deployment data: {self.ident=}, {self.alias=}")

    @classmethod
    def using(cls, ident: str, alias: str = "", name: str = "") -> "Deployment":
        http_port = port_from(ident)
        return Deployment(
            ident=ident.strip(),
            alias=alias.strip() or ident.strip(),
            name=name.strip() or ident.strip(),
            http_port=http_port,
            captive_http_port=10000 + http_port,
        )

    @property
    def fqdn(self) -> str:
        return f"{self.alias}.{OFFSPOT_DEMO_MAIN_FQDN}"

    @property
    def image_url(self) -> str:
        return f"https://api.imager.kiwix.org/auto-images/{self.ident}/json"

    def get_download_url(self) -> str:
        imager_service_api_url = "https://api.imager.kiwix.org"

        def _get_imager_api_token(url: str, username: str, password: str) -> str:
            resp = requests.post(
                url=f"{url}/auth/authorize",
                headers={
                    "username": username,
                    "password": password,
                    "Content-type": "application/json",
                },
                timeout=DEFAULT_HTTP_TIMEOUT_SECONDS,
            )
            resp.raise_for_status()
            return resp.json()["access_token"]

        headers = {"Content-type": "application/json"}
        if self.image_url.startswith(imager_service_api_url):
            headers.update(
                {
                    "token": _get_imager_api_token(
                        url=imager_service_api_url,
                        username=IMAGER_SERVICE_API_USERNAME,
                        password=IMAGER_SERVICE_API_PASSWORD,
                    ),
                }
            )

        resp = requests.get(
            self.image_url, headers=headers, timeout=DEFAULT_HTTP_TIMEOUT_SECONDS
        )
        resp.raise_for_status()
        payload = resp.json()
        if not payload.get("http_url"):
            logger.warning(f"'http_url' not found in response from {self.image_url}")
            logger.debug(resp.text)
            raise Exception("Unexpected response from image provider")
        return payload["http_url"]

    @property
    def download_url(self) -> str:
        if not self._download_url:
            self._download_url = self.get_download_url()
        return self._download_url

    @property
    def target_dir(self) -> Path:
        return OFFSPOT_DEMO_TARGET_ROOT_DIR.joinpath(self.ident)

    @property
    def compose_dir(self) -> Path:
        return OFFSPOT_DEMO_COMPOSE_ROOT_DIR.joinpath(self.ident)

    @property
    def compose_path(self) -> Path:
        self.compose_dir.mkdir(parents=True, exist_ok=True)
        return self.compose_dir.joinpath("compose.yaml")

    @property
    def image_compose_path(self) -> Path:
        return self.compose_dir.joinpath("image-compose.yaml")

    @property
    def maint_compose_path(self) -> Path:
        return self.compose_dir.joinpath("maint-compose.yaml")

    @property
    def maint_compose_installed(self) -> bool:
        return self.maint_compose_path.exists()

    @property
    def image_path(self) -> Path:
        return OFFSPOT_DEMO_IMAGES_ROOT_DIR / self.ident / "image.img"

    @property
    def tmp_image_path(self) -> Path:
        return self.image_path.with_suffix(".img.tmp")

    @property
    def last_image_url_path(self) -> Path:
        return self.image_path.with_name("last_image")

    @property
    def last_image_url(self) -> str:
        try:
            return self.last_image_url_path.read_text()
        except Exception:
            return ""

    def write_last_image_url(self):
        self.last_image_url_path.parent.mkdir(parents=True, exist_ok=True)
        self.last_image_url_path.write_text(self.download_url)

    @property
    def prepared_ok_path(self) -> Path:
        return self.target_dir.joinpath("prepared.ok")

    @property
    def is_already_prepared(self) -> bool:
        return self.prepared_ok_path.exists()

    @property
    def has_new_image(self) -> bool:
        return self.get_download_url() != self.last_image_url

    @property
    def subdomains(self) -> list[str]:
        if not self._subdomains:
            try:
                self._subdomains = self.subdomains_path.read_text().split(",")
            except Exception:
                ...
        return self._subdomains

    @subdomains.setter
    def subdomains(self, subdomains: list[str]):
        self.subdomains_path.write_text(",".join(subdomains))

    @property
    def subdomains_path(self) -> Path:
        return self.target_dir.joinpath("subdomains")

    def __str__(self) -> str:
        return self.ident


DEPLOYMENTS: dict[str, Deployment] = {
    entry.split(":", 3)[0]: Deployment.using(
        ident=entry.split(":", 3)[0],
        alias=(entry.split(":", 3)[1] or entry.split(":", 3)[0]),
        name=(entry.split(":", 3)[2] or entry.split(":", 3)[0]),
    )
    for entry in OFFSPOT_DEMOS_LIST
}
