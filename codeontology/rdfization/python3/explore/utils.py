"""Utilities for Python3 projects and sources handling."""

from __future__ import annotations

from pathlib import Path
import re as regex
import requests
import shutil
import subprocess
import sys
from typing import Dict, List, Set, Tuple

from codeontology import LOGGER


class ProjectHandler:
    """A handler for Python3 projects.

    Allows the download and installation of projects from the 'Python Package Index' (PyPI), along with local projects
     that are properly packaged according to the 'Python Package Authority' (PyPA) specifics. Gives access to PyPI index
     to get available projects and versions. Gives access to projects distribution info.

    Attributes:
        py3_exec (Path): the path to a locally installed 'Python3 executable', used to run 'pip' functionalities.

    """
    py3_exec: Path

    __CONFIG_FILES: Set[str] = ["setup.py", "setup.cfg", "pyproject.toml"]

    def __init__(self, python3_exec: Path = Path(sys.executable)):
        """Create a Python3 project handler.

        Args:
            python3_exec (Path): the path to a locally installed 'Python3 executable', used to run 'pip'
             functionalities. By default it is the same Python3 executable with which this code is running.

        """
        self.py3_exec = python3_exec.resolve().absolute()

    def install_local_project(self, project_dir: Path, install_dir: Path) -> Tuple[str, Path, Path]:
        """Identify the source code of a properly packaged project (according to PyPA specs) and download all of its
         dependencies.

        Args:
            project_dir (Path): the path to the folder containing the project.
            install_dir (Path): the path to the empty folder in which to install and download the dependencies.

        Returns:
            Tuple[str, Path, Path]: a triple indicating respectively the name of the installed project, the
             path to the folder containing the top level packages paths related to the project, and the path to the
             folder containing the top level packages paths related to the project dependencies.

        Raises:
            ValueError: invalid project folder; non empty install directory.
            InstallError: unable to install project; unable to retrieve dependencies.

        Notes:
            This method makes use of the functionalities offered by the 'pip' module, and it has been used accordingly
             to what stated in <https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program>.

        """
        project_dir = project_dir.resolve().absolute()
        install_dir = install_dir.resolve().absolute()

        if not ProjectHandler.is_project_dir(project_dir):
            raise ValueError("Invalid project folder.")
        if install_dir.exists():
            if len(set(install_dir.iterdir())) > 0:
                raise ValueError("Non empty install directory.")
        else:
            install_dir.mkdir()
        install_dir_tmp = install_dir.joinpath("tmp")
        install_dir_tmp.mkdir()

        # TODO should try avoiding 'install' and use 'download' to get the dependencies as stand-alone projects one by
        #  one, since this way OS dependant dependencies (like only for 'Linux' or 'Windows') may be skipped by 'pip'
        #  because of the OS we are running on. Problem is the `pip` `download` option seems highly unreliable!

        # Install only the project (no dependencies), to determine which folders and files are project packages
        command_list = [
            str(self.py3_exec),
            "-m", "pip",
            "install", str(project_dir),
            "-t", str(install_dir_tmp),
            "--no-cache-dir",  # no use of caches
            "--no-deps",  # no dependencies
        ]
        LOGGER.info(f"Installing project in '{install_dir}'.")
        LOGGER.debug(f"Sub-processing command <{' '.join(command_list)}>.")
        process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if process.returncode != 0:
            raise InstallError(f"Unable to install project from '{project_dir}'.")

        # HACK should be better to get the name from the configuration file, but this way it is just easier.
        project_name = regex.search(r"(?<=Successfully installed ).*?(?=\\r\\n)", str(out)).group()
        if " " in project_name:
            raise InstallError(f"Unexpected result! More than one distribution installed: '{project_name}'.")
        # NOTE Focusing only on distribution packages, ignoring 'test' or other kind of development packages
        project_pkg_dirs = ProjectHandler.get_packages_from_installation_dir(install_dir_tmp)
        LOGGER.info(f"Installed project '{project_name}'.")

        # Install the project with its dependencies, to determine which folders and files are dependency packages
        command_list.pop(-1)  # remove the 'no dependencies' option
        LOGGER.info(f"Installing project with its dependencies in '{install_dir}'.")
        LOGGER.debug(f"Sub-processing command <{' '.join(command_list)}>.")
        process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        _, err = process.communicate()
        if process.returncode != 0:
            raise InstallError(f"Unable to install dependencies of project '{project_name}': {str(err)}.")

        # TODO add a way to add dependencies from reading the import statements in the packages. Some modules, like
        #  testing modules, do import libraries that are not declared in the configuration dependencies, since they
        #  contain code supposed to be run only for testing and not for normal use. This way we are missing the chance
        #  to get their triples.
        dependencies_pkg_dirs = ProjectHandler.get_packages_from_installation_dir(install_dir_tmp) - project_pkg_dirs

        # Move the packages and dependencies in ad-hoc folders
        project_pkg_folder = install_dir.joinpath("project")
        assert not project_pkg_folder.exists()
        project_pkg_folder.mkdir()
        for file in project_pkg_dirs:
            file.rename(project_pkg_folder.joinpath(file.name))
        dependencies_pkg_folder = install_dir.joinpath("dependencies")
        assert not dependencies_pkg_folder.exists()
        dependencies_pkg_folder.mkdir()
        for file in dependencies_pkg_dirs:
            file.rename(dependencies_pkg_folder.joinpath(file.name))
        shutil.rmtree(install_dir_tmp)

        return project_name, project_pkg_folder, dependencies_pkg_folder

    def get_local_project_name(self, project_dir: Path) -> str:
        """Get the name of a local project.

        Args:
            project_dir (Path): the path to the folder containing the project.

        Returns:
            str: the name of the local project.

        Raises:
            ValueError: invalid project folder.
            InstallError: unable to retrieve name.

        Notes:
            This method makes use of the functionalities offered by the 'pip' module, and it has been used accordingly
             to what stated in <https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program>.

        """
        project_dir = project_dir.resolve().absolute()

        if not ProjectHandler.is_project_dir(project_dir):
            raise ValueError("Invalid project folder.")

        # Make a fake install of the project, to determine its name
        command_list = [
            str(self.py3_exec),
            "-m", "pip",
            "install", str(project_dir),
            "--no-cache-dir",  # no use of caches
            "--no-deps",  # no dependencies
            "--dry-run",  # fake install process
        ]
        LOGGER.info(f"Retrieving project name.")
        LOGGER.debug(f"Sub-processing command <{' '.join(command_list)}>.")
        process = subprocess.Popen(command_list, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = process.communicate()
        if process.returncode != 0:
            raise InstallError(f"Unable to retrieve project name from '{project_dir}'.")

        # HACK should be better to get the name from the configuration file, but this way it is just easier.
        project_name = regex.search(r"(?<=Would install ).*?(?=\\r\\n)", str(out)).group()
        if " " in project_name:
            raise InstallError(f"Unexpected result! More than one distribution installed: '{project_name}'.")

        return project_name

    def download_source_from_pypi(self, project_target: str, download_dir: Path) -> Path:
        """Downloads the source code of a Python3 project from the PyPI index.

        Args:
            project_target (str): the name of the project in the index, eventually with the specific version, such as
             '<project_name>' or '<project_name>==<version>' (using the 'version matching' clause, '==').
            download_dir (Path): the path to the folder in which to download the project source.

        Returns:
            Path: the path to the folder that will contain the source code of the project.

        Raises:
            ValueError: invalid download directory, project name or version.
            DownloadError: unable to download from PyPI.

        Notes:
            This method makes use of the download functionality offered by the 'pip' module, which seems to be not very
             reliable. The 'download' option for the source code seems to trigger some unwanted and unexpected build
             steps that may bring to a fail, even where the 'install' option would succeed! Check the link
             <https://github.com/pypa/pip/issues/8387> and <https://github.com/pypa/pip/issues/7995>.
            We don't just use the 'install' option because it does not provide the source version of the code, not
             providing the 'configuration' file or other 'test' folders that may be of interest.
            The 'pip' module has been used accordingly to what stated in
             <https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program>.

        """
        download_dir = download_dir.resolve().absolute()

        # Split the target in name and version of the project
        project_target += "=="
        project_name, project_version = project_target.split("==")[:2]

        # Check input
        if not download_dir.is_dir():
            raise ValueError(f"Specified folder '{download_dir}' is not a valid directory.")
        if not ProjectHandler.is_valid_project_name(project_name):
            raise ValueError(f"Invalid project name '{project_name}' in specified target '{project_target}'.")
        available_versions = self.get_project_versions(project_name)
        if not available_versions:
            raise ValueError(f"Project name '{project_name}' not available from PyPI.")
        if project_version and project_version not in available_versions:
            raise ValueError(f"Specified project version '{project_version}' not available from PyPI.")
        if not project_version:
            project_version = available_versions[0]

        # Download only the project source archive
        download_target = f"{project_name}=={project_version}"
        pre_download_dir_content = set(download_dir.iterdir())
        command_list = [
            str(self.py3_exec),
            "-m", "pip",
            "download", download_target,
            "-d", str(download_dir),
            "--no-deps",  # no dependencies
            "--no-binary", ":all:",  # no distributions, source code
            "--no-cache-dir",  # no use of caches, no track of the download on your venv
        ]
        LOGGER.info(f"Downloading '{download_target}' sources in '{download_dir}'.")
        LOGGER.debug(f"Sub-processing command <{' '.join(command_list)}>.")
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        _, _ = process.communicate()
        if process.returncode != 0:
            raise DownloadError(
                f"Unable to download '{download_target}' from PyPI as source. Probably only wheels packages"
                f" are available. Try to manually download the source code and try again with the `local` option."
            )

        # Find the downloaded source archive
        archive_path = set(download_dir.iterdir()) - pre_download_dir_content
        assert len(archive_path) == 1
        archive_path = archive_path.pop()

        # Extract the archive content then delete it
        shutil.unpack_archive(archive_path, download_dir)
        archive_path.unlink()
        source_path = set(download_dir.iterdir()) - pre_download_dir_content
        assert len(source_path) == 1
        source_path = source_path.pop()

        return source_path

    @staticmethod
    def get_config_file_content(project_dir: Path) -> Dict:
        """Reads the configuration file/s of a project to extract the distribution info.

        !!! Actually unused

        Args:
            project_dir (Path): the path to the folder containing the project.

        Returns:
            Dict: a dictionary containing an entry for each of the keywords specified in the project configuration file.
            Allowed keywords for the 'setup.py' file can be found at
             <https://setuptools.pypa.io/en/latest/references/keywords.html>.
            The 'pyproject.toml' is not yet supported.

        Raises:
            SetupReadingError: unable to securely read the setup file.

        Notes:
            Actually unused, but may be useful, or even of better use, in those parts where some information is
             extracted looking at the 'pip' module output.

        """
        from contextlib import contextmanager
        from importlib import import_module
        import os
        import setuptools
        import sys
        from unittest import mock

        @contextmanager
        def safe_setup_read(setup_dir: Path):
            # Backup os.cwd, sys.stdout, sys.stderr
            saved_cwd = os.getcwd()
            saved_stdout, saved_stderr = sys.stdout, sys.stderr
            # Add current setup directory to sys.path to find it on import
            sys.path.insert(0, str(setup_dir))

            # Move to setup directory and deactivate output prints
            os.chdir(str(setup_dir))
            sys.stdout = sys.stderr = open(os.devnull, "w")

            try:
                yield

            finally:
                # Restore previous values
                os.chdir(saved_cwd)
                sys.stdout, sys.stderr = saved_stdout, saved_stderr
                sys.path = sys.path[1:]
                if sys.modules.get("setup", None):
                    # Delete the imported module from the cache to not retrieve it again when we try to import other
                    #  setups for other projects
                    del sys.modules["setup"]

        project_dir = project_dir.resolve().absolute()

        # Use mocking and a context manager to read the setup file content securely
        # SEE mocking at https://stackoverflow.com/a/24236320/13640701
        # SEE context manager at https://stackoverflow.com/a/37996581/13640701
        # SEE stop setup prints at https://stackoverflow.com/a/10321751/13640701
        setup_path = project_dir.joinpath(f"setup.py")
        config_dict = dict()
        LOGGER.info(f"Reading setup file '{setup_path}'.")
        if setup_path.exists():
            with safe_setup_read(project_dir), \
                    mock.patch.object(setuptools, "setup") as mock_setup:
                try:
                    # IDEA Another option could be to use subprocess to read it
                    import_module("setup")
                    assert mock_setup.called
                    # Get the args passed to the mock object faking the 'setuptools.setup' needed for a real setup
                    _, config_dict = mock_setup.call_args
                    # conf_dict = read_configuration(self.__PROJECT_CONF_FILE)  # may be useful, but not yet
                except Exception as e:
                    LOGGER.warning(f"Bare except clause with observed type '{type(e)}' in `get_config_file_content`.")
                    raise SetupReadingError(f"Unable to securely read the '{setup_path.resolve().absolute()}' file"
                                            f" content.")

        return config_dict

    @staticmethod
    def is_project_dir(folder_path: Path) -> bool:
        """Identifies a folder as a Python3 project folder.

        Note:
            The principle used to identify a project is the presence of the configuration file in the specified folder.
             The most popular configuration files are 'setup.py/setup.cfg' and 'pyproject.toml'

        Args:
            folder_path (Path): a path to an existing folder.

        Returns:
            bool: `True` for a Python3 project, `False` otherwise.

        Raises:
            ValueError: nonexistent folder.

        """
        folder_path = folder_path.resolve().absolute()
        if not folder_path.exists():
            raise ValueError(f"Nonexistent folder '{folder_path}'.")
        for file in folder_path.iterdir():
            if file.name in ProjectHandler.__CONFIG_FILES:
                return True
        return False

    @staticmethod
    def is_valid_project_name(project_name: str) -> bool:
        """Determines if a project name is a valid one, according to PyPI specifics.

        Args:
            project_name (str): the only name of the project (no version).

        Returns:
            bool: `True` if the name respects the naming conventions, `False` otherwise.

        Notes:
            Check the link <https://packaging.python.org/en/latest/tutorials/packaging-projects/> to know more about the
             naming conventions.

        """
        return bool(regex.match(r"[a-zA-Z][a-zA-Z0-9._\-]*", project_name))

    def is_existing_project(self, project_name: str, project_version: str = "") -> bool:
        """Determines whether a project (with a optional specifiable version) exists on PyPI.

        Args:
            project_name (str): the name of the project on PyPI.
            project_version (str): the specific version of interest of the project.

        Returns:
            bool: `True` if the the project, eventually with that specified version, exists on PyPI; `False` otherwise.

        Raises:
            PipError: unable to communicate with PyPI.

        """
        available_versions = self.get_project_versions(project_name)
        # return available_versions and ((project_version in available_versions) if project_version else True)
        if available_versions:
            if project_version:
                return project_version in available_versions
            else:
                return True
        else:
            return False

    def get_project_versions(self, project_name: str) -> List[str]:
        """Get the available version of the project from PyPI.

        Args:
            project_name (str): the name of the project in the PyPI index.

        Returns:
            List[str]: the list of identified project versions.

        Raises:
            PipError: unable to communicate with PyPI.

        Notes:
            This method makes use of the functionalities offered by the 'pip' module, and it has been used accordingly
             to what stated in <https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program>.

        """
        command_list = [
            str(self.py3_exec),
            "-m", "pip",
            "index", "versions", project_name
        ]
        LOGGER.info(f"Accessing availables '{project_name}' versions.")
        LOGGER.debug(f"Sub-processing command <{' '.join(command_list)}>.")
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, _ = process.communicate()

        if process.returncode != 0:
            raise PipError(f"Unable to communicate with PyPI about project '{project_name}'.")

        versions = []
        if process.returncode == 0:
            out = str(out).split("\\r\\n")[1]
            assert out.startswith("Available versions: ")  # TODO change with raise
            versions = out.split(": ")[1].split(", ")

        return versions

    @staticmethod
    def get_packages_from_installation_dir(install_dir: Path) -> Set[Path]:
        """Identifies the installed packages from an installation directory.

        Args:
            install_dir (Path): the directory in which the distributions have been installed.

        Returns:
            Set[Path]: the set of identified installed distributions.

        Raises:
            InstallError: impossible to find packages related to distribution.

        """
        install_dir = install_dir.resolve().absolute()
        installed_distr_paths: Set[Path] = set()

        # Scroll all the files in the installation directory
        for file in install_dir.iterdir():
            # The `pip install` command creates some folders ending with '-info' that are not Python packages and
            #  instead contain metadata about the installed distribution. We can leverage this folders!
            if file.name.endswith("-info"):
                assert file.is_dir()
                lib_distr_paths = set()
                # We scroll all the metadata files.
                for metadata_file in file.iterdir():
                    # One of the metadata files could be 'RECORD', that should report a list of all the files
                    #  installed for the distribution. We can then extract the top level packages paths from there.
                    if metadata_file.name == "RECORD":
                        with open(metadata_file, "r", encoding="utf8") as f:
                            for line in f.readlines():
                                line = line.strip()
                                if line:
                                    # Every non-empty line has 3 entries: '<installed file path>,<hash>,<#bytes>'.
                                    rel_path = Path(line.split(",")[0])
                                    # A file is surely a top level package
                                    if len(rel_path.parents) == 1:
                                        if rel_path.suffix == ".py":
                                            lib_distr_paths.add(install_dir.joinpath(rel_path))
                                    # A folder is a top level package only if it is not a cache folder, a folder with
                                    #  metadata and has a valid package name
                                    else:
                                        rel_path_root = list(rel_path.parents)[-2]
                                        if not rel_path_root.name.startswith("_") and \
                                                not rel_path_root.name.startswith(".") and \
                                                not rel_path_root.name.endswith("-info") and \
                                                is_valid_package_name(rel_path_root.name):
                                            lib_distr_paths.add(install_dir.joinpath(rel_path_root))
                    # Another metadata file could be 'top_level.txt', that should indicate only the top level
                    #  package names installed for the distribution. We can then infer the top level packages paths.
                    if metadata_file.name == "top_level.txt":
                        with open(metadata_file, "r", encoding="utf8") as f:
                            for line in f.readlines():
                                top_package_name = line.strip()
                                if top_package_name:
                                    package_path_folder = install_dir.joinpath(top_package_name)
                                    if package_path_folder.exists():
                                        lib_distr_paths.add(package_path_folder)
                                    package_path_file = install_dir.joinpath(top_package_name + ".py")
                                    if package_path_file.exists():
                                        lib_distr_paths.add(package_path_file)

                # If we found none of the useful metadata files, we infer the top level packages paths from the name of
                #  the metadata folder.
                if not lib_distr_paths:
                    package_dir = install_dir.joinpath(file.name.split("-")[0])
                    package_file = install_dir.joinpath(file.name.split("-")[0] + ".py")
                    if package_dir.exists():
                        installed_distr_paths.add(package_dir)
                    if package_file.exists():
                        installed_distr_paths.add(package_file)
                    if not package_dir.exists() and not package_file.exists():
                        raise InstallError(f"Impossible to find packages related to distribution info in '{file}'.")
                else:
                    for path in lib_distr_paths:
                        installed_distr_paths.add(path)

        return installed_distr_paths


class PySourceHandler:
    """A handler for Python3 source code.

    Allows the download of the source code for various Python3 distributions, to find the available versions and to
     validate the format of a potential version.

    """
    __norm_python_versions: List[str]

    __REGEX_PY3_VERSION: str = r"[3](\.[0-9]+){0,2}"

    def __init__(self):
        self.__norm_python_versions = list()
        self.get_norm_python_versions()

    @staticmethod
    def is_valid_py_version(version: str) -> bool:
        """Checks if the specified version respects the format of a Python3 version, i.e. `3.x.y`, where `x` and `y` are
        optional version numbers.

        Args:
            version (str): a version string.

        Returns:
            bool: `True` for a potentially valid Python3 version string (respecting the format), `False` otherwise.

        """
        return bool(regex.match(PySourceHandler.__REGEX_PY3_VERSION, version))

    @staticmethod
    def normalize_python_version(version: str) -> str:
        """Converts any string representing a properly formatted Python3 version to the normalized full format '3.x.y'.

        Args:
            version (str): a potentially valid Python version.

        Returns:
            str: the specified Python3 version in a full '3.x.y' format.

        Raises:
            ValueError: invalid Python3 version format.

        """
        if PySourceHandler.is_valid_py_version(version):
            version_nums_list = version.split(".")
            return ".".join(version_nums_list + ["0"] * (3 - len(version_nums_list)))
        else:
            raise ValueError("Invalid Python3 version format.")

    def download_python_source(self, python_version: str, download_dir: Path) -> Path:
        """Downloads the source code for a specific Python3 version.

        Args:
            python_version (str): Python3 version to download.
            download_dir (Path): the path to the folder in which to download the Python3 source.

        Returns:
            Path: the path to the folder containing the source code.

        Raises:
            ValueError: invalid version format or unknown version.
            DownloadError: unable to download source.

        """
        python_version = self.normalize_python_version(python_version)
        download_dir = download_dir.resolve().absolute()

        if not self.is_valid_py_version(python_version):
            raise ValueError(f"Specified version '{python_version}' has an invalid format.")
        python_version = self.normalize_python_version(python_version)
        if python_version not in self.__norm_python_versions:
            raise ValueError(f"Specified Python version '{python_version}' is unknown.")

        # Request the source archive
        download_url = f"https://www.python.org/ftp/python/{python_version}/Python-{python_version}.tgz"
        response = requests.get(download_url)
        if not response.status_code == 200:
            raise DownloadError(f"Unable to find the specified Python version '{python_version}', something went"
                                f" wrong.")

        # Store the requested archive
        archive_path = download_dir.joinpath(f"python-{python_version}.tgz")
        with open(archive_path, "wb") as f:
            f.write(response.content)

        # Extract and delete the archive
        shutil.unpack_archive(archive_path, download_dir)
        archive_path.unlink()

        # Store only the 'Lib' folder with the standard library packages
        extracted_path = download_dir.joinpath(f"Python-{python_version}")
        assert extracted_path.exists(), \
            f"Wrong assumption on Python3 source naming, '{extracted_path}' does not exist."  # TODO change with raise
        stdlib_path = extracted_path.joinpath("Lib")
        assert stdlib_path.exists(), \
            f"Wrong assumption on Python3 standard library location, '{stdlib_path}' does not exist."  # TODO change with raise
        source_path = download_dir.joinpath(f"python-source-{python_version}")
        stdlib_path.rename(source_path)
        shutil.rmtree(extracted_path)

        return source_path

    def get_norm_python_versions(self) -> List[str]:
        """Get all the known available Python3 versions for download.

        Returns:
            List[str]: the list of known Python3 versions available to download.
        """
        if not self.__norm_python_versions:
            releases_url = "https://www.python.org/downloads/"
            regex_html_release = r'<a href="/downloads/release/python-[0-9]+/">Python (' \
                                 r'[3](\.[0-9]+){0,2}' \
                                 r')</a>'
            response = requests.get(releases_url)
            releases_html = str(response.content)
            self.__norm_python_versions = list()
            for release_match in regex.finditer(regex_html_release, releases_html):
                released_version = regex.search(self.__REGEX_PY3_VERSION + r'(?=<)',
                                                release_match.group(0)).group(0)
                assert released_version == self.normalize_python_version(released_version), \
                    f"Wrong assumption, '{released_version}' is not normalized"  # TODO change with raise
                self.__norm_python_versions.append(released_version)
        return self.__norm_python_versions

    @staticmethod
    def get_py_executable_version(py3_exec: Path) -> str:
        """Get the Python3 version from a Python3 executable file.

        Args:
            py3_exec (Path): the path to a locally installed 'Python3 executable'.

        Returns:
            str: a string representing the Python3 version, something like '3.x.y'.

        Raises:
            PipError: Unable to read Python3 version.

        """
        command_list = [
            str(py3_exec),
            "-V"
        ]
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        out, _ = process.communicate()
        if process.returncode != 0:
            raise PipError(f"Unable to read Python3 version from '{py3_exec}' executable.")

        return regex.search(r"(?<=Python )3(\.\d+){,2}", str(out)).group()


def is_valid_package_name(package_name: str) -> bool:
    """Tells whether or not a string could represent a valid package name.

    Args:
        package_name (str): the string representing the potential name of the package.

    Returns:
        bool: `True` for a valid package name, `False` otherwise.

    """
    return bool(regex.match(r"^[A-Za-z_]+$", package_name))


class PipError(Exception):
    """Generic Error during the use of pip."""
    pass


class InstallError(Exception):
    """Error during the installation of Python libraries."""
    pass


class DownloadError(Exception):
    """Error during the download of Python libraries."""
    pass


class SetupReadingError(Exception):
    """Error during the parsing/reading of Python setup files."""
    pass
