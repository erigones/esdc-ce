from django.utils.translation import ugettext as _
from gui.signals import navigation_initialized

STYLE_KEY = 'li_class'
STYLE_KEY_DEFAULT = 'li_class_default'

SYSTEM = {
    'title': _('System'),
    'icon': 'dashboard',
    'url': 'system_overview',
    'active_views': {'system_overview', 'system_settings', 'system_maintenance'},
    'children': [
        {
            'title': _('Overview'),
            'icon': 'dashboard',
            'url': 'system_overview'
        },
        {
            'title': _('Configuration'),
            'icon': 'cogs',
            'url': 'system_settings'
        },
        {
            'title': _('Maintenance'),
            'icon': 'wrench',
            'url': 'system_maintenance'
        },
    ]
}

DATACENTER = {
    'title': _('Datacenter'),
    'icon': 'cloud',
    'url': 'dc_node_list',
    'active_views': {'dc_list', 'dc_node_list', 'dc_storage_list', 'dc_network_list', 'dc_image_list',
                     'dc_template_list', 'dc_iso_list', 'dc_domain_list', 'dc_settings', 'dc_user_list',
                     'dc_group_list', 'dc_user_profile'}
    # 'children': []  # Built on runtime
}

DATACENTER_BASE = [
    {
        'title': _('Datacenters'),
        'icon': 'cloud',
        'url': 'dc_list'
    },

    {
        'title': _('Compute nodes'),
        'icon': 'sitemap',
        'url': 'dc_node_list'
    },

    {
        'title': _('Storages'),
        'icon': 'th',
        'url': 'dc_storage_list'
    },

    {
        'title': _('Networks'),
        'icon': 'retweet',
        'url': 'dc_network_list'
    },

    {
        'title': _('Images'),
        'icon': 'save',
        'url': 'dc_image_list'
    },

    {
        'title': _('Templates'),
        'icon': 'umbrella',
        'url': 'dc_template_list'
    },

    {
        'title': _('ISO Images'),
        'icon': 'play-circle',
        'url': 'dc_iso_list'
    },

    {
        'title': _('Users'),
        'icon': 'user',
        'url': 'dc_user_list',
    },

    {
        'title': _('Groups'),
        'icon': 'group',
        'url': 'dc_group_list'
    },
]

DATACENTER_DNS = {
    'title': _('DNS'),
    'icon': 'globe',
    'url': 'dc_domain_list'
}

DATACENTER_SETTINGS = {
    'title': _('Settings'),
    'icon': 'cogs',
    'url': 'dc_settings'
}

NODES = {
    'title': _('Nodes'),
    'icon': 'sitemap',
    'url': 'node_list',
    'active_views': {'node_list', 'node_details'},
}

SERVERS = {
    'title': _('Servers'),
    'icon': 'hdd',
    'url': 'vm_list',
    'active_views': {'vm_list', 'vm_add'},
    'children': [
        {
            'title': _('Add Server'),
            'icon': 'plus',
            'url': 'vm_add',
        },
    ]
}

MONITORING = {
    'title': _('Monitoring'),
    'icon': 'bar-chart',
    'url': 'monitoring_server_redirect',
    'active_views': {'monitoring'},
    'a_class': 'no-ajax',
    'a_target': '_blank',
}

TASKLOG = {
    'title': _('Task log'),
    'icon': 'tasks',
    'url': 'tasklog',
    'active_views': {'tasklog'},
    'children': [],
}

SUPPORT = {
    'title': _('Support'),
    'icon': 'wrench',
    'url': 'api_docs',
    'active_views': {'api_docs', 'user_guide', 'faq', 'add_ticket'},
    # 'children': []  # Built on runtime
}

SUPPORT_FAQ = {
    'title': _('FAQ'),
    'icon': 'question-sign',
    'url': 'faq'
}

SUPPORT_API_DOCS = {
    'title': _('API Documentation'),
    'icon': 'book',
    'url': 'api_docs'
}

SUPPORT_USER_GUIDE = {
    'title': _('User Guide'),
    'icon': 'book',
    'url': 'user_guide'
}

