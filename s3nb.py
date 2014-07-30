"""
An ipython 2.x notebook manager that uses s3 for storage.

# Configuration file for ipython-notebook.
c = get_config()

c.NotebookApp.notebook_manager_class = 's3nb.S3NotebookManager'
c.NotebookApp.log_level = 'DEBUG'
c.S3NotebookManager.s3_base_uri = 's3://bucket/notebook/prefix/'
"""
import boto
from tornado import web

from IPython.html.services.notebooks.nbmanager import NotebookManager
from IPython.utils.traitlets import Unicode


class S3NotebookManager(NotebookManager):
    s3_bucket = Unicode(u"", config=True)
    s3_prefix = Unicode(u"", config=True)

    @staticmethod
    def _parse_s3_uri(uri, delimiter='/'):
        if not uri.startswith("s3://"):
            raise Exception("Unexpected s3 uri scheme in '{}', expected s3://".format(uri))
        return uri[5:].split(delimiter, 1)

    def __init__(self, **kwargs):
        super(S3NotebookManager, self).__init__(**kwargs)
        config = kwargs['parent'].config[self.__class__.__name__]  # this can't be right
        self.s3_base_uri = config['s3_base_uri']
        self.s3_key_delimiter = config.get('s3_key_delimiter', '/')
        self.s3_bucket, self.s3_prefix = self._parse_s3_uri(self.s3_base_uri, self.s3_key_delimiter)
        self.s3_connection = boto.connect_s3()
        self.bucket = self.s3_connection.get_bucket(self.s3_bucket)

    def info_string(self):
        return "Serving notebooks from {}".format(self.s3_base_uri)
