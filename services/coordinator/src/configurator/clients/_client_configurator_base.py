from typing import Dict

from .. import _configurator_base

import launch

class ClientConfigurator(_configurator_base.Configurator):

    def __init__(self, target: 'DBTarget'):
        super().__init__()
        self.target = target

    def get_experiment_results(self, config: Dict[str, object], kube_context: launch.KubeContext):
        raise NotImplementedError()
