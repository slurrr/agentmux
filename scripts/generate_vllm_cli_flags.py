#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import shutil
import sys
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV_SITE = ROOT / ".venv" / "lib"
if VENV_SITE.exists():
    for candidate in sorted(VENV_SITE.glob("python*/site-packages")):
        sys.path.insert(0, str(candidate))

from vllm import platforms  # type: ignore[import-not-found]
from vllm.platforms.cpu import CpuPlatform  # type: ignore[import-not-found]

platforms.current_platform = CpuPlatform()

import vllm.entrypoints.cli.benchmark.main as bench_main  # type: ignore[import-not-found]
import vllm.entrypoints.cli.collect_env as collect_env  # type: ignore[import-not-found]
import vllm.entrypoints.cli.openai as openai  # type: ignore[import-not-found]
import vllm.entrypoints.cli.run_batch as run_batch  # type: ignore[import-not-found]
import vllm.entrypoints.cli.serve as serve  # type: ignore[import-not-found]
from vllm.entrypoints.utils import VLLM_SUBCMD_PARSER_EPILOG  # type: ignore[import-not-found]
from vllm.utils.argparse_utils import FlexibleArgumentParser  # type: ignore[import-not-found]

OUT = ROOT / "docs" / "reference" / "vllm-cli-flags.md"
PREV = ROOT / "docs" / "reference" / "vllm-cli-flags-prev.md"
CAPABILITIES_OUT = ROOT / "docs" / "reference" / "vllm-cli-capabilities.md"

PREFERRED_CANONICAL_TITLES = {
    "vllm serve": 0,
    "vllm run-batch": 1,
    "vllm bench throughput": 2,
    "vllm bench latency": 3,
    "vllm bench startup": 4,
    "vllm bench mm-processor": 5,
    "vllm bench serve": 6,
    "vllm bench sweep": 7,
    "vllm complete": 8,
    "vllm chat": 9,
    "vllm collect-env": 10,
    "vllm bench": 11,
    "vllm": 12,
}


def build_parser_tree() -> tuple[FlexibleArgumentParser, dict[str, argparse.ArgumentParser]]:
    mods = [openai, serve, bench_main, collect_env, run_batch]
    root = FlexibleArgumentParser(
        description="vLLM CLI",
        epilog=VLLM_SUBCMD_PARSER_EPILOG.format(subcmd="[subcommand]"),
    )
    root.add_argument(
        "-v",
        "--version",
        action="version",
        version=importlib.metadata.version("vllm"),
    )
    subparsers = root.add_subparsers(required=False, dest="subparser")
    command_parsers: dict[str, argparse.ArgumentParser] = {}
    for mod in mods:
        for cmd in mod.cmd_init():
            parser = cmd.subparser_init(subparsers)
            command_parsers[cmd.name] = parser
    return root, command_parsers


def flatten(text: str) -> str:
    return text.replace("\n", " ").strip()


def default_text(value: object) -> str | None:
    if value in (argparse.SUPPRESS, None, False, [], (), {}):
        return None
    try:
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    except Exception:
        return repr(value)


def metavar_for(action: argparse.Action) -> str:
    if action.metavar:
        if isinstance(action.metavar, tuple):
            return " ".join(str(x) for x in action.metavar)
        return str(action.metavar)
    if action.nargs == 0:
        return ""
    if action.choices:
        return "<" + "|".join(str(c) for c in action.choices) + ">"
    if action.type is int:
        return "<int>"
    if action.type is float:
        return "<float>"
    return f"<{getattr(action, 'dest', 'value').upper()}>"


def option_signature(action: argparse.Action) -> str:
    metavar = metavar_for(action)
    return ", ".join(f"{opt} {metavar}".rstrip() for opt in action.option_strings)


def sort_key(action: argparse.Action) -> tuple[int, str]:
    if action.option_strings:
        return (0, action.option_strings[0])
    return (1, action.dest)


def action_lines(action: argparse.Action) -> list[str]:
    help_text = flatten(action.help or "")
    if action.option_strings:
        signature = option_signature(action)
        default = default_text(action.default)
        suffix = f" Default: `{default}`." if default is not None else ""
        return [f"- `{signature}`: {help_text}{suffix}".rstrip()]
    return [f"- `{action.dest}`: {help_text}".rstrip()]


