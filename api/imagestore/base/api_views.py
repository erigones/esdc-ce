# -*- coding: utf-8 -*-
from logging import getLogger
from django.utils import timezone
from celery.states import SUCCESS, FAILURE

from api.api_views import APIView
from api.exceptions import ObjectNotFound, TaskIsAlreadyRunning
from api.task.utils import task_log
from api.task.response import SuccessTaskResponse, FailureTaskResponse
from api.utils.http import HttpClient, RequestException
from api.imagestore.messages import LOG_IMAGE_STORE_UPDATE
from que import TG_DC_UNBOUND, TT_DUMMY
from que.lock import TaskLock
from que.utils import task_id_from_request
from vms.models import ImageStore

logger = getLogger(__name__)


class ImageStoreView(APIView):
    """
    List or refresh image repositories (a.k.a. imagestores).

    VMS_IMAGE_REPOSITORIES is a global setting manage by SuperAdmins in the default DC (main) =>
        => operations are DC-unbound
        => task log messages are updated in the default DC (main) task log
        => imagestore api calls are available for every SuperAdmin or ImageImportAdmin
    """
    dc_bound = False
    HTTP_TIMEOUT = 20
    HTTP_MAX_SIZE = 10485760
    LOCK_KEY = 'imagestore-update'

    def __init__(self, request, name, data, many=False):
        super(ImageStoreView, self).__init__(request)
        self.data = data
        self.name = name
        self.many = many
        repositories = ImageStore.get_repositories()

        if name:
            assert not many
            try:
                self.repo = ImageStore(name, url=repositories[name])
            except KeyError:  # The name is not in VMS_IMAGE_REPOSITORIES
                raise ObjectNotFound(model=ImageStore)
        else:
            assert many
            if request.method == 'PUT' or (self.full or self.extended):
                self.repo = ImageStore.all(repositories)
            else:
                self.repo = repositories.keys()

    @classmethod
    def _update(cls, task_id, repo):
        err = res = images = None
        repo_url = repo.get_images_url()
        logger.info('Downloading images from image repository %s (%s)', repo.name, repo_url)

        try:
            curl = HttpClient(repo_url)
            res = curl.get(timeout=cls.HTTP_TIMEOUT, max_size=cls.HTTP_MAX_SIZE, allow_redirects=True)
            images = res.json()
        except RequestException as exc:
            err = '%s' % exc
        except ValueError as exc:
            err = 'Image server response could not be decoded (%s)' % exc
        else:
            if not isinstance(images, list):
                err = 'Unexpected output from image server (%s)' % type(images)

        if err:
            status = FAILURE
            msg = err
            logger.error(err)
            repo.error = err
            repo.save()
        else:
            status = SUCCESS
            img_count = len(images)
            msg = u'Downloaded metadata for %d images from image repository %s in %d μs' % (
                  img_count, repo.name, res.elapsed.microseconds)
            logger.info(msg)
            repo.image_count = img_count
            repo.last_update = timezone.now()
            repo.error = None
            repo.save(images=images)
            del images  # The list can be big => remove from memory, we don't need it now

        task_log(task_id, LOG_IMAGE_STORE_UPDATE, obj=repo, task_status=status, detail=msg, update_user_tasks=False)

        return repo

    @classmethod
    def update(cls, task_id, repo):
        lock = TaskLock(cls.LOCK_KEY, desc='Image repository %s update' % repo.name)

        if not lock.acquire(task_id, timeout=60, save_reverse=False):
            raise TaskIsAlreadyRunning

        try:
            return cls._update(task_id, repo)
        finally:
            lock.delete(fail_silently=True, delete_reverse=False)

    def get(self):
        return SuccessTaskResponse(self.request, self.repo, dc_bound=self.dc_bound)

    def put(self):
        request = self.request
        task_id = task_id_from_request(request, dummy=True, tt=TT_DUMMY, tg=TG_DC_UNBOUND)

        if self.many:
            res = [self.update(task_id, repo) for repo in self.repo]
            err = any(bool(repo['error']) for repo in res)
        else:
            res = self.update(task_id, self.repo)
            err = bool(res.error)

        if err:
            response_class = FailureTaskResponse
        else:
            response_class = SuccessTaskResponse

        return response_class(self.request, res, task_id=task_id, dc_bound=self.dc_bound)
