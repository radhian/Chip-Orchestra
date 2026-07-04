"""Dependency-injectable command runner.

The EDA toolchain shells out to external binaries (``iverilog``, ``vvp``,
``librelane``). To keep the runners unit-testable without those tools installed,
all subprocess execution goes through the :class:`CommandRunner` protocol. Tests
substitute a fake runner that returns canned logs (and optionally writes fake
artifacts) instead of spawning real processes.
"""
from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Mapping, Optional, Protocol, Sequence, Union


@dataclass
class CommandResult:
    """Captured result of a single command invocation."""

    args: List[str]
    returncode: int
    stdout: str = ""
    stderr: str = ""
    timed_out: bool = False
    not_found: bool = False

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out and not self.not_found

    @property
    def output(self) -> str:
        """Combined stderr/stdout, mirroring how the tools print diagnostics."""
        return (self.stderr or self.stdout or "").strip()


class CommandRunner(Protocol):
    """Protocol implemented by real and fake command runners."""

    def run(
        self,
        args: Sequence[Union[str, Path]],
        *,
        cwd: Optional[Union[str, Path]] = None,
        timeout: Optional[float] = None,
        env: Optional[Mapping[str, str]] = None,
    ) -> CommandResult:
        ...


class SubprocessCommandRunner:
    """Default :class:`CommandRunner` backed by :mod:`subprocess`.

    Never raises for the common failure modes (missing binary, timeout); those
    are reported on the returned :class:`CommandResult` so callers can build a
    user-facing log instead of a 500.
    """

    def run(
        self,
        args: Sequence[Union[str, Path]],
        *,
        cwd: Optional[Union[str, Path]] = None,
        timeout: Optional[float] = None,
        env: Optional[Mapping[str, str]] = None,
    ) -> CommandResult:
        str_args = [str(a) for a in args]
        try:
            proc = subprocess.run(
                str_args,
                cwd=str(cwd) if cwd is not None else None,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=dict(env) if env is not None else None,
            )
        except FileNotFoundError:
            return CommandResult(
                args=str_args,
                returncode=127,
                stderr=f"{str_args[0] if str_args else 'command'} is not installed / not on PATH.",
                not_found=True,
            )
        except subprocess.TimeoutExpired as exc:  # pragma: no cover - timing dependent
            return CommandResult(
                args=str_args,
                returncode=124,
                stdout=exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or ""),
                stderr=(exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or ""))
                + f"\n(timed out after {timeout}s)",
                timed_out=True,
            )
        return CommandResult(
            args=str_args,
            returncode=proc.returncode,
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
        )


# Shared default instance for production code paths.
default_runner: CommandRunner = SubprocessCommandRunner()
