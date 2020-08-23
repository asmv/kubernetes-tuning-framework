from typing import List, Dict

import subprocess
import uuid
import os
from kubernetes import client, config, stream
# import tempfile
from enum import Enum
import time
import yaml
import json
import docker
import random
import warnings
import tqdm

# FIXME: Remove since this is not a small set of possible values and app != application
class IdentifierType(Enum):
    app = "app"
    application = "application"
    name = "name"

class KubeApi:

    def __init__(self, api_client=None):
        self.api_client = api_client

    def __enter__(self):
        return client.CoreV1Api(api_client=self.api_client)

    def __exit__(self, type, value, traceback):
        if traceback:
            raise Exception(traceback)

# TODO: Determine if this should be more narrowwly scoped/ per class, etc
docker_client = docker.client.from_env()

class KubeContext:

    STATEFULSET_WAIT = "8m"
    DEPLOYMENT_WAIT = "8m"

    def __init__(self):
        config.load_kube_config()

    PREFIX = "experiment-"

    def _create_namespace(self):
        # https://github.com/kubernetes-client/python/issues/613#issuecomment-429425777
        with KubeApi() as ka:
            self.namespace = ka.create_namespace(client.V1Namespace(metadata=client.V1ObjectMeta(name="{0}{1}".format(self.PREFIX, str(uuid.uuid4())))))
        self.namespace_name = self.namespace.metadata.name
        print(self.namespace_name)

    def command_prefix_for_subprocess(self, namespaced=True):
        return ["kubectl", "--namespace", self.namespace_name] if namespaced else ["kubectl"]

    def __enter__(self):
        # Configure Kind Cluster
        self._create_namespace()       
        return self

    def kubectl_subprocess(self, command, encoding="UTF-8", namespaced=True):
        if type(command) is str:
            command = " ".join(self.command_prefix_for_subprocess(namespaced=namespaced)) + command
            output = subprocess.run(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        else:
            command = self.command_prefix_for_subprocess(namespaced=namespaced) + command
            output = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if output.returncode != 0:
            raise RuntimeError(output.stderr.decode(encoding))
        return output.stdout.decode(encoding)

    def get_pod_ids_for_identifier(self, pod_fetch_dict: Dict[str, IdentifierType]):
        with KubeApi() as ka:
            namespaced_pods = ka.list_namespaced_pod(self.namespace_name, watch=False).items
        ids = {}
        for identifier_value, identifier_type in pod_fetch_dict.items():
            ids[identifier_value] = []
            for pod in namespaced_pods:
                if identifier_type.value in pod.metadata.labels:
                    if pod.metadata.labels[identifier_type.value] == identifier_value:
                        ids[identifier_value].append(pod.metadata.name)
        return ids

    def copy_to_pod(self, pod_id: str, source_filepath: str, destination_filepath: str):
        # Requires tar command installed in pod
        # TODO: See if this command is possible to do with Kubernetes API (was unable to find example)
        self.kubectl_subprocess(["cp", source_filepath, "{0}:{1}".format(pod_id, destination_filepath)])

    def run_command(self, pod_id: str, command: List[str]):
        # Follows example from here: https://github.com/kubernetes-client/python/blob/master/examples/pod_exec.py
        # TODO: The example streams the output, determine if necessary.
        with KubeApi() as ka:
            return stream.stream(ka.connect_get_namespaced_pod_exec, pod_id, self.namespace_name, command=command, stderr=True, stdin=False, stdout=True, tty=False)

    # TODO: Use the Kubernetes API instead: https://github.com/kubernetes-client/python
    #    Example here: https://github.com/kubernetes-client/python/blob/master/examples/deployment_create.py
    def apply_kubectl_yaml_config(self, config_file_or_dir: str, wait_for_ready: bool=True, namespaced=True):
        if os.path.isdir(config_file_or_dir) and "kustomization.yaml" in os.listdir(config_file_or_dir):
             # TODO: try using the API here
            apply_command = ["apply", "-k", config_file_or_dir]
            print("applying kustomization file:", os.path.join(config_file_or_dir, "kustomization.yaml"))
        else:
            apply_command = ["apply", "-f", config_file_or_dir]
            print("applying yaml file:", config_file_or_dir)
        self.kubectl_subprocess(apply_command, namespaced=namespaced) # FIXME: This appears to change permissions on the kustomization directory to user 999
        if wait_for_ready:
            time.sleep(1) # Sometimes helps if extended
            self.kubectl_wait_for(config_file_or_dir)

    def _sts_wait(self, statefulset_name, statefulset_replica_count, max_wait="2m"):
        # If we are in this function, then we already know the statefulset exists or should exist shortly. Not sure if there's a more elegant solution for this.
        while statefulset_name not in self.kubectl_subprocess(["get", "statefulsets", "-o", "jsonpath={.items[*].metadata.name}"]).split(" "):
            time.sleep(0.5)
        wait_commands = [["wait", "--timeout", max_wait, "--for=condition=Ready", "pod", "{0}-{1}".format(statefulset_name, i)] for i in range(statefulset_replica_count)]
        for wait_command in tqdm.tqdm(wait_commands, desc="Waiting for StatefulSet {0} in namespace {1}".format(statefulset_name, self.namespace_name)):
            self.kubectl_subprocess(wait_command)

    def _wait_for_statefulsets(self, json_resource_list, max_wait="2m"):
        split_output = [(j["metadata"]["name"], int(j["spec"]["replicas"])) for j in json_resource_list if j["kind"] == "StatefulSet"]
        for statefulset_name, replica_count in split_output:
            try:
                self._sts_wait(statefulset_name, replica_count, max_wait=max_wait)
            except RuntimeError:
                raise TimeoutError("Timed out waiting for StatefulSet {0} in namespace {1}. StatefulSet logs:\n{2}".format(
                statefulset_name,
                self.namespace_name,
                self.kubectl_subprocess(["logs", "statefulset/{0}".format(statefulset_name)])
            ))

    def _deployment_wait(self, deployment_name, max_wait="2m"):
        self.kubectl_subprocess(["wait", "--timeout", max_wait, "--for=condition=Available", "deployment/"+deployment_name])

    def _wait_for_deployments(self, json_resource_list, max_wait="2m"):
        split_output = [j["metadata"]["name"] for j in json_resource_list if j["kind"] == "Deployment"]
        for deployment_name in split_output:
            try:
                self._deployment_wait(deployment_name, max_wait=max_wait)
            except RuntimeError:
                raise TimeoutError("Timed out waiting for Deployment {0} in namespace {1}. Deployment logs:\n{2}".format(
                    deployment_name,
                    self.namespace_name,
                    self.kubectl_subprocess(["logs", "deployment/{0}".format(deployment_name)])
                ))

    def kubectl_wait_for(self, config_file_or_dir: str):
        if os.path.isdir(config_file_or_dir) and "kustomization.yaml" in os.listdir(config_file_or_dir):
            wait_resource = ["-k", config_file_or_dir]
        else:
            wait_resource = ["-f", config_file_or_dir]
        json_resource_list = json.loads(self.kubectl_subprocess(["get", "-o", "json"] + wait_resource))
        if json_resource_list["kind"] == "List":
            json_resource_list = json_resource_list["items"]
        else:
            json_resource_list = [json_resource_list]
        self._wait_for_deployments(json_resource_list, self.DEPLOYMENT_WAIT)
        self._wait_for_statefulsets(json_resource_list, self.STATEFULSET_WAIT)

    # TODO: Use the correct contextmanager types on these parameters
    # https://www.python.org/dev/peps/pep-0343/
    def __exit__(self, type, value, traceback):
        if traceback:
            self.kind_export_logs()
        print("Deleting namespace:", self.namespace_name)
        self.kubectl_subprocess(["delete", "ns", self.namespace_name, "--grace-period=0", "--force"], namespaced=False)
        # with KubeApi() as ka:
        #     ka.delete_namespace(self.namespace_name, grace_period_seconds=0)

    def kind_export_logs(self, also_warn=True):
        try:
            subprocess.run(["kind", "export", "logs", "--name", "db_hparam_test", "/workspaces/dist_db_testing/logs"])
        except FileNotFoundError:
            warnings.warn("Unable to export Kind logs.")

if __name__ == "__main__":
    with KubeContext() as kc:
        res = kc.command_prefix_for_subprocess()
        print(res)