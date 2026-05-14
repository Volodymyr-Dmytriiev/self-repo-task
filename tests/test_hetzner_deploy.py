"""
Tests for hetzner_deploy.py

Uses unittest.mock to avoid real API calls.
Run with:  pytest tests/ -v
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import requests

# Make root importable
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from hetzner_deploy import (
    HetznerClient,
    GitHubClient,
    build_cloud_init,
)


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def mock_response(status: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    if status >= 400:
        resp.raise_for_status.side_effect = requests.HTTPError(
            response=resp
        )
    else:
        resp.raise_for_status.return_value = None
    return resp


# ──────────────────────────────────────────────────────────────────────────────
# HetznerClient
# ──────────────────────────────────────────────────────────────────────────────

class TestHetznerClient:
    def setup_method(self):
        self.client = HetznerClient("fake-hetzner-token")

    @patch("requests.Session.request")
    def test_create_firewall_returns_id(self, mock_req):
        mock_req.return_value = mock_response(201, {"firewall": {"id": 42}})
        fw_id = self.client.create_firewall("test-fw")
        assert fw_id == 42

    @patch("requests.Session.request")
    def test_create_firewall_sends_empty_rules(self, mock_req):
        mock_req.return_value = mock_response(201, {"firewall": {"id": 99}})
        self.client.create_firewall("my-fw")
        call_kwargs = mock_req.call_args
        payload = call_kwargs[1]["json"]
        assert payload["rules"] == [], "Firewall must have no inbound rules"

    @patch("requests.Session.request")
    def test_delete_firewall_returns_true(self, mock_req):
        mock_req.return_value = mock_response(204, {})
        result = self.client.delete_firewall(42)
        assert result is True

    @patch("requests.Session.request")
    def test_delete_firewall_handles_error(self, mock_req):
        mock_req.side_effect = Exception("network error")
        result = self.client.delete_firewall(42)
        assert result is False

    @patch("requests.Session.request")
    def test_create_server_sanitizes_name(self, mock_req):
        mock_req.return_value = mock_response(
            201, {"server": {"id": 1, "public_net": {"ipv4": {"ip": "1.2.3.4"}}}}
        )
        self.client.create_server(
            name="My_Server_Name",
            image="ubuntu-22.04",
            server_type="cx22",
            user_data="#!/bin/bash\necho hi",
            firewall_id=1,
        )
        payload = mock_req.call_args[1]["json"]
        assert payload["name"] == "my-server-name", \
            "Server name must be lowercase with dashes"

    @patch("requests.Session.request")
    def test_create_server_attaches_firewall(self, mock_req):
        mock_req.return_value = mock_response(
            201, {"server": {"id": 7, "public_net": {"ipv4": {"ip": "5.6.7.8"}}}}
        )
        self.client.create_server("s", "ubuntu-22.04", "cx22", "#!/bin/bash", 55)
        payload = mock_req.call_args[1]["json"]
        assert payload["firewalls"] == [{"firewall": 55}]

    @patch("requests.Session.request")
    def test_get_cheapest_server_type(self, mock_req):
        mock_req.return_value = mock_response(200, {
            "server_types": [
                {"name": "cx22", "deprecated": False,
                 "prices": [{"price_monthly": {"net": "3.29"}}]},
                {"name": "cx32", "deprecated": False,
                 "prices": [{"price_monthly": {"net": "6.59"}}]},
                {"name": "old-type", "deprecated": True,
                 "prices": [{"price_monthly": {"net": "1.00"}}]},
            ]
        })
        result = self.client.get_cheapest_server_type()
        assert result == "cx22", "Should pick cheapest non-deprecated type"

    @patch("requests.Session.request")
    def test_wait_for_server_running_success(self, mock_req):
        mock_req.side_effect = [
            mock_response(200, {"server": {"status": "initializing"}}),
            mock_response(200, {"server": {"status": "running"}}),
        ]
        result = self.client.wait_for_server_running(1, timeout=60)
        assert result is True

    @patch("requests.Session.request")
    def test_wait_for_server_running_error_state(self, mock_req):
        mock_req.return_value = mock_response(200, {"server": {"status": "error"}})
        result = self.client.wait_for_server_running(1, timeout=60)
        assert result is False

    @patch("requests.Session.request")
    def test_delete_server_returns_true(self, mock_req):
        mock_req.return_value = mock_response(204, {})
        result = self.client.delete_server(123)
        assert result is True

    @patch("requests.Session.request")
    def test_delete_server_returns_false_on_failure(self, mock_req):
        mock_req.side_effect = Exception("boom")
        result = self.client.delete_server(123)
        assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# GitHubClient
# ──────────────────────────────────────────────────────────────────────────────

class TestGitHubClient:
    def setup_method(self):
        self.client = GitHubClient("fake-gh-token", "myorg", "myrepo")

    @patch("requests.Session.post")
    def test_get_registration_token(self, mock_post):
        mock_post.return_value = mock_response(201, {"token": "REGTOKEN123"})
        token = self.client.get_registration_token()
        assert token == "REGTOKEN123"

    @patch("requests.Session.get")
    def test_get_latest_runner_version_strips_v(self, mock_get):
        mock_get.return_value = mock_response(200, {"tag_name": "v2.317.0"})
        version = self.client.get_latest_runner_version()
        assert version == "2.317.0"

    @patch("requests.Session.get")
    def test_get_latest_runner_version_fallback(self, mock_get):
        mock_get.side_effect = Exception("network error")
        version = self.client.get_latest_runner_version()
        assert version == "2.317.0"

    @patch("requests.Session.get")
    def test_wait_for_runner_online_found(self, mock_get):
        mock_get.return_value = mock_response(200, {
            "runners": [
                {"name": "hetzner-42", "status": "online"},
            ]
        })
        result = self.client.wait_for_runner_online("hetzner-42", timeout=30)
        assert result is True

    @patch("requests.Session.get")
    def test_wait_for_runner_online_timeout(self, mock_get):
        mock_get.return_value = mock_response(200, {"runners": []})
        result = self.client.wait_for_runner_online("hetzner-42", timeout=1)
        assert result is False

    @patch("requests.Session.get")
    def test_get_runner_id(self, mock_get):
        mock_get.return_value = mock_response(200, {
            "runners": [
                {"name": "other-runner", "id": 1},
                {"name": "hetzner-42", "id": 99},
            ]
        })
        runner_id = self.client.get_runner_id("hetzner-42")
        assert runner_id == 99

    @patch("requests.Session.get")
    def test_get_runner_id_not_found(self, mock_get):
        mock_get.return_value = mock_response(200, {"runners": []})
        runner_id = self.client.get_runner_id("nonexistent")
        assert runner_id is None

    @patch("requests.Session.delete")
    def test_delete_runner_success(self, mock_delete):
        mock_delete.return_value = mock_response(204, {})
        result = self.client.delete_runner(99)
        assert result is True

    @patch("requests.Session.delete")
    def test_delete_runner_failure(self, mock_delete):
        mock_delete.return_value = mock_response(403, {"message": "Forbidden"})
        result = self.client.delete_runner(99)
        assert result is False


# ──────────────────────────────────────────────────────────────────────────────
# build_cloud_init
# ──────────────────────────────────────────────────────────────────────────────

class TestBuildCloudInit:
    def test_returns_bash_shebang(self):
        script = build_cloud_init(
            repo_url="https://github.com/user/repo",
            runner_name="hetzner-42",
            runner_token="TOKEN",
            runner_label="hetzner-42",
            runner_version="2.317.0",
        )
        assert script.startswith("#!/bin/bash")

    def test_contains_runner_name(self):
        script = build_cloud_init(
            repo_url="https://github.com/user/repo",
            runner_name="my-unique-runner",
            runner_token="TOKEN",
            runner_label="my-label",
            runner_version="2.317.0",
        )
        assert "my-unique-runner" in script

    def test_contains_runner_label(self):
        script = build_cloud_init(
            repo_url="https://github.com/user/repo",
            runner_name="name",
            runner_token="TOKEN",
            runner_label="unique-label-xyz",
            runner_version="2.317.0",
        )
        assert "unique-label-xyz" in script

    def test_contains_runner_version(self):
        script = build_cloud_init(
            repo_url="https://github.com/user/repo",
            runner_name="name",
            runner_token="TOKEN",
            runner_label="label",
            runner_version="9.9.9",
        )
        assert "9.9.9" in script

    def test_does_not_expose_token_in_obvious_way(self):
        """Token should be used only inside config.sh call, not echoed."""
        script = build_cloud_init(
            repo_url="https://github.com/user/repo",
            runner_name="name",
            runner_token="SUPER_SECRET_TOKEN",
            runner_label="label",
            runner_version="2.317.0",
        )
        # Token should appear exactly once (in config.sh --token flag)
        assert script.count("SUPER_SECRET_TOKEN") == 1

    def test_installs_service(self):
        script = build_cloud_init(
            repo_url="https://github.com/user/repo",
            runner_name="name",
            runner_token="TOKEN",
            runner_label="label",
            runner_version="2.317.0",
        )
        assert "svc.sh install" in script
        assert "svc.sh start" in script
