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

import json
import os
import pathlib
import pytest
import re
import shutil
import subprocess
import unittest

print("PYTHONPATH " + os.environ.get("PYTHONPATH"))

from synthtool import metadata
from synthtool.tmp import tmpdir
from synthtool.gcp.googleapis import clone_googleapis


class TestCase(unittest.TestCase):
    def test_clone_googleapis(self):
        path = clone_googleapis(False)
        # Second call will just retrieve cached value.
        assert path == clone_googleapis(False)

    def test_clone_private_googleapis(self):
        # The test doesn't have credentials to clone the private repo.
        with self.assertRaises(subprocess.CalledProcessError):
            path = clone_googleapis(True)
    
