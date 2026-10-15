import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location('jarvis_stage_linux',Path(__file__).with_name('stage-linux.py'))
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
stage=module.stage
