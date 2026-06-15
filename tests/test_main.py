from pathlib import Path

from agentmux.main import run


def test_render_json_cli(tmp_path: Path, capsys) -> None:
    mux_dir = tmp_path / "core"
    mux_dir.mkdir(parents=True)
    (mux_dir / "demo.toml").write_text(
        """
[mux]
name = "demo"

[services.main]
image = "localhost/demo:latest"
container_name = "agentmux-demo-main"
port = 8002
""".strip()
        + "\n",
        encoding="utf-8",
    )

    rc = run(["--root", str(tmp_path), "render", "demo", "--json"])
    out = capsys.readouterr().out

    assert rc == 0
    assert '"mux": "demo"' in out
    assert '"container_name": "agentmux-demo-main"' in out
    assert '"podman"' in out
