import os
import sys
from configs.settings import SETTINGS

VERSION = '1.2.0'
RELEASE_DATE = os.environ.get('PDF_COMPARE_RELEASE_DATE', '2025-12-31')
DEVELOPER = SETTINGS['COMPANY_NAME']
APP_NAME = SETTINGS['APP_NAME']
COMPANY_NAME = SETTINGS['COMPANY_NAME']
THEME_COLOR_PRIMARY = SETTINGS['THEME_COLOR_PRIMARY']


def _runtime_base_path():
    try:
        return sys._MEIPASS
    except Exception:
        return str(SETTINGS['BASE_DIR'])


def _candidate_paths(relative_path):
    runtime_base = _runtime_base_path()
    asset_dir = SETTINGS['ASSET_DIR']
    build_target = SETTINGS['BUILD_TARGET']
    legacy_aliases = {
        'posid_logo.png': [f'{asset_dir}/{build_target}_logo.png', f'{asset_dir}/logo.png', 'posid_logo.png'],
        'posid_logo.ico': [f'{asset_dir}/icon.ico', f'{asset_dir}/{build_target}.ico', 'posid_logo.ico'],
        'icon.ico': [f'{asset_dir}/icon.ico', 'posid_logo.ico'],
    }
    raw_candidates = legacy_aliases.get(relative_path, [relative_path, f'{asset_dir}/{relative_path}'])
    return [os.path.join(runtime_base, candidate) for candidate in raw_candidates]


def get_resource_path(relative_path):
    for candidate in _candidate_paths(relative_path):
        if os.path.exists(candidate):
            return candidate
    return _candidate_paths(relative_path)[0]


def get_logo_path():
    for candidate in _candidate_paths('posid_logo.png'):
        if os.path.exists(candidate):
            return candidate
    return None


def get_icon_path():
    for candidate in _candidate_paths('icon.ico'):
        if os.path.exists(candidate):
            return candidate
    return None


def get_timer_gif_path():
    """로딩 다이얼로그용 타이머 GIF 경로 반환"""
    gif_path = os.path.join(_runtime_base_path(), SETTINGS['ASSET_DIR'], 'nuni_timer.gif')
    if os.path.exists(gif_path):
        return gif_path
    # Fallback to direct assets path
    fallback_path = os.path.join(SETTINGS['BASE_DIR'], 'assets', 'nuni_timer.gif')
    if os.path.exists(fallback_path):
        return fallback_path
    return None
