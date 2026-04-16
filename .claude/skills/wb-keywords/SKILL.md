---
name: wb-keywords
description: Weekly keyword lifecycle management. Identifies high-performing keywords to protect, underperforming ones to block, and blocked ones ready for re-test. Updates keyword_rules.json and applies cluster minus lists.
triggers:
  - "keyword review"
  - "manage keywords"
  - "block keywords"
  - "keyword performance"
  - "cluster review"
---

# wb-keywords

Weekly keyword lifecycle management. Reads cluster analytics, joins against `~/.wb-cli/keyword_rules.json` lifecycle state, and applies changes via cluster minus-list commands.

## Input

`campaign_id` and `nm_id` — the campaign and product to review.

## Steps

### 1. Run keyword analysis script

```bash
.venv/Scripts/python .claude/skills/wb-keywords/scripts/wb_keywords.py \
  --campaign <campaign_id> \
  --nm <nm_id> \
  --days 14
```

The script calls wb cluster commands sequentially (respects rate limits), reads `~/.wb-cli/keyword_rules.json`, and outputs a ranked keyword report.

**If `~/.wb-cli/keyword_rules.json` does not exist**: the script creates it from the template.

### 2. Review output

```json
{
  "data_as_of": "2026-04-17T10:00:00+00:00",
  "hot": [{"query": "платье летнее", "ctr": 4.2, "orders": 8}],
  "underperforming": [{"query": "сарафан", "ctr": 0.3, "spend_rub": 120.0, "suggestion": "block"}],
  "blocked": [{"query": "юбка", "blocked_since": "2026-04-03", "restore_after_days": 14, "ready": true}],
  "ready_to_restore": [{"query": "юбка", "blocked_days": 15}]
}
```

### 3. Handle large keyword sets (>10 underperforming)

Spawn a subagent to rank: "Rank these keywords by cost-efficiency and suggest top 3 to block: `<list>`". Apply only the top 3 to avoid over-blocking.

### 4. Block underperforming keywords

```bash
wb cluster minus set \
  --campaign <campaign_id> \
  --nm <nm_id> \
  --phrases "keyword1,keyword2,keyword3" \
  --yes
```

Update `keyword_rules.json` status to `blocked` with today's date and reason.

### 5. Restore ready keywords

```bash
wb cluster minus clear \
  --campaign <campaign_id> \
  --nm <nm_id> \
  --phrases "keyword_to_restore" \
  --yes
```

Update `keyword_rules.json` status to `re_test`.

### 6. Output

```json
{
  "campaign_id": 123,
  "nm_id": 789,
  "blocked": ["сарафан", "юбка длинная"],
  "restored": ["юбка"],
  "hot_keywords": ["платье летнее", "платье миди"],
  "next_review_days": 7
}
```

## Notes

- Review cadence: weekly. More frequent reviews risk over-blocking keywords that need time to accumulate data.
- `hot` keywords should **not** be blocked even if CTR dips temporarily — protect them.
- After blocking, run `wb-pulse` to confirm campaign is still running (minus list changes take effect immediately).
