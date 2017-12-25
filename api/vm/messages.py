from django.utils.translation import ugettext_noop as _


LOG_DEF_CREATE = _('Create server definition')
LOG_DEF_UPDATE = _('Update server definition')
LOG_DEF_DELETE = _('Delete server definition')
LOG_DEF_REVERT = _('Revert server definition')

LOG_DISK_CREATE = _('Create server disk definition')
LOG_DISK_UPDATE = _('Update server disk definition')
LOG_DISK_DELETE = _('Delete server disk definition')

LOG_NIC_CREATE = _('Create server NIC definition')
LOG_NIC_UPDATE = _('Update server NIC definition')
LOG_NIC_DELETE = _('Delete server NIC definition')


LOG_VM_CREATE = _('Create server')
LOG_VM_RECREATE = _('Recreate server')
LOG_VM_UPDATE = _('Update server')
LOG_VM_DELETE = _('Delete server')


LOG_BKPDEF_CREATE = _('Create server backup definition')
LOG_BKPDEF_UPDATE = _('Update server backup definition')
LOG_BKPDEF_DELETE = _('Delete server backup definition')

LOG_SNAPDEF_CREATE = _('Create server snapshot definition')
LOG_SNAPDEF_UPDATE = _('Update server snapshot definition')
LOG_SNAPDEF_DELETE = _('Delete server snapshot definition')

LOG_SNAP_CREATE = _('Create snapshot of server\'s disk')
LOG_SNAP_UPDATE = _('Rollback snapshot of server\'s disk')
LOG_SNAP_DELETE = _('Delete snapshot of server\'s disk')
LOG_SNAPS_DELETE = _('Delete snapshots of server\'s disk')
LOG_SNAPS_SYNC = _('Synchronize snapshots of server\'s disk')

LOG_BKP_CREATE = _('Create backup of server\'s disk')
LOG_BKP_UPDATE = _('Restore backup of server\'s disk')
LOG_BKP_DELETE = _('Delete backup of server\'s disk')
LOG_BKPS_DELETE = _('Delete backups of server\'s disk')


LOG_STATUS_CHANGE = _('Status of server changed')
LOG_STATUS_GET = _('Current status of server')

LOG_START = _('Start server')
LOG_START_UPDATE = _('Update and start server')
LOG_START_ISO = _('Start server from CD image')
LOG_START_UPDATE_ISO = _('Update and start server from CD image')
LOG_REBOOT = _('Reboot server')
LOG_REBOOT_UPDATE = _('Update and reboot server')
LOG_REBOOT_FORCE = _('Force server reboot')
LOG_REBOOT_FORCE_UPDATE = _('Update and force server reboot')
LOG_STOP = _('Stop server')
LOG_STOP_UPDATE = _('Update and stop server')
LOG_STOP_FORCE = _('Force server stop')
LOG_STOP_FORCE_UPDATE = _('Update and force server stop')


LOG_MIGRATE = _('Migrate server')
LOG_MIGRATE_DC = _('Migrate server to datacenter')


LOG_QGA_COMMAND = _('Run QGA command')
