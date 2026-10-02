#!/usr/bin/env bash
# NEVERMIND session keeper — stays alive for the whole session so the preview
# port stays registered. If nobody serves 8317, it starts the server itself.
cd /home/user/nevermind || exit 1
echo "[keeper] online — watching 8317"
while true; do
  if timeout 0.5 bash -c '</dev/tcp/127.0.0.1/8317' 2>/dev/null; then
    sleep 4
  else
    echo "[$(date '+%F %T')] [keeper] port free → starting server"
    /usr/local/bin/python3 run.py >> data/keeper.log 2>&1
    sleep 1
  fi
done