def parser_title_rank(title: str) -> tuple[int, str]:
    normalized = title.strip("`")
    return (PREFERRED_CANONICAL_TITLES.get(normalized, 100), normalized)


def group_body_lines(actions: list[argparse.Action]) -> list[str]:
    lines: list[str] = []
    for action in sorted(actions, key=sort_key):
        lines.extend(action_lines(action))
    return lines


def collect_group_registry(
    title: str,
    parser: argparse.ArgumentParser,
    registry: dict[tuple[str, tuple[str, ...]], list[str]],
) -> None:
    for group in parser._action_groups:
        actions = [
            action
            for action in group._group_actions
            if not isinstance(action, argparse._SubParsersAction)
        ]
        if not actions:
            continue
        key = (group.title, tuple(group_body_lines(actions)))
        registry[key].append(title)

    subparser_action = next(
        (action for action in parser._actions if isinstance(action, argparse._SubParsersAction)),
        None,
    )
    if subparser_action is None:
        return
    for name in sorted(subparser_action.choices):
        collect_group_registry(f"{title} {name}", subparser_action.choices[name], registry)


def build_canonical_group_map(
    root: argparse.ArgumentParser,
) -> dict[tuple[str, tuple[str, ...]], str]:
    registry: dict[tuple[str, tuple[str, ...]], list[str]] = defaultdict(list)
    collect_group_registry("vllm", root, registry)
    return {
        key: min(owners, key=parser_title_rank)
        for key, owners in registry.items()
    }


def emit_parser(
    title: str,
    parser: argparse.ArgumentParser,
    canonical_groups: dict[tuple[str, tuple[str, ...]], str],
    level: int = 2,
) -> list[str]:
    lines: list[str] = []
    lines.append(f"{'#' * level} `{title}`")
    usage = flatten(parser.format_usage()).removeprefix("usage: ")
    lines.append(f"- Usage: `{usage}`")

    subparser_action = next(
        (action for action in parser._actions if isinstance(action, argparse._SubParsersAction)),
        None,
    )
    if subparser_action is not None:
        names = ", ".join(f"`{name}`" for name in sorted(subparser_action.choices))
        lines.append(f"- Subcommands: {names}")

    if isinstance(parser, FlexibleArgumentParser) and subparser_action is None:
        groups = [group.title for group in parser._action_groups if group._group_actions]
        if groups:
            names = ", ".join(f"`{name}`" for name in groups)
            lines.append(f"- Help groups: {names}")
            lines.append(
                "- `--help=<group>` works on this parser. `--help=all` shows the full bottom-level help output."
            )

    for group in parser._action_groups:
        actions = [
            action
            for action in group._group_actions
            if not isinstance(action, argparse._SubParsersAction)
        ]
        if not actions:
            continue
        body_lines = group_body_lines(actions)
        key = (group.title, tuple(body_lines))
        canonical_title = canonical_groups[key]
        lines.append(f"### {group.title}")
        if canonical_title != title:
            lines.append(
                f"- Same as `{canonical_title}` -> `{group.title}`."
            )
            continue
        lines.extend(body_lines)

    if subparser_action is not None:
        for name in sorted(subparser_action.choices):
            lines.append("")
            lines.extend(
                emit_parser(
                    f"{title} {name}",
                    subparser_action.choices[name],
                    canonical_groups,
                    level + 1,
                )
            )

    return lines


