FROM		alpine:3.21

RUN			apk add --no-cache frr tini iproute2 tcpdump && \
	sed -i -e 's/bgpd=no/bgpd=yes/' -e 's/ospfd=no/ospfd=yes/' \
	-e 's/isisd=no/isisd=yes/' /etc/frr/daemons

COPY		entrypoint.sh /usr/local/bin/entrypoint.sh
COPY		--chown=frr:frr frr.conf /etc/frr/frr.conf

ENTRYPOINT	[ "/sbin/tini", "--" ]
CMD			[ "/usr/local/bin/entrypoint.sh" ]
