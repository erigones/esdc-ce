def pair_keys_to_items(items, key):
    """
    Convert the list of key:value dicts (nics or disks) into a dict.
    The key for the new dict is one value of the current dict identified by the
    key parameter. If it does not exist, then the key is the order number in
    the list.
    """
    new_items = {}

    for i, item in enumerate(items):
        new_items[item.get(key, i)] = item

    return new_items


def diff_dict(old, new):
    """
    Compare two dicts and create dict (set_) with new or changed values/keys or
    a list (remove_) of missing keys.
    """
    set_ = {}
    remove_ = []

    for k in new.keys():
        if k in old:  # key exists in both
            if new[k] != old[k]:  # but the value changed
                set_[k] = new[k]
        else:  # something new appeared in new dict
            set_[k] = new[k]

    for k in old.keys():
        if k not in new:  # key from old which was not found in new
            remove_.append(k)  # the remove array is a list of identifiers

    return set_, remove_


def diff_dict_nested(old, new, key, remove_empty=()):
    """
    Compare two dicts of dicts and create lists of values that are different
    (update_) or values that are new (add_) or missing keys (remove_).
    """
    add_ = []
    remove_ = []
    update_ = []

    for k in new.keys():
        if k in old:  # key exists in both
            if new[k] != old[k]:  # some settings have changed
                for i in remove_empty:
                    if i not in new[k] and i in old[k]:
                        new[k][i] = ''
                for i, new_i in new[k].items():  # remove same attributes
                    if i != key and i in old[k] and new_i == old[k][i]:
                        del new[k][i]
                update_.append(new[k])
        else:  # something new appeared in new dict
            add_.append(new[k])

    for k in old.keys():
        if k not in new:  # key from old which was not found in new
            remove_.append(old[k][key])  # the remove array is a list of identifiers

    return add_, remove_, update_
