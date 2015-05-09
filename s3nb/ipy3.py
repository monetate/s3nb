import codecs
from collections import namedtuple
import datetime
import tempfile

import boto

from tornado import web

from IPython import nbformat
from IPython.html.services.contents.filecheckpoints import GenericFileCheckpoints
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
        return self.s3_prefix + path.strip(self.s3_key_delimiter)

    def _path_to_s3_key_dir(self, path):
        key = self._path_to_s3_key(path)
        # append delimiter if path is non-empty to avoid s3://bucket//
        if path != '':
            key += self.s3_key_delimiter
        return key

    def _get_key_dir_name(self, name):
        try:
            return name.rsplit(self.s3_key_delimiter, 2)[-2]
        except IndexError:
            return ''

    def _s3_key_dir_to_model(self, key):
        self.log.debug("_s3_key_dir_to_model: %s: %s", key, key.name)
        model = {
            'name': self._get_key_dir_name(key.name),
            'path': key.name.replace(self.s3_prefix, ''),
            'last_modified': datetime.datetime.utcnow(), # key.last_modified,  will be used in an HTTP header
            'created': None, # key.last_modified,
            'type': 'directory',
            'content': None,
            'mimetype': None,
            'writable': True,
            'format': None,
        }
        self.log.debug("_s3_key_dir_to_model: %s: %s", key.name, model)
        return model

    def _s3_key_file_to_model(self, key, timeformat):
        self.log.debug("_s3_key_file_to_model: %s: %s", key, key.name)
        model = {
            'content': None,
            'name': key.name.rsplit(self.s3_key_delimiter, 1)[-1],
            'path': key.name.replace(self.s3_prefix, ''),
            'last_modified': datetime.datetime.strptime(
                key.last_modified, timeformat).replace(tzinfo=tz.UTC),
            'created': None,
            'type': 'file',
            'mimetype': None,
            'writable': True,
            'format': None,
        }
        self.log.debug("_s3_key_file_to_model: %s: %s", key.name, model)
        return model

    def _s3_key_notebook_to_model(self, key, timeformat):
        self.log.debug("_s3_key_notebook_to_model: %s: %s", key, key.name)
        model = {
            'content': None,
            'name': key.name.rsplit(self.s3_key_delimiter, 1)[-1],
            'path': key.name.replace(self.s3_prefix, ''),
            'last_modified': datetime.datetime.strptime(
                key.last_modified, timeformat).replace(tzinfo=tz.UTC),
            'created': None,
            'type': 'notebook',
            'mimetype': None,
            'writable': True,
            'format': None,
        }
        self.log.debug("_s3_key_notebook_to_model: %s: %s", key.name, model)
        return model

    def __init__(self, **kwargs):
        super(S3ContentsManager, self).__init__(**kwargs)
        config = self.config[self.__class__.__name__]  # this still can't be right
        self.s3_base_uri = config['s3_base_uri']
        self.s3_key_delimiter = config.get('s3_key_delimiter', '/')
        self.s3_bucket, self.s3_prefix = self._parse_s3_uri(self.s3_base_uri, self.s3_key_delimiter)
        # ensure prefix ends with the delimiter
        if not self.s3_prefix.endswith(self.s3_key_delimiter) and self.s3_prefix != '':
            self.s3_prefix += self.s3_key_delimiter
        self.s3_connection = boto.connect_s3()
        self.bucket = self.s3_connection.get_bucket(self.s3_bucket)
        self.log.debug("initialized base_uri: %s bucket: %s prefix: %s",
            self.s3_base_uri, self.s3_bucket, self.s3_prefix)

    def _checkpoints_class_default(self):
        return GenericFileCheckpoints

    def list_dirs(self, path):
        self.log.debug('list_dirs: %s', locals())
        key = self._path_to_s3_key_dir(path)
        self.log.debug('list_dirs: looking in bucket:%s under:%s', self.bucket.name, key)
        dirs = []
        for k in self.bucket.list(key, self.s3_key_delimiter):
            if k.name.endswith(self.s3_key_delimiter) and k.name != key:
                dirs.append(self._s3_key_dir_to_model(k))
                self.log.debug('list_dirs: found %s', k.name)
        return dirs

    def list_files(self, path):
        self.log.debug('list_files: %s', locals())
        key = self._path_to_s3_key_dir(path)
        self.log.debug('list_files: looking in bucket:%s under:%s', self.bucket.name, key)
        files = []
        for k in self.bucket.list(key, self.s3_key_delimiter):
            if not k.name.endswith(self.s3_key_delimiter) and not k.name.endswith('.ipynb') and k.name != key:
                files.append(self._s3_key_file_to_model(k, timeformat=S3_TIMEFORMAT_BUCKET_LIST))
                self.log.debug('list_files: found %s', k.name)
        return files

    def list_notebooks(self, path=''):
        self.log.debug('list_notebooks: %s', locals())
        key = self._path_to_s3_key_dir(path)
        self.log.debug('list_notebooks: looking in bucket:%s under:%s', self.bucket.name, key)
        notebooks = []
        for k in self.bucket.list(key, self.s3_key_delimiter):
            if k.name.endswith('.ipynb'):
                notebooks.append(self._s3_key_notebook_to_model(k, timeformat=S3_TIMEFORMAT_BUCKET_LIST))
                self.log.debug('list_notebooks: found %s', k.name)
        return notebooks

    def delete(self, path):
        self.log.debug('delete: %s', locals())
        key = self._path_to_s3_key(path)
        self.log.debug('removing notebook in bucket: %s : %s', self.bucket.name, key)
        self.bucket.delete_key(key)

    def get(self, path, content=True, type=None, format=None):
        self.log.debug('get: %s', locals())
        # get: {'content': 1, 'path': '', 'self': <ipy3.S3ContentsManager object at 0x10a650e90>, 'type': u'directory', 'format': None}
        # get: {'content': False, 'path': u'graphaelli/notebooks/2015-01 Hack.ipynb', 'self': <ipy3.S3ContentsManager object at 0x10d60ce90>, 'type': None, 'format': None}

        if type == 'directory':
            key = self._path_to_s3_key_dir(path)
            model = self._s3_key_dir_to_model(fakekey(key))
            if content:
                model['content'] = self.list_dirs(path) + self.list_notebooks(path) + self.list_files(path)
                model['format'] = 'json'
            return model
        elif type == 'notebook' or (type is None and path.endswith('.ipynb')):
            key = self._path_to_s3_key(path)
            k = self.bucket.get_key(key)
            if not k:
                raise web.HTTPError(400, "{} not found".format(key))
            model = self._s3_key_notebook_to_model(k, timeformat=S3_TIMEFORMAT_GET_KEY)
            if content:
                try:
                    with tempfile.NamedTemporaryFile() as t:
                        # download bytes
                        k.get_file(t)
                        t.seek(0)
                        # read with utf-8 encoding
                        with codecs.open(t.name, mode='r', encoding='utf-8') as f:
                            nb = nbformat.read(f, as_version=4)
                except Exception as e:
                    raise web.HTTPError(400, u"Unreadable Notebook: %s %s" % (path, e))
                self.mark_trusted_cells(nb, path)
                model['content'] = nb
                model['format'] = 'json'
                self.validate_notebook_model(model)
            return model
        else: # assume that it is file
            key = self._path_to_s3_key(path)
            k = self.bucket.get_key(key)

            model = self._s3_key_file_to_model(k, timeformat=S3_TIMEFORMAT_GET_KEY)

            if content:
                try:
                    model['content'] = k.get_contents_as_string()
                except Exception as e:
                    raise web.HTTPError(400, u"Unreadable file: %s %s" % (path, e))

                model['mimetype'] = 'text/plain'
                model['format'] = 'text'

            return model

    def dir_exists(self, path):
        self.log.debug('dir_exists: %s', locals())
        key = self._path_to_s3_key(path)
        if path == '':
            return True
        else:
            try:
                next(iter(self.bucket.list(key, self.s3_key_delimiter)))
                return True
            except StopIteration:
                return False

    def is_hidden(self, path):
        self.log.debug('is_hidden %s', locals())
        return False

    def file_exists(self, path):
        self.log.debug('file_exists: %s', locals())
        if path == '':
            return False
        key = self._path_to_s3_key(path)
        k = self.bucket.get_key(key)
        return k is not None and not k.name.endswith(self.s3_key_delimiter)

    exists = file_exists

    def new_untitled(self, path='', type='', ext=''):
        self.log.debug('new_untitled: %s', locals())
        model = {
            'mimetype': None,
            'created': datetime.datetime.utcnow(),
            'last_modified': datetime.datetime.utcnow(),
            'writable': True,
        }

        if type:
            model['type'] = type

        if ext == '.ipynb':
            model.setdefault('type', 'notebook')
        else:
            model.setdefault('type', 'file')

        insert = ''
        if model['type'] == 'directory':
            untitled = self.untitled_directory
            insert = ' '
        elif model['type'] == 'notebook':
            untitled = self.untitled_notebook
            ext = '.ipynb'
        elif model['type'] == 'file':
            untitled = self.untitled_file
        else:
            raise web.HTTPError(400, "Unexpected model type: %r" % model['type'])

        name = self.increment_filename(untitled + ext, self.s3_prefix + path, insert=insert)
        path = u'{0}/{1}'.format(path, name)
        model.update({
            'name': name,
            'path': path,
        })
        return self.new(model, path)

    def _save_file(self, path, content, format):
        if format != 'text':
            raise web.HTTPError(400, u'Only text files are supported')

        try:
            bcontent = content.encode('utf8')
        except Exception as e:
            raise web.HTTPError(400, u'Encoding error saving {}: {}'.format(content, e))

        k = boto.s3.key.Key(self.bucket)
        k.key = self._path_to_s3_key(path)

        with tempfile.NamedTemporaryFile() as f:
            f.write(content)
            f.seek(0)
            k.set_contents_from_file(f)

    def _save_notebook(self, path, nb):
        self.log.debug('_save_notebook: %s', locals())

        k = boto.s3.key.Key(self.bucket)
        k.key = self._path_to_s3_key(path)

        try:
            with tempfile.NamedTemporaryFile() as t, codecs.open(t.name, mode='w', encoding='utf-8') as f:
                # write tempfile with utf-8 encoding
                nbformat.write(nb, f, version=nbformat.NO_CONVERT)
                # upload as bytes (t's fp didn't advance)
                k.set_contents_from_file(t)
        except Exception as e:
            raise web.HTTPError(400, u"Unexpected Error Writing Notebook: %s %s" % (path, e))

    def rename(self, old_path, new_path):
        self.log.debug('rename: %s', locals())
        if new_path == old_path:
            return

        src_key = self._path_to_s3_key(old_path)
        dst_key = self._path_to_s3_key(new_path)
        self.log.debug('copying notebook in bucket: %s from %s to %s', self.bucket.name, src_key, dst_key)
        if self.bucket.get_key(dst_key):
            raise web.HTTPError(409, u'Notebook with name already exists: %s' % dst_key)
        self.bucket.copy_key(dst_key, self.bucket.name, src_key)
        self.log.debug('removing notebook in bucket: %s : %s', self.bucket.name, src_key)
        self.bucket.delete_key(src_key)

    def save(self, model, path):
        """ very similar to filemanager.save """
        self.log.debug('save: %s', locals())

        if 'type' not in model:
            raise web.HTTPError(400, u'No file type provided')
        if 'content' not in model and model['type'] != 'directory':
            raise web.HTTPError(400, u'No file content provided')

#        self.run_pre_save_hook(model=model, path=path)

        if model['type'] == 'notebook':
            nb = nbformat.from_dict(model['content'])
            self.check_and_sign(nb, path)
            self._save_notebook(path, nb)
        elif model['type'] == 'file':
            self._save_file(path, model['content'], model.get('format'))
        elif model['type'] == 'directory':
            pass  # keep symmetry with filemanager.save
        else:
            raise web.HTTPError(400, "Unhandled contents type: %s" % model['type'])

        validation_message = None
        if model['type'] == 'notebook':
            self.validate_notebook_model(model)
            validation_message = model.get('message', None)

        model = self.get(path, content=False, type=model['type'])
        if validation_message:
            model['message'] = validation_message

#        self.run_post_save_hook(model=model, os_path=path)

        model['content'] = None

        return model
