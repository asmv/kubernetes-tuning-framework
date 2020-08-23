from .. import _configurator_base

class TargetConfigurator(_configurator_base.Configurator):

    def __init__(self, client: 'DBClient'):
        super().__init__()
        self.client = client 
        self.open_temp_dirs = []