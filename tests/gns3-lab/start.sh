#!/bin/sh
# Starts the private Docker daemon, then the GNS3 server on port 3080.
dockerd --storage-driver=vfs --iptables=false --ip6tables=false --bridge=none \
    >/var/log/dockerd.log 2>&1 &

until docker info >/dev/null 2>&1; do sleep 1; done

exec gns3server --local --host 0.0.0.0 --port 3080
