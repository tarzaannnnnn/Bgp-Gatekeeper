#!/usr/bin/env python3
"""Drives the P1, P2 and P3 labs in GNS3, for `make` and the tests.

    build P1|P2|P3    write P?/P?.gns3project from the files in that folder
    up P1|P2|P3       import that project in GNS3 and start every device
    down P1|P2|P3     stop the devices and close the project
    mode static|group switch P2 between static and multicast VXLAN
    hosts             give the P3 hosts their IP address (they boot without one)
    status            list the projects and devices known to GNS3
    clean             remove our projects from GNS3

Only the Python standard library is used. GNS3 is found automatically: the
server from `make lab` if it runs, otherwise the GNS3 app on this machine.
"""
import base64
import configparser
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOGIN = "elakhfif"
HOST_IMAGE = "alpine-host:latest"
ROUTER_IMAGE = "alpine-router:latest"
# Devices of the same kind share these settings.
SETTINGS = {
    HOST_IMAGE: {"adapters": 2, "symbol": ":/symbols/docker_guest.svg"},
    ROUTER_IMAGE: {"adapters": 4, "symbol": ":/symbols/multilayer_switch.svg"},
}
LAB = "badass-gns3-lab"
LAB_URL = "http://localhost:13080"
NAMESPACE = uuid.UUID("0b4d4a55-6241-4453-9053-000000000042")
GNS3_FORMAT = {"revision": 9, "version": "2.2.61"}
SETTLE = 15  # seconds a started device needs to apply its startup file


def node(name, image, x, y, startup=None, extra=()):
    """Describes one device. startup is its file in P?/, run when it boots.
    extra files are copied to /etc/network, to be run by hand."""
    return {"name": name, "image": image, "x": x, "y": y,
            "startup": startup, "extra": list(extra)}


def switch(name, x, y):
    return {"name": name, "image": None, "x": x, "y": y, "startup": None, "extra": []}


H, R = HOST_IMAGE, ROUTER_IMAGE
L = LOGIN
TOPOLOGIES = {
    "P1": {
        "nodes": [
            node(f"host_{L}-1", H, -150, 0, f"_{L}-1_host"),
            node(f"routeur_{L}", R, 100, 0, f"_{L}-2"),
        ],
        "links": [],
    },
    "P2": {
        "nodes": [
            switch(f"Switch_{L}", 0, -200),
            node(f"routeur_{L}-1", R, -150, -50, f"_{L}-1_g", [f"_{L}-1_s", f"_{L}-1_g"]),
            node(f"routeur_{L}-2", R, 150, -50, f"_{L}-2_g", [f"_{L}-2_s", f"_{L}-2_g"]),
            node(f"host_{L}-1", H, -250, 150, f"_{L}-1_host"),
            node(f"host_{L}-2", H, 250, 150, f"_{L}-2_host"),
        ],
        # (device, port), (device, port), as drawn in the subject.
        "links": [
            ((f"routeur_{L}-1", 0), (f"Switch_{L}", 0)),
            ((f"routeur_{L}-2", 0), (f"Switch_{L}", 1)),
            ((f"routeur_{L}-1", 1), (f"host_{L}-1", 1)),
            ((f"routeur_{L}-2", 1), (f"host_{L}-2", 1)),
        ],
    },
    "P3": {
        "nodes": [
            node(f"_{L}-1", R, 0, -200, f"_{L}-1"),
            node(f"_{L}-2", R, -250, 0, f"_{L}-2"),
            node(f"_{L}-3", R, 0, 0, f"_{L}-3"),
            node(f"_{L}-4", R, 250, 0, f"_{L}-4"),
            node(f"host_{L}-1", H, -250, 200, extra=[f"_{L}-1_host"]),
            node(f"host_{L}-2", H, 0, 200, extra=[f"_{L}-2_host"]),
            node(f"host_{L}-3", H, 250, 200, extra=[f"_{L}-3_host"]),
        ],
        "links": [
            ((f"_{L}-1", 0), (f"_{L}-2", 0)),
            ((f"_{L}-1", 1), (f"_{L}-3", 1)),
            ((f"_{L}-1", 2), (f"_{L}-4", 2)),
            ((f"_{L}-2", 1), (f"host_{L}-1", 1)),
            ((f"_{L}-3", 0), (f"host_{L}-2", 0)),
            ((f"_{L}-4", 0), (f"host_{L}-3", 0)),
        ],
    },
}


