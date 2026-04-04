import argparse
import os
import subprocess
import sys
from pathlib import Path

TARGETS = {
    'posid': {
        'app_name': 'Posid 데스크',
        'asset_dir': 'assets/posid',
        'icon': 'assets/posid/posid_icon.ico',
    },
    'qamate': {
        'app_name': 'QaMate',
        'asset_dir': 'assets/qamate',
        'icon': 'assets/qamate/qamate_icon.ico',
    },
    'nuni': {
        'app_name': 'Nuni',
        'asset_dir': 'assets/nuni',
        'icon': 'assets/nuni/nuni_icon.ico',
    },
}


def build(target_name: str):
    project_root = Path(__file__).resolve().parent
    target = TARGETS[target_name]
    env = os.environ.copy()
    env['BUILD_TARGET'] = target_name
    separator = ';' if os.name == 'nt' else ':'
    command = [
        sys.executable,
        '-m',
        'PyInstaller',
        '--noconfirm',
        '--clean',
        '--windowed',
        '--name',
        target['app_name'],
        '--hidden-import',
        'configs.settings',
        '--hidden-import',
        'configs.target_posid',
        '--hidden-import',
        'configs.target_qamate',
        '--hidden-import',
        'configs.target_nuni',
        str(project_root / 'main.py'),
    ]
    icon_path = project_root / target['icon']
    if icon_path.exists():
        command[10:10] = ['--icon', str(icon_path)]
    asset_dir_path = project_root / target['asset_dir']
    if asset_dir_path.exists():
        add_data_arg = f"{asset_dir_path}{separator}{target['asset_dir']}"
        command[10:10] = ['--add-data', add_data_arg]
    subprocess.run(command, cwd=project_root, env=env, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=sorted(TARGETS.keys()), required=True)
    args = parser.parse_args()
    build(args.target)
