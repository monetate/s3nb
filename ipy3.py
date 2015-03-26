from collections import namedtuple
import datetime

import boto

from IPython.html.services.contents.manager import ContentsManager
from IPython.utils import tz


# s3 return different time formats in different situations apparently
S3_TIMEFORMAT_GET_KEY = '%a, %d %b %Y %H:%M:%S GMT'
S3_TIMEFORMAT_BUCKET_LIST = '%Y-%m-%dT%H:%M:%S.000Z'

fakekey = namedtuple('fakekey', 'name')


class S3ContentsManager(ContentsManager):
    @staticmethod
    def _parse_s3_uri(uri, delimiter='/'):
        if not uri.startswith("s3://"):
            raise Exception("Unexpected s3 uri scheme in '{}', expected s3://".format(uri))
        return uri[5:].split(delimiter, 1)

    def _path_to_s3_key(self, path):
        key = self.s3_prefix + path.strip(self.s3_key_delimiter)
        # append delimiter if path is non-empty to avoid s3://bucket//
        if path != '':
            key += self.s3_key_delimiter
        return key

    def _s3_key_dir_to_model(self, key):
        self.log.debug("_s3_key_dir_to_model: {}: {}".format(key, key.name))
        model = {
            'name': key.name.rsplit(self.s3_key_delimiter, 2)[-2],
            'path': key.name,
            'last_modified': datetime.datetime.utcnow(), # key.last_modified,  will be used in an HTTP header
            'created': None, # key.last_modified,
            'type': 'directory',
            'content': None,
            'mimetype': None,
            'writable': True,
            'format': None,
        }
        self.log.debug("_s3_key_dir_to_model: {}: {}".format(key.name, model))
        return model

    def _s3_key_notebook_to_model(self, key, timeformat):
        self.log.debug("_s3_key_notebook_to_model: {}: {}".format(key, key.name))
        model = {
            'name': key.name.rsplit(self.s3_key_delimiter, 1)[-1],
            'path': key.name,
            'last_modified': datetime.datetime.strptime(
                key.last_modified, timeformat).replace(tzinfo=tz.UTC),
            'created': None,
            'type': 'notebook',
        }
        self.log.debug("_s3_key_notebook_to_model: {}: {}".format(key.name, model))
        return model

    def __init__(self, **kwargs):
        super(S3ContentsManager, self).__init__(**kwargs)
        config = self.config[self.__class__.__name__]  # this still can't be right
        self.s3_base_uri = config['s3_base_uri']
        self.s3_key_delimiter = config.get('s3_key_delimiter', '/')
        self.s3_bucket, self.s3_prefix = self._parse_s3_uri(self.s3_base_uri, self.s3_key_delimiter)
        # ensure prefix ends with the delimiter
        if not self.s3_prefix.endswith(self.s3_key_delimiter):
            self.s3_prefix += self.s3_key_delimiter
        self.s3_connection = boto.connect_s3()
        self.bucket = self.s3_connection.get_bucket(self.s3_bucket)
        self.log.debug("initialized")

    def list_dirs(self, path):
        self.log.debug('list_dirs: {}'.format(locals()))
        key = self.s3_prefix + path.strip(self.s3_key_delimiter)
        # append delimiter if path is non-empty to avoid s3://bucket//
        if path != '':
            key += self.s3_key_delimiter
        self.log.debug('list_dirs: looking in bucket:{} under:{}'.format(self.bucket.name, key))
        dirs = []
        for k in self.bucket.list(key, self.s3_key_delimiter):
            if k.name.endswith(self.s3_key_delimiter):
                dirs.append(self._s3_key_dir_to_model(k))
                self.log.debug('list_dirs: found {}'.format(k.name))
        return dirs

    def list_notebooks(self, path=''):
        self.log.debug('list_notebooks: {}'.format(locals()))
        key = self._path_to_s3_key(path)
        self.log.debug('list_notebooks: looking in bucket:{} under:{}'.format(self.bucket.name, key))
        notebooks = []
        for k in self.bucket.list(key, self.s3_key_delimiter):
            if k.name.endswith('.ipynb'):
                notebooks.append(self._s3_key_notebook_to_model(k, timeformat=S3_TIMEFORMAT_BUCKET_LIST))
                self.log.debug('list_notebooks: found {}'.format(k.name))
        return notebooks

    def get(self, path, content=True, type=None, format=None):
        self.log.debug('get: {}'.format(locals()))
        #  get: {'content': 1, 'path': '', 'self': <ipy3.S3ContentsManager object at 0x10a650e90>, 'type': u'directory', 'format': None}
        if type == 'directory':
            key = self._path_to_s3_key(path)
            self.log.debug(key)
            model = self._s3_key_dir_to_model(fakekey(key))
            if content:
                model['content'] = self.list_dirs(path) + self.list_notebooks(path)
                model['format'] = 'json'
            return model

    def dir_exists(self, path):
        self.log.debug('dir_exists: {}'.format(locals()))
        key = self._path_to_s3_key(path)
        try:
            next(iter(self.bucket.list(key, self.s3_key_delimiter)))
            return True
        except StopIteration:
            return False

    def is_hidden(self, path):
        self.log.debug('is_hidden {}'.format(locals()))
        return False
