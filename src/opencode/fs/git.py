"""Git operations via subprocess."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path


class GitOps:
    """Git operations for a working directory."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    async def _run(self, *args: str) -> str:
        """Run a git command and return stdout. Raises on failure."""
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(self.root), *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise subprocess.CalledProcessError(
                proc.returncode or 1, ["git", *args],
                output=stdout, stderr=stderr,
            )
        return stdout.decode().strip()

    async def status(self) -> str:
        """Return short git status."""
        return await self._run("status", "--short")

    async def diff(self) -> str:
        """Return unstaged diff."""
        return await self._run("diff")

    async def log(self, *, n: int = 10) -> str:
        """Return recent commit log."""
        return await self._run("log", f"--oneline", f"-{n}")

    async def current_branch(self) -> str:
        """Return current branch name."""
        return await self._run("rev-parse", "--abbrev-ref", "HEAD")

    async def is_git_repo(self) -> bool:
        """Check if the root is inside a git repository."""
        proc = await asyncio.create_subprocess_exec(
            "git", "-C", str(self.root), "rev-parse", "--git-dir",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await proc.communicate()
        return proc.returncode == 0
