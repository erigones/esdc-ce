import base64
import zlib

try:
    # noinspection PyCompatibility
    from StringIO import StringIO
except ImportError:
    from io import StringIO

from PIL import Image

from vms.models import Vm
from que.tasks import cq, get_task_logger
from que.exceptions import TaskException
from api.task.utils import callback

__all__ = ('vm_screenshot_cb',)

logger = get_task_logger(__name__)


@cq.task(name='api.vm.other.tasks.vm_screenshot_cb')
@callback(log_exception=False)
def vm_screenshot_cb(result, task_id, vm_uuid=None):
    """
    A callback function for api.vm.other.views.vm_screenshot_cb.
    """
    if result['returncode'] == 0:
        vm = Vm.objects.get(uuid=vm_uuid)
        try:
            _ppm = StringIO(zlib.decompress(base64.b64decode(result['image'])))
            _ppm.seek(0)
            ppm = Image.open(_ppm)
            png = StringIO()
            ppm.save(png, format='PNG')
            del _ppm
            del ppm
            png.seek(0)
            _png = base64.b64encode(png.read())
            vm.screenshot = _png
            result['image'] = _png
            result['message'] += '\nScreenshot saved'
            del _png
        except Exception as e:
            logger.exception(e)
            logger.error('Could not parse or save image from vm_screenshot(%s). Error: %s', vm_uuid, e)
            # noinspection PyBroadException
            try:
                del result['image']
            except:
                pass
            raise TaskException(result, 'Could not parse or save screenshot image')
    else:
        logger.error('Found nonzero returncode in result from vm_screenshot(%s). Error: %s',
                     vm_uuid, result.get('message', ''))
        # noinspection PyBroadException
        try:
            del result['image']
        except:
            pass
        raise TaskException(result, 'Did not receive a proper screenshot image')

    vm.tasks_del(task_id)
    return result
