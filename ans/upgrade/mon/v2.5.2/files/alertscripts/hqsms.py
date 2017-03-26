#!/usr/bin/env python

import sys
import requests

__USERNAME__ = '@USERNAME@'
__PASSWORD__ = '@PASSWORD@'  # md5 hash
__FROM__ = '@FROM@'


def login_data():
    """
    Login credentials in HQSMS service.
    """
    return {
        'username': __USERNAME__,
        'password': __PASSWORD__,
        'from': __FROM__,
    }


def sms_send(phone, message):
    """
    Send text message.
    """
    data = login_data()
    data['to'] = phone.replace('+', '')
    data['message'] = message

    return requests.post("https://ssl.hqsms.com/sms.do", data)


if __name__ == '__main__':
    if len(sys.argv) < 3:
        sys.stderr.write('Usage: %s <phone> <message>\n' % sys.argv[0])
        sys.exit(1)

    msg = str(' '.join(sys.argv[2:]))
    r = sms_send(sys.argv[1], msg[:160])

    print('%s (%s)' % (r.text, r.status_code))

    if r.status_code == 200 and r.text.startswith('OK:'):
        sys.exit(0)

    sys.exit(1)