# ---------------------------------------------------------------- the zip file

def stable_id(*parts):
    """Same input, same id: rebuilding a project gives the same file."""
    return str(uuid.uuid5(NAMESPACE, "/".join(parts)))


def docker_node(part, spec):
    settings = SETTINGS[spec["image"]]
    return {
        "compute_id": "local",
        "console": None,
        "console_auto_start": False,
        "console_type": "telnet",
        "custom_adapters": [],
        "first_port_name": None,
        "height": 59,
        "label": label(spec["name"]),
        "locked": False,
        "name": spec["name"],
        "node_id": stable_id(part, spec["name"]),
        "node_type": "docker",
        "port_name_format": "eth{0}",
        "port_segment_size": 0,
        "properties": {
            "adapters": settings["adapters"],
            "aux": None,
            "console_http_path": "/",
            "console_http_port": 80,
            "console_resolution": "1024x768",
            "environment": None,
            "extra_hosts": None,
            "extra_volumes": [],
            "image": spec["image"],
            "mac_address": None,
            "start_command": None,
            "usage": "Build the images first, see the README.",
        },
        "symbol": settings["symbol"],
        "template_id": stable_id("template", spec["image"]),
        "width": 65,
        "x": spec["x"],
        "y": spec["y"],
        "z": 1,
    }


def switch_node(part, spec):
    ports = [{"name": f"Ethernet{i}", "port_number": i, "type": "access", "vlan": 1}
             for i in range(8)]
    return {
        "compute_id": "local",
        "console": None,
        "console_auto_start": False,
        "console_type": "none",
        "custom_adapters": [],
        "first_port_name": None,
        "height": 32,
        "label": label(spec["name"]),
        "locked": False,
        "name": spec["name"],
        "node_id": stable_id(part, spec["name"]),
        "node_type": "ethernet_switch",
        "port_name_format": "Ethernet{0}",
        "port_segment_size": 0,
        "properties": {"ports_mapping": ports},
        "symbol": ":/symbols/ethernet_switch.svg",
        "width": 72,
        "x": spec["x"],
        "y": spec["y"],
        "z": 1,
    }


def label(text):
    return {"rotation": 0, "style": "font-weight: bold;", "text": text,
            "x": None, "y": -25}


def project_json(part):
    topology = TOPOLOGIES[part]
    nodes = [docker_node(part, n) if n["image"] else switch_node(part, n)
             for n in topology["nodes"]]
    ids = {n["name"]: n["node_id"] for n in nodes}
    links = []
    for side_a, side_b in topology["links"]:
        ends = []
        for name, port in (side_a, side_b):
            is_switch = name.startswith("Switch_")
            ends.append({"adapter_number": 0 if is_switch else port,
                         "node_id": ids[name],
                         "port_number": port if is_switch else 0})
        links.append({"filters": {}, "link_id": stable_id(part, str(side_a), str(side_b)),
                      "link_style": {}, "nodes": ends, "suspend": False})
    return {
        "auto_close": True,
        "auto_open": False,
        "auto_start": False,
        "drawing_grid_size": 25,
        "grid_size": 75,
        "name": part,
        "project_id": stable_id(part),
        "revision": GNS3_FORMAT["revision"],
        "scene_height": 1000,
        "scene_width": 2000,
        "show_grid": False,
        "show_interface_labels": True,
        "show_layers": False,
        "snap_to_grid": False,
        "supplier": None,
        "topology": {"computes": [], "drawings": [], "links": links, "nodes": nodes},
        "type": "topology",
        "variables": None,
        "version": GNS3_FORMAT["version"],
        "zoom": 100,
    }


def add_file(archive, name, data):
    entry = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o755 << 16
    archive.writestr(entry, data)


def project_file(part):
    return ROOT / part / f"{part}.gns3project"


