"""Protect the tested Windows GPU profile and fail on silent BF16 fallback."""
import importlib.util
from pathlib import Path
import unittest

ROOT=Path(__file__).resolve().parents[1]

def load_script(name):
    spec=importlib.util.spec_from_file_location(name,ROOT/'scripts'/f'{name}.py')
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

class EngineProfileTests(unittest.TestCase):
    def test_launcher_uses_tested_memory_policy(self):
        env=load_script('start_music').engine_environment(Path('runtime'))
        self.assertEqual(env['ACESTEP_OFFLOAD_TO_CPU'],'true')
        self.assertEqual(env['ACESTEP_OFFLOAD_DIT_TO_CPU'],'false')
        self.assertEqual(env['ACESTEP_INIT_LLM'],'true')
        self.assertEqual(env['CUDA_LAUNCH_BLOCKING'],'1')

    def test_quantization_keeps_original_initialization_and_parameters(self):
        class Handler:
            def initialize_service(self,**kwargs):
                self.received=kwargs
                self.quantization=kwargs['quantization']
                return 'ready',True
        load_script('run_engine').configure_handler(Handler)
        handler=Handler()
        self.assertEqual(handler.initialize_service(device='auto',compile_model=False),('ready',True))
        self.assertEqual(handler.received,dict(device='auto',compile_model=False,quantization='int8_weight_only'))

    def test_silent_quantization_fallback_stops_startup(self):
        class Handler:
            def initialize_service(self,**kwargs):
                self.quantization=None
                return 'ready',True
        load_script('run_engine').configure_handler(Handler)
        with self.assertRaisesRegex(RuntimeError,'INT8'):
            Handler().initialize_service()

    def test_original_initialization_failure_is_preserved(self):
        class Handler:
            def initialize_service(self,**kwargs):return 'model unavailable',False
        load_script('run_engine').configure_handler(Handler)
        self.assertEqual(Handler().initialize_service(),('model unavailable',False))

if __name__=='__main__':unittest.main()
