from logging import getLogger
from django.conf import settings as django_settings
from django.core.mail import EmailMessage
from django.core.mail.backends.smtp import EmailBackend
from django.template.loader import render_to_string
from django.utils import translation, timezone

from core.version import __version__
from vms.models import DefaultDc

logger = getLogger(__name__)


# noinspection PyAbstractClass
class SMTPEmailBackend(EmailBackend):
    """
    Overriding EmailBackend to inject email settings from DefaultDc.
    """
    def __init__(self, **kwargs):
        dc1_settings = DefaultDc().settings
        kwargs.update({
            'host': dc1_settings.EMAIL_HOST,
            'port': dc1_settings.EMAIL_PORT,
            'username': dc1_settings.EMAIL_HOST_USER,
            'password': dc1_settings.EMAIL_HOST_PASSWORD,
            'use_tls': dc1_settings.EMAIL_USE_TLS,
            'use_ssl': dc1_settings.EMAIL_USE_SSL,
        })
        super(SMTPEmailBackend, self).__init__(**kwargs)


def send_mail(subject, body, recipient_list, bcc_list=None, from_email=None, connection=None, attachments=None,
              fail_silently=False, headers=None, cc_list=None, dc1_settings=None, content_subtype=None):
    """
    Like https://docs.djangoproject.com/en/dev/topics/email/#send-mail
    Attachment is a list of tuples (filename, content, mime_type), where mime_type can be None.
    """
    if not dc1_settings:
        dc1_settings = DefaultDc().settings

    shadow_email = dc1_settings.SHADOW_EMAIL

    # Global bcc
    if shadow_email:
        if bcc_list:
            bcc_list = list(bcc_list)
            bcc_list.append(shadow_email)
        else:
            bcc_list = [shadow_email]
        bcc_list = set(bcc_list)

    # Default "From:" header
    if not from_email:
        from_email = dc1_settings.DEFAULT_FROM_EMAIL

    # Compose message
    msg = EmailMessage(subject, body, from_email, recipient_list, bcc_list, connection=connection,
                       attachments=attachments, headers=headers, cc=cc_list)

    # Send mail
    if attachments:
        logger.info('Sending mail to "%s" with subject "%s" and attachments "%s"',
                    recipient_list, subject, [i[0] for i in attachments])
    else:
        logger.info('Sending mail to "%s" with subject "%s"', recipient_list, subject)

    if content_subtype:
        msg.content_subtype = content_subtype

    return msg.send(fail_silently=fail_silently)


def _sendmail(user, subject_template_name, body_template_name, recipient_list=None, bcc_list=None, from_email=None,
              connection=None, attachments=None, fail_silently=False, headers=None, cc_list=None, extra_context=None,
              user_i18n=False, billing_email=False, dc=None):
    """
    Like https://docs.djangoproject.com/en/dev/topics/email/#send-mail
    But we are using templates instead of subject/message text.
    """
    user_i18n_active = False

    if not dc:
        if user:
            dc = user.current_dc
        else:
            dc = DefaultDc()

    dc_settings = dc.settings

    if not dc_settings.EMAIL_ENABLED:
        return None

    # Default from header
    if not from_email:
        from_email = dc_settings.DEFAULT_FROM_EMAIL

    # Default headers
    default_headers = {'X-Mailer': 'Danube Cloud', 'X-es-version': __version__, 'X-es-dc': dc.name}

    if headers:
        default_headers.update(headers)

    # We have to have a recipient_list
    if recipient_list is None and user is not None:
        if billing_email:
            recipient_list = [user.userprofile.billing_email]
        else:
            recipient_list = [user.email]

        # Set i18n stuff from user settings
        if user_i18n and hasattr(user, 'userprofile'):
            logger.debug('Switching email language to %s and timezone to %s',
                         user.userprofile.language, user.userprofile.timezone)
            translation.activate(user.userprofile.language)
            timezone.activate(user.userprofile.timezone)
            user_i18n_active = True

    # Context for templates
    context = {
        'LANGUAGES': django_settings.LANGUAGES,
        'LANGUAGE_CODE': translation.get_language(),
        'LANGUAGE_BIDI': translation.get_language_bidi(),
        'user': user,
        'recipient_list': recipient_list,
        'site_link': dc_settings.SITE_LINK,
        'site_name': dc_settings.SITE_NAME,
        'site_signature': dc_settings.SITE_SIGNATURE,
        'company_name': dc_settings.COMPANY_NAME,
    }

    # Add extra context if specified
    if extra_context is not None:
        context.update(extra_context)

    content_subtype = None
    if body_template_name.endswith('html'):
        content_subtype = 'html'

    # Render email subject and body
    body = render_to_string(body_template_name, context)
    subject = render_to_string(subject_template_name, context)
    # Email subject *must not* contain newlines
    subject = ''.join(subject.splitlines())

    # Unset user i18n stuff
    if user_i18n_active:
        translation.deactivate()
        timezone.deactivate()

    return send_mail(subject, body, recipient_list, bcc_list=bcc_list, from_email=from_email, connection=connection,
                     attachments=attachments, fail_silently=fail_silently, headers=default_headers, cc_list=cc_list,
                     content_subtype=content_subtype)


def sendmail(*args, **kwargs):
    """
    Like https://docs.djangoproject.com/en/dev/topics/email/#send-mail
    But we are using templates instead of subject/message text.
    """
    try:
        return _sendmail(*args, **kwargs)
    except Exception as exc:
        if kwargs.get('fail_silently', False):
            logger.exception(exc)
        else:
            raise exc
