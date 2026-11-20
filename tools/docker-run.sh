#!/usr/bin/env bash
# Linux Docker launcher: forward host addresses without giving containers host access.
set -euo pipefail

if [[ $# -eq 0 ]]; then
  echo 'Usage: bash tools/docker-run.sh [docker run options] IMAGE [COMMAND...]' >&2
  exit 2
fi

# hostname -I reads assigned interfaces; it does not contact an external IP service.
host_addresses=$(hostname -I)
read -r -a host_ips <<< "$host_addresses"
if [[ ${#host_ips[@]} -eq 0 ]]; then
  echo 'Could not detect host addresses; container was not started.' >&2
  exit 1
fi
joined_ips=$(IFS=,; echo "${host_ips[*]}")
extra_ips=${LNBITS_OUTBOUND_HOST_IPS:-}
if [[ -n $extra_ips && $extra_ips != "[]" ]]; then
  joined_ips="$joined_ips,$extra_ips"
fi
exec docker run --env "LNBITS_OUTBOUND_HOST_IPS=$joined_ips" "$@"
