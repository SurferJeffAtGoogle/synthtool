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

import json
from jinja2 import FileSystemLoader, Environment
from pathlib import Path
import os
import re
from synthtool import _tracked_paths, gcp, shell, transforms
from synthtool.gcp import samples, snippets
from synthtool.log import logger
from synthtool.sources import git
from typing import Any, Dict, List, Optional
import logging
import shutil

_REQUIRED_FIELDS = ["name", "repository"]
_TOOLS_DIRECTORY = "/synthtool"


def read_metadata():
    """
    read package name and repository in package.json from a Node library.

    Returns:
        data - package.json file as a dict.
    """
    with open("./package.json") as f:
        data = json.load(f)

        if not all(key in data for key in _REQUIRED_FIELDS):
            raise RuntimeError(
                f"package.json is missing required fields {_REQUIRED_FIELDS}"
            )

        repo = git.parse_repo_url(data["repository"])

        data["repository"] = f'{repo["owner"]}/{repo["name"]}'
        data["repository_name"] = repo["name"]
        data["lib_install_cmd"] = f'npm install {data["name"]}'

        return data


def template_metadata() -> Dict[str, Any]:
    """Load node specific template metadata.

    Returns:
        Dictionary of metadata. Includes the entire parsed contents of the package.json file if
        present. Other expected fields:
        * quickstart (str): Contents of the quickstart snippet if available, otherwise, ""
        * samples (List[Dict[str, str]]): List of available samples. See synthtool.gcp.samples.all_samples()
    """
    metadata = {}
    try:
        metadata = read_metadata()
    except FileNotFoundError:
        pass

    all_samples = samples.all_samples(["samples/*.js"])

    # quickstart.js sample is special - only include it in the samples list if there is
    # a quickstart snippet present in the file
    quickstart_snippets = list(
        snippets.all_snippets_from_file("samples/quickstart.js").values()
    )
    metadata["quickstart"] = quickstart_snippets[0] if quickstart_snippets else ""
    metadata["samples"] = list(
        filter(
            lambda sample: sample["file"] != "samples/quickstart.js"
            or metadata["quickstart"],
            all_samples,
        )
    )
    return metadata


def get_publish_token(package_name: str):
    """
    parses the package_name into the name of the token to publish the package.

    Example:
        @google-cloud/storage => google-cloud-storage-npm-token
        dialogflow => dialogflow-npm-token

    Args:
        package: Name of the npm package.
    Returns:
        The name of the key to fetch the publish token.
    """
    return package_name.strip("@").replace("/", "-") + "-npm-token"


def extract_clients(filePath: Path) -> List[str]:
    """
    parse the client name from index.ts file

    Args:
        filePath: the path of index.ts.
    Returns:
        Array of client name str extract from index.ts file.
    """
    with open(filePath, "r") as fh:
        content = fh.read()
    return re.findall(r"\{(.*Client)\}", content)


def generate_index_ts(versions: List[str], default_version: str) -> None:
    """
    generate src/index.ts to export the client name and versions in the client library.

    Args:
      versions: the list of versions, like: ['v1', 'v1beta1', ...]
      default_version: a stable version provided by API producer. It must exist in argument versions.
    Return:
      True/False: return true if successfully generate src/index.ts, vice versa.
    """
    # sanitizer the input arguments
    if len(versions) < 1:
        err_msg = (
            "List of version can't be empty, it must contain default version at least."
        )
        logger.error(err_msg)
        raise AttributeError(err_msg)
    if default_version not in versions:
        err_msg = f"Version {versions} must contain default version {default_version}."
        logger.error(err_msg)
        raise AttributeError(err_msg)

    # compose default version's index.ts file path
    versioned_index_ts_path = Path("src") / default_version / "index.ts"
    clients = extract_clients(versioned_index_ts_path)
    if not clients:
        err_msg = f"No client is exported in the default version's({default_version}) index.ts ."
        logger.error(err_msg)
        raise AttributeError(err_msg)

    # compose template directory
    template_path = (
        Path(__file__).parent.parent / "gcp" / "templates" / "node_split_library"
    )
    template_loader = FileSystemLoader(searchpath=str(template_path))
    template_env = Environment(loader=template_loader, keep_trailing_newline=True)
    TEMPLATE_FILE = "index.ts.j2"
    index_template = template_env.get_template(TEMPLATE_FILE)
    # render index.ts content
    output_text = index_template.render(
        versions=versions, default_version=default_version, clients=clients
    )
    with open("src/index.ts", "w") as fh:
        fh.write(output_text)
    logger.info("successfully generate `src/index.ts`")


def install(hide_output=False):
    """
    Installs all dependencies for the current Node.js library.
    """
    logger.debug("Installing dependencies...")
    shell.run(["npm", "install"], hide_output=hide_output)


def fix(hide_output=False):
    """
    Fixes the formatting in the current Node.js library.
    Before running fix script, run prelint to install extra dependencies
    for samples, but do not fail if it does not succeed.
    """
    logger.debug("Running prelint...")
    shell.run(["npm", "run", "prelint"], check=False, hide_output=hide_output)
    logger.debug("Running fix...")
    shell.run(["npm", "run", "fix"], hide_output=hide_output)


