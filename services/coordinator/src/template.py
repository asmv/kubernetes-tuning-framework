from typing import Dict
import docker
import tempfile
import shutil
import os
import jinja2
import warnings
from distutils import dir_util
import pathlib
import uuid
import tarfile
import subprocess

TEMPDIR_LOC = "/var/tmp/db_hparam_test"

# https://stackoverflow.com/a/273227
import pathlib
pathlib.Path(TEMPDIR_LOC).mkdir(parents=True, exist_ok=True)

# TODO: Determine if this should be more narrowly scoped/ per class, etc
docker_client = docker.client.from_env()

def get_tempdir_from_image(image_name: str, folderpath: str):
    tdir = tempfile.TemporaryDirectory(dir=TEMPDIR_LOC)
    with tempfile.NamedTemporaryFile("wb", suffix=".tar", dir=TEMPDIR_LOC) as tarobject:
        # Shows error `tar: Unexpected EOF in archive` but stiull calculates results as expected
        # TODO: Determine if this is an issue
        image = docker_client.images.get(image_name)
        tarstream, _ = docker_client.containers.create(image).get_archive(folderpath)
        for chunk in tarstream:
            tarobject.write(chunk)
        tarobject.flush()
        tarobject.seek(0)
        subprocess.run(["tar", "xf", tarobject.name, "--strip-components=1", "-C", tdir.name])
        # TODO: Find better way to make sure the user of the extracted temp directory does not own the file in hostpath volume.
        subprocess.run(["chmod", "-R", "777", tdir.name]) # FIXME: change back to ugo+x when done debugging.
    return tdir

def get_tempdir_with_config(config_dir: str, configuration: Dict[str, object]) -> tempfile.TemporaryDirectory:
    tdir = tempfile.TemporaryDirectory(dir=TEMPDIR_LOC)
    dir_util.copy_tree(config_dir, tdir.name, preserve_mode=1) # Looks like this function also removes all tmp folders that don't have references? Confusing behavior.
    template_directory(tdir, configuration)
    return tdir

def get_tempfile_empty(filename: str):
    suffix = "".join(pathlib.PurePath(filename.suffixes))
    return tempfile.NamedTemporaryFile(suffix=suffix, mode="w+", dir=TEMPDIR_LOC)

def get_tempfile_with_config(filename: str, configuration: Dict[str, object]):
    if not filename.endswith(".j2"):
        warnings.warn("File to template does not have j2 extension.")
    suffix = "".join(pathlib.PurePath(filename.strip(".j2")).suffixes)
    tfile = tempfile.NamedTemporaryFile(suffix=suffix, mode="w+", dir=TEMPDIR_LOC)
    with open(filename, mode='r') as templatefile:
        template = jinja2.Template(templatefile.read())
        tfile.write(template.render(configuration))
        tfile.flush() # Check if file has contents.
        tfile.seek(0)
    return tfile

def template_directory(tempdir: tempfile.TemporaryDirectory, configuration: Dict[str, object]):
    for fname in pathlib.Path(tempdir.name).glob("*.j2"):
        with open(fname, "r") as templatefile:
            template = jinja2.Template(templatefile.read())
        with open(str(fname).strip(".j2"), "w") as configured_file:
            configured_file.write(template.render(configuration))

def create_volume_with_contents(tempdir: tempfile.TemporaryDirectory, volume_name: str = None) -> docker.models.volumes.Volume:
    volume = docker_client.volumes.create(volume_name)
    docker_client.containers.run("busybox:latest", "mv /tempdir/* /volume", stdout=True, stderr=True, volumes={
        os.path.abspath(tempdir.path): {"bind": "/tempdir"},
        volume.id: {"bind": "/volume"}
    })
    return volume


if __name__ == "__main__":
    tdir = get_tempdir_from_image("python:3.6", "/run")
    print(tdir)