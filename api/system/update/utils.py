from logging import getLogger

from api.task.response import SuccessTaskResponse, FailureTaskResponse

logger = getLogger(__name__)


def process_update_reply(reply, target, version):
    """Handles reply which is output of the :func:`que.handlers.update_command`

    :return: Returns tuple of SuccessTaskResponse or FailureTaskResponse class object and result dictionary
    """
    try:
        rc = reply['returncode']
    except (KeyError, TypeError):
        logger.error('Unexpected output from "%s" update: "%s"', target, reply)
        response_class = FailureTaskResponse
        result = {'message': str(reply)}
    else:
        if rc == 0:
            msg = reply['stdout']
            logger.info('Updating "%s" to version %s was successful: "%s"', target, version, msg)
            response_class = SuccessTaskResponse
        else:
            msg = reply['stderr'] or reply['stdout']
            logger.error('Updating %s to version %s failed: "%s"', target, version, msg)
            response_class = FailureTaskResponse

        result = {'message': msg, 'returncode': rc}

    return response_class, result