SUPPORT_ADD_TICKET = {
    'title': _('Add Ticket'),
    'icon': 'wrench',
    'url': 'add_ticket',
}

MORE = {
    'title': _('More'),
    'icon': 'share-alt',
    'url': None,
    'active_views': set(),
    STYLE_KEY_DEFAULT: 'dropdown',
    'a_class': 'no-ajax dropdown-toggle',
}


class Navi(object):
    def __init__(self, request, dc_dns_only=False):
        self.request = request
        dc_settings = request.dc.settings
        user = request.user
        is_admin = user.is_admin(request)  # DCAdmin
        is_staff = user.is_staff  # SuperAdmin

        # Primary menu starts like this:
        if is_admin:
            DATACENTER['children'] = list(DATACENTER_BASE)  # Copy, because it is changed below

            if dc_settings.DNS_ENABLED:
                if dc_dns_only:
                    DATACENTER['children'] = [DATACENTER_DNS]
                else:
                    DATACENTER['children'] += [DATACENTER_DNS]

            if is_staff:
                if not dc_dns_only:
                    DATACENTER['children'] += [DATACENTER_SETTINGS]
                nav = [SYSTEM, DATACENTER, NODES, SERVERS]  # SuperAdmin
            else:
                nav = [DATACENTER, SERVERS]  # DCAdmin

            # Continues with monitoring for DC admins and SuperAdmins
            if dc_settings.MON_ZABBIX_ENABLED:
                nav.append(MONITORING)
        else:
            nav = [SERVERS]  # Normal user (no monitoring section)

        # The task log section is always visible
        nav.append(TASKLOG)

        # The last item is always the support section
        support_base = [SUPPORT_USER_GUIDE, SUPPORT_API_DOCS]

        if dc_settings.FAQ_ENABLED:
            support_children = support_base + [SUPPORT_FAQ]
            SUPPORT['url'] = SUPPORT_FAQ['url']  # The default page when FAQ is enabled is faq
        else:
            support_children = list(support_base)
            SUPPORT['url'] = SUPPORT_API_DOCS['url']  # The default page when FAQ is disabled is api_docs

        if dc_settings.SUPPORT_ENABLED:
            SUPPORT['children'] = support_children + [SUPPORT_ADD_TICKET]
            # The default page when FAQ is disabled and SUPPORT is enabled is add_ticket
            if not dc_settings.FAQ_ENABLED:
                SUPPORT['url'] = SUPPORT_ADD_TICKET['url']
        else:
            SUPPORT['children'] = support_children

        nav.append(SUPPORT)
        navigation_initialized.send(sender=self.__class__, request=request, nav=nav)

        # Save and initialize navigation
        self.navigation = nav
        self.init()

    @staticmethod
    def _reset_section(nav_section):
        nav_section[STYLE_KEY] = nav_section.get(STYLE_KEY_DEFAULT, '')

    @staticmethod
    def _activate_section(nav_section):
        nav_section[STYLE_KEY] += ' active'

    def reset(self):
        # Restore initial state of each navigation item and children items dictionaries
        for item in self.navigation:
            self._reset_section(item)
            for subitem in item.get('dropdown', ()):
                self._reset_section(subitem)

    def init(self):
        if len(self.navigation) > 7:
            # Split navigation into two lists and add the extra navigation into the last menu item as dropdown
            MORE['dropdown'] = self.navigation[5:]
            self.navigation = self.navigation[:5]
            self.navigation.append(MORE)
        self.reset()

    def get_main_nav(self):
        return self.navigation

    def get_secondary_nav(self, section):
        if section:
            # Search section in navigation's active_views
            for item in self.navigation:
                if section in item['active_views']:
                    self._activate_section(item)
                    return item.get('children', [])

                # Search section in subitems if item has a dropdown menu
                for subitem in item.get('dropdown', ()):
                    if section in subitem['active_views']:
                        self._activate_section(item)
                        self._activate_section(subitem)
                        return subitem.get('children', [])

        return []
