# BADASS

*Bgp At Doors of Autonomous Systems is Simple*: a 42 network administration
project. It simulates a small datacenter with GNS3 and Docker, in three parts.

| Part | What it builds |
|---|---|
| **P1** | Two Docker images used as GNS3 devices: a host and an FRRouting router |
| **P2** | Two hosts joined by VXLAN 10, in static mode, then in multicast mode |
| **P3** | BGP EVPN: 1 route reflector, 3 leafs (VTEPs), 3 hosts, with OSPF underneath |

**Preparing the defense?** Read **[EVALUATION.md](EVALUATION.md)**: everything
explained from zero, what to show, and the likely questions.

## Contents

```
P1/
  P1.gns3project    GNS3 project, as a ZIP
  _elakhfif-*       Commented config of each device
  host/             Source of the alpine-host image
  router/           Source of the alpine-router image
P2/                 Project, plus _s (static) and _g (multicast) router configs
P3/                 Project, plus the config of each device
tests/              GNS3 in Docker, the checks, and the script behind `make`
```

Each device file is also stored in the `.gns3project`, as
`/etc/network/startup.sh` of that device, and runs when the device starts. The
images hold no IP address: addresses only exist in these files. The P3 hosts are
the exception: they boot with no address, and their file is stored as
`/etc/network/_elakhfif-N_host`, to be run by hand.

## Quick start

You need Docker, `make`, `curl` and Python 3. GNS3 itself is optional here:
`make lab` runs a real GNS3 server inside a container.

```bash
make lab       # start GNS3 in Docker (about 5 minutes the first time)
make test      # start and check the three parts, about 3 minutes
make           # list every command
```

Each part ends with `all checks passed`. To work on one part:

```bash
make p3        # start it, stopping any other part
make test-p3   # check it
```

Open <http://localhost:13080/>, click the project, then right-click a device and
choose **Web console**. Starting a part rebuilds it from the files, so a change
in `P1/`, `P2/` or `P3/` is picked up. It also rewrites the `.gns3project`.

| Command | Effect |
|---|---|
| `make stop` | Stops the running part, removes nothing |
| `make lab-down` | Removes the GNS3 container |
| `make clean` | Removes the lab, our projects in GNS3, and the images |
| `make fclean` | Same as `clean`, plus the Docker build cache and Python caches |
| `make prune` | Same as `fclean`, plus every container, image and volume in Docker, even from other projects |

## With the GNS3 app

The subject asks to install GNS3 in a virtual machine. On Ubuntu, with Docker
installed:

```bash
sudo add-apt-repository ppa:gns3/ppa
sudo apt install gns3-gui gns3-server busybox-static
sudo usermod -aG ubridge,docker $USER     # then log out and back in
```

Build the two images. GNS3 does not store Docker images in a `.gns3project`, so
this is needed on every new machine:

```bash
docker build -t alpine-host P1/host
docker build -t alpine-router P1/router
```

To add them to GNS3 as devices, use **Edit > Preferences > Docker containers >
New > Existing image**, and pick `alpine-host:latest`, then `alpine-router:latest`.

Then in GNS3, use **File > Import portable project**, pick `P1/P1.gns3project`,
and press the green play button. Right-click a device for its **Console**, or a
cable for **Start capture**, which opens Wireshark. Run one part at a time.

The `make` commands also work with the app: open it, run `make lab-down`, then
`make p3`. To export a device you changed by hand, use **File > Export portable
project**.

## P1: images in GNS3

There is no address on purpose. On `routeur_elakhfif`:

```bash
ps                                 # zebra, bgpd, ospfd and isisd are running
vtysh -c "show running-config"     # bgp, ospf and isis are configured
```

## P2: VXLAN

