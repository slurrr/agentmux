from pathlib import Path

from agentmux.config import iter_muxes, resolve_mux


def write_mux(root: Path) -> None:
    path = root / "core" / "demo.toml"
    path.parent.mkdir(parents=True)
    path.write_text(
        """
[mux]
name = "demo"
primary_service = "main"

[defaults]
podman_args = ["--security-opt", "label=disable"]
ports = ["8002:8002"]

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
podman_args = ["--device", "nvidia.com/gpu=all"]
command = ["serve", "--config", "/config.yml"]

[services.main.env]
A = "service"
B = "only-service"

[[services.main.volumes]]
source = "~/models"
target = "/models"
mode = "ro"
""".strip()
        + "\n",
        encoding="utf-8",
    )


def test_resolve_mux_merges_defaults(tmp_path: Path) -> None:
    write_mux(tmp_path)
    mux = resolve_mux("demo", root=tmp_path)
    service = mux.services["main"]

    assert mux.name == "demo"
    assert mux.primary_service == "main"
    assert service.image == "localhost/demo:latest"
    assert service.container_name == "agentmux-demo-main"
    assert service.host == "127.0.0.1"
    assert service.podman_args == [
        "--security-opt",
        "label=disable",
        "--device",
        "nvidia.com/gpu=all",
    ]
    assert service.ports == ["8002:8002"]
    assert service.env == {
        "HF_HOME": "/models/hf",
        "A": "service",
        "B": "only-service",
    }
    assert service.volumes[0].source == str((tmp_path / "core" / "shared").resolve())
    assert service.volumes[0].podman_value().endswith(":/shared:ro")


def test_iter_muxes_uses_tracks(tmp_path: Path) -> None:
    write_mux(tmp_path)
    muxes = iter_muxes(tmp_path)
    assert [mux.name for mux in muxes] == ["demo"]
    assert muxes[0].track == "core"


def test_workspace_export_supplies_backend_recipe(tmp_path: Path) -> None:
    export_dir = tmp_path / "core" / "exports" / "demo"
    export_dir.mkdir(parents=True)
    (export_dir / "agentmux-service.toml").write_text(
        """
[agentmux_export]
version = 1
name = "demo"
backend = "test-backend"

[service]
image = "localhost/exported:latest"
container_port = 5000
runtime_target = "/data"
podman_args = ["--device", "nvidia.com/gpu=all"]
command = ["serve"]

[service.env]
A = "export"

[[service.volumes]]
source = "./config.yml"
target = "/config.yml"
mode = "ro"
""".strip()
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "core" / "demo.toml").write_text(
        """
[mux]
name = "demo"

[services.main]
workspace_export = "./exports/demo"
container_name = "agentmux-demo-main"
port = 8002

[services.main.env]
A = "service"
""".strip()
        + "\n",
        encoding="utf-8",
    )

    mux = resolve_mux("demo", root=tmp_path)
    service = mux.services["main"]

    assert service.image == "localhost/exported:latest"
    assert service.container_port == 5000
    assert service.ports == ["8002:5000"]
    assert service.env == {"A": "service"}
    assert service.runtime_dir == str(Path.home() / "runs" / "agentmux" / "demo" / "main")
    assert service.volumes[-1].podman_value().endswith(":/data:rw")
    assert service.workspace_export is not None
    assert service.workspace_export.backend == "test-backend"
