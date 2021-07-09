import logging
import sys

from _4chan import _4chan

logging.basicConfig(format='%(asctime)s - %(name)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

_4c = _4chan(cached=False)

thread = _4c.thread_info(sys.argv[1], int(sys.argv[2]))

print('URL:', thread['url'])
print('Subject:', thread['subject'])
print('Image info:', thread['image_info'])
print('Text:')
print(thread['text'])
