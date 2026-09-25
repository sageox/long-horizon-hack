<!-- ox:prime-check -->
Run `ox agent prime` at session start to load SageOx team context — it's fine to read the user's request first.

# AI Agent Instructions

<!-- ox:prime --> Run SageOx `ox agent prime` on session start, after compaction, or clear. (DO NOT REMOVE)

<!-- ox:prime:pi:start -->
## SageOx Team Context

This project uses [SageOx](https://sageox.ai) for team context. Run the following command at the start of every session to load team knowledge:

```bash
ox agent prime
```

This provides architectural decisions, coding conventions, and session history from your team.
<!-- ox:prime:pi:end -->
