#!/bin/sh
set -e

/usr/lib/frr/frrinit.sh start

# Daemons take a moment to accept commands.
until vtysh -c "show version" >/dev/null 2>&1; do sleep 1; done

# GNS3 keeps each device's /etc/network inside the project, so this file travels
# with the .gns3project while the image itself stays free of any address.
if [ -f /etc/network/startup.sh ]; then
	sh /etc/network/startup.sh || echo "/etc/network/startup.sh failed."
fi

# GNS3 plugs its console into this process. The shell comes back after `exit`,
# otherwise the device would stop.
while true; do
	sh
	sleep 1
done
