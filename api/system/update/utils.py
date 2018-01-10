from logging import getLogger

app_logger = getLogger(__name__)


def process_update_reply(reply, target, version, logger=app_logger):
    """Handles reply which is output of the :func:`que.handlers.update_command`

    :return: Returns tuple of SuccessTaskResponse or FailureTaskResponse class object and result dictionary
    """
    try:
        rc = reply['returncode']
    except (KeyError, TypeError):
        logger.error('Unexpected output from "%s" update: "%s"', target, reply)
        error = True
        result = {'message': str(reply)}
    else:
        if rc == 0:
            msg = reply['stdout']
            logger.info('Updating "%s" to version %s was successful: "%s"', target, version, msg)
            error = False
        else:
            msg = reply['stderr'] or reply['stdout']
            logger.error('Updating %s to version %s failed with rc=%s: "%s"', target, version, rc, msg)
            error = True

        result = {'message': msg, 'returncode': rc}

    return result, error
