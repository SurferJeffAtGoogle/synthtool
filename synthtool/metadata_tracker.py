# Copyright 2018 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import locale
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import time
from typing import List, Iterable, Dict

from synthtool import metadata
from synthtool import log
from synthtool.protos import metadata_pb2


class MetadataTrackerAndWriter:
    """Writes metadata file upon exiting scope.  Tracks obsolete files."""

    def __init__(self, metadata_file_path: str):
        self.metadata_file_path = metadata_file_path

    def __enter__(self):
        self.start_time = time.time() - 1
        self.old_metadata = metadata.read_or_empty(self.metadata_file_path)

    def __exit__(self, type, value, traceback):
        if metadata.should_track_obsolete_files():
            new_files = _get_new_files(self.start_time)
            tracked_new_files = git_ignore(new_files)
            _add_new_files(tracked_new_files)
            _remove_obsolete_files(self.old_metadata)
        _append_git_logs(self.old_metadata, metadata.get())
        _clear_local_paths(metadata.get())
        metadata.write(self.metadata_file_path)


def _remove_obsolete_files(old_metadata):
    """Remove obsolete files from the file system.

    Call add_new_files() before this function or it will remove all generated
    files.

    Parameters:
        old_metadata:  old metadata loaded from a call to read_or_empty().
    """
    old_files = set([new_file.path for new_file in old_metadata.new_files])
    new_files = set([new_file.path for new_file in metadata.get().new_files])
    obsolete_files = old_files - new_files
    for file_path in git_ignore(obsolete_files):
        try:
            log.info(f"Removing obsolete file {file_path}...")
            os.unlink(file_path)
        except FileNotFoundError:
            pass  # Already deleted.  That's OK.


def _add_new_files(files: Iterable[str]) -> None:
    for filepath in files:
        new_file = metadata.get().new_files.add()
        new_file.path = _git_slashes(filepath)


def git_ignore(file_paths: Iterable[str]):
    """Returns a new list of the same files, with ignored files removed."""
    # Surprisingly, git check-ignore doesn't ignore .git directories, take those
    # files out manually.
    nongit_file_paths = [
        file_path
        for file_path in file_paths
        if ".git" not in pathlib.Path(file_path).parts
    ]

    encoding = locale.getpreferredencoding(False)
    # Write the files to a temporary text file.
    with tempfile.TemporaryFile("w+b") as f:
        for file_path in nongit_file_paths:
            f.write(_git_slashes(file_path).encode(encoding))
            f.write("\n".encode(encoding))
        # Invoke git.
        f.seek(0)
        git = shutil.which("git")
        if not git:
            raise FileNotFoundError("Could not find git in PATH.")
        completed_process = subprocess.run(
            [git, "check-ignore", "--stdin"], stdin=f, stdout=subprocess.PIPE
        )
    # Digest git output.
    output_text = completed_process.stdout.decode(encoding)
    ignored_file_paths = set(
        [os.path.normpath(path.strip()) for path in output_text.split("\n")]
    )
    # Filter the ignored paths from the file_paths.
    return [
        path
        for path in nongit_file_paths
        if os.path.normpath(path) not in ignored_file_paths
    ]


def _git_slashes(path: str):
    # git speaks only forward slashes
    return path.replace("\\", "/") if sys.platform == "win32" else path


def _get_new_files(newer_than: float) -> List[str]:
    """Searchs current directory for new files and returns them in a list.

    Parameters:
        newer_than: any file modified after this timestamp (from time.time())
            will be added to the metadata
    """
    new_files = []
    for (root, dirs, files) in os.walk(os.getcwd()):
        for filename in files:
            filepath = os.path.join(root, filename)
            try:
                mtime = os.path.getmtime(filepath)
            except FileNotFoundError:
                log.warning(
                    f"FileNotFoundError while getting modified time for {filepath}."
                )
                continue
            if mtime >= newer_than:
                new_files.append(os.path.relpath(filepath))
    return new_files


def _append_git_logs(old_metadata, new_metadata):
    """Adds git logs to git sources in new_metadata.

    Parameters:
        old_metadata: instance of metadata_pb2.Metadata
        old_metadata: instance of metadata_pb2.Metadata
    """
    old_map = _get_git_source_map(old_metadata)
    new_map = _get_git_source_map(new_metadata)
    git = shutil.which("git")
    for name, git_source in new_map.items():
        # Get the git history since the last run:
        old_source = old_map.get(name, metadata_pb2.GitSource())
        if not old_source.sha or not git_source.local_path:
            continue
        output = subprocess.run(
            [
                git,
                "-C",
                git_source.local_path,
                "log",
                "--pretty=oneline",
                "--no-decorate",
                f"{old_source.sha}..HEAD",
            ],
            stdout=subprocess.PIPE,
            universal_newlines=True,
        ).stdout
        git_source.log = output


def _get_git_source_map(metadata) -> Dict[str, object]:
    """Gets the git sources from the metadata.

    Parameters:
        metadata: an instance of metadata_pb2.Metadata.

    Returns:
        A dict mapping git source name to metadata_pb2.GitSource instance.
    """
    source_map = {}
    for source in metadata.sources:
        if source.HasField("git"):
            git_source = source.git
            source_map[git_source.name] = git_source
    return source_map


def _clear_local_paths(metadata):
    """Clear the local_path from the git sources.

    There's no reason to preserve it, and it may leak some info we don't
    want to leak in the path.
    """
    for source in metadata.sources:
        if source.HasField("git"):
            git_source = source.git
            git_source.ClearField("local_path")
