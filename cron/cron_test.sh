#!/bin/bash

# This script is used to test that cron is working.
# It writes the current date and time to a cron_status.txt file.

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Cron running at: $(date)" > "$DIR/cron_status.txt"
