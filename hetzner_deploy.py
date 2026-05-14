#!/usr/bin/env python3
"""
Hetzner VPS Deployment Script - Fixed & Improved

Manages lifecycle of a GitHub self-hosted runner on Hetzner Cloud:
  * Creates a Hetzner Firewall with NO inbound rules (SSH blocked, outbound free)
  * Spins up the cheapest available VPS with cloud-init that installs the runner
  * Polls the GitHub API until the runner comes online
  * Saves deployment state to deployment.json + GITHUB_OUTPUT for cross-job use
  * On cleanup: deregisters runner from GitHub, deletes server, deletes firewall

Usage (provision):
    python hetzner_deploy.py provision \
        --hetzner-token $HETZNER_TOKEN \
        --github-token  $GITHUB_TOKEN \
        --repo          owner/repo \
        --run-id        $GITHUB_RUN_ID

Usage (cleanup):
    python hetzner_deploy.py cleanup \
        --hetzner-token $HETZNER_TOKEN \
        --github-token  $GITHUB_TOKEN \
        --repo          owner/repo \
        --server-id     12345 \
        --firewall-id   67890 \
        --runner-name   hetzner-12345
"""

import json
import os
import sys
import time
import argparse
import requests
from typing import Optional


# ------------------------------------------------------------------------------
# Hetzner Cloud API client
# ------------------------------------------------------------------------------

class HetznerClient:
    BASE_URL = "https://api.hetzner.cloud/v1"

    def __init__(self, api_token: str):
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        })

    def _request(self, method: str, endpoint: str, data=None) -> dict:
        url = f"{self.BASE_URL}{endpoint}"
        response = self.session.request(method, url, json=data)
        if response.status_code == 204:
            return {}
        try:
            response.raise_for_status()
        except requests.HTTPError:
            print(f"Hetzner API {method} {endpoint} -> {response.status_code}")
            print(f"   {response.text[:400]}")
            raise
        return response.json()

    # -- Firewall ---------------------------------------------------------------

    def create_firewall(self, name: str) -> int:
        """
        Create a firewall with NO inbound rules.
        Hetzner Cloud Firewalls only control inbound -- outbound is always free.
        Empty rules list = all inbound blocked (including SSH port 22).
        """
        payload = {"name": name, "rules": []}
        resp = self._request("POST", "/firewalls", payload)
        fw_id = resp["firewall"]["id"]
        print(f"Firewall '{name}' created (ID: {fw_id}) -- all inbound blocked")
        return fw_id

    def delete_firewall(self, firewall_id: int) -> bool:
        try:
            self._request("DELETE", f"/firewalls/{firewall_id}")
            print(f"Firewall {firewall_id} deleted")
            return True
        except Exception as exc:
            print(f"Could not delete firewall {firewall_id}: {exc}")
            return False

    # -- Server type ------------------------------------------------------------

    def get_cheapest_server_type(self) -> str:
        """Return name of cheapest non-deprecated server type by monthly price."""
        types = self._request("GET", "/server_types")["server_types"]
        active = [t for t in types if not t.get("deprecated", False)]
        if not active:
            active = types

        def monthly_price(t: dict) -> float:
            for price in t.get("prices", []):
                net = price.get("price_monthly", {}).get("net")
                if net is not None:
                    return float(net)
            return 999.0

        active.sort(key=monthly_price)
        chosen = active[0]
        print(f"Cheapest server: {chosen['name']} (EUR {monthly_price(chosen):.2f}/month)")
        return chosen["name"]

    # -- Server -----------------------------------------------------------------

    def create_server(self, name: str, image: str, server_type: str,
                      user_data: str, firewall_id: int,
                      location: str = "") -> dict:
        name = name[:63].replace("_", "-").lower()

        # Try each location in order until one succeeds.
        # "error during placement" (412) means no capacity in that DC.
        locations_to_try = [location] if location else ["nbg1", "fsn1", "hel1", "ash", "hil"]

        last_exc = None
        for loc in locations_to_try:
            payload = {
                "name": name,
                "image": image,
                "server_type": server_type,
                "location": loc,
                "firewalls": [{"firewall": firewall_id}],
                "user_data": user_data,
                "labels": {
                    "purpose": "github-runner",
                    "managed-by": "hetzner-deploy",
                },
            }
            try:
                resp = self._request("POST", "/servers", payload)
                server = resp["server"]
                actual_loc = server.get("datacenter", {}).get("location", {}).get("name", loc)
                print(f"Server '{name}' created (ID: {server['id']}, location: {actual_loc})")
                return server
            except Exception as exc:
                print(f"  Placement failed in {loc}: {exc} — trying next location...")
                last_exc = exc

        raise RuntimeError(f"Could not place server in any location: {last_exc}")

    def wait_for_server_running(self, server_id: int, timeout: int = 300) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            server = self._request("GET", f"/servers/{server_id}")["server"]
            status = server["status"]
            if status == "running":
                return True
            if status == "error":
                print("Server entered error state")
                return False
            time.sleep(5)
        return False

    def get_server_ip(self, server_id: int) -> Optional[str]:
        server = self._request("GET", f"/servers/{server_id}")["server"]
        return server.get("public_net", {}).get("ipv4", {}).get("ip")

    def delete_server(self, server_id: int) -> bool:
        try:
            self._request("DELETE", f"/servers/{server_id}")
            print(f"Server {server_id} deleted")
            return True
        except Exception as exc:
            print(f"Failed to delete server {server_id}: {exc}")
            return False


