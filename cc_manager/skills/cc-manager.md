# cc-manager

cc-manager is installed and managing your Claude Code ecosystem.

## Quick commands
- `ccm status` — see all installed tools and hook status
- `ccm doctor` — run health check
- `ccm analyze` — see token/cost analytics
- `ccm recommend` — get personalized tool suggestions
- `ccm dashboard` — open visual dashboard at localhost:9847

## During this session
cc-manager hooks are active and collecting session data (tokens, tool usage, cost).
Run `ccm logs` after the session to see what was captured.

## Tool management
Install new tools: `ccm install <tool>`
Browse registry: `ccm list --available`
Search: `ccm search <query>`
