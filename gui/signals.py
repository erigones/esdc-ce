from django.dispatch import Signal
"""
View signals
------------
View signals are generated when the view function is finishing, just before calling the render() function.
"""
VIEW_SIGNAL_ARGS = ('request', 'context')

view_vm_details = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_vm_snapshot = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_vm_backup = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_vm_console = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_vm_monitoring = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_vm_tasklog = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_faq = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_node_list = Signal(providing_args=VIEW_SIGNAL_ARGS)
view_node_details = Signal(providing_args=VIEW_SIGNAL_ARGS)

"""
Partial view signals
--------------------
View signals that are generated for particular purpose to update certain function in view.
"""

"""
Signal that is called when collect_view_data is called, eg. every template generation.
"""
view_data_collected = Signal(providing_args=VIEW_SIGNAL_ARGS)

"""
Signal that is called when generating navigation.
"""
navigation_initialized = Signal(providing_args=['request', 'nav'])

"""
Signal that is to restrict user profile to be company only.
"""
allow_switch_company_profile = Signal(providing_args=['user'])
