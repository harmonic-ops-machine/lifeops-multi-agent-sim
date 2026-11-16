# How Each Session Uses `SESSION_CLOSEOUT_TEMPLATE.md`

## 1. Global Instruction Snippet (for Gemini `/u/0/saved-info`, `GEMINI.md`, and `AGENTS.md`)

```text
At the conclusion of any session where substantive work, analysis, or configuration took place (or whenever asked to close out / export a session), fill out the canonical template at `templates/SESSION_CLOSEOUT_TEMPLATE.md` from `harmonic-ops-machine/lifeops-enclave-private` (also mirrored in `harmonic-ops-machine/lifeops-multi-agent-sim`), including honest Section 3 entries for any errors, misheard voice inputs, or user corrections so the Separate Refinery Auditor can prune noise and extract root-cause fixes.
```

## 2. Quick Trigger Phrase (Voice or Text in Any Session)

- **English:** `"Fill out the GitHub session closeout template for this session."`
- **Polish:** `"Wypełnij szablon zamknięcia sesji z GitHuba dla tej rozmowy."`

## 3. Downstream Refinery Mapping (`inbox/raw-sessions` → `main`)

| Template Section | Auditor Action | Output Target on `main` |
| :--- | :--- | :--- |
| **YAML Frontmatter + Section 1 + Section 5** | Retains clean verified state & open handoff items | `distilled/<YYYY-MM-DD>_<session_id>.md` |
| **Section 2 (Dead Ends)** | Strips verbose retry chatter; keeps 1-line anti-pattern note if reusable | Pruned from active prompt context |
| **Section 3 (Errors & Corrections Table)** | Converts rows into validated `SESSION-RCA-v1` JSON records | `postmortems/<session_id>_rca.json` |
| **Section 4 (Proposed Patches)** | Formats concrete diff / guardrail proposal in Pull Request | `patches/<session_id>_patch.md` |
