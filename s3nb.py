"""
An ipython 2.x notebook manager that uses s3 for storage.

# Configuration file for ipython-notebook.
c = get_config()

c.NotebookApp.notebook_manager_class = 's3nb.S3NotebookManager'
c.NotebookApp.log_level = 'DEBUG'
c.S3NotebookManager.s3_base_uri = 's3://bucket/notebook/prefix/'
"""
import datetime

import boto
from tornado import web

from IPython.html.services.notebooks.nbmanager import NotebookManager
from IPython.utils.traitlets import Unicode
from IPython.utils import tz


class S3NotebookManager(NotebookManager):
    s3_bucket = Unicode(u"", config=True)
    s3_prefix = Unicode(u"", config=True)
    notebook_dir = Unicode(u"", config=True)  # not used

    @staticmethod
    def _parse_s3_uri(uri, delimiter='/'):
        if not uri.startswith("s3://"):
            raise Exception("Unexpected s3 uri scheme in '{}', expected s3://".format(uri))
        return uri[5:].split(delimiter, 1)

    def _s3_key_dir_to_model(self, key):
        self.log.debug("_s3_key_dir_to_model: {}: {}".format(key, key.name))
        model = {
            'name': key.name.rsplit(self.s3_key_delimiter, 2)[-2],
            'path': key.name,
            'last_modified': None, # key.last_modified,
            'created': None, # key.last_modified,
            'type': 'directory',
        }
        self.log.debug("_s3_key_dir_to_model: {}: {}".format(key.name, model))
        return model

    def _s3_key_notebook_to_model(self, key):
        self.log.debug("_s3_key_notebook_to_model: {}: {}".format(key, key.name))
        model = {
            'name': key.name.rsplit(self.s3_key_delimiter, 1)[-1],
            'path': key.name,
            'last_modified': datetime.datetime.strptime(
                key.last_modified[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=tz.UTC),
            'created': None,
            'type': 'notebook',
        }
        self.log.debug("_s3_key_notebook_to_model: {}: {}".format(key.name, model))
        return model

    def __init__(self, **kwargs):
        super(S3NotebookManager, self).__init__(**kwargs)
        config = kwargs['parent'].config[self.__class__.__name__]  # this can't be right
        self.s3_base_uri = config['s3_base_uri']
        self.s3_key_delimiter = config.get('s3_key_delimiter', '/')
        self.s3_bucket, self.s3_prefix = self._parse_s3_uri(self.s3_base_uri, self.s3_key_delimiter)
        # ensure prefix ends with the delimiter
        if not self.s3_prefix.endswith(self.s3_key_delimiter):
            self.s3_prefix += s3_key_delimiter
        self.s3_connection = boto.connect_s3()
        self.bucket = self.s3_connection.get_bucket(self.s3_bucket)

    def info_string(self):
        return "Serving notebooks from {}".format(self.s3_base_uri)

    def path_exists(self, path):
        self.log.debug('path_exists: {}'.format(locals()))
        return True

    def is_hidden(self, path):
        self.log.debug('is_hidden: {}'.format(locals()))
        return False

    def list_dirs(self, path):
        self.log.debug('list_dirs: {}'.format(locals()))
        key = self.s3_prefix + path.strip(self.s3_key_delimiter)
        # append delimiter if path is non-empty to avoid s3://bucket//
        if path != '':
            key += self.s3_key_delimiter
        self.log.debug('list_dirs: looking in bucket:{} under:{}'.format(self.bucket.name, key))
        notebooks = []
        for k in self.bucket.list(key, self.s3_key_delimiter):
            if k.name.endswith(self.s3_key_delimiter):
                notebooks.append(self._s3_key_dir_to_model(k))
                self.log.debug('list_dirs: found {}'.format(k.name))
        return notebooks

    def list_notebooks(self, path=''):
        self.log.debug('list_notebooks: {}'.format(locals()))
        key = self.s3_prefix + path.strip(self.s3_key_delimiter)
        # append delimiter if path is non-empty to avoid s3://bucket//
        if path != '':
            key += self.s3_key_delimiter
        self.log.debug('list_notebooks: looking in bucket:{} under:{}'.format(self.bucket.name, key))
        notebooks = []
        for k in self.bucket.list(key, self.s3_key_delimiter):
            if k.name.endswith(self.filename_ext):
                notebooks.append(self._s3_key_notebook_to_model(k))
                self.log.debug('list_notebooks: found {}'.format(k.name))
        return notebooks
