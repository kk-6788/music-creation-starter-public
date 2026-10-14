"""Run the installed vendor API with this PC's verified Windows memory policy."""
from functools import wraps
from pathlib import Path
import sys


def configure_handler(handler_class):
    """Request vendor INT8 and refuse its silent fallback to full-size weights."""
    initialize = handler_class.initialize_service

    @wraps(initialize)
    def initialize_int8(self, *args, **kwargs):
        kwargs['quantization'] = 'int8_weight_only'
        result = initialize(self, *args, **kwargs)
        if result[1] and self.quantization != 'int8_weight_only':
            raise RuntimeError('INT8 初始化未生效，请查看模型日志；为避免内存峰值，不继续加载完整精度模型。')
        return result

    handler_class.initialize_service = initialize_int8


def main():
    # The launcher sets cwd to the existing ACE-Step checkout. Import its source
    # rather than an unrelated globally installed package with the same name.
    sys.path.insert(0, str(Path.cwd()))
    from acestep.handler import AceStepHandler
    configure_handler(AceStepHandler)
    from acestep.api_server import main as run_api
    run_api()


if __name__ == '__main__':
    main()