def render_markdown() -> str:
    root, command_parsers = build_parser_tree()
    canonical_groups = build_canonical_group_map(root)
    lines: list[str] = []
    lines.append("# vLLM CLI Flag Map")
    lines.append("")
    lines.append(
        "This document is generated from the `vllm` installation in this repo environment. It lists commands, help layers, and registered flags that are actually present here."
    )
    lines.append("")
    lines.append("## Probe Context")
    lines.append(f"- Date: `{date.today().isoformat()}`")
    lines.append(f"- Repo: `{ROOT}`")
    lines.append(f"- Python: `{sys.version.split()[0]}`")
    lines.append(f"- vLLM: `{importlib.metadata.version('vllm')}`")
    lines.append(f"- vLLM entrypoint: `{ROOT / '.venv' / 'bin' / 'vllm'}`")
    lines.append(f"- Host: `{platform.platform()}`")
    lines.append(
        "- Probe mode: force `vllm.platforms.current_platform = CpuPlatform()` before parser construction so help can be introspected on this host."
    )
    lines.append(
        "- Why the force is needed: plain `uv run vllm --help` currently aborts here with `RuntimeError: Failed to infer device type` while building the `serve` parser."
    )
    lines.append("")
    lines.append("## Command Tree")
    lines.append(
        f"- Top-level commands: {', '.join(f'`{name}`' for name in sorted(command_parsers))}"
    )
    lines.append(
        "- Nested commands: `vllm bench latency`, `vllm bench mm-processor`, `vllm bench serve`, `vllm bench startup`, `vllm bench sweep`, `vllm bench throughput`"
    )
    lines.append("")
    lines.append("## Help Layers")
    lines.append("- `vllm --help`: top-level command list.")
    lines.append("- `vllm <command> --help`: command-level help.")
    lines.append("- `vllm bench <subcommand> --help`: nested benchmark help.")
    lines.append(
        "- Bottom-level parsers built with `FlexibleArgumentParser` also support `--help=<group>`, `--help=all`, and substring matching such as `--help=tokenizer`."
    )
    lines.append(
        "- Identical named flag groups are emitted once and later occurrences point back to the canonical command section."
    )
    lines.append("")
    lines.extend(emit_parser("vllm", root, canonical_groups, 2))
    return "\n".join(lines) + "\n"


def build_command_index(
    root: argparse.ArgumentParser,
) -> dict[str, dict[str, dict[str, argparse.Action]]]:
    index: dict[str, dict[str, dict[str, argparse.Action]]] = {}

    def walk(title: str, parser: argparse.ArgumentParser) -> None:
        group_map: dict[str, dict[str, argparse.Action]] = {}
        for group in parser._action_groups:
            actions = [
                action
                for action in group._group_actions
                if not isinstance(action, argparse._SubParsersAction)
            ]
            if not actions:
                continue
            action_map: dict[str, argparse.Action] = {}
            for action in actions:
                if action.option_strings:
                    for opt in action.option_strings:
                        action_map[opt] = action
                action_map[action.dest] = action
            group_map[group.title] = action_map
        index[title] = group_map

        subparser_action = next(
            (action for action in parser._actions if isinstance(action, argparse._SubParsersAction)),
            None,
        )
        if subparser_action is None:
            return
        for name in sorted(subparser_action.choices):
            walk(f"{title} {name}", subparser_action.choices[name])

    walk("vllm", root)
    return index


def lookup_action(
    index: dict[str, dict[str, dict[str, argparse.Action]]],
    command: str,
    identifier: str,
) -> argparse.Action:
    for actions in index[command].values():
        if identifier in actions:
            return actions[identifier]
    raise KeyError(f"{command}: missing action for {identifier}")


def section_lines(
    title: str,
    command: str,
    descriptions: list[str],
    flags: list[str],
    index: dict[str, dict[str, dict[str, argparse.Action]]],
) -> list[str]:
    lines = [f"## {title}", "", "Primary command:", f"- `{command}`", ""]
    for block in descriptions:
        lines.append(block)
        lines.append("")
    for flag in flags:
        lines.extend(action_lines(lookup_action(index, command, flag)))
    lines.append("")
    return lines


