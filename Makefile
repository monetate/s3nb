SSH=vagrant ssh

CONFIG_FILE=ipython/profile_s3nb/ipython_notebook_config.py
IPYTHON_DIR=/vagrant/ipython

AWS_USER=s3nb

.PHONY=clean configure creds kill restart run

clean:
	rm -rf ipython/ credentials

configure:
	${SSH} -c "ipython profile create --ipython-dir=${IPYTHON_DIR} s3nb"
	mv ${CONFIG_FILE} ${CONFIG_FILE}.orig
	echo "c = get_config()" >> ${CONFIG_FILE}
	echo "c.NotebookApp.log_level = 'DEBUG'" >> ${CONFIG_FILE}
	echo "c.NotebookApp.contents_manager_class = 's3nb.S3ContentsManager'" >> ${CONFIG_FILE}
	echo "c.S3ContentsManager.s3_base_uri = '${S3_BASE_URI}'" >> ${CONFIG_FILE}
	echo "c.S3ContentsManager.checkpoints_kwargs = {'root_dir': '/vagrant/.checkpoints'}" 

creds:
	grep -A2 ${AWS_USER} ~/.aws/credentials | sed 's/${AWS_USER}/default/g' > credentials
	${SSH} -c "mkdir -p ~/.aws && ln -sf /vagrant/credentials ~/.aws/credentials"

kill:
	${SSH} -c "tmux kill-session -t server || true"

restart: kill run;

run:
	${SSH} -c "tmux new-session -d -n run -s server 'PYTHONPATH=/vagrant ipython notebook --ipython-dir=${IPYTHON_DIR} --profile=s3nb --ip=0.0.0.0 --no-browser > /vagrant/s3nb.log 2>&1'"
