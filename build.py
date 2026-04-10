import argparse
import os
import subprocess
import sys
from pathlib import Path

TARGETS = {
    'posid': {
        'app_name': 'nunidesk',
        'asset_dir': 'assets/posid',
        'icon': 'assets/posid/posid_icon.ico',
    },
    'qamate': {
        'app_name': 'nunidesk',
        'asset_dir': 'assets/qamate',
        'icon': 'assets/qamate/qamate_icon.ico',
    },
    'nuni': {
        'app_name': 'nunidesk',
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
        '--hidden-import',
        'app.tools.pdf_compare',
        '--hidden-import',
        'app.tools.pdf_header_footer_compare',
        '--hidden-import',
        'app.tools.dual_pane_manager',
        '--hidden-import',
        'app.tools.document_search_ui',
        str(project_root / 'main.py'),
    ]
    icon_path = project_root / target['icon']
    if icon_path.exists():
        command[10:10] = ['--icon', str(icon_path)]
    
    # 타겟별 에셋 디렉토리 추가
    asset_dir_path = project_root / target['asset_dir']
    if asset_dir_path.exists():
        add_data_arg = f"{asset_dir_path}{separator}{target['asset_dir']}"
        command[10:10] = ['--add-data', add_data_arg]
    
    # 공통 assets 폴더 추가 (AIResearch.png 포함)
    assets_dir = project_root / 'assets'
    if assets_dir.exists():
        add_data_arg = f"{assets_dir}{separator}assets"
        command[10:10] = ['--add-data', add_data_arg]
    
    subprocess.run(command, cwd=project_root, env=env, check=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=sorted(TARGETS.keys()), required=True)
    args = parser.parse_args()
    build(args.target)
