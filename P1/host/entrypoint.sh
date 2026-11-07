#!/bin/sh
# Applies the device config kept by GNS3 in /etc/network, if any. The image has
# no address by itself.
if [ -f /etc/network/startup.sh ]; then
	sh /etc/network/startup.sh
fi

# GNS3 plugs its console into this process. The shell comes back after `exit`,
# otherwise the device would stop.
while true; do
	sh
	sleep 1
done
