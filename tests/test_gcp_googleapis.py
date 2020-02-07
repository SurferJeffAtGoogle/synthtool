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

import copy
import os
import importlib
import subprocess
import unittest
import unittest.mock

import synthtool
from synthtool import metadata
from synthtool.gcp.googleapis import clone_googleapis


class TestCase(unittest.TestCase):
    def setUp(self):
        metadata.reset()
        self.environ = copy.copy(os.environ)

    def tearDow(self):
        os.environ = self.environ

    def test_clone_googleapis(self):
        path = clone_googleapis(False)
        # Confirm it was recorded in metadata.
        metadata.get().sources[0].git.name == "googleapis"
        # Second call will just retrieve cached value.
        assert path == clone_googleapis(False)
        assert 1 == len(metadata.get().sources)

    def test_clone_private_googleapis(self):
        try:
            path = clone_googleapis(True)
            # Confirm it was recorded in metadata.
            metadata.get().sources[0].git.name == "googleapis-private"
            # Second call will just retrieve cached value.
            assert path == clone_googleapis(False)
            assert 1 == len(metadata.get().sources)
        except subprocess.CalledProcessError:
            pass  # The test may not have credentials to clone the private repo.

    def test_clone_googleapis_with_environment_variable(self):
        path = clone_googleapis(False)
        metadata.reset()
        # Reset the caching.
        importlib.reload(synthtool.gcp.googleapis)
        os.environ["SYNTHTOOL_GOOGLEAPIS"] = str(path)
        path = synthtool.gcp.googleapis.clone_googleapis(False)
        # Confirm it was recorded in metadata.
        metadata.get().sources[0].git.name == "googleapis"
        # Second call will just retrieve cached value.
        assert path == clone_googleapis(False)
        assert 1 == len(metadata.get().sources)
