from logging import getLogger

from core.external.utils import get_third_party_apps_serializer_settings

logger = getLogger(__name__)


def _update_serializer_modules(third_party_app, dc_modules, serializer, default_dc=False):
    logger.info('Updating app %s modules (default_dc: %s).', third_party_app, default_dc)

    # noinspection PyShadowingBuiltins
    for module, field_type in dc_modules:
        serializer.base_fields.update({module: field_type})
        logger.debug('%s has been updated with attribute %s (%s)', serializer.__name__, module,
                     getattr(field_type, 'type_name', field_type))

        if default_dc:
            serializer.default_dc_third_party_modules.append(module)
        else:
            serializer.third_party_modules.append(module)


def _collect_template_data(serializer, dc_settings, settings_templates):
    template_collector = []

    for setting, field_type in dc_settings:
        serializer.base_fields[setting] = field_type
        logger.debug('%s has been updated with attribute %s (%s)', serializer.__name__, setting,
                     getattr(field_type, 'type_name', field_type))

        template = settings_templates.get(setting, 'gui/table_form_field.html')
        template_collector.append((setting, template))
        logger.debug('GUI Form for setting %s will use template: %s' % (setting, template))

    return template_collector


def _update_serializer_settings(third_party_app, dc_settings, serializer, default_dc=False):
    logger.info('Updating app %s settings (default_dc: %s).', third_party_app, default_dc)
    icon = getattr(dc_settings, 'SETTINGS_ICON', 'icon-cogs')
    name = getattr(dc_settings, 'SETTINGS_NAME', third_party_app)

    if default_dc:
        template_collector = _collect_template_data(serializer, dc_settings.DEFAULT_DC_SETTINGS,
                                                    dc_settings.SETTINGS_TEMPLATES)
        serializer.default_dc_third_party_settings.append((third_party_app, template_collector, name, icon))
    else:
        template_collector = _collect_template_data(serializer, dc_settings.DC_SETTINGS, dc_settings.SETTINGS_TEMPLATES)
        serializer.third_party_settings.append((third_party_app, template_collector, name, icon))


def third_party_apps_dc_modules_and_settings(klass):
    """
    Decorator for DcSettingsSerializer class.

    Updates modules and settings fields defined in installed third party apps.
    """
    logger.info('Loading third party apps DC modules and settings.')

    for third_party_app, app_dc_settings in get_third_party_apps_serializer_settings():
        try:
            app_dc_settings.DC_MODULES
        except AttributeError:
            logger.info('Skipping app: %s does not have any DC modules defined.', third_party_app)
        else:
            _update_serializer_modules(third_party_app, app_dc_settings.DC_MODULES, klass)

        try:
            app_dc_settings.DC_SETTINGS
        except AttributeError:
            logger.info('Skipping app: %s does not have any DC settings defined.', third_party_app)
        else:
            _update_serializer_settings(third_party_app, app_dc_settings, klass)

    return klass


def third_party_apps_default_dc_modules_and_settings(klass):
    """
    Decorator for DefaultDcSettingsSerializer class.

    Updates modules and settings fields defined in installed third party apps.
    """
    logger.info('Loading third party apps DEFAULT DC modules and settings.')

    for third_party_app, app_dc_settings in get_third_party_apps_serializer_settings():
        try:
            app_dc_settings.DEFAULT_DC_MODULES
        except AttributeError:
            logger.info('Skipping app: %s does not have any DEFAULT DC modules defined.', third_party_app)
        else:
            _update_serializer_modules(third_party_app, app_dc_settings.DEFAULT_DC_MODULES, klass, default_dc=True)

        try:
            app_dc_settings.DEFAULT_DC_SETTINGS
        except AttributeError:
            logger.info('Skipping app: %s does not have any DEFAULT DC settings defined.', third_party_app)
        else:
            _update_serializer_settings(third_party_app, app_dc_settings, klass, default_dc=True)

    return klass
