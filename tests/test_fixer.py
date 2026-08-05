from __future__ import annotations

import pytest

from dockerbrain.fixer.safety import is_safe_command


class TestIsSafeCommand:
    def test_safe_update(self):
        assert is_safe_command("docker update --memory 512m web") is True

    def test_safe_restart(self):
        assert is_safe_command("docker restart web") is True

    def test_safe_stop(self):
        assert is_safe_command("docker stop web") is True

    def test_safe_pull(self):
        assert is_safe_command("docker pull nginx:latest") is True

    def test_safe_logs(self):
        assert is_safe_command("docker logs --tail 50 web") is True

    def test_blocked_rm(self):
        assert is_safe_command("docker rm my-container") is False

    def test_blocked_rmi(self):
        assert is_safe_command("docker rmi my-image") is False

    def test_blocked_system_prune(self):
        assert is_safe_command("docker system prune") is False

    def test_blocked_volume_rm(self):
        assert is_safe_command("docker volume rm data") is False

    def test_blocked_network_rm(self):
        assert is_safe_command("docker network rm bridge") is False

    def test_blocked_image_rm(self):
        assert is_safe_command("docker image rm nginx") is False

    def test_non_docker_command(self):
        assert is_safe_command("rm -rf /") is False

    def test_just_docker(self):
        assert is_safe_command("docker") is False

    def test_empty_string(self):
        assert is_safe_command("") is False

    def test_case_insensitive(self):
        assert is_safe_command("Docker RM container") is False
        assert is_safe_command("DOCKER UPDATE --memory 512m web") is True

    def test_leading_trailing_whitespace(self):
        assert is_safe_command("  docker update --memory 512m web  ") is True
        assert is_safe_command("  docker rm container  ") is False

    def test_docker_compose_not_blocked(self):
        assert is_safe_command("docker compose up -d") is True

    def test_docker_inspect(self):
        assert is_safe_command("docker inspect web") is True

    def test_docker_exec(self):
        assert is_safe_command("docker exec -it web bash") is True
