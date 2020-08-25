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

import importlib
import sys
from pprint import pprint
from typing import Dict, List, Any


def shard_list(alist: List[Any], shard_count: int) -> List[List[Any]]:
    """Breaks the list up into roughly-equally sized shards.

    Args:
        alist: A list of things.
        shard_count (int): The total number of shards.

    Returns:
        List[List[Any]]: The shards.
    """
    shard_size = len(alist) / shard_count
    shard_start = 0.0
    for i in range(shard_count - 1):
        shard_end = shard_start + shard_size
        yield alist[int(shard_start):int(shard_end)]
        shard_start = shard_end
    yield alist[int(shard_start):]


def main(args: List[str]):
    provider = args[1]
    shard_count = int(args[2])

    mod_name = "autosynth.providers." + provider
    mod = importlib.import_module(mod_name)

    print("Collecting list of repositories...")
    repos: List[Dict[str, str]] = mod.list_repositories()
    repos.sort(key=lambda repo: repo["name"])
    shards = list(shard_list(repos, 10))
    pprint(shards)    


if __name__ == "__main__":
    main(sys.argv)
