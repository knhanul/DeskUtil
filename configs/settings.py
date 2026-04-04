import importlib
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_TARGET = 'posid'
TARGET_MODULES = {
    'posid': 'configs.target_posid',
    'qamate': 'configs.target_qamate',
    'nuni': 'configs.target_nuni',
}


def _load_target():
    build_target = os.environ.get('BUILD_TARGET', DEFAULT_TARGET).strip().lower()
    module_name = TARGET_MODULES.get(build_target, TARGET_MODULES[DEFAULT_TARGET])
    module = importlib.import_module(module_name)
    target = dict(module.TARGET)
    target['BUILD_TARGET'] = build_target if build_target in TARGET_MODULES else DEFAULT_TARGET
    target['BASE_DIR'] = BASE_DIR
    target['ASSET_DIR_PATH'] = BASE_DIR / target['ASSET_DIR']
    target['LOGO_FILE_NAME'] = f"{target['BUILD_TARGET']}_logo.png"
    if 'ICON_FILE_NAME' not in target:
        target['ICON_FILE_NAME'] = 'icon.ico'
    target['LOGO_PATH'] = target['ASSET_DIR_PATH'] / target['LOGO_FILE_NAME']
    target['ICON_PATH'] = target['ASSET_DIR_PATH'] / target['ICON_FILE_NAME']
    return target


SETTINGS = _load_target()
