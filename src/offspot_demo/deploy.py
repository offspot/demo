import sys


def deploy_url(url: str, *, reuse_image: bool):  # noqa: ARG001
    print("Hello from deploy")


def entrypoint():
    deploy_url("", reuse_image=False)


if __name__ == "__main__":
    sys.exit(entrypoint())
