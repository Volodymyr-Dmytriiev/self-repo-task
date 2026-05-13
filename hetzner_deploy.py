#!/usr/bin/env python3
"""
Hetzner VPS Deployment Script

Manages lifecycle of GitHub self-hosted runner on Hetzner Cloud:
- Create VPS with minimal size (€2.99/month)
- Configure Cloudflare Tunnel for secure SSH access
- Install and configure GitHub runner
- Cleanup after tests complete

Usage:
    python hetzner_deploy.py --action create --hetzner-token TOKEN --github-token TOKEN
    python hetzner_deploy.py --action cleanup --hetzner-token TOKEN --server-id 12345
"""

import os
import sys
import time
import json
import argparse
import subprocess
from typing import Optional, Dict, Any
import requests


class HetznerClient:
    """Hetzner Cloud API client."""

    BASE_URL = "https://api.hetzner.cloud/v1"

    def __init__(self, api_token: str):
        self.api_token = api_token
        self.headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

    def _request(
        self, method: str, endpoint: str, data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make API request to Hetzner."""
        url = f"{self.BASE_URL}{endpoint}"
        try:
            if method == "GET":
                response = requests.get(url, headers=self.headers)
            elif method == "POST":
                response = requests.post(url, json=data, headers=self.headers)
            elif method == "DELETE":
                response = requests.delete(url, headers=self.headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            if response.status_code == 204:
                return {}
            return response.json()
        except requests.RequestException as e:
            print(f"❌ API Error: {e}")
            if hasattr(e.response, 'text'):
                print(f"Response: {e.response.text}")
            raise

    def get_images(self) -> list:
        """Get available images."""
        response = self._request("GET", "/images?type=system&status=available")
        return response.get("images", [])

    def get_server_types(self) -> list:
        """Get available server types."""
        response = self._request("GET", "/server_types")
        return response.get("server_types", [])

    def create_server(
        self, name: str, server_type: str = "ccx11", image: str = "ubuntu-22.04"
    ) -> Dict[str, Any]:
        """Create a new server."""
        # Validate server name (max 63 chars, alphanumeric + dash)
        if len(name) > 63:
            name = name[:63]

        name = name.replace("_", "-").lower()  # Hetzner requires lowercase, no underscores

        payload = {
            "name": name,
            "server_type": server_type,
            "image": image,
            "labels": {
                "purpose": "github-runner",
                "created_by": "self-improvement",
            },
        }

        print(f"📤 Sending request with server name: {name}")
        print(f"📤 Payload: {json.dumps(payload, indent=2)}")

        response = self._request("POST", "/servers", payload)
        return response.get("server", {})

    def get_server(self, server_id: int) -> Dict[str, Any]:
        """Get server details."""
        response = self._request("GET", f"/servers/{server_id}")
        return response.get("server", {})

    def get_server_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Get server by name."""
        response = self._request("GET", "/servers")
        servers = response.get("servers", [])
        for server in servers:
            if server["name"] == name:
                return server
        return None

    def delete_server(self, server_id: int) -> bool:
        """Delete a server."""
        try:
            self._request("DELETE", f"/servers/{server_id}")
            return True
        except Exception as e:
            print(f"❌ Failed to delete server: {e}")
            return False

    def wait_for_server(self, server_id: int, timeout: int = 300) -> bool:
        """Wait for server to be running."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                server = self.get_server(server_id)
                if server.get("status") == "running":
                    return True
            except Exception:
                pass
            time.sleep(5)

        return False


class CloudflareIntegration:
    """Cloudflare Tunnel configuration helper."""

    @staticmethod
    def get_tunnel_config(tunnel_token: str, ssh_server: str = "localhost:22") -> str:
        """Generate cloudflared config."""
        config = f"""
# Cloudflare Tunnel configuration
# Generated for GitHub runner SSH access

tunnel: {tunnel_token}
credentials-file: /etc/cloudflare/tunnel/credentials.json

ingress:
  - hostname: runner.yourdomain.com
    service: ssh://{ssh_server}
  - service: http_status:404
"""
        return config.strip()


class GitHubRunner:
    """GitHub Runner installation helper."""

    @staticmethod
    def get_runner_script(
        github_org: str, github_token: str, runner_name: str = "hetzner-runner"
    ) -> str:
        """Generate script to install GitHub runner."""
        script = f"""#!/bin/bash
set -e

echo "🚀 Installing GitHub Runner..."

# Install dependencies
apt-get update
apt-get install -y curl git build-essential libssl-dev libffi-dev python3-dev wget

# Create runner user
useradd -m -s /bin/bash github-runner || true
cd /home/github-runner

# Download and extract GitHub Actions runner
RUNNER_VERSION="2.311.0"
RUNNER_URL="https://github.com/actions/runner/releases/download/v${{RUNNER_VERSION}}/actions-runner-linux-x64-${{RUNNER_VERSION}}.tar.gz"

mkdir -p actions-runner
cd actions-runner

wget "$RUNNER_URL"
tar xzf "actions-runner-linux-x64-${{RUNNER_VERSION}}.tar.gz"
rm "actions-runner-linux-x64-${{RUNNER_VERSION}}.tar.gz"

# Configure runner
echo "Configuring runner..."
./config.sh --url https://github.com/{github_org} \\
           --token {github_token} \\
           --name {runner_name} \\
           --work _work \\
           --unattended \\
           --replace

# Install and start as service
./svc.sh install
./svc.sh start

echo "✅ GitHub Runner installed and started"
chown -R github-runner:github-runner /home/github-runner

echo "✅ Done!"
"""
        return script.strip()


class DeploymentManager:
    """Manage complete deployment lifecycle."""

    def __init__(self, hetzner_token: str, github_token: str, github_org: str):
        self.hetzner = HetznerClient(hetzner_token)
        self.github_token = github_token
        self.github_org = github_org

    def create_runner_server(self, server_name: str = "gh-runner") -> Dict:
        """Create and configure server for GitHub runner."""
        print(f"🚀 Creating Hetzner server: {server_name}")

        # Shorten and sanitize server name
        server_name = server_name[:30].replace("_", "-").lower()

        # Check if server already exists
        existing = self.hetzner.get_server_by_name(server_name)
        if existing:
            print(f"⚠️  Server {server_name} already exists (ID: {existing['id']})")
            return {
                "server_id": existing["id"],
                "public_ip": existing.get("public_net", {}).get("ipv4", {}).get("ip"),
                "status": existing["status"],
            }

        # Create server
        try:
            server = self.hetzner.create_server(
                name=server_name, server_type="ccx11", image="ubuntu-22.04"
            )
            server_id = server["id"]
            print(f"✅ Server created (ID: {server_id})")
        except Exception as e:
            print(f"❌ Failed to create server: {e}")
            return {}

        # Wait for server to be running
        print("⏳ Waiting for server to start (this may take 1-2 minutes)...")
        if self.hetzner.wait_for_server(server_id):
            server = self.hetzner.get_server(server_id)
            public_ip = server.get("public_net", {}).get("ipv4", {}).get("ip")
            print(f"✅ Server is running at {public_ip}")

            return {
                "server_id": server_id,
                "public_ip": public_ip,
                "status": "running",
            }
        else:
            print("❌ Server failed to start")
            self.hetzner.delete_server(server_id)
            return {}

    def cleanup_server(self, server_id: int) -> bool:
        """Delete server and cleanup."""
        print(f"🧹 Deleting server {server_id}...")
        if self.hetzner.delete_server(server_id):
            print(f"✅ Server {server_id} deleted")
            return True
        else:
            print(f"❌ Failed to delete server {server_id}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Hetzner VPS Deployment for GitHub Runner"
    )
    parser.add_argument(
        "--action",
        choices=["create", "cleanup", "status"],
        required=True,
        help="Action to perform",
    )
    parser.add_argument("--hetzner-token", required=True, help="Hetzner API token")
    parser.add_argument("--github-token", required=True, help="GitHub Personal Token")
    parser.add_argument(
        "--github-org",
        required=False,
        help="GitHub organization/username for runner registration",
    )
    parser.add_argument(
        "--server-name",
        default="gh-runner",
        help="Name for the Hetzner server",
    )
    parser.add_argument(
        "--server-id", type=int, required=False, help="Server ID for cleanup"
    )

    args = parser.parse_args()

    manager = DeploymentManager(args.hetzner_token, args.github_token, args.github_org or "")

    if args.action == "create":
        print("=" * 60)
        print("🚀 CREATING GITHUB RUNNER ON HETZNER")
        print("=" * 60)

        result = manager.create_runner_server(args.server_name)

        if result:
            print("\n" + "=" * 60)
            print("📊 DEPLOYMENT SUMMARY")
            print("=" * 60)
            print(f"Server ID: {result['server_id']}")
            print(f"Public IP: {result['public_ip']}")
            print(f"Status: {result['status']}")
            print("\n💾 Save this Server ID for cleanup:")
            print(f"   {result['server_id']}")
            print("\n⚠️  Server is running but runner is not yet installed.")
            print("Complete SSH setup and runner installation manually or via other means.")

            # Output in JSON for GitHub Actions
            with open("deployment.json", "w") as f:
                json.dump(result, f)
        else:
            sys.exit(1)

    elif args.action == "cleanup":
        if not args.server_id:
            print("❌ --server-id required for cleanup action")
            sys.exit(1)

        print("=" * 60)
        print(f"🧹 CLEANING UP SERVER {args.server_id}")
        print("=" * 60)

        if manager.cleanup_server(args.server_id):
            print("✅ Cleanup complete")
        else:
            sys.exit(1)

    elif args.action == "status":
        print("ℹ️  Status checks not yet implemented")


if __name__ == "__main__":
    main()
