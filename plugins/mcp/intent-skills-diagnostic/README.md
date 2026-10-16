# Intent Skills Diagnostic

A hosted MCP app from Intent Solutions. It asks a few questions about how you use Claude or Codex, then recommends at most two plugins from a reviewed list of Tons of Skills plugins and Intent Solutions offerings, each with the install route for the tool you use.

## What it does

- Asks only what it still needs: where you use AI, what you use it for, how far your setup goes, what you keep explaining to the AI, and where it goes wrong. It asks what you build only for software work, and never when it can read the project instead.
- On Claude Code or Codex, it can list the names of installed skills and plugins (names only, never config contents) so it does not recommend what you already have.
- Returns one of four results: a fitting match, more information needed, no verified match, or no new tool needed. It never invents a pick.
- Every pick shows why it fits, how to install it in your tool, its source page and the date it was checked.
- An optional link to Intent Solutions, shown only when you ask for more help. Nothing is booked or submitted.

All five tools are read-only. Nothing is stored, sent or installed for you.

## Install

Claude Code:

```
/plugin marketplace add jeremylongshore/claude-code-plugins
/plugin install intent-skills-diagnostic@claude-code-plugins-plus
```

claude.ai, Claude Desktop or Cowork: add it as a custom connector (Settings, Connectors, Add custom connector) with this URL:

```
https://intent-skills-diagnostic.max-sheahan.workers.dev/mcp
```

The connector has no sign-in. If the dialog says it could not check how the server signs in, choose Continue anyway, then no authentication.

## Try it

- "What skills should I add to Claude Code?"
- "I keep telling Claude how to write our commit messages. Is there a skill for that?"
- "I teach middle school and use claude.ai for lesson plans. What would help?"

## Tools

| Tool | Returns |
|---|---|
| `start_here` | Welcome card with examples |
| `scan_setup` | What to list on Claude Code or Codex (names only) |
| `ask_questions` | The questions still open, on a card |
| `recommend_skills` | Up to two reviewed picks with install routes |
| `talk_to_intent` | A link to intentsolutions.io/contact |

## Verification (2026-10-15)

- End-to-end smoke suite: 34 checks against the live endpoint, four consecutive clean runs.
- Browser QA of every card state at 375 px and desktop width, light and dark.
- Security: secure-launch 0.3.0, 0 FAIL, 0 UNKNOWN, 24 PASS; security headers on every path.
- Install routes: Claude Code and Codex installs verified in throwaway homes; claude.ai, Desktop and Cowork routes from Anthropic's documentation.
