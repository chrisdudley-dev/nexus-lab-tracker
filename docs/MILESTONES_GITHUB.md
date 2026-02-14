# Milestones (Source of Truth)

Project milestones are tracked in GitHub Issues → Milestones.
This repository does not maintain a parallel milestone ledger.

CLI:
- List milestones:
  gh api repos/chrisdudley-dev/nexus-lab-tracker/milestones --paginate \
    --jq '.[] | "\(.number)\t\(.state)\t\(.title)\t(open:\(.open_issues) closed:\(.closed_issues))"'

- List issues in a milestone:
  gh issue list -R chrisdudley-dev/nexus-lab-tracker --milestone <number> --state all --limit 200