def fix_hermetic(hide_output=False):
    """
    Fixes the formatting in the current Node.js library. It assumes that gts
    is already installed in a well known location on disk:
    """
    logger.debug("Copy eslint config")
    shell.run(
        ["cp", "-r", f"{_TOOLS_DIRECTORY}/node_modules", "."],
        check=True,
        hide_output=hide_output,
    )
    logger.debug("Running fix...")
    shell.run(
        [f"{_TOOLS_DIRECTORY}/node_modules/.bin/gts", "fix"],
        check=False,
        hide_output=hide_output,
    )


def compile_protos(hide_output=False):
    """
    Compiles protos into .json, .js, and .d.ts files using
    compileProtos script from google-gax.
    """
    logger.debug("Compiling protos...")
    shell.run(["npx", "compileProtos", "src"], hide_output=hide_output)


def detect_versions(path="./src") -> List[str]:
    """
    Detects the versions a library has, based on distinct folders
    within path. This is based on the fact that our GAPIC libraries are
    structured as follows:

    src/v1
    src/v1beta
    src/v1alpha

    With folder names mapping directly to versions.
    """
    versions = []
    for directory in os.listdir("./src"):
        if os.path.isdir(os.path.join("./src", directory)):
            versions.append(directory)
    return versions


def compile_protos_hermetic(hide_output=False):
    """
    Compiles protos into .json, .js, and .d.ts files using
    compileProtos script from google-gax.
    """
    logger.debug("Compiling protos...")
    shell.run(
        [f"{_TOOLS_DIRECTORY}/node_modules/.bin/compileProtos", "src"],
        check=True,
        hide_output=hide_output,
    )


def postprocess_gapic_library(hide_output=False):
    logger.debug("Post-processing GAPIC library...")
    install(hide_output=hide_output)
    fix(hide_output=hide_output)
    compile_protos(hide_output=hide_output)
    logger.debug("Post-processing completed")


def postprocess_gapic_library_hermetic(hide_output=False):
    logger.debug("Post-processing GAPIC library...")
    fix_hermetic(hide_output=hide_output)
    compile_protos_hermetic(hide_output=hide_output)
    logger.debug("Post-processing completed")


_s_copy = transforms.move


"""List of files te exclude from copy_and_delete_staging_dir() by default."""
default_staging_excludes = ["README.md", "package.json", "src/index.ts"]


def copy_and_delete_staging_dir(excludes: Optional[List[str]] = None) -> None:
    f"""Copies the staging directory into the root.

    Args:
        excludes: list of files to exclude while copying.  Defaults to
          {default_staging_excludes}
    """
    if excludes is None:
        excludes = default_staging_excludes
    staging = Path("owl-bot-staging")
    versions = collect_version_sub_dirs(staging)
    if versions:
        # Copy each version directory into the root.
        for version in versions:
            library = staging / version
            _tracked_paths.add(library)
            _s_copy([library], excludes=excludes)
        # The staging directory should never be merged into the main branch.
        shutil.rmtree(staging)


def load_default_version() -> str:
    """Loads the default_version declared in .repo-metadata.json."""
    return json.load(open(".repo-metadata.json", "rt"))["default_version"]


def collect_version_sub_dirs(parent_dir: Path) -> List[str]:
    """Collects the subdirectories of parent_dir; the default version is the
    final item in the returned list.
    """
    if not parent_dir.is_dir():
        return []
    default_version = load_default_version()
    # Collect the subdirectories of the directory.
    versions = [v.name for v in parent_dir.iterdir() if v.is_dir()]
    # Reorder the versions so the default version always comes last.
    versions = [v for v in versions if v != default_version] + [default_version]
    return versions


def collect_versions_from_src() -> List[str]:
    """Examines ./src to collect the list of versions."""
    return collect_version_sub_dirs(Path("src"))


def copy_common_templates(
    template_path: Optional[Path] = None,
    versions: Optional[List[str]] = None,
    excludes: Optional[List[str]] = None,
    source_location: str = "build/src",
) -> None:
    """Generates and copies common templates into the current working dir.

    Args:
        template_path: path to the template directory, optional
        versions: list of API versions, optional
        excludes: files to exclude during the copy, defaults to empty
    """
    common_templates = gcp.CommonTemplates(template_path)
    default_version = versions[-1] if versions else None
    templates = common_templates.node_library(
        source_location=source_location,
        versions=versions,
        default_version=default_version,
    )
    _s_copy([templates], excludes=(excludes or []))


def owlbot_main(template_path: Optional[Path] = None):
    """Copies files from staging and template directories into current working dir.

    When there is no owlbot.py file, run this function instead.  Also, when an
    owlbot.py file is necessary, the first statement of owlbot.py should probably
    call this function.

    Depends on owl-bot copying into a staging directory, so your .Owlbot.yaml should
    look a lot like this:

        docker:
            image: gcr.io/repo-automation-bots/owlbot-nodejs:latest

        deep-remove-regex:
            - /owl-bot-staging

        deep-copy-regex:
            - source: /google/cloud/video/transcoder/(.*)/.*-nodejs/(.*)
              dest: /owl-bot-staging/$1/$2

    Also, this function requires a default_version in your .repo-metadata.json.  Ex:
        "default_version": "v1",
    """
    logging.basicConfig(level=logging.DEBUG)
    copy_and_delete_staging_dir()
    versions = collect_versions_from_src()

    copy_common_templates(template_path, versions)

    postprocess_gapic_library_hermetic()


if __name__ == "__main__":
    owlbot_main()
