"""Bounded, descriptor-relative file access for Studio's untrusted drafts."""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from uuid import uuid4

MAX_FILE = 1024 * 1024
MAX_SOURCE = 16 * MAX_FILE
MAX_FILES = 512
TEXT_SUFFIXES = {".py", ".json", ".wit", ".html", ".css", ".js", ".md", ".txt", ".svg"}
ASSET_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".ico", ".woff", ".woff2"}
SKIP_DIRS = {"dev", "dist", "node_modules", "venv", "__pycache__"}


class DraftFiles:
    def __init__(self, root: Path):
        self.root = root

    def read(self, name: str, *, binary: bool = False) -> bytes:
        with self.parent(name) as (directory, leaf):
            fd = os.open(
                leaf, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            with os.fdopen(fd, "rb") as stream:
                info = os.fstat(stream.fileno())
                limit = 64 * MAX_FILE if binary else MAX_FILE
                if (
                    not stat.S_ISREG(info.st_mode)
                    or info.st_nlink != 1
                    or info.st_size > limit
                ):
                    raise ValueError(
                        "Only bounded, unlinked regular files are allowed."
                    )
                value = stream.read(limit + 1)
                if len(value) > limit:
                    raise ValueError("File size limit exceeded.")
                return value

    def write(self, name: str, value: str) -> None:
        self.check_name(name)
        content = value.encode("utf-8")
        if len(content) > MAX_FILE:
            raise ValueError("File exceeds the 1 MiB limit.")
        current = self.snapshot()
        current[name] = content
        self.check_size(current)
        with self.parent(name, create=True) as (directory, leaf):
            temporary = f".studio-{uuid4().hex}"
            fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(content)
                os.replace(temporary, leaf, src_dir_fd=directory, dst_dir_fd=directory)
            finally:
                try:
                    os.unlink(temporary, dir_fd=directory)
                except FileNotFoundError:
                    pass

    def delete(self, name: str) -> None:
        self.check_name(name)
        self.read(name)
        with self.parent(name) as (directory, leaf):
            os.unlink(leaf, dir_fd=directory)

    def snapshot(self) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        with self.parent("placeholder") as (directory, _):
            self._walk(directory, "", files)
        self.check_size(files)
        return files

    def check_name(self, name: str) -> None:
        parts = PurePosixPath(name).parts
        if (
            not parts
            or name != "/".join(parts)
            or name.startswith("/")
            or any(
                part in {"..", "."} or part.startswith(".") or part in SKIP_DIRS
                for part in parts
            )
            or "\\" in name
            or "\x00" in name
            or len(name) > 240
            or not re.fullmatch(r"[A-Za-z0-9_./ -]+", name)
        ):
            raise ValueError("Use a relative path inside this extension.")
        if PurePosixPath(name).suffix.lower() not in TEXT_SUFFIXES:
            raise ValueError(
                "Only Python, WIT, JSON, documentation and frontend text files are"
                " editable."
            )

    @staticmethod
    def check_size(files: dict[str, bytes]) -> None:
        if len(files) > MAX_FILES or sum(map(len, files.values())) > MAX_SOURCE:
            raise ValueError("Draft exceeds 512 files or 16 MiB of source/assets.")

    @contextmanager
    def parent(self, name: str, *, create: bool = False) -> Iterator[tuple[int, str]]:
        # Every component is opened without following links; the model cannot
        # supply absolute paths, create links, rename directories or access data/.
        parts = PurePosixPath(name).parts
        if not parts or name.startswith("/") or ".." in parts or "\\" in name:
            raise ValueError("Invalid relative path.")
        fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, 0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                os.close(fd)
                fd = child
            yield fd, parts[-1]
        finally:
            os.close(fd)

    def _walk(self, directory: int, prefix: str, files: dict[str, bytes]) -> None:
        for name in sorted(os.listdir(directory)):
            info = os.stat(name, dir_fd=directory, follow_symlinks=False)
            if stat.S_ISLNK(info.st_mode):
                raise ValueError("Drafts must not contain symbolic links.")
            if name.startswith(".") or name in SKIP_DIRS:
                continue
            relative = prefix + name
            if stat.S_ISDIR(info.st_mode):
                child = os.open(
                    name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory
                )
                try:
                    self._walk(child, relative + "/", files)
                finally:
                    os.close(child)
            elif Path(name).suffix.lower() in TEXT_SUFFIXES | ASSET_SUFFIXES:
                files[relative] = self.read(relative)
                self.check_size(files)


def source_digest(files: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for name, content in sorted(files.items()):
        digest.update(name.encode() + b"\0" + hashlib.sha256(content).digest())
    return digest.hexdigest()


def write_snapshot(root: Path, files: dict[str, bytes]) -> None:
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, content in files.items():
        path = root / name
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        path.write_bytes(content)


def atomic_json(path: Path, value: object) -> None:
    temporary = path.with_name(f".{uuid4().hex}.json")
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def source_diff(before: dict[str, bytes], after: dict[str, bytes]) -> list[dict]:
    changes = []
    for name in sorted(before.keys() | after.keys()):
        if before.get(name) == after.get(name):
            continue
        try:
            diff = "".join(
                difflib.unified_diff(
                    before.get(name, b"").decode().splitlines(keepends=True),
                    after.get(name, b"").decode().splitlines(keepends=True),
                    fromfile="before/" + name,
                    tofile="after/" + name,
                )
            )
        except UnicodeDecodeError:
            diff = "Binary asset changed."
        changes.append({"path": name, "diff": diff})
    return changes
