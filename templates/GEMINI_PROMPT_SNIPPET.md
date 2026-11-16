# Quick Reference: Triggering & Automating `SESSION-BUNDLE-v3` Uploads

Full protocol: [`templates/SESSION_UPLOAD_INSTRUCTIONS.md`](SESSION_UPLOAD_INSTRUCTIONS.md)  
Canonical template: [`templates/SESSION_CLOSEOUT_TEMPLATE.md`](SESSION_CLOSEOUT_TEMPLATE.md)

## 1. Global Instruction Snippet (Saved in Gemini `/u/0/saved-info`, `GEMINI.md` & `AGENTS.md`)

```text
Session full-work upload rule (SESSION-BUNDLE-v3): Whenever substantive work occurs in a session (or when asked to close out / upload), follow templates/SESSION_UPLOAD_INSTRUCTIONS.md and populate templates/SESSION_CLOSEOUT_TEMPLATE.md from harmonic-ops-machine/lifeops-enclave-private (mirrored in harmonic-ops-machine/lifeops-multi-agent-sim). Upload all deliverables under products/ with clickable links and live availability status, specify the exact host/OS/model/workspace environment, list every skill, plugin, MCP tool, and hook used, and document exact accounts, OAuth scopes, and non-secret credential identifiers per app while scrubbing all Tier-A secrets (passwords, tokens, keys, cookies, verification codes).
```

## 2. One-Line Trigger Phrases (Voice or Text)

- **English:** `"Upload this entire session and its products using the SESSION-BUNDLE-v3 instructions."`
- **Polish:** `"Wyślij całą pracę z tej sesji wraz z produktami zgodnie z instrukcją SESSION-BUNDLE-v3."`