# ------------------------------------------------------------------------------
# GitHub API client
# ------------------------------------------------------------------------------

class GitHubClient:
    BASE_URL = "https://api.github.com"

    def __init__(self, token: str, owner: str, repo: str):
        self.owner = owner
        self.repo = repo
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        })

    def _runners_url(self) -> str:
        return f"{self.BASE_URL}/repos/{self.owner}/{self.repo}/actions/runners"

    def get_registration_token(self) -> str:
        """Exchange PAT for a short-lived runner registration token (1h TTL)."""
        url = f"{self._runners_url()}/registration-token"
        resp = self.session.post(url)
        resp.raise_for_status()
        return resp.json()["token"]

    def get_latest_runner_version(self) -> str:
        """Fetch the latest Actions runner release tag."""
        url = f"{self.BASE_URL}/repos/actions/runner/releases/latest"
        try:
            resp = self.session.get(url)
            resp.raise_for_status()
            return resp.json()["tag_name"].lstrip("v")
        except Exception:
            return "2.317.0"

    def wait_for_runner_online(self, runner_name: str, timeout: int = 360) -> bool:
        """Poll until the named runner shows status=online."""
        deadline = time.time() + timeout
        print(f"Waiting for runner '{runner_name}' (timeout {timeout}s)...")
        while time.time() < deadline:
            resp = self.session.get(self._runners_url())
            for runner in resp.json().get("runners", []):
                if runner["name"] == runner_name:
                    elapsed = int(timeout - (deadline - time.time()))
                    status = runner["status"]
                    print(f"  [{elapsed:>3}s] runner status: {status}")
                    if status == "online":
                        return True
            time.sleep(15)
        return False

    def get_runner_id(self, runner_name: str) -> Optional[int]:
        resp = self.session.get(self._runners_url())
        for runner in resp.json().get("runners", []):
            if runner["name"] == runner_name:
                return runner["id"]
        return None

    def delete_runner(self, runner_id: int) -> bool:
        url = f"{self._runners_url()}/{runner_id}"
        resp = self.session.delete(url)
        return resp.status_code == 204


# ------------------------------------------------------------------------------
# Cloud-init script builder
# ------------------------------------------------------------------------------

