#!/usr/bin/env bash
# Idempotent GitHub Multi-Agent Governance Bootstrap (Zero-PII)
# Run from an authenticated admin shell (HIGHRES-enclave SSH/gh or Project-attached session).
set -euo pipefail

REPO="${1:-harmonic-ops-machine/lifeops-multi-agent-sim}"

echo "[1/3] Configuring linear squash-merge, auto-merge, branch cleanup & Discussions on $REPO..."
gh api -X PATCH "repos/$REPO" \
  -F allow_squash_merge=true \
  -F allow_merge_commit=false \
  -F allow_rebase_merge=false \
  -F allow_auto_merge=true \
  -F delete_branch_on_merge=true \
  -F allow_update_branch=true \
  -F has_discussions=true \
  -F has_wiki=false >/dev/null

echo "[2/3] Provisioning atomic multi-agent state-machine labels..."
declare -A LABELS=(
  ["state:ready"]="0E8A16|Unclaimed task ready for agent pickup"
  ["state:claimed"]="FBCA04|Leased by an active agent worker"
  ["state:blocked"]="D93F0B|Blocked on operator gate or upstream dependency"
  ["state:review"]="1D76DB|Pull request open and awaiting verification"
  ["actor:claude-local"]="5319E7|Assigned to local Claude Code executor"
  ["actor:agy-cloud"]="0052CC|Assigned to Antigravity Cloud VM worker"
  ["actor:carbon-audit"]="006B75|Assigned to Gemini Carbon auditor"
  ["prio:p0"]="B60205|Critical-path execution item"
  ["prio:p1"]="D93F0B|High-priority sprint item"
  ["gate:enclave"]="333333|Touches security boundary, CI gate, or schema contract"
)

for name in "${!LABELS[@]}"; do
  IFS='|' read -r color desc <<< "${LABELS[$name]}"
  gh label create "$name" -R "$REPO" --color "$color" --description "$desc" --force >/dev/null
done

echo "[3/3] Applying main-branch Zero-PII & linear-history Repository Ruleset..."
EXISTING_ID=$(gh api "repos/$REPO/rulesets" --jq '.[] | select(.name=="main-zero-pii-and-linear-history") | .id' || true)
if [[ -n "${EXISTING_ID:-}" ]]; then
  echo "Ruleset already active (id=$EXISTING_ID); skipping duplicate creation."
else
  gh api -X POST "repos/$REPO/rulesets" --input - <<'JSON' >/dev/null
{
  "name": "main-zero-pii-and-linear-history",
  "target": "branch",
  "enforcement": "active",
  "conditions": {
    "ref_name": {
      "include": ["~DEFAULT_BRANCH"],
      "exclude": []
    }
  },
  "rules": [
    { "type": "deletion" },
    { "type": "non_fast_forward" },
    { "type": "required_linear_history" },
    {
      "type": "pull_request",
      "parameters": {
        "dismiss_stale_reviews_on_push": true,
        "require_code_owner_review": false,
        "require_last_push_approval": false,
        "required_approving_review_count": 0,
        "required_review_thread_resolution": true
      }
    },
    {
      "type": "required_status_checks",
      "parameters": {
        "strict_required_status_checks_policy": true,
        "required_status_checks": [
          { "context": "verify-zero-pii" }
        ]
      }
    }
  ]
}
JSON
fi

echo "Done: $REPO hardened for multi-agent orchestration."
