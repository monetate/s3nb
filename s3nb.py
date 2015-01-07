"""
An ipython 2.x notebook manager that uses s3 for storage.

# Configuration file for ipython-notebook.
c = get_config()

c.NotebookApp.notebook_manager_class = 's3nb.S3NotebookManager'
c.NotebookApp.log_level = 'DEBUG'
c.S3NotebookManager.s3_base_uri = 's3://bucket/notebook/prefix/'
"""
import datetime
import tempfile
from os.path import join, splitext

import boto
from tornado import web

from IPython.html.services.notebooks.nbmanager import NotebookManager
from IPython.nbformat import current
from IPython.utils.traitlets import Unicode
from IPython.utils import tz


__version__ = '0.0.3'

# s3 return different time formats in different situations apparently
S3_TIMEFORMAT_GET_KEY = '%a, %d %b %Y %H:%M:%S GMT'
S3_TIMEFORMAT_BUCKET_LIST = '%Y-%m-%dT%H:%M:%S.000Z'


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

    def _notebook_s3_key_string(self, path, name):
        key = self.s3_prefix + path.strip(self.s3_key_delimiter)
        # append delimiter if path is non-empty to avoid s3://bucket//
        if path != '':
            key += self.s3_key_delimiter
        key += name
        return key

    def _notebook_s3_key(self, path, name):
        key = self._notebook_s3_key_string(path, name)
        self.log.debug('_notebook_s3_key: looking in bucket:{} for:{}'.format(self.bucket.name, key))
        return self.bucket.get_key(key)

    def __init__(self, **kwargs):
        super(S3NotebookManager, self).__init__(**kwargs)
        config = kwargs['parent'].config[self.__class__.__name__]  # this can't be right
        self.s3_base_uri = config['s3_base_uri']
        self.s3_key_delimiter = config.get('s3_key_delimiter', '/')
        self.s3_bucket, self.s3_prefix = self._parse_s3_uri(self.s3_base_uri, self.s3_key_delimiter)
        # ensure prefix ends with the delimiter
        if not self.s3_prefix.endswith(self.s3_key_delimiter):
            self.s3_prefix += self.s3_key_delimiter
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
                notebooks.append(self._s3_key_notebook_to_model(k, timeformat=S3_TIMEFORMAT_BUCKET_LIST))
                self.log.debug('list_notebooks: found {}'.format(k.name))
        return notebooks

    def notebook_exists(self, name, path=''):
        self.log.debug('notebook_exists: {}'.format(locals()))
        k = self._notebook_s3_key(path, name)
        return k is not None and not k.name.endswith(self.s3_key_delimiter)

    def get_notebook(self, name, path='', content=True):
        self.log.debug('get_notebook: {}'.format(locals()))
        k = self._notebook_s3_key(path, name)
        model = self._s3_key_notebook_to_model(k, timeformat=S3_TIMEFORMAT_GET_KEY)
        if content:
            try:
                with tempfile.NamedTemporaryFile() as f:
                    k.get_file(f)
                    f.seek(0)
                    nb = current.read(f, u'json')
            except Exception as e:
                raise web.HTTPError(400, u"Unreadable Notebook: %s %s" % (os_path, e))
            self.mark_trusted_cells(nb, name, path)
            model['content'] = nb
        return model

    def save_notebook(self, model, name, path=''):
        self.log.debug('save_notebook: {}'.format(locals()))
        if 'content' not in model:
            raise web.HTTPError(400, u'No notebook JSON data provided')

        k = boto.s3.key.Key(self.bucket)
        k.key = self._notebook_s3_key_string(path, name)

        nb = current.to_notebook_json(model['content'])
        self.check_and_sign(nb, name, path)

        try:
            with tempfile.NamedTemporaryFile() as f:
                current.write(nb, f, u'json')
                f.seek(0)
                k.set_contents_from_file(f)
        except Exception as e:
            raise web.HTTPError(400, u"Unexpected Error Writing Notebook: %s %s %s" % (path, name, e))

        return self.get_notebook(name, path, content=False)

    def update_notebook(self, model, name, path=''):
        self.log.debug('update_notebook: {}'.format(locals()))

        # support updating just name or path even though there doesn't seem to be a way to do this via the UI
        new_name = model.get('name', name)
        new_path = model.get('path', path)
        if path != new_path or name != new_name:
            src_key = self._notebook_s3_key_string(path, name)
            dst_key = self._notebook_s3_key_string(new_path, new_name)
            self.log.debug('copying notebook in bucket: {} from {} to {}'.format(self.bucket.name, src_key, dst_key))
            if self.bucket.get_key(dst_key):
                raise web.HTTPError(409, u'Notebook with name already exists: %s' % src_key)
            self.bucket.copy_key(dst_key, self.bucket.name, src_key)
            self.log.debug('removing notebook in bucket: {} : {}'.format(self.bucket.name, src_key))
            self.bucket.delete_key(src_key)

        return self.get_notebook(new_name, new_path, content=False)

    def delete_notebook(self, name, path=''):
        self.log.debug('delete_notebook: {}'.format(locals()))

        key = self._notebook_s3_key_string(path, name)
        self.log.debug('removing notebook in bucket: {} : {}'.format(self.bucket.name, key))
        self.bucket.delete_key(key)

    def copy_notebook(self, from_name, to_name=None, path=''):
        """
        Copy an existing notebook and return its new model.

        If to_name not specified, increment from_name-Copy#.ipynb.
        """
        self.log.debug('copy_notebook: {}'.format(locals()))
        if to_name is None:
            from_name_root, _ = splitext(from_name)
            to_name = self.increment_filename(from_name_root + '-Copy', path)

        model = self.get_notebook(from_name, path)
        model['name'] = to_name

        self.log.debug('copying notebook from {} to {} with path {}'.format(from_name, to_name, path))
        self.create_notebook(model, path)

        return model

    # Checkpoint methods
    checkpoint_dir = Unicode(u'ipynb_checkpoints', config=True)

    def get_checkpoint_name(self, checkpoint_id, name):
        basename, _ = splitext(name)
        checkpoint_name = '{name}--{checkpoint_id}{ext}'.format(
            name=basename,
            checkpoint_id=checkpoint_id,
            ext=self.filename_ext
        )

        return checkpoint_name

    def get_checkpoint_path(self, path=''):
        return join(path, self.checkpoint_dir)

    def get_checkpoint_model(self, checkpoint_id, name, path=''):
        checkpoint_id = u'checkpoint'
        checkpoint_path = self.get_checkpoint_path(path)
        checkpoint_name = self.get_checkpoint_name(checkpoint_id, name)

        key = self._notebook_s3_key(checkpoint_path, checkpoint_name)
        checkpoint_notebook_model = self._s3_key_notebook_to_model(
            key,
            timeformat=S3_TIMEFORMAT_GET_KEY
        )
        checkpoint_model = {
            'id': checkpoint_id,
            'last_modified': checkpoint_notebook_model['last_modified']
        }

        return checkpoint_model

    def create_checkpoint(self, name, path=''):
        checkpoint_id = u'checkpoint'
        checkpoint_name = self.get_checkpoint_name(checkpoint_id, name)
        checkpoint_path = self.get_checkpoint_path(path)

        self.log.debug('creating checkpoint for notebook {}'.format(name))
        model = self.get_notebook(name, path)
        model['name'] = checkpoint_name
        self.create_notebook(model, checkpoint_path)

        return self.get_checkpoint_model(checkpoint_id, name, path)

    def restore_checkpoint(self, checkpoint_id, name, path=''):
        checkpoint_name = self.get_checkpoint_name(checkpoint_id, name)
        checkpoint_path = self.get_checkpoint_path(path)

        self.log.info('Restoring {} from checkpoint {}'.format(name, checkpoint_name))
        model = self.get_notebook(checkpoint_name, checkpoint_path)
        model['name'] = name
        self.create_notebook(model, path)

    def list_checkpoints(self, name, path=''):
        checkpoint_id = u'checkpoint'
        checkpoint_name = self.get_checkpoint_name(checkpoint_id, name)
        checkpoint_path = self.get_checkpoint_path(path)

        key = self._notebook_s3_key(checkpoint_path, checkpoint_name)
        if key is None:
            return []
        else:
            return [self.get_checkpoint_model(checkpoint_id, name, path)]
