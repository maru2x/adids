#!/bin/sh
set -eu

ssh-keygen -A >/dev/null 2>&1
exec /usr/sbin/sshd -D -e -f /etc/ssh/sshd_config