def render_capabilities_markdown() -> str:
    root, _ = build_parser_tree()
    index = build_command_index(root)
    lines: list[str] = []
    lines.append("# vLLM CLI Capabilities")
    lines.append("")
    lines.append(
        "This document reorganizes the registered local `vllm` CLI surface for fast human lookup. "
        "It keeps broad serving coverage while excluding obvious non-serving noise like `bench` and `collect-env`."
    )
    lines.append("")
    lines.append("Source of truth:")
    lines.append(f"- [{OUT.name}]({OUT})")
    lines.append("")
    lines.append("## Quick Find")
    lines.append("")
    lines.append("If you want to find:")
    lines.append("- basic serving and addressing: `Serving Identity And Addressing`")
    lines.append("- OpenAI-compatible HTTP/API behavior: `API Server And Request Surface`")
    lines.append("- tool-capable agents: `Tools And Structured Outputs`")
    lines.append("- multimodal serving: `Multimodal And Media`")
    lines.append("- LoRA or adapter routing: `LoRA And Adapters`")
    lines.append("- model loading and tokenizer control: `Model, Tokenizer, And Loading`")
    lines.append("- scaling and topology: `Parallelism And Topology`")
    lines.append("- cache, memory, and throughput knobs: `Memory, Cache, And Throughput`")
    lines.append("- logs, traces, and metrics: `Logging, Metrics, And Debugging`")
    lines.append("- lower-level execution internals: `Advanced Execution Controls`")
    lines.append("- batch processing: `Batch Command Surface`")
    lines.append("- interactive chat/completion clients: `Client Commands`")
    lines.append("")
    lines.append("## Relevant Commands")
    lines.append("")
    lines.append("- `vllm serve [model_tag] [options]`")
    lines.append("- `vllm run-batch -i INPUT.jsonl -o OUTPUT.jsonl --model <model>`")
    lines.append("- `vllm chat [options]`")
    lines.append("- `vllm complete [options]`")
    lines.append("")
    lines.append("## Common Operator Questions")
    lines.append("")
    lines.append("- Context length / window: `--max-model-len` under `Model, Tokenizer, And Loading`.")
    lines.append("- Output cap at serve boot: there is no obvious `vllm serve --max-new-tokens` style launch flag in this registered CLI surface.")
    lines.append("- Output cap at client/request time: `vllm complete` exposes `--max-tokens`; OpenAI-compatible request bodies are where generation limits usually live.")
    lines.append("- Sampling controls: they do not appear as normal `vllm serve` launch flags in this installed CLI surface. For this environment, treat sampling as primarily request-level rather than boot-time configuration.")
    lines.append("- Tool-capable serving: start with `Tools And Structured Outputs`.")
    lines.append("- Multimodal serving: start with `Multimodal And Media`.")
    lines.append("- LoRA/adapters: start with `LoRA And Adapters`.")
    lines.append("- Throughput and memory tuning: start with `Memory, Cache, And Throughput` and `Parallelism And Topology`.")
    lines.append("")

    lines.extend(
        section_lines(
            "Serving Identity And Addressing",
            "vllm serve",
            [
                "Core identity and addressing flags:",
                "Serve mode and process shape:",
            ],
            [
                "model_tag",
                "--model",
                "--served-model-name",
                "--host",
                "--port",
                "--uds",
                "--root-path",
                "--headless",
                "--api-server-count",
                "--config",
            ],
            index,
        )
    )
    lines.append("Related batch/client identity flags:")
    lines.extend(action_lines(lookup_action(index, "vllm run-batch", "--host")))
    lines.extend(action_lines(lookup_action(index, "vllm run-batch", "--port")))
    lines.extend(action_lines(lookup_action(index, "vllm run-batch", "--url")))
    lines.extend(action_lines(lookup_action(index, "vllm chat", "--url")))
    lines.extend(action_lines(lookup_action(index, "vllm chat", "--model-name")))
    lines.extend(action_lines(lookup_action(index, "vllm complete", "--url")))
    lines.extend(action_lines(lookup_action(index, "vllm complete", "--model-name")))
    lines.append("")

    lines.extend(
        section_lines(
            "API Server And Request Surface",
            "vllm serve",
            [
                "OpenAI-compatible frontend behavior:",
            ],
            [
                "--api-key",
                "--response-role",
                "--return-tokens-as-token-ids",
                "--tokens-only",
                "--enable-force-include-usage",
                "--enable-prompt-tokens-details",
                "--enable-request-id-headers",
                "--enable-tokenizer-info-endpoint",
                "--enable-server-load-tracking",
            ],
            index,
        )
    )
    lines.append("Docs and operator-facing HTTP surface:")
    lines.extend(action_lines(lookup_action(index, "vllm serve", "--disable-fastapi-docs")))
    lines.extend(action_lines(lookup_action(index, "vllm serve", "--enable-offline-docs")))
    lines.append("")
    lines.append("Access logging and HTTP parser limits:")
    for ident in [
        "--disable-uvicorn-access-log",
        "--disable-access-log-for-endpoints",
        "--uvicorn-log-level",
        "--h11-max-header-count",
        "--h11-max-incomplete-event-size",
    ]:
        lines.extend(action_lines(lookup_action(index, "vllm serve", ident)))
    lines.append("")
    lines.append("CORS and middleware surface:")
    for ident in [
        "--allow-credentials",
        "--allowed-origins",
        "--allowed-methods",
        "--allowed-headers",
        "--middleware",
    ]:
        lines.extend(action_lines(lookup_action(index, "vllm serve", ident)))
    lines.append("")
    lines.append("TLS and HTTPS:")
    for ident in [
        "--ssl-keyfile",
        "--ssl-certfile",
        "--ssl-ca-certs",
        "--enable-ssl-refresh",
        "--ssl-cert-reqs",
        "--ssl-ciphers",
    ]:
        lines.extend(action_lines(lookup_action(index, "vllm serve", ident)))
    lines.append("")

    lines.extend(
        section_lines(
            "Tools And Structured Outputs",
            "vllm serve",
            ["Tool-capable agent controls:"],
            [
                "--enable-auto-tool-choice",
                "--exclude-tools-when-tool-choice-none",
                "--tool-call-parser",
                "--tool-parser-plugin",
                "--tool-server",
            ],
            index,
        )
    )
    lines.append("Prompt/template trust and chat rendering:")
    for ident in [
        "--chat-template",
        "--chat-template-content-format",
        "--default-chat-template-kwargs",
        "--trust-request-chat-template",
    ]:
        lines.extend(action_lines(lookup_action(index, "vllm serve", ident)))
    lines.append("")
    lines.append("Structured output and reasoning-related flags:")
    for ident in [
        "--reasoning-parser",
        "--reasoning-parser-plugin",
        "--structured-outputs-config",
        "--speculative-config",
        "--generation-config",
        "--override-generation-config",
        "--max-logprobs",
        "--logprobs-mode",
    ]:
        lines.extend(action_lines(lookup_action(index, "vllm serve", ident)))
    lines.append("")

    lines.extend(
        section_lines(
            "Multimodal And Media",
            "vllm serve",
            [
                "Model/media permissions:",
                "Multimodal execution controls:",
            ],
            [
                "--allowed-local-media-path",
                "--allowed-media-domains",
                "--enable-mm-embeds",
                "--interleave-mm-strings",
                "--language-model-only",
                "--limit-mm-per-prompt",
                "--media-io-kwargs",
                "--mm-encoder-attn-backend",
                "--mm-encoder-only",
                "--mm-encoder-tp-mode",
                "--mm-processor-kwargs",
                "--skip-mm-profiling",
                "--video-pruning-rate",
                "--mm-processor-cache-gb",
                "--mm-processor-cache-type",
                "--mm-shm-cache-max-object-size-mb",
                "--io-processor-plugin",
                "--default-mm-loras",
            ],
            index,
        )
    )

    lines.extend(
        section_lines(
            "LoRA And Adapters",
            "vllm serve",
            [
                "Runtime LoRA enablement and modules:",
                "LoRA scaling and capacity:",
            ],
            [
                "--enable-lora",
                "--lora-modules",
                "--max-loras",
                "--max-lora-rank",
                "--max-cpu-loras",
                "--lora-dtype",
                "--fully-sharded-loras",
                "--specialize-active-lora",
                "--enable-tower-connector-lora",
            ],
            index,
        )
    )

    lines.extend(
        section_lines(
            "Model, Tokenizer, And Loading",
            "vllm serve",
            [
                "Model selection and implementation:",
            ],
            [
                "--model",
                "--model-impl",
                "--runner",
                "--convert",
                "--tokenizer",
                "--tokenizer-mode",
                "--tokenizer-revision",
                "--skip-tokenizer-init",
                "--revision",
                "--code-revision",
                "--trust-remote-code",
                "--hf-token",
                "--dtype",
                "--quantization",
                "--allow-deprecated-quantization",
                "--enforce-eager",
                "--enable-sleep-mode",
                "--override-attention-dtype",
                "--max-model-len",
                "--seed",
                "--disable-sliding-window",
                "--disable-cascade-attn",
                "--enable-prompt-embeds",
                "--enable-return-routed-experts",
                "--pooler-config",
                "--logits-processors",
                "--download-dir",
                "--load-format",
                "--model-loader-extra-config",
                "--pt-load-map-location",
                "--safetensors-load-strategy",
                "--ignore-patterns",
                "--use-tqdm-on-load",
                "--hf-config-path",
                "--hf-overrides",
                "--config-format",
            ],
            index,
        )
    )

    lines.extend(
        section_lines(
            "Parallelism And Topology",
            "vllm serve",
            ["Core topology and cluster coordination:"],
            [
                "--tensor-parallel-size",
                "--pipeline-parallel-size",
                "--data-parallel-size",
                "--data-parallel-size-local",
                "--decode-context-parallel-size",
                "--prefill-context-parallel-size",
                "--nnodes",
                "--node-rank",
                "--data-parallel-address",
                "--data-parallel-rpc-port",
                "--data-parallel-rank",
                "--data-parallel-start-rank",
                "--data-parallel-backend",
                "--master-addr",
                "--master-port",
                "--data-parallel-external-lb",
                "--data-parallel-hybrid-lb",
                "--all2all-backend",
                "--enable-expert-parallel",
                "--enable-elastic-ep",
                "--enable-eplb",
                "--eplb-config",
                "--expert-placement-strategy",
                "--distributed-executor-backend",
                "--max-parallel-loading-workers",
                "--worker-cls",
                "--worker-extension-cls",
                "--ray-workers-use-nsight",
                "--disable-custom-all-reduce",
                "--disable-nccl-for-dp-synchronization",
                "--ubatch-size",
                "--cp-kv-cache-interleave-size",
                "--dcp-kv-cache-interleave-size",
                "--dbo-decode-token-threshold",
                "--dbo-prefill-token-threshold",
                "--enable-dbo",
            ],
            index,
        )
    )

    lines.extend(
        section_lines(
            "Memory, Cache, And Throughput",
            "vllm serve",
            ["GPU, cache, batching, and offload knobs:"],
            [
                "--gpu-memory-utilization",
                "--kv-cache-dtype",
                "--kv-cache-memory-bytes",
                "--block-size",
                "--num-gpu-blocks-override",
                "--calculate-kv-scales",
                "--enable-prefix-caching",
                "--prefix-caching-hash-algo",
                "--kv-sharing-fast-prefill",
                "--enable-chunked-prefill",
                "--disable-chunked-mm-input",
                "--long-prefill-token-threshold",
                "--max-long-partial-prefills",
                "--max-num-partial-prefills",
                "--disable-hybrid-kv-cache-manager",
                "--max-num-batched-tokens",
                "--max-num-seqs",
                "--scheduler-cls",
                "--scheduling-policy",
                "--async-scheduling",
                "--stream-interval",
                "--swap-space",
                "--cpu-offload-gb",
                "--cpu-offload-params",
                "--offload-backend",
                "--offload-group-size",
                "--offload-num-in-group",
                "--offload-params",
                "--offload-prefetch-step",
                "--kv-offloading-backend",
                "--kv-offloading-size",
                "--mamba-block-size",
                "--mamba-cache-dtype",
                "--mamba-cache-mode",
                "--mamba-ssm-cache-dtype",
            ],
            index,
        )
    )

    lines.extend(
        section_lines(
            "Logging, Metrics, And Debugging",
            "vllm serve",
            ["General logging, metrics, and validation:"],
            [
                "--disable-log-stats",
                "--aggregate-engine-logging",
                "--enable-log-requests",
                "--enable-log-outputs",
                "--enable-log-deltas",
                "--max-log-len",
                "--log-config-file",
                "--log-error-stack",
                "--fail-on-environ-validation",
                "--collect-detailed-traces",
                "--cudagraph-metrics",
                "--enable-layerwise-nvtx-tracing",
                "--enable-logging-iteration-details",
                "--enable-mfu-metrics",
                "--kv-cache-metrics",
                "--kv-cache-metrics-sample",
                "--otlp-traces-endpoint",
                "--show-hidden-metrics-for-version",
            ],
            index,
        )
    )

    lines.extend(
        section_lines(
            "Advanced Execution Controls",
            "vllm serve",
            ["Lower-level backend, compilation, transfer, and profiler knobs:"],
            [
                "--attention-backend",
                "--kernel-config",
                "--attention-config",
                "--enable-flashinfer-autotune",
                "--moe-backend",
                "--cudagraph-capture-sizes",
                "--max-cudagraph-capture-size",
                "--compilation-config",
                "--optimization-level",
                "--performance-mode",
                "--additional-config",
                "--kv-transfer-config",
                "--kv-events-config",
                "--ec-transfer-config",
                "--weight-transfer-config",
                "--profiler-config",
            ],
            index,
        )
    )

    lines.append("## Batch Command Surface")
    lines.append("")
    lines.append("Primary command:")
    lines.append("- `vllm run-batch`")
    lines.append("")
    lines.append("Purpose:")
    lines.append("- run prompts from input file(s) and write results out, while still inheriting most of the same engine/config groups as `serve`")
    lines.append("")
    for ident in [
        "--input-file",
        "--output-file",
        "--output-tmp-dir",
        "--url",
        "--host",
        "--port",
        "--enable-metrics",
        "--chat-template",
        "--chat-template-content-format",
        "--default-chat-template-kwargs",
        "--disable-frontend-multiprocessing",
        "--enable-auto-tool-choice",
        "--enable-force-include-usage",
        "--enable-log-deltas",
        "--enable-log-outputs",
        "--enable-prompt-tokens-details",
        "--enable-server-load-tracking",
        "--enable-tokenizer-info-endpoint",
        "--exclude-tools-when-tool-choice-none",
        "--lora-modules",
        "--response-role",
        "--return-tokens-as-token-ids",
        "--tokens-only",
        "--tool-call-parser",
        "--tool-parser-plugin",
        "--tool-server",
        "--trust-request-chat-template",
    ]:
        lines.extend(action_lines(lookup_action(index, "vllm run-batch", ident)))
    lines.append("")
    lines.append("Shared inherited config groups:")
    for group_name in [
        "ModelConfig",
        "LoadConfig",
        "AttentionConfig",
        "StructuredOutputsConfig",
        "ParallelConfig",
        "CacheConfig",
        "OffloadConfig",
        "MultiModalConfig",
        "LoRAConfig",
        "ObservabilityConfig",
        "SchedulerConfig",
        "CompilationConfig",
        "KernelConfig",
        "VllmConfig",
    ]:
        lines.append(f"- `{group_name}`")
    lines.append("")

    lines.append("## Client Commands")
    lines.append("")
    lines.append("These do not launch a server. They talk to a running OpenAI-compatible endpoint.")
    lines.append("")
    lines.append("### `vllm chat`")
    lines.append("")
    for ident in ["--url", "--model-name", "--api-key", "--system-prompt", "--quick"]:
        lines.extend(action_lines(lookup_action(index, "vllm chat", ident)))
    lines.append("")
    lines.append("### `vllm complete`")
    lines.append("")
    for ident in ["--url", "--model-name", "--api-key", "--max-tokens", "--quick"]:
        lines.extend(action_lines(lookup_action(index, "vllm complete", ident)))
    lines.append("")
    lines.append("Sampling note:")
    lines.append("- The registered local CLI does not expose a normal `vllm serve` sampling block with flags like `--temperature` or `--top-p`.")
    lines.append("- Inference from the installed CLI surface: sampling appears to live mainly at request time for OpenAI-compatible serving, not as a primary server boot-time knob.")
    lines.append("- The only directly exposed client-side generation cap in these kept commands is `vllm complete --max-tokens`.")
    lines.append("")
    lines.append("## Deliberately Excluded")
    lines.append("")
    lines.append("- `vllm bench ...`")
    lines.append("- `vllm collect-env`")
    lines.append("")
    lines.append("Reason:")
    lines.append("- they are useful, but they are not part of the first-pass question of what this environment can serve and route agent traffic through")
    lines.append("")
    return "\n".join(lines)


def write_snapshot(markdown: str) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", delete=False, dir=OUT.parent, encoding="utf-8") as tmp:
        tmp.write(markdown)
        tmp_path = Path(tmp.name)

    try:
        if OUT.exists():
            shutil.copy2(OUT, PREV)
        tmp_path.replace(OUT)
        OUT.chmod(0o644)
        if PREV.exists():
            PREV.chmod(0o644)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + ("" if content.endswith("\n") else "\n"), encoding="utf-8")
    path.chmod(0o644)


def main() -> int:
    markdown = render_markdown()
    capabilities_markdown = render_capabilities_markdown()
    write_snapshot(markdown)
    write_file(CAPABILITIES_OUT, capabilities_markdown)
    print(OUT)
    if PREV.exists():
        print(PREV)
    print(CAPABILITIES_OUT)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
