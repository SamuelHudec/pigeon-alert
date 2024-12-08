#!/bin/bash
# debug
echo "Script started at $(date)" >> /tmp/debug_log.log
env > /tmp/cron_env.log

# Use the first argument as the timeout, default to 3590 if not provided
TIMEOUT=${1:-3590}
LOCKFILE="/job_run.lock"

# Check if the lock file exists
if [ -e "$LOCKFILE" ]; then
    echo "Script is already running." >> /tmp/debug_log.log
    exit 1
fi

# Create the lock file
trap "rm -f $LOCKFILE" EXIT
touch $LOCKFILE

source setup_env.sh
python src/detection.py -i rpi -t $TIMEOUT --display-off
