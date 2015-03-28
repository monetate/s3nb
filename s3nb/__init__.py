imported = False

try:
    from .ipy2 import S3NotebookManager
    imported = True
except ImportError:
    pass

try:
    from .ipy3 import S3ContentsManager
    imported = True
except ImportError:
    pass

if not imported:
    raise ImportError("failed to import any s3nb managers")
