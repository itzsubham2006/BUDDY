# Jarvis — Personal AI Desktop Agent

A modular, permission-gated personal AI agent for Windows. Jarvis listens
for a wake word, understands natural-language commands, executes approved
actions on your computer, and responds through speech.

> **Status: V1 foundation.** The LLM → orchestrator → tool pipeline,
> permission system, memory, and core tools are implemented and tested.
> Voice input (wake word, STT), the system tray, and Windows autostart
> have defined interfaces but are not yet fully implemented — see
> [Roadmap](#roadmap) below. Until then, Jarvis runs as a text console
> app so the full agent logic can be used and tested today.

---

## Architecture

```
Microphone → Wake Word → Speech-to-Text → Agent Orchestrator → LLM
    → Tool Selection → Permission Check → Confirmation (if needed)
    → Tool Execution → Result → LLM Response → Text-to-Speech → Speaker
```

| Layer | Role | Location |
|---|---|---|
| LLM | The **brain** — decides intent and picks tools | `app/llm/` |
| Tools | The **hands** — do one thing each | `app/tools/` |
| Permission system | The **safety layer** — the LLM cannot bypass it | `app/security/` |
| Orchestrator | The **control center** — runs the pipeline | `app/agent/` |
| Wake word / mic | The **ears** | `app/audio/` |
| TTS | The **voice** | `app/speech/` |

Each layer is independent and swappable: change LLM providers, STT/TTS
backends, or add tools without touching the others.

```
jarvis/
├── app/
│   ├── main.py              # entry point / composition root
│   ├── config.py            # .env + config.yaml loader
│   ├── logging_config.py    # structured, secret-redacting logging
│   ├── agent/                # orchestrator, planner, prompts, state
│   ├── audio/                 # microphone, recorder, wake word (interfaces)
│   ├── speech/                # STT, TTS
│   ├── llm/                   # provider-agnostic LLM client
│   ├── tools/                 # registry + all concrete tools
│   ├── browser/                # Playwright wrapper
│   ├── memory/                 # short-term + long-term memory
│   ├── security/                # permissions + confirmations
│   ├── desktop/                  # system tray, Windows startup
│   └── ui/                        # optional desktop notifications
├── config/config.example.yaml    # copy to config.yaml
├── tests/                         # 32 passing unit tests
├── scripts/                        # install / build / uninstall
├── .env.example                    # copy to .env — NEVER commit .env
└── requirements.txt
```

## Setup

```bash
pip install -r requirements.txt
python scripts/install.py          # creates .env and config.yaml, prompts for API key
playwright install chromium        # required once, for browser tools
python -m app.main                 # starts the text console loop
```

Or set up manually:

```bash
cp .env.example .env               # then edit LLM_API_KEY etc.
cp config/config.example.yaml config/config.yaml
```

`.env` holds secrets (API keys) — **never commit it**. `config/config.yaml`
holds non-secret settings (application paths, wake word text, timeouts).

### Try it

```
You: what time is it
🔊 Jarvis: It is 2:14 PM on Thursday, September 03.

You: open chrome
🔊 Jarvis: Opening Google Chrome.

You: search youtube for workout music
🔊 Jarvis: Searching YouTube for workout music.
```

Sensitive actions (permission level HIGH/CRITICAL — none are wired in V1
by default, but the mechanism is live for anything you add) pause for a
yes/no confirmation before running, and the LLM cannot skip that step.

## Testing

```bash
pytest                 # 32 tests: registry, permissions, confirmations,
                        # config, memory, orchestrator, application launching
```

External services (LLM, browser) are mocked/faked in tests — no network
or API key required to run the suite.

## Adding a tool

1. Subclass `app.tools.base.Tool`, set `name`, `description`,
   `permission_level`, `parameters`, and implement `async def execute()`.
2. Register it in `build_tool_registry()` in `app/main.py`.
3. That's it — the LLM sees it automatically via `registry.schemas()`,
   and the orchestrator enforces its permission level automatically.

```python
class MyTool(Tool):
    name = "my_tool"
    description = "What it does, for the LLM."
    permission_level = PermissionLevel.LOW
    parameters = [ToolParameter(name="query", type="string", description="...")]

    async def execute(self, arguments: dict) -> ToolResult:
        return ToolResult.ok(message="Done.")
```

## Permission levels

| Level | Examples | Confirmation required? |
|---|---|---|
| LOW | open app, search web, volume control | No |
| MEDIUM | read files, browser interactions | No |
| HIGH | send messages/emails, modify/delete files, shell commands | **Yes** |
| CRITICAL | financial transactions, password/account changes | **Yes** |

No general-purpose "run any shell command" tool exists, by design. If one
is ever added, it must ship with an allowlist, argument validation,
HIGH/CRITICAL permission, mandatory confirmation, and full logging.

## Roadmap

- [x] **Phase 1-4**: project structure, config, logging, LLM abstraction,
      orchestrator, tool registry, core tools (apps/files/system/browser/YouTube),
      permissions, confirmations, memory
- [ ] **Phase 5**: real microphone + local/offline speech-to-text
- [ ] **Phase 6**: wake word ("Hey Jarvis") using an on-device detector
      (no continuous audio ever leaves the device or reaches the LLM)
- [ ] **Phase 7**: system tray app (Listening/Processing/Speaking/Paused/Error)
- [ ] **Phase 8**: "Start with Windows" via the per-user Run registry key
- [ ] **Phase 9**: expanded confirmation UX (voice-based, not just console)
- [ ] **Phase 10**: PyInstaller packaging into a standalone `.exe`
      (`scripts/build.py` is scaffolded, untested on real Windows yet)

Future, larger phases (not started): screenshot/vision/OCR, computer-use
control, WhatsApp/Telegram/Discord/email integration, calendar/reminders,
scheduled autonomous workflows.

## Security notes

- Application launches use `subprocess.Popen([executable])` with a fixed
  argument list — never a shell string built from LLM output.
- File/folder tools resolve and validate paths before touching disk, and
  only open with the OS default handler (no read/write/delete tool exists
  in V1).
- Logs pass through a filter that redacts anything matching common
  `api_key=`, `token=`, `password=`, `Authorization: Bearer ...` patterns.
- `LongTermMemory` only ever writes what is explicitly passed to
  `remember()` — nothing is stored automatically from conversation.

## License

MIT — see [LICENSE](LICENSE).