def build_cloud_init(repo_url: str, runner_name: str, runner_token: str,
                     runner_label: str, runner_version: str) -> str:
    """
    Generate a bash cloud-init script that:
      1. Installs system deps
      2. Creates a dedicated 'runner' user
      3. Downloads the GitHub Actions runner binary (arch-aware)
      4. Configures it with a unique label so the test job can target it
      5. Installs and starts it as a systemd service

    The runner connects OUTBOUND to GitHub -- no inbound ports needed.
    Substitution note: ${{VAR}} in an f-string produces ${VAR} in the output.
    """
    lines = [
        "#!/bin/bash",
        "set -euo pipefail",
        "exec > >(tee /var/log/runner-setup.log) 2>&1",
        "",
        'echo "=== GitHub Self-Hosted Runner Setup $(date -u) ==="',
        "",
        "# System prep",
        "export DEBIAN_FRONTEND=noninteractive",
        "apt-get update -q",
        "apt-get install -yq curl git wget jq tar python3 python3-pip build-essential libssl-dev libffi-dev",
        "",
        "# Create dedicated runner user",
        "id runner 2>/dev/null || useradd -m -s /bin/bash runner",
        "echo 'runner ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/runner",
        "chmod 440 /etc/sudoers.d/runner",
        "",
        "# Download runner",
        f'RUNNER_VERSION="{runner_version}"',
        'RUNNER_DIR="/home/runner/actions-runner"',
        'mkdir -p "$RUNNER_DIR"',
        'cd "$RUNNER_DIR"',
        "",
        "ARCH=$(dpkg --print-architecture 2>/dev/null || uname -m)",
        'if [[ "$ARCH" == "aarch64" || "$ARCH" == "arm64" ]]; then',
        '    RUNNER_FILE="actions-runner-linux-arm64-${RUNNER_VERSION}.tar.gz"',
        "else",
        '    RUNNER_FILE="actions-runner-linux-x64-${RUNNER_VERSION}.tar.gz"',
        "fi",
        "",
        'RUNNER_URL="https://github.com/actions/runner/releases/download/v${RUNNER_VERSION}/${RUNNER_FILE}"',
        'echo "Downloading ${RUNNER_URL}"',
        'curl -sSfL "$RUNNER_URL" -o runner.tar.gz',
        "tar xzf runner.tar.gz",
        "rm runner.tar.gz",
        "chown -R runner:runner /home/runner",
        "",
        "# Install runner dependencies",
        "./bin/installdependencies.sh",
        "",
        "# Configure runner",
        f'echo "Configuring runner {runner_name} with label {runner_label}"',
        "sudo -u runner ./config.sh \\",
        f'    --url "{repo_url}" \\',
        f'    --token "{runner_token}" \\',
        f'    --name "{runner_name}" \\',
        f'    --labels "{runner_label}" \\',
        '    --work "_work" \\',
        "    --unattended \\",
        "    --replace",
        "",
        "# Install as systemd service",
        "./svc.sh install runner",
        "./svc.sh start runner",
        "",
        f'echo "Runner {runner_name} is up at $(date -u)"',
    ]
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------------------
# Commands
# ------------------------------------------------------------------------------

