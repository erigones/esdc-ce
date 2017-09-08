from vms.models import Image


for img in Image.objects.filter(access=Image.INTERNAL):
    img.access = Image.PRIVATE
    img.save()
    print('Updated image: %s' % img)