def build_project(part):
    """Writes P?/P?.gns3project: a zip with the topology and the device files."""
    path = project_file(part)
    with zipfile.ZipFile(path, "w") as archive:
        add_file(archive, "project.gns3", json.dumps(project_json(part), indent=4, sort_keys=True))
        for spec in TOPOLOGIES[part]["nodes"]:
            if not spec["image"]:
                continue
            folder = f"project-files/docker/{stable_id(part, spec['name'])}/etc/network"
            # GNS3 looks for this file to know the folder is already initialised.
            add_file(archive, f"{folder}/.gns3_perms", "")
            add_file(archive, f"{folder}/interfaces", "# Addresses are set by startup.sh\n")
            if spec["startup"]:
                add_file(archive, f"{folder}/startup.sh",
                         (ROOT / part / spec["startup"]).read_bytes())
            for extra in spec["extra"]:
                add_file(archive, f"{folder}/{extra}", (ROOT / part / extra).read_bytes())
    return path


# ---------------------------------------------------------------- talking to GNS3

def lab_running():
    result = subprocess.run(["docker", "ps", "-q", "--filter", f"name=^{LAB}$"],
                            capture_output=True, text=True)
    return bool(result.stdout.strip())


def docker_command():
    """In the test lab, devices run in the lab's own Docker daemon."""
    return ["docker", "exec", "-i", LAB, "docker"] if lab_running() else ["docker"]


def server():
    """Finds the URL and login. The GNS3 app generates a password in its config."""
    if lab_running():
        return LAB_URL, None
    url, auth = "http://localhost:3080", None
    for path in sorted(Path.home().glob(".config/GNS3/*/gns3_server.conf")):
        config = configparser.ConfigParser(interpolation=None)
        config.read(path)
        if not config.has_section("Server"):
            continue
        section = config["Server"]
        url = f"http://localhost:{section.get('port', '3080')}"
        auth = None
        if section.getboolean("auth", fallback=False):
            auth = f"{section.get('user', '')}:{section.get('password', '')}"
    return url, auth


def api(method, path, data=None, raw=False, timeout=120):
    url, auth = server()
    body = data if isinstance(data, bytes) else None
    if data is not None and body is None:
        body = json.dumps(data).encode()
    request = urllib.request.Request(f"{url}/v2{path}", data=body, method=method)
    if auth:
        token = base64.b64encode(auth.encode()).decode()
        request.add_header("Authorization", f"Basic {token}")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            content = answer.read()
    except urllib.error.HTTPError as error:
        sys.exit(f"GNS3 refused {method} {path}: {error.code} {error.read().decode()[:1500]}")
    except OSError as error:
        sys.exit(f"Cannot reach GNS3 at {url} ({error}).\n"
                 "Run `make lab`, or open the GNS3 application.")
    if raw:
        return content
    return json.loads(content) if content else None


def require_gns3():
    version = api("GET", "/version")["version"]
    if not version.startswith("2."):
        sys.exit(f"GNS3 {version} found, this tool speaks the 2.x API.")
    return version


def find_project(part):
    return next((p for p in api("GET", "/projects") if p["name"] == part), None)


def nodes_of(project):
    return api("GET", f"/projects/{project['project_id']}/nodes")


def image_date(image, docker=("docker",)):
    """The build date identifies an image, even after a copy into the lab."""
    command = [*docker, "image", "inspect", "--format", "{{.Created}}", image]
    return subprocess.run(command, capture_output=True, text=True).stdout.strip()


def load_images_into_lab():
    if not lab_running():
        return
    for image in (HOST_IMAGE, ROUTER_IMAGE):
        if image_date(image) == image_date(image, docker_command()):
            continue
        print(f"Copying {image} into the lab")
        saved = subprocess.Popen(["docker", "save", image], stdout=subprocess.PIPE)
        subprocess.run(["docker", "exec", "-i", LAB, "docker", "load"],
                       stdin=saved.stdout, check=True, capture_output=True)
        if saved.wait() != 0:
            sys.exit(f"{image} is missing, run `make images` first.")


