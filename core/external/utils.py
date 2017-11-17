import logging
import os
import pkgutil
from importlib import import_module

logger = logging.getLogger(__name__)

PROJECT_DIR = None
THIRD_PARTY_APPS_CSS = None
THIRD_PARTY_APPS_JS = None
SETTINGS_THIRD_PARTY_APPS = []
SETTINGS_THIRD_PARTY_MODULES = []
COLLECTED_THIRD_PARTY_APPS_DC_SETTINGS = None
DC_MODULES = None
DC_MODULES_EXTENDED = None
DEFAULT_DC_MODULES = None
DEFAULT_DC_MODULES_EXTENDED = None


def collect_third_party_apps_and_settings(settings):
    """
    Import all modules and its settings in core.external.apps directory during Django settings setup.

    We generate list of third party apps (setting THIRD_PARTY_APPS), and automatically collect all settings defined in
    third party apps modules. Files in the directory have to have the name of the app (_ is replaced with .) and will
    be automatically appended to INSTALLED_APPS setting.
    """
    global SETTINGS_THIRD_PARTY_APPS, SETTINGS_THIRD_PARTY_MODULES, PROJECT_DIR
    PROJECT_DIR = settings['PROJECT_DIR']
    apps_dir = os.path.join(PROJECT_DIR, 'core', 'external', 'apps')

    if settings['THIRD_PARTY_APPS_ENABLED']:
        for _, name, is_pkg in pkgutil.iter_modules([apps_dir]):
            if not is_pkg:
                SETTINGS_THIRD_PARTY_APPS.append(name.replace('_', '.'))
                # noinspection PyShadowingBuiltins
                module = import_module('core.external.apps.' + name)

                for setting in dir(module):
                    if setting == 'DC_MODULES':
                        SETTINGS_THIRD_PARTY_MODULES += getattr(module, setting)
                    elif setting.isupper() and not setting.startswith('_'):
                        settings[setting] = getattr(module, setting)

        settings['COMPRESS_OFFLINE_CONTEXT']['THIRD_PARTY_JS'] = get_third_party_js()
        settings['COMPRESS_OFFLINE_CONTEXT']['THIRD_PARTY_CSS'] = get_third_party_css()

    return SETTINGS_THIRD_PARTY_APPS, SETTINGS_THIRD_PARTY_MODULES


def get_third_party_apps_serializer_settings():
    """
    Get installed third party apps and its serializer configuration (way how to generate modules and settings).

    Look for all available modules and settings defined in dc_settings.py file in all available third party apps.
    Function also stores result in variable (cache) so we do not try to import multiple times.

    @return: list of imported python modules
    @rtype: list
    """
    global COLLECTED_THIRD_PARTY_APPS_DC_SETTINGS

    if COLLECTED_THIRD_PARTY_APPS_DC_SETTINGS is None:
        COLLECTED_THIRD_PARTY_APPS_DC_SETTINGS = []

        for third_party_app in SETTINGS_THIRD_PARTY_APPS:
            logger.debug('Searching for dc_settings.py file to import in app: %s', third_party_app)

            try:
                app_dc_settings = import_module(third_party_app + '.dc_settings')
            except ImportError:
                logger.debug('App: %s does not have any dc_settings.py file.', third_party_app)
            else:
                logger.debug('App: %s dc_settings.py has been successfully imported.', third_party_app)
                COLLECTED_THIRD_PARTY_APPS_DC_SETTINGS.append((third_party_app, app_dc_settings))

    return COLLECTED_THIRD_PARTY_APPS_DC_SETTINGS


def collect_third_party_modules():
    """
    Import all modules for third party apps during Django settings setup.
    """
    global DC_MODULES, DEFAULT_DC_MODULES, DC_MODULES_EXTENDED, DEFAULT_DC_MODULES_EXTENDED

    if DEFAULT_DC_MODULES is None or DC_MODULES is None:
        DC_MODULES = []
        DEFAULT_DC_MODULES = []
        DC_MODULES_EXTENDED = []
        DEFAULT_DC_MODULES_EXTENDED = []

        for third_party_app, app_dc_settings in get_third_party_apps_serializer_settings():
            # noinspection PyShadowingBuiltins
            for module, field_type in getattr(app_dc_settings, 'DC_MODULES', ()):
                DC_MODULES_EXTENDED.append((module, field_type))
                DC_MODULES.append(module)
                DEFAULT_DC_MODULES_EXTENDED.append((module, field_type))
                DEFAULT_DC_MODULES.append(module)

            # noinspection PyShadowingBuiltins
            for module, field_type in getattr(app_dc_settings, 'DEFAULT_DC_MODULES', ()):
                DEFAULT_DC_MODULES_EXTENDED.append((module, field_type))
                DEFAULT_DC_MODULES.append(module)

    return DEFAULT_DC_MODULES


def get_third_party_css():
    """
    Collect stylesheets from third party apps. Used to update base.html template, due to ajax movement.
    """
    global THIRD_PARTY_APPS_CSS

    if THIRD_PARTY_APPS_CSS is None:
        THIRD_PARTY_APPS_CSS = []

        if SETTINGS_THIRD_PARTY_APPS:
            for third_party_app in SETTINGS_THIRD_PARTY_APPS:
                third_party_app = third_party_app.replace('.', '/')
                static_dir = os.path.join(PROJECT_DIR, third_party_app, 'static')
                css_dir = os.path.join(static_dir, third_party_app, 'css')
                logger.debug('Searching recursively for stylesheet files in %s', css_dir)

                if os.path.isdir(css_dir):
                    for directory, dirnames, filenames in os.walk(css_dir):
                        for f in filenames:
                            if f.endswith('.css'):
                                file_in_template = os.path.join(directory.replace(static_dir, '')[1:], f)
                                logger.debug('Found stylesheet file! Updating base.html to load: %s', file_in_template)
                                THIRD_PARTY_APPS_CSS.append(file_in_template)
                else:
                    logger.debug('%s does not exists.', css_dir)

    return THIRD_PARTY_APPS_CSS


def get_third_party_js():
    """
    Collect javascript from third party apps. Used to update base.html template, due to ajax movement.
    """
    global THIRD_PARTY_APPS_JS

    if THIRD_PARTY_APPS_JS is None:
        THIRD_PARTY_APPS_JS = []

        if SETTINGS_THIRD_PARTY_APPS:
            for third_party_app in SETTINGS_THIRD_PARTY_APPS:
                third_party_app = third_party_app.replace('.', '/')
                static_dir = os.path.join(PROJECT_DIR, third_party_app, 'static')
                js_dir = os.path.join(static_dir, third_party_app, 'js')
                logger.debug('Searching recursively for javascript files in %s', js_dir)

                if os.path.isdir(js_dir):
                    for directory, dirnames, filenames in os.walk(js_dir):
                        for f in filenames:
                            if f.endswith('.js'):
                                file_in_template = os.path.join(directory.replace(static_dir, '')[1:], f)
                                logger.debug('Found javascript file! Updating base.html to load: %s', file_in_template)
                                THIRD_PARTY_APPS_JS.append(file_in_template)
                else:
                    logger.debug('%s does not exists.', js_dir)

    return THIRD_PARTY_APPS_JS
