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

    # and this
    IPYTHON_MAJOR_VERSION=4

    # optionally set this - checkpoints will be stored locally, relative to this path (for IPython 3)
    CHECKPOINT_ROOT_DIR=~/.checkpoints

    # optionally set this
    PROFILE=s3nbserver

    # shouldn't need to edit beyond this point

    ## IPython 2.x
    IPYNB_MANAGER=S3NotebookManager
    IPYNB_MANAGER_CFG=notebook_manager_class

    ## IPython 3.x
    if [ $IPYTHON_MAJOR_VERSION == 3 ]; then
        IPYNB_MANAGER=S3ContentsManager
        IPYNB_MANAGER_CFG=contents_manager_class
    fi

    ## IPython 4.x
    if [ $IPYTHON_MAJOR_VERSION == 4 ]; then
        IPYNB_MANAGER=S3ContentsManager
        IPYNB_MANAGER_CFG=contents_manager_class
    fi

    IPYTHONDIR=${IPYTHONDIR:-$HOME/.ipython}
    PROFILE_DIR=${IPYTHONDIR}/profile_${PROFILE}

    if [ ! -d $PROFILE_DIR ]; then
        ipython profile create $PROFILE
        IPYNB_CONFIG=${PROFILE_DIR}/ipython_notebook_config.py
        mv $IPYNB_CONFIG $IPYNB_CONFIG.orig
        cat > $IPYNB_CONFIG <<EOF
    c = get_config()
    c.NotebookApp.${IPYNB_MANAGER_CFG} = 's3nb.${IPYNB_MANAGER}'
    c.${IPYNB_MANAGER}.s3_base_uri = '$S3_NOTEBOOK_URI'
    EOF
    fi


    if  [ $IPYTHON_MAJOR_VERSION == 3 ] || [$IPYTHON_MAJOR_VERSION == 4 ] ; then
        echo "c.S3ContentsManager.checkpoints_kwargs = {'root_dir': '${CHECKPOINT_ROOT_DIR}'}"  >> ${IPYNB_CONFIG}
    fi
    ```

3. If you haven't already, configure AWS variables for boto.  [Follow these instructions](http://blogs.aws.amazon.com/security/post/Tx3D6U6WSFGOK2H/A-New-and-Standardized-Way-to-Manage-Credentials-in-the-AWS-SDKs).

4. Run
    ``` bash
    jupyter notebook --config=~/.ipython/s3nbserver/ipython_notebook_config.py
    ```

## Development

1. Provision a virtual machine with `vagrant up`
2. Create an IPython profile with `make configure -e S3_BASE_URI=YOUR_BUCKET`
4. Share you AWS credentials with the virtual machine with `make creds -e AWS_USER=YOUR_USER`
4. Run the notebook server with `make run`
