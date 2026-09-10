# Current Goal
Stabilize the local Qwen/AgentMux + voice-agentd session path and explain the observed thought-only turn endings.

# Current State
- Diagnosed pi session `01a08c34-abe0-795e-8613-426ab91c258e`: two apparent mid-turn exits were backend EOS events while still inside `reasoning_content`, not client aborts or timeouts. Backend logs show `truncated=0`, no error, and no reasoning deactivation for those requests.
- `hauhau38-smol` and prior `hauhau38` target the exact same Q3_K_P file/inode/SHA. Serving differences are reduced KV precision/context and MTP max draft length.
- Registered `hauhau38-smol` correctly in Pi (`~/.pi/agent/models.json`, commit `c86c426`): 229376 context, 32768 total output, explicit chat-template kwargs for enable/preserve/effort, llama.cpp `thinking_budget_tokens`, and supported Pi effort mappings. Global configurable budgets are minimal=1024, low=2048, medium=8192, high=16384; the model defaults to high. Verified the exact medium request payload and a successful response.
- Synced and versioned the separate Agent TUI model/settings surface in dotfiles commit `9689944`; live files under `~/.pi-agent-tui` are symlinked to that source.
- Found two distinct causes of exact 180-second Breeze failures. ASS-consumed empty turn streams are now cleaned up at `turn.finished` in `voice-agentd`. More importantly for native Pi, `agent-session-srv/.pi/extensions/ass.ts` opened one explicit speech stream for every assistant message containing text but finished only the last stream at `agent_end`; tool loops therefore permanently blocked the FIFO on the first stream. Session `01a08c7e-a630-784d-8b3f-697fed6f9e22` accumulated 17 stuck speech jobs and timed out every three minutes while all ports/health checks remained green.
- Patched the Pi ASS extension to finish each assistant stream on Pi's `message_end`, retain `agent_end` only as a fallback/final-event publisher, clear per-message state, and cancel all outstanding producer speech on extension shutdown. Extension contract smoke and voice contract smoke pass. Cleared the 17 live jobs; a direct start/delta/finish lifecycle synthesized and played/completed in ~3 seconds. Committed as `agent-session-srv` `4a89c9b`; the isolated verified `voice-clients` series ends at `83c0f7b`.

# Decisions
- Output and thinking limits are proper registration/safety controls, not a proven explanation for the prior short thought-only EOS. Keep that distinction explicit. Do not change global sampler temperature or disable MTP without comparative evidence.
- Close ASS-owned empty streams at terminal turn lifecycle and close Pi-owned explicit speech streams at each `message_end`; `agent_end` is too late because it covers the entire multi-message tool loop.

# Open Problems
- Watch new long-context local-model tool loops for another reasoning-only EOS; compare context length and KV precision if it recurs.
- The running Pi process still has the old extension closure. Run `/reload` in that Pi session before the next turn, then confirm Breeze no longer logs exact 180-second timeouts during multi-message tool loops.
- If thought-only EOS recurs materially, compare no-MTP and/or lower-temperature serving before changing global behavior.

# Resume Instructions
In active Pi session `01a08c7e-a630-784d-8b3f-697fed6f9e22`, run `/reload` for the TTS extension fix, then open `/model` and reselect `agentmux/hauhau38-smol` for the model registration refresh. Change reasoning caps in `~/.pi/agent/settings.json` under `thinkingBudgets`; change the active level with `/thinking`. Check `~/runs/voice-agentd/agentd.log` for new 180-second timeouts. For a new thought-only stop, correlate the session timestamp with `~/runs/agentmux/hauhau38-smol/main/podman.log`.
