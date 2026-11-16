#!/usr/bin/env bash
# Run the release document on the demo node and wait for the result.
# Usage: release.sh deploy|rollback <commit-sha>
# Needs AWS credentials, NODE_INSTANCE_ID and RELEASE_DOCUMENT.
set -euo pipefail

ACTION="$1"
SHA="$2"

COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$NODE_INSTANCE_ID" \
  --document-name "$RELEASE_DOCUMENT" \
  --parameters "action=$ACTION,sha=$SHA" \
  --comment "lotse $ACTION $SHA" \
  --query Command.CommandId --output text)
echo "command $COMMAND_ID"

invocation() {
  aws ssm get-command-invocation --command-id "$COMMAND_ID" --instance-id "$NODE_INSTANCE_ID" \
    --query "$1" --output text
}

# `aws ssm wait command-executed` gives up after about 100 seconds; a first install takes longer.
STATUS=Pending
for _ in $(seq 1 150); do
  STATUS=$(invocation Status 2> /dev/null || echo Pending)
  case "$STATUS" in
    Pending | InProgress | Delayed) sleep 10 ;;
    *) break ;;
  esac
done

invocation StandardOutputContent | tail -n 40
if [ "$STATUS" != "Success" ]; then
  invocation StandardErrorContent | tail -n 40 >&2
  echo "release $ACTION ended with status $STATUS" >&2
  exit 1
fi
