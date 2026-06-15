from pathlib import Path

from agentmux.config import iter_muxes, resolve_mux


def write_mux(root: Path) -> None:
    path = root / "core" / "demo" / "mux.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
[mux]
name = "demo"
primary_service = "main"

[defaults]
podman_args = ["--security-opt", "label=disable"]

[defaults.env]
HF_HOME = "/models/hf"
A = "default"

[[defaults.volumes]]
source = "./shared"
target = "/shared"
mode = "ro"

[services.main]
image = "localhost/demo:latest"
container_name = "agentmux-demo-main"
port = 8002
container_port = 5000
podman_args = ["--device", "nvidia.com/gpu=all"]
command = ["serve"]

[services.main.env]
A = "service"
B = "only-service"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_resolve_mux_merges_defaults_and_adds_runtime(tmp_path: Path) -> None:
    write_mux(tmp_path)
    mux = resolve_mux("demo", root=tmp_path)
    service = mux.services["main"]

    assert mux.name == "demo"
    assert mux.primary_service == "main"
    assert service.image == "localhost/demo:latest"
    assert service.container_name == "agentmux-demo-main"
    assert service.host == "127.0.0.1"
    assert service.ports == ["8002:5000"]
    assert service.podman_args == [
        "--security-opt",
        "label=disable",
        "--device",
        "nvidia.com/gpu=all",
    ]
    assert service.env == {
        "HF_HOME": "/models/hf",
        "A": "service",
        "B": "only-service",
    }
    assert service.volumes[0].source == str((tmp_path / "core" / "demo" / "shared").resolve())
    assert service.volumes[0].podman_value().endswith(":/shared:ro")
    assert service.volumes[-1].podman_value() == (
        f"{Path.home() / 'runs' / 'agentmux' / 'demo' / 'main'}:/runs:rw"
    )


def test_iter_muxes_uses_directory_tracks(tmp_path: Path) -> None:
    write_mux(tmp_path)
    muxes = iter_muxes(tmp_path)
    assert [mux.name for mux in muxes] == ["demo"]
    assert muxes[0].track == "core"


def test_directory_name_can_resolve_mux(tmp_path: Path) -> None:
    write_mux(tmp_path)
    assert resolve_mux("demo", root=tmp_path).path == tmp_path / "core" / "demo" / "mux.toml"
