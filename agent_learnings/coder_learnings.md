# Coder Learnings

This file is updated by the Coder agent as it discovers patterns and gotchas while working in this codebase. Each entry documents a reusable lesson learned during implementation.

## Example Entry Format

```markdown
## [Date] - [Task Summary]
**Pattern:** [What you learned — the reusable technique or approach]
**Gotcha:** [Things to watch out for — subtle bugs, edge cases, or surprises]
```

---

## 2026-04-07 - Jira custom fields via additional_fields parameter
**Pattern:** When adding an optional catch-all dict parameter (`additional_fields: dict = None`) to a Jira tool, merge it into the `fields` dict _after_ all the named parameters with `fields.update(additional_fields)`. Placing the merge last ensures the caller can intentionally override any field set by a named param.
**Gotcha:** To discover what custom fields a Jira project requires, call `getIssue` on an existing ticket and examine the `fields` object. Custom field IDs are stable (e.g., `customfield_11700`) but value formats vary by field type: plain string, `{"value": "..."}` for select, `[{"value": "..."}]` for multi-select, `{"id": "..."}` for select-by-ID, `{"accountId": "..."}` for user fields.

## 2026-04-07 - Validating open-ended dict parameters
**Pattern:** When a tool exposes an escape-hatch dict parameter (e.g. `additional_fields`), restrict accepted keys with `re.fullmatch(r"customfield_\d+", key)` before merging into the payload. Extract the check into a small helper that returns `None` on success or an error response dict on failure.
**Gotcha:** Using `re.fullmatch` (not `re.match`) ensures the _entire_ key string matches the pattern, so `customfield_123_extra` is correctly rejected. Also validate `isinstance(additional_fields, dict)` first to give a clear error when the LLM accidentally passes a list or string.
