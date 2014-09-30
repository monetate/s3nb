# S3-backed notebook manager for IPython

## Setup

1. Install:

    from pypi:
    ```bash
    pip install s3nb
    ```

    from source with pip:
    ```bash
    pip install git+https://github.com/monetate/s3nb
    ```

    or from source the old fashioned way:
    ```bash
    git clone git@github.com:monetate/s3nb.git
    cd s3nb
    python ./setup.py install
    ```

2. Configure

    ``` bash
    # set this - notebooks will be stored relative to this uri
    S3_NOTEBOOK_URI=s3://path/to/notebooks/

    # optionally set this
    PROFILE=s3nbserver

    # shouldn't need to edit beyond this point
    IPYTHONDIR=${IPYTHONDIR:-$HOME/.ipython}
    PROFILE_DIR=${IPYTHONDIR}/profile_${PROFILE}

    if [ ! -d $PROFILE_DIR ]; then
        ipython profile create $PROFILE
        IPYNB_CONFIG=${PROFILE_DIR}/ipython_notebook_config.py
        mv $IPYNB_CONFIG $IPYNB_CONFIG.orig
        cat > $IPYNB_CONFIG <<EOF
    c = get_config()
    c.NotebookApp.notebook_manager_class = 's3nb.S3NotebookManager'
    c.S3NotebookManager.s3_base_uri = '$S3_NOTEBOOK_URI'
    EOF
    fi
    ```

3. Run
    ``` bash
    ipython notebook --profile=s3nbserver
    ```
