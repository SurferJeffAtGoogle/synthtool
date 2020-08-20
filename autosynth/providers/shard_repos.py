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
from typing import Dict, List


def main(args: List[str]):
    provider = args[1]
    shard_count = int(args[2])
    mod_name = "autosynth.providers." + provider
    mod = importlib.import_module(mod_name)

    print("Collecting list of repositories...")
    repos: List[Dict[str, str]] = mod.list_repositories()
    
    # Split the repos into equal-sized N shards.
    repos.sort(key=lambda repo: repo["name"])
    shard_size, shard_mod = divmod(len(repos), shard_count)
    shard_start = 0
    shards = []
    for i in range(shard_count):
        if shard_mod > 0:
            i_shard_size = shard_size + 1
            shard_mod -= 1
        else:
            i_shard_size = shard_size
        shard_end = shard_start + i_shard_size
        shards.append(repos[shard_start:shard_end])
        shard_start = shard_end  # Advance to next shard.
    pprint(shards)
    # Make sure we didn't misplace a repo while sharding.
    assert len(repos) == sum([len(shard) for shard in shards])


if __name__ == "__main__":
    main(sys.argv)
