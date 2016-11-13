from api.api_views import APIView
from api.exceptions import ObjectNotFound
from api.task.response import SuccessTaskResponse
from api.utils.views import call_api_view
from api.image.base.views import image_manage
from vms.models import Image, ImageStore


class ImageStoreImageView(APIView):
    """
    List images or import image from remote disk image repositories (a.k.a. imagestores).
    """
    dc_bound = False

    def __init__(self, request, name, uuid, data):
        super(ImageStoreImageView, self).__init__(request)
        self.data = data
        self.name = name
        self.uuid = uuid
        repositories = ImageStore.get_repositories()

        try:
            self.repo = ImageStore(name, url=repositories[name])
        except KeyError:  # The name is not in VMS_IMAGE_REPOSITORIES
            raise ObjectNotFound(model=ImageStore)

    def get_image(self):
        uuid = self.uuid

        for img in self.repo.images:
            if img['uuid'] == uuid:
                return img
        else:
            raise ObjectNotFound(model=Image)

    def get(self, many=False):
        if many:
            assert not self.uuid

            if self.full or self.extended:
                res = self.repo.images
            else:
                res = [img['uuid'] for img in self.repo.images]
        else:
            assert self.uuid

            res = self.get_image()

        return SuccessTaskResponse(self.request, res, dc_bound=False)

    def post(self):
        img = self.get_image()
        data = self.data
        data['manifest_url'] = self.repo.get_image_manifes_url(img['uuid'])
        data.pop('file_url', None)
        name = data.get('name', None)

        if not name:
            name = data['name'] = img['name']

        return call_api_view(self.request, 'POST', image_manage, name, data=data)