def cmd_provision(args) -> None:
    """Create firewall + server, wait for runner, write outputs."""
    print("=" * 60)
    print("PROVISION: Hetzner self-hosted runner")
    print("=" * 60)

    owner, repo = args.repo.split("/", 1)
    run_id = args.run_id or "local"
    runner_name = f"hetzner-{run_id}"
    runner_label = f"hetzner-{run_id}"
    server_name = f"gh-runner-{run_id}"[:40]
    firewall_name = f"fw-runner-{run_id}"[:40]

    hetzner = HetznerClient(args.hetzner_token)
    github = GitHubClient(args.github_token, owner, repo)

    # 1. Runner registration token (expires in 1h)
    print("\n[1/6] Fetching runner registration token...")
    reg_token = github.get_registration_token()
    print("  OK")

    # 2. Runner binary version
    runner_version = github.get_latest_runner_version()
    print(f"[2/6] Runner version: {runner_version}")

    # 3. Hetzner Firewall -- no inbound rules = SSH blocked
    print("\n[3/6] Creating Hetzner Firewall (no inbound rules)...")
    firewall_id = hetzner.create_firewall(firewall_name)

    # 4. Cheapest server type
    server_type = args.server_type or hetzner.get_cheapest_server_type()
    print(f"[4/6] Using server type: {server_type}")

    # 5. Build cloud-init and create server
    repo_url = f"https://github.com/{args.repo}"
    user_data = build_cloud_init(
        repo_url=repo_url,
        runner_name=runner_name,
        runner_token=reg_token,
        runner_label=runner_label,
        runner_version=runner_version,
    )

    print(f"\n[5/6] Creating server '{server_name}'...")
    server = hetzner.create_server(
        name=server_name,
        image="ubuntu-22.04",
        server_type=server_type,
        user_data=user_data,
        firewall_id=firewall_id,
        location=getattr(args, "location", ""),
    )
    server_id = server["id"]

    print("  Waiting for server to boot...")
    if not hetzner.wait_for_server_running(server_id):
        print("ERROR: Server did not start -- cleaning up...")
        hetzner.delete_server(server_id)
        hetzner.delete_firewall(firewall_id)
        sys.exit(1)

    public_ip = hetzner.get_server_ip(server_id)
    print(f"  Server running at {public_ip} (SSH blocked by firewall)")

    # 6. Wait for runner to register
    print(f"\n[6/6] Waiting for runner to register with GitHub...")
    if not github.wait_for_runner_online(runner_name, timeout=360):
        print("ERROR: Runner did not come online -- cleaning up...")
        hetzner.delete_server(server_id)
        hetzner.delete_firewall(firewall_id)
        sys.exit(1)
    print(f"  Runner '{runner_name}' is online!")

    # Save state
    result = {
        "server_id": server_id,
        "firewall_id": firewall_id,
        "runner_name": runner_name,
        "runner_label": runner_label,
        "public_ip": public_ip,
        "server_type": server_type,
    }
    with open("deployment.json", "w") as fh:
        json.dump(result, fh, indent=2)
    print("\nSaved deployment.json")

    # Write to GITHUB_OUTPUT (GitHub Actions cross-job outputs)
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            for key, val in result.items():
                fh.write(f"{key}={val}\n")
        print("Wrote job outputs to GITHUB_OUTPUT")

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for k, v in result.items():
        print(f"  {k}: {v}")


def cmd_cleanup(args) -> None:
    """Deregister runner + delete server + delete firewall."""
    print("=" * 60)
    print("CLEANUP")
    print("=" * 60)

    owner, repo = args.repo.split("/", 1)
    hetzner = HetznerClient(args.hetzner_token)
    github = GitHubClient(args.github_token, owner, repo)

    # Deregister runner
    if args.runner_name:
        print(f"\nRemoving runner '{args.runner_name}' from GitHub...")
        runner_id = github.get_runner_id(args.runner_name)
        if runner_id:
            if github.delete_runner(runner_id):
                print(f"  Runner removed (ID: {runner_id})")
            else:
                print("  Could not delete runner (may need manage_runners:org scope)")
        else:
            print("  Runner not found (already removed or never registered)")

    # Delete server
    if args.server_id:
        print(f"\nDeleting server {args.server_id}...")
        hetzner.delete_server(args.server_id)

    # Delete firewall (after server -- Hetzner won't delete an attached firewall)
    if args.firewall_id:
        print(f"\nDeleting firewall {args.firewall_id}...")
        time.sleep(5)
        hetzner.delete_firewall(args.firewall_id)

    print("\nCleanup complete")


# ------------------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Hetzner ephemeral runner -- provision / cleanup"
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # provision
    p = sub.add_parser("provision", help="Create server + register runner")
    p.add_argument("--hetzner-token", required=True)
    p.add_argument("--github-token", required=True)
    p.add_argument("--repo", required=True, help="GitHub repo in owner/name format")
    p.add_argument("--run-id", default="local",
                   help="GitHub run ID (used for unique naming)")
    p.add_argument("--server-type", default="",
                   help="Hetzner server type (default: cheapest available)")
    p.add_argument("--location", default="",
                   help="Hetzner datacenter location (default: tries nbg1->fsn1->hel1->ash->hil)")

    # cleanup
    c = sub.add_parser("cleanup", help="Delete server, firewall, deregister runner")
    c.add_argument("--hetzner-token", required=True)
    c.add_argument("--github-token", required=True)
    c.add_argument("--repo", required=True)
    c.add_argument("--server-id", type=int, default=0)
    c.add_argument("--firewall-id", type=int, default=0)
    c.add_argument("--runner-name", default="")

    args = parser.parse_args()
    if args.command == "provision":
        cmd_provision(args)
    elif args.command == "cleanup":
        cmd_cleanup(args)


if __name__ == "__main__":
    main()
