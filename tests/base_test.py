from abc import ABC
from src.utils import load_config

class BaseTest(ABC):

    def __init__(self):
        self.models_config = load_config('models.json')
        self.ollama_config = load_config('ollama.json')
        self.model_parameters_config = load_config('modelParameters.json')
        self.tests = load_config('tests.json')

        self.testable_model = self.models_config['testable_model']
        self.evaluator_model = self.models_config['evaluator_model']
        self.api_url = self.ollama_config["api_url"]