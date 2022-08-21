# SEE https://pip.pypa.io/en/stable/user_guide/#using-pip-from-your-program

import subprocess
import sys
import tarfile

from codeontology import *


class Pypi:

    @staticmethod
    def download_python_source(python_version: str):
        pass

    @staticmethod
    def download_project(
            project_name: str,
            project_version: str,
            abs_download_dir: str
    ) -> str:

        if project_version:
            download_target = f"{project_name}=={project_version}"
        else:
            download_target = project_name

        # Create a temporary directory in which to download the source archive
        assert os.path.isdir(abs_download_dir)
        abs_temp_path = os.path.join(abs_download_dir, "temp")
        assert not os.path.isdir(abs_temp_path)
        os.mkdir(abs_temp_path)

        # Download only the project source archive
        process = subprocess.Popen(
            [sys.executable,
             "-m", "pip",
             "download", download_target,
             "-d", abs_temp_path,
             "--no-deps",             # no dependencies
             "--no-binary", ":all:"]  # no distributions, source code
        )
        process.communicate()
        assert process.returncode == 0

        # Find the downloaded source archive
        assert len(os.listdir(abs_temp_path)) == 1
        abs_archive_path = os.path.join(abs_temp_path, os.listdir(abs_temp_path)[0])

        # Open the archive, extract its content in the temporary directory, then delete it
        with tarfile.open(abs_archive_path) as f_archive:
            f_archive.extractall(abs_temp_path)
        os.remove(abs_archive_path)

        # Move the extracted project folder to the download directory
        assert len(os.listdir(abs_temp_path)) == 1
        project_folder = os.listdir(abs_temp_path)[0]
        project_path = shutil.move(os.path.join(abs_temp_path, project_folder), abs_download_dir)
        assert os.path.isdir(project_path) and project_path == os.path.abspath(project_path)

        # Delete the temporary directory
        shutil.rmtree(abs_temp_path)

        # Return the project folder path
        return project_path

    @staticmethod
    def get_project_versions(project_name: str):
        import subprocess
        import sys

        process = subprocess.Popen(
            [sys.executable,
             "-m", "pip",
             "index", "versions", project_name],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )
        out, _ = process.communicate()
        assert process.returncode == 0

        out = str(out).split("\\r\\n")[1]
        assert out.startswith("Available versions: ")
        versions = out.split(": ")[1].split(", ")

        return versions
