#!/usr/bin/env python3
"""Checks the minimum the subject asks of a running part.

Usage: test_gns3.py P1|P2|P3 (start the part first, with `make p1` for example).
"""
import sys
import time

sys.dont_write_bytecode = True
import badass  # noqa: E402
from badass import LOGIN as L, find_project, nodes_of, run_on  # noqa: E402

failed = 0
EVPN = 'vtysh -c "show bgp l2vpn evpn"'


def check(text, test, wait=0):
    """Prints the result of test(). Networks settle slowly: retry for wait seconds."""
    global failed
    deadline = time.time() + wait
    while not (ok := test()) and time.time() < deadline:
        time.sleep(2)
    print(f"  [{'OK' if ok else 'FAIL'}] {text}")
    failed += not ok


def output(part, device, command):
    return run_on(part, device, command, check=False)


def ping(part, host, ip):
    return " 0% packet loss" in output(part, host, f"ping -c 2 -W 2 {ip}")


def test_p1():
    host, router = f"host_{L}-1", f"routeur_{L}"
    processes = output("P1", router, "ps")
    for daemon in ("zebra", "bgpd", "ospfd", "isisd"):
        check(f"{daemon} runs", lambda: daemon in processes)
    for name in (host, router):
        check(f"{name} has no IP address", lambda: not output(
            "P1", name, "ip -4 -o addr | grep -v ' lo '").strip())


def test_p2():
    router, host = f"routeur_{L}-1", f"host_{L}-1"
    for mode, word in (("static", "remote 10.1.1.2"), ("group", "group 239.1.1.1")):
        badass.switch_mode(mode)
        check(f"vxlan10 has VNI 10 and {word}", lambda: all(
            text in output("P2", router, "ip -d link show vxlan10")
            for text in ("vxlan id 10", word, "master br0")))
        check("host-1 reaches host-2", lambda: ping("P2", host, "30.1.1.2"), 30)


def test_p3():
    rr, leaf, host = f"_{L}-1", f"_{L}-2", f"host_{L}-1"
    check("the RR has 3 OSPF neighbours in Full", lambda: output(
        "P3", rr, 'vtysh -c "show ip ospf neighbor"').count("Full") == 3, 90)
    check("type 3 routes of the 3 leafs", lambda: all(
        f"[3]:[0]:[32]:[1.1.1.{i}]" in output("P3", leaf, EVPN) for i in (2, 3, 4)), 90)
    hosts = [f"host_{L}-{i}" for i in (1, 2, 3)]
    check("the hosts boot without an IP address", lambda: not any(
        output("P3", name, "ip -4 -o addr | grep -v ' lo '").strip() for name in hosts))
    macs = [output("P3", f"host_{L}-{i}", f"cat /sys/class/net/{eth}/address").strip()
            for i, eth in ((1, "eth1"), (2, "eth0"), (3, "eth0"))]
    check("type 2 routes of the 3 hosts, learned without any IP", lambda: all(
        f"[2]:[0]:[48]:[{mac}]" in output("P3", leaf, EVPN) for mac in macs), 30)
    badass.configure_hosts()
    for ip in ("20.1.1.2", "20.1.1.3"):
        check(f"host-1 reaches {ip}", lambda: ping("P3", host, ip), 30)


def main():
    tests = {"P1": test_p1, "P2": test_p2, "P3": test_p3}
    part = sys.argv[1].upper() if len(sys.argv) > 1 else ""
    if part not in tests:
        sys.exit(__doc__)
    print(f"== {part} ==")
    project = find_project(part)
    if not project:
        sys.exit(f"{part} is not in GNS3, run `make {part.lower()}` first.")
    devices = nodes_of(project)
    check("every device is started", lambda: all(n["status"] == "started" for n in devices))
    check("every device name holds the login", lambda: all(L in n["name"] for n in devices))
    tests[part]()
    print(f"{part}: {f'{failed} FAILED' if failed else 'all checks passed'}")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