def stop_others(part):
    """Only one lab at a time, so the three parts cannot disturb each other."""
    for project in api("GET", "/projects"):
        if project["name"] in TOPOLOGIES and project["name"] != part \
                and project["status"] == "opened":
            down(project["name"])


def up(part):
    """Imports the project, replacing any older copy, and starts its devices."""
    print(f"GNS3 {require_gns3()} ready")
    load_images_into_lab()
    stop_others(part)
    delete(part)
    project_id = stable_id(part)
    api("POST", f"/projects/{project_id}/import?name={part}", project_file(part).read_bytes())
    api("POST", f"/projects/{project_id}/open")
    print(f"{part} imported, starting its devices")
    api("POST", f"/projects/{project_id}/nodes/start", {}, timeout=300)
    project = find_project(part)
    deadline = time.time() + 120
    while time.time() < deadline:
        if all(item["status"] == "started" for item in nodes_of(project)):
            time.sleep(SETTLE)
            print(f"{part} is running. Run `make test-{part.lower()}` to check it.")
            return
        time.sleep(1)
    sys.exit(f"{part}: some devices did not start, look at the GNS3 server log.")


def down(part):
    project = find_project(part)
    if not project:
        return
    if project["status"] == "opened":
        api("POST", f"/projects/{project['project_id']}/nodes/stop", {}, timeout=300)
        api("POST", f"/projects/{project['project_id']}/close", {})
    print(f"{part} stopped")


def delete(part):
    project = find_project(part)
    if project:
        down(part)
        api("DELETE", f"/projects/{project['project_id']}")
        print(f"{part} removed from GNS3")


def container(part, name):
    project = find_project(part)
    if not project:
        sys.exit(f"{part} is not in GNS3, run `make {part.lower()}` first.")
    found = next((n for n in nodes_of(project) if n["name"] == name), None)
    if not found:
        sys.exit(f"{name} is not a device of {part}.")
    return found["properties"]["container_id"]


def run_on(part, name, command, check=True, timeout=60):
    """Runs a shell command on a device and returns what it prints."""
    result = subprocess.run(docker_command() + ["exec", container(part, name), "sh", "-c", command],
                            capture_output=True, text=True, timeout=timeout)
    if check and result.returncode != 0:
        raise RuntimeError(f"{name}: {command}\n{result.stdout}{result.stderr}")
    return result.stdout


def switch_mode(mode):
    suffix = {"static": "s", "group": "g"}.get(mode)
    if not suffix:
        sys.exit("Use: mode static  or  mode group")
    for number in (1, 2):
        run_on("P2", f"routeur_{LOGIN}-{number}", f"sh /etc/network/_{LOGIN}-{number}_{suffix}")
    print(f"P2 is now in {mode} mode")


def configure_hosts():
    """P3 hosts boot without an address: the evaluation checks that a host is
    learned by its MAC alone. This does the step that comes after."""
    for number in (1, 2, 3):
        run_on("P3", f"host_{LOGIN}-{number}", f"sh /etc/network/_{LOGIN}-{number}_host")
    print("The P3 hosts have their IP address")


def status():
    for project in api("GET", "/projects"):
        print(f"{project['name']}: {project['status']}")
        if project["status"] == "opened":
            for item in nodes_of(project):
                print(f"  {item['name']:<24} {item['status']}")


def clean():
    """Removes our projects. A closed server has nothing to remove now."""
    try:
        require_gns3()
    except SystemExit:
        print("No GNS3 server is running, so nothing to remove from it.\n"
              "If you use the GNS3 app, open it and run this again.")
        return
    for part in TOPOLOGIES:
        delete(part)


def main():
    args = sys.argv[1:]
    command = args[0] if args else ""
    part = args[1].upper() if len(args) > 1 else None
    if command == "status":
        status()
    elif command == "clean":
        clean()
    elif command == "hosts":
        configure_hosts()
    elif command == "mode" and part:
        switch_mode(args[1])
    elif command in ("build", "up", "down") and part in TOPOLOGIES:
        {"build": build_project, "up": up, "down": down}[command](part)
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main()
