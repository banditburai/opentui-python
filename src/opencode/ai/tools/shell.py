"""Shell execution tool."""

from __future__ import annotations

import asyncio

from . import Tool


def shell_tool(*, timeout: int = 30) -> Tool:
    """Create a shell execution tool with a timeout (seconds)."""

    async def execute(*, command: str, **_: object) -> str:
        try:
            proc = await asyncio.create_subprocess_shell(
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
            output = stdout.decode()
            if proc.returncode != 0:
                err = stderr.decode()
                output += f"\n[exit code {proc.returncode}]"
                if err:
                    output += f"\n{err}"
            return output.strip()
        except asyncio.TimeoutError:
            try:
                proc.kill()
            except ProcessLookupError:
                pass  # Process already exited
            await proc.communicate()
            return f"Error: command timed out after {timeout}s"
        except OSError as e:
            return f"Error: {e}"

    return Tool(
        name="shell",
        description="Execute a shell command and return its output.",
        parameters={
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to execute."},
            },
            "required": ["command"],
        },
        execute=execute,
    )
