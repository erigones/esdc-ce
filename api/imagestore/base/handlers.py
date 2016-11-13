from vms.models import DefaultDc, ImageStore


# noinspection PyUnusedLocal
def imagestore_settings_changed_handler(task_id, dc, old_settings, new_settings):
    """
    DC settings have changed (triggered by dc_settings_changed signal).
    Look for changes of VMS_IMAGE_REPOSITORIES in the default DC
    """
    # noinspection PyUnresolvedReferences
    if dc.id == DefaultDc.id:
        old_img_repositories = old_settings.get('VMS_IMAGE_REPOSITORIES', {})
        new_img_repositories = new_settings.get('VMS_IMAGE_REPOSITORIES', {})

        # We just need to delete cached data of removed image repositories
        if old_img_repositories != new_img_repositories:
            for old_name, old_url in old_img_repositories.items():
                if new_img_repositories.get(old_name, None) != old_url:
                    ImageStore(old_name).delete()
