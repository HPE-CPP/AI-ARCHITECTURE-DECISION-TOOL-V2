# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# communication-style
- When asked "where" or "which file" questions, respond with exact file paths and line numbers, not just general descriptions. Confidence: 0.70

# git
- Use Conventional Commits format for commit messages (e.g., `feat:`, `fix:`, `chore:`, `refactor:`). Confidence: 0.70
- When asked for commit messages, provide ONLY the subject line heading — not the full body or bullet points. Confidence: 0.75
- When providing commit messages, include the full `git add <file>` and `git commit -m \"...\"` commands as a ready-to-run block. Confidence: 0.70
- Split logically distinct changes into separate commits rather than bundling unrelated file changes together. Confidence: 0.65
- When asked for separate commits, split by file — one commit per file even when files are part of the same logical change. Confidence: 0.70

# verification
- Proactively verify all changes work end-to-end after completing a task — don't wait to be asked. Include running lint (ruff) in the verification process. Confidence: 0.75

