# SEE https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program

import os
import re as regex
import requests
import shutil
import subprocess
import sys
import tarfile
from typing import List, Set


class PyPI:
    # IDEA may need to specify a Python and 'pip' version to avoid download errors.
    abs_download_path: str
    _downloads_cache: Set[str]
    norm_python_versions: List[str]

    _REGEX_PRJ_VERSION: str = r"[0-9]+(\.[0-9]+)*"
    _REGEX_PY_VERSION: str = r"[3](\.[0-9]+){0,2}"

    def __init__(self, download_path: str):
        assert os.path.isdir(download_path), f"{download_path} is not an existing directory"
        self.abs_download_path = os.path.abspath(download_path)
        self.norm_python_versions = self._get_norm_python_versions()
        self._downloads_cache = set()

    def download_python_source(self, python_version: str = "") -> str:
        if not python_version:
            python_version = self.norm_python_versions[0]
        else:
            python_version = self.normalize_python_version(python_version)

            if not self.is_valid_py_version(python_version):
                raise Exception(f"Specified version {python_version} has an invalid format")
            python_version = self.normalize_python_version(python_version)
            if python_version not in self.norm_python_versions:
                raise Exception(f"Specified Python version {python_version} is unknown")

        # Request the source archive
        download_url = f"https://www.python.org/ftp/python/{python_version}/Python-{python_version}.tgz"
        archive_path = os.path.join(self.abs_download_path, f"{self.build_dir_name(python_version)}.tgz")
        response = requests.get(download_url)
        if not response.status_code == 200:
            raise Exception(f"Unable to find the specified Python version {python_version}, something went wrong")

        # Store the requested archive
        with open(archive_path, "wb") as f:
            f.write(response.content)

        # Extract and delete the archive
        with tarfile.open(archive_path) as f:
            f.extractall(self.abs_download_path)
        os.remove(archive_path)

        # Store only the 'Lib' folder with the standard library packages
        downloaded_python_folder = f"Python-{python_version}"
        stdlib_folder = "Lib"
        python_source_path = os.path.join(self.abs_download_path, self.build_dir_name(python_version))
        os.rename(os.path.join(self.abs_download_path, downloaded_python_folder, stdlib_folder), python_source_path)
        shutil.rmtree(os.path.join(self.abs_download_path, downloaded_python_folder))

        # Create an init file to make it appear a library
        with open(os.path.join(python_source_path, "__init__.py"), "w"):
            pass

        # Cache and return the final Python source folder path
        assert os.path.isdir(python_source_path), f"{python_source_path} is not an existing directory"
        assert python_source_path == os.path.abspath(python_source_path), f"{python_source_path} is not an absolute path"
        self._downloads_cache.add(python_source_path)
        return python_source_path

    def download_project(self, project_name: str, project_version: str = "") -> str:

        # Check input
        if project_version and not self.is_valid_prj_version(project_version):
            raise Exception(f"Specified version {project_version} has an invalid format")
        available_versions = self.get_project_versions(project_name)
        if not available_versions:
            raise Exception(f"Project name {project_name} not found in PyPI")
        if project_version and project_version not in available_versions:
            raise Exception(f"Specified project version {project_version} not available in PyPI")

        if not project_version:
            project_version = available_versions[0]
        download_target = f"{project_name}=={project_version}"

        # Create a temporary directory in which to download the source archive
        assert os.path.isdir(self.abs_download_path), f"{self.abs_download_path} is not an existing directory"
        abs_temp_path = os.path.join(self.abs_download_path, "temp")
        assert not os.path.isdir(abs_temp_path), f"{abs_temp_path} is an already existing directory"
        os.mkdir(abs_temp_path)

        # Download only the project source archive
        # TODO upgrade 'pip' and 'setuptools'
        # IDEA when 'Library'es analysis will be supported, there will be no need to download dependencies one by one
        #  but installing the root project will be enough
        process = subprocess.Popen(
            [sys.executable,
             "-m", "pip",
             "download", download_target,
             "-d", abs_temp_path,
             "--no-deps",             # no dependencies
             "--no-binary", ":all:"]  # no distributions, source code
        )
        process.communicate()
        assert process.returncode == 0, f"process return code is {process.returncode}"

        # Find the downloaded source archive
        assert len(os.listdir(abs_temp_path)) == 1, f"there are {len(os.listdir(abs_temp_path))} files"
        abs_archive_path = os.path.join(abs_temp_path, os.listdir(abs_temp_path)[0])

        # Open the archive, extract its content in the temporary directory, then delete it
        with tarfile.open(abs_archive_path) as f_archive:
            f_archive.extractall(abs_temp_path)
        os.remove(abs_archive_path)

        # Move the extracted project folder to the download directory with standard name
        assert len(os.listdir(abs_temp_path)) == 1, f"there are {len(os.listdir(abs_temp_path))} files"
        temp_project_path = os.path.join(abs_temp_path, os.listdir(abs_temp_path)[0])
        project_path = os.path.join(self.abs_download_path, self.build_dir_name(project_version, project_name))
        os.rename(temp_project_path, project_path)
        assert os.path.isdir(project_path), f"{project_path} is not an existing directory"
        assert project_path == os.path.abspath(project_path), f"{project_path} is not an absolute path"

        # Delete the temporary directory
        shutil.rmtree(abs_temp_path)

        # Cache and return the project folder path
        self._downloads_cache.add(project_path)
        return project_path

    @staticmethod
    def is_existing_project(project_name: str, project_version: str = "") -> bool:
        available_versions = PyPI.get_project_versions(project_name)
        # return available_versions and project_version in available_versions if project_version else True
        if available_versions:
            if project_version:
                return project_version in available_versions
            else:
                return True
        else:
            return False

    @staticmethod
    def get_project_versions(project_name: str) -> List[str]:

        process = subprocess.Popen(
            [sys.executable,
             "-m", "pip",
             "index", "versions", project_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, _ = process.communicate()

        versions = []
        if process.returncode == 0:
            out = str(out).split("\\r\\n")[1]
            assert out.startswith("Available versions: "), f"wrong parsing of {out}"
            versions = out.split(": ")[1].split(", ")

        return versions

    def _get_norm_python_versions(self) -> List[str]:
        releases_url = "https://www.python.org/downloads/"
        regex_html_release = r'<a href="/downloads/release/python-[0-9]+/">Python (' + \
                             self._REGEX_PY_VERSION + \
                             ')</a>'

        response = requests.get(releases_url)
        releases_html = str(response.content)
        versions = list()
        for release_match in regex.finditer(regex_html_release, releases_html):
            released_version = regex.search(self._REGEX_PY_VERSION + r'(?=<)',
                                            release_match.group(0)).group(0)
            assert released_version == self.normalize_python_version(released_version), \
                   f"Wrong assumption, '{released_version}' is not normalized"
            versions.append(released_version)
        return versions

    def already_downloaded(self, version: str, name: str = "Python") -> bool:
        if name == "Python":
            assert regex.match(self._REGEX_PY_VERSION, version), f"invalid Python version {version}"
        else:
            assert regex.match(self._REGEX_PRJ_VERSION, version), f"invalid project version {version}"
        return self.build_dir_name(version, name) in self._downloads_cache

    @staticmethod
    def build_dir_name(version: str, name: str = "Python") -> str:
        dir_name = name.lower() + "_"
        for version_number in version.split("."):
            dir_name += f"{int(version_number):03}"
        return dir_name

    def is_valid_prj_version(self, version: str) -> bool:
        return bool(regex.match(self._REGEX_PRJ_VERSION, version))

    def is_valid_py_version(self, version: str) -> bool:
        return bool(regex.match(self._REGEX_PY_VERSION, version))

    def normalize_python_version(self, version: str) -> str:
        # Example
        # - 3 becomes 3.0.0
        # - 3.4 becomes 3.4.0
        # - 3.6.2 stays this way
        # - 3.8.2.1 throws exception, invalid format
        assert self.is_valid_py_version(version)
        version_nums_list = version.split(".")
        assert 0 < len(version_nums_list) < 4
        return ".".join(version_nums_list + ["0"] * (3-len(version_nums_list)))
