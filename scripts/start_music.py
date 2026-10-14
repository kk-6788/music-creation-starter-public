"""Start this PC's installed ACE-Step runtime and the LAN creation workspace."""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def engine_environment(runtime):
    env = os.environ.copy()
    env.update({
        'PYTHONUTF8': '1',
        'PYTHONUNBUFFERED': '1',
        'HF_HOME': str(runtime / 'hf-cache'),
        'HF_HUB_DISABLE_TELEMETRY': '1',
        'HF_HUB_OFFLINE': '1',
        'ACESTEP_TMPDIR': str(runtime / 'tmp'),
        'ACESTEP_API_HOST': '127.0.0.1',
        'ACESTEP_API_PORT': '8001',
        'ACESTEP_CONFIG_PATH': 'acestep-v15-turbo',
        'ACESTEP_INIT_LLM': 'true',
        'ACESTEP_NO_INIT': 'false',
        'ACESTEP_LM_MODEL_PATH': 'acestep-5Hz-lm-0.6B',
        'ACESTEP_LM_BACKEND': 'pt',
        'ACESTEP_LM_DEVICE': 'auto',
        'ACESTEP_OFFLOAD_TO_CPU': 'true',
        'ACESTEP_OFFLOAD_DIT_TO_CPU': 'false',
        'CUDA_LAUNCH_BLOCKING': '1',
        'PYTHONFAULTHANDLER': '1',
        'ACESTEP_USE_FLASH_ATTENTION': 'false',
        'ACESTEP_COMPILE_MODEL': 'false',
        'ACESTEP_QUEUE_WORKERS': '1',
        'ACESTEP_API_WORKERS': '1',
    })
    return env


def port_in_use(port):
    with socket.socket() as connection:
        connection.settimeout(1)
        return connection.connect_ex(('127.0.0.1', port)) == 0


def main():
    parser = argparse.ArgumentParser(description='启动 Music Creator 电脑与手机工作台')
    parser.add_argument('--runtime', type=Path, default=PROJECT.parent / 'runtime')
    parser.add_argument('--data-dir', type=Path, default=PROJECT.parent / '作品数据')
    parser.add_argument('--local-only', action='store_true')
    args = parser.parse_args()
    runtime = args.runtime.resolve()
    engine = runtime / 'ACE-Step-1.5'
    python = engine / '.venv' / 'Scripts' / 'python.exe'
    if not python.is_file():
        raise SystemExit('独立模型环境尚未安装完成。请查看使用说明，不会自动安装或更改现有环境。')
    required = ('acestep-v15-turbo/model.safetensors', 'vae/diffusion_pytorch_model.safetensors',
                'Qwen3-Embedding-0.6B/model.safetensors', 'acestep-5Hz-lm-0.6B/model.safetensors',
                'acestep-5Hz-lm-1.7B/model.safetensors')
    missing = [name for name in required if not (engine / 'checkpoints' / name).is_file()]
    if missing:
        raise SystemExit('模型文件尚未齐全：' + ', '.join(missing))
    if port_in_use(8765) or port_in_use(8001):
        raise SystemExit('工作台或模型端口已经被占用。如果已经启动，请使用原来的窗口；请勿重复启动。')
    logs = runtime / 'logs'
    logs.mkdir(parents=True, exist_ok=True)
    (runtime / 'tmp').mkdir(exist_ok=True)
    with (logs / 'engine.log').open('a', encoding='utf-8') as log:
        print('正在加载电脑上的音乐模型，首次加载可能需要几分钟。', flush=True)
        process = subprocess.Popen(
            [str(python), '-X', 'utf8', str(PROJECT / 'scripts' / 'run_engine.py')], cwd=engine,
            env=engine_environment(runtime), stdout=log, stderr=subprocess.STDOUT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        try:
            from app.server import main as run_workspace
            sys.argv = ['music-creator', '--data-dir', str(args.data_dir.resolve())]
            if not args.local_only:
                sys.argv.append('--lan')
            print('保留此窗口以便手机访问；结束使用时按 Ctrl+C。', flush=True)
            print(f'模型加载日志：{logs / "engine.log"}', flush=True)
            run_workspace()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()


if __name__ == '__main__':
    main()
