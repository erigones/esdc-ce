from api.event import DirectEvent


class UserCurrentDcChanged(DirectEvent):
    """
    The User's current_dc was changed by another user/event and the user's current GUI view may be outdated - #108.
    This is a direct event => it should only go to the Object owner identified by user_id.
    """
    _name_ = 'user_current_dc_changed'