|        Device        |                   Port                   |    Address    |
|----------------------|------------------------------------------|---------------|
| `routeur_elakhfif-1` | `eth0` to the switch, `eth1` to its host | `10.1.1.1/24` |
| `routeur_elakhfif-2` | `eth0` to the switch, `eth1` to its host | `10.1.1.2/24` |
| `host_elakhfif-1`    | `eth1`                                   | `30.1.1.1/24` |
| `host_elakhfif-2`    | `eth1`                                   | `30.1.1.2/24` |

The project starts in multicast mode. To switch mode, use `make p2-static` and
`make p2-group`, or run the matching file on each router. `_s` is static, `_g`
is multicast:

```bash
sh /etc/network/_elakhfif-1_s     # on routeur_elakhfif-1
sh /etc/network/_elakhfif-2_s     # on routeur_elakhfif-2
```

Check the tunnel. Listen on a router, then ping from a host:

```bash
# routeur_elakhfif-1
ip -d link show vxlan10                 # vxlan id 10, with group or remote
tcpdump -nn -l -i eth0 udp port 4789

# host_elakhfif-1
ip neigh flush all
ping -c 2 30.1.1.2

# routeur_elakhfif-1, once traffic has passed
brctl showmacs br0                      # "no" under "is local?": learned
```

In multicast mode the first ARP request goes to the group `239.1.1.1`. In static
mode it goes straight to the other router. In both modes the replies and the ICMP
packets go directly between `10.1.1.1` and `10.1.1.2`, inside `VXLAN, vni 10`.

## P3: BGP EVPN

|    Device     |     Role        |                Ports                 | Loopback  |             Host side                   |
|---------------|-----------------|--------------------------------------|-----------|-----------------------------------------|
| `_elakhfif-1` | Route reflector | `eth0`, `eth1`, `eth2` to the leafs  | `1.1.1.1` |                                         |
| `_elakhfif-2` | Leaf            | `eth0` to the RR, `eth1` to its host | `1.1.1.2` | `host_elakhfif-1`, `20.1.1.1` on `eth1` |
| `_elakhfif-3` | Leaf            | `eth1` to the RR, `eth0` to its host | `1.1.1.3` | `host_elakhfif-2`, `20.1.1.2` on `eth0` |
| `_elakhfif-4` | Leaf            | `eth2` to the RR, `eth0` to its host | `1.1.1.4` | `host_elakhfif-3`, `20.1.1.3` on `eth0` |

Links use `10.1.1.0/30`, `10.1.1.4/30` and `10.1.1.8/30`. All routers are in AS 1.
The leafs only know the RR, and the RR accepts any peer in `1.1.1.0/29`, so its
sessions are dynamic: it shows them with a `*` in `show bgp l2vpn evpn summary`.

OSPF and BGP need about a minute to settle after starting. On a leaf:

|            Command                |                   Expected                         |
|-----------------------------------|----------------------------------------------------|
| `vtysh -c "show ip route"`        | `O` routes to the three other loopbacks            |
| `vtysh -c "show bgp summary"`     | One neighbour, `1.1.1.1`                           |
| `vtysh -c "show bgp l2vpn evpn"`  | `[3]`: one route per leaf. `[2]`: one per host MAC |
| `vtysh -c "show evpn mac vni 10"` | Each MAC, `local` or `remote` with its leaf        |

The hosts boot with no IP address, as the evaluation requires. A type 2 route
is about a MAC, so it still appears: the IPv6 messages a host sends at startup
are enough for the bridge to learn it. After about 5 minutes of silence, the
bridge forgets the MAC and the route goes away, leaving the type 3 routes.

Give the hosts their addresses, with `make p3-hosts`, or on each host:

```bash
sh /etc/network/_elakhfif-1_host     # on host_elakhfif-1, and so on
```

Check the path with a ping:

```bash
# _elakhfif-2
tcpdump -nn -l -i eth0 udp port 4789

# host_elakhfif-1
ping -c 2 20.1.1.3
```

The ICMP packets travel between `1.1.1.2` and `1.1.1.4`, inside `VXLAN, vni 10`.
Use `tcpdump -nn -l -i eth0 proto ospf` to see OSPF.
