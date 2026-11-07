# A real GNS3 server in a box, started by `make lab`.
#
# Why it exists: it lets us check the .gns3project files against the
# real GNS3 software, on any machine, without installing GNS3 and without sudo.
# It runs its own private Docker daemon, because GNS3 starts one container per
# device and joins them with uBridge. dynamips powers the built-in Ethernet switch.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
        busybox-static ca-certificates cmake curl docker.io g++ gcc git iproute2 iptables libc6-dev \
        libelf-dev libpcap-dev make python3 python3-pip python3-dev tcpdump \
    && git clone --depth 1 https://github.com/GNS3/ubridge.git /tmp/ubridge \
    && make -C /tmp/ubridge \
    && cp /tmp/ubridge/ubridge /usr/local/bin/ \
    && rm -rf /tmp/ubridge \
    && git clone --depth 1 https://github.com/GNS3/dynamips.git /tmp/dynamips \
    && cmake -S /tmp/dynamips -B /tmp/dynamips/build -DDYNAMIPS_CODE=stable \
    && make -C /tmp/dynamips/build install \
    && rm -rf /tmp/dynamips \
    && pip3 install --no-cache-dir gns3-server==2.2.61

COPY start.sh /start.sh
ENTRYPOINT ["/bin/sh", "/start.sh"]
