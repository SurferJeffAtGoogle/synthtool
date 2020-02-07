# Copyright 2020 Google LLC
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

# Common functions for fetching https://github.com/googleapis/googleapis

import functools
import os
from pathlib import Path

import synthtool.metadata
from synthtool import log
from synthtool.sources import git

GOOGLEAPIS_URL_PATH = "googleapis/googleapis"
GOOGLEAPIS_PRIVATE_URL_PATH = "googleapis/googleapis-private"


@functools.lru_cache(maxsize=None)  # Execute once and cache the result.
def clone_googleapis(private: bool) -> Path:
    """Examines environment variable to find local copy of googleapis, or clones it.

    Returns:
        local path to cloned googleapis.
    """
    if private:
        name = "googleapis-private"
        url_path = GOOGLEAPIS_PRIVATE_URL_PATH
        local_googleapis = os.environ.get("SYNTHTOOL_GOOGLEAPIS_PRIVATE")
    else:
        name = "googleapis"
        url_path = GOOGLEAPIS_URL_PATH
        local_googleapis = os.environ.get("SYNTHTOOL_GOOGLEAPIS")

    if local_googleapis:
        googleapis_path = Path(local_googleapis).expanduser()
        log.debug(f"Using local {name} at {googleapis_path}")
        synthtool.metadata.add_git_source_from_directory(name, str(googleapis_path))

    else:
        log.debug(f"Cloning {name}.")
        googleapis_path = git.clone(git.make_repo_clone_url(url_path))

    return googleapis_path
