import logging
import os
import pickle
import re
import shutil

import bs4
import requests


logging.basicConfig(format='%(asctime)s - %(name)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


class _4chan:
    CATALOG_URL = 'https://boards.4chan.org/%s/catalog'
    THREAD_URL = 'https://boards.4chan.org/%s/thread/%d'

    def __init__(self, cached=True):
        self.rx_thread_ids = re.compile(r'[{\,]"(\d+)\":{')
        self.cached = cached
        if self.cached:
            from redis_client import db as cache
            self.cache = cache

    @staticmethod
    def _download_file(url, name):
        target = 'tmp/%s' % name
        if os.path.exists(target):
            return target

        if url.startswith('//'):
            url = 'https:' + url
        logger.info('downloading from %s to %s', url, target)
        with requests.get(url, stream=True) as r:
            with open(target, 'wb') as f:
                shutil.copyfileobj(r.raw, f)
        logger.info('done downloading from %s', url)

        return target

    @staticmethod
    def _soup_to_text(soup):
        """turn a soup element into plain text"""
        text = ''

        if not soup:
            return text

        for element in soup.contents:
            if isinstance(element, bs4.element.Tag) and element.name == 'br':
                text += '\n'
            elif element.string:
                text += element.string
            elif element.text:
                text += element.text

        return text

    def _request_thread(self, board, thread):
        """makes an http request to obtain a thread and parses it"""
        url = self.THREAD_URL % (board, thread,)
        logger.info('requesting %s ...', url)

        r = requests.get(url)
        if r.status_code != requests.codes.ok:
            raise RuntimeError("couldn't request a thread: %d" % r.status_code)

        soup = bs4.BeautifulSoup(r.text, features='html.parser')
        # find the op message container
        soup_op = soup.find('div', class_='opContainer')
        # inside, the metadata
        soup_info = soup_op.find('div', class_='postInfo')
        # and inside the metadata, the subject if any
        subject = soup_info.find('span', class_='subject').string
        if subject:
            subject = str(subject)
        # file: get info and download and store it
        soup_file = soup_op.find('div', class_='file')
        try:
            image_info = ' '.join(soup_file.find('div', class_='fileText').strings)
            image_url = soup_file.find('a', class_='fileThumb')['href']
            image_file = self._download_file(image_url, 'image_%s_%d.%s' %
                                             (board, thread, image_url.split('.')[-1]))
        except AttributeError:
            image_info = '(file deleted)'
            image_url, image_file = None, None
        # and finally the text
        soup_message = soup_op.find('blockquote', class_='postMessage')
        text = self._soup_to_text(soup_message)

        return {'url': self.THREAD_URL % (board, thread,),
                'subject': subject,
                'image_url': image_url,
                'image_file': image_file,
                'image_info': image_info,
                'text': text}

    def thread_info(self, board, thread):
        """returns info about a thread"""
        if self.cached:
            cached = self.cache.get('thread_%s_%d' % (board, thread))
            if cached:
                logger.info('using cached result for /%s/%s', board, thread)
                return pickle.loads(cached)
            logger.info('nothing in cache for /%s/%s; retrieving fresh info', board, thread)
        return self.refresh_thread_cache(board, thread)

    def refresh_thread_cache(self, board, thread):
        """requests and parses a thread and puts it in cache"""
        logger.info('retrieving thread /%s/%s', board, thread)
        thread_content = self._request_thread(board, thread)
        if self.cached:
            pickled = pickle.dumps(thread_content)
            self.cache.set('thread_%s_%d' % (board, thread), pickled, ex=60 * 60)
        logger.info('done retrieving thread /%s/%s', board, thread)
        return thread_content

    def threads_in_board(self, board):
        """returns a list of all threads in a board, either from cache
            or by making a request to the live site"""
        if self.cached:
            cached = self.cache.get('threads_%s' % board)
            if cached:
                logger.info('using cached result for /%s/', board)
                return pickle.loads(cached)
            logger.info('nothing in cache for /%s/; retrieving fresh info', board)
        return self.refresh_board_cache(board)

    def refresh_board_cache(self, board):
        """requests and parses a board and puts it in cache"""
        logger.info('retrieving board /%s/', board)
        r = requests.get(self.CATALOG_URL % board)
        if r.status_code != requests.codes.ok:
            raise RuntimeError("couldn't request the board catalog: %d" % r.status_code)
        threads_ids = [int(x) for x in self.rx_thread_ids.findall(r.text)]
        if self.cached:
            self.cache.set('threads_%s' % board, pickle.dumps(threads_ids), ex=60)
        logger.info('done retrieving /%s/', board)
        return threads_ids
