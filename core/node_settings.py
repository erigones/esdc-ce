# -*- coding: utf-8 -*-
# Django settings for Danube Cloud project on compute node.

from os import path

PROJECT_DIR = path.abspath(path.join(path.dirname(__file__), '..'))

SECRET_KEY = '-&amp;yqav1*(fqt+#qzq%)!92(ao3qonhn!8n5y9=xy$g8%2w_#=z'

INSTALLED_APPS = ['core']

MIDDLEWARE_CLASSES = ()  # To suppress Django warnings
