# Course lab: running the whistle demo on a cluster node

Instructions for one lab exercise of the course: running the web demo on node 7 (host name `slave7`) of the college's
teaching cluster, a Hadoop setup with HDFS. They are specific to that cluster and are kept here because
`cluster/make_cluster_bundle.py` packs this file into `whistle_app.zip`. Nothing else in the project needs them.

`whistle_app.zip` is the whole runnable app: the web page (frontend), the FastAPI inference API (backend), the trained
models (whistle detector, VAE, GMM) and the settings that connect them. The page calls the API with relative URLs
(`api/...`), so it works on any host and port without changes.

HDFS only stores and hands over the zip. Slave 7 copies it out of HDFS onto its own disk and runs it there, because
Python cannot run a program straight out of HDFS and the app writes its results next to itself (`runs/infer/`).

**On this cluster every team logs in as `student`, so the HDFS home `/user/student` and the home folder on each node are
shared with the other teams.** Everything below uses one folder of its own, `whistle_slave7`, so nobody's files collide.

## 1. Laptop -> HDFS (browser)

Open the NameNode web page in the browser (usually `http://<master>:9870`) -> Utilities -> Browse the file system.
Go to `/user/student`, create the folder `whistle_slave7`, open it and upload `whistle_app.zip` and
`whistle_app.zip.sha256`.

If the upload hangs or fails: the browser sends the file to a DataNode by its host name (for example `slave3`), which the
laptop may not know. Then copy the two files to slave 7 instead (`scp whistle_app.zip* student@<slave 7 IP>:~/`) and
put them into HDFS from there (`hdfs dfs -mkdir -p whistle_slave7 && hdfs dfs -put -f whistle_app.zip* whistle_slave7/`).

## 2. Laptop -> slave 7 (ssh)

    ssh student@<slave 7 IP>

Take slave 7's address from the lab's node list. Once logged in, the prompt must read `student@slave7`.

## 3. HDFS -> slave 7

    hdfs dfs -ls whistle_slave7
    mkdir -p ~/whistle_slave7 && cd ~/whistle_slave7
    hdfs dfs -copyToLocal whistle_slave7/whistle_app.zip whistle_slave7/whistle_app.zip.sha256 .
    sha256sum -c whistle_app.zip.sha256
    unzip -q whistle_app.zip          # no unzip?  python3 -m zipfile -e whistle_app.zip .
    cd whistle_app

A path without a leading `/` is read from the HDFS home `/user/student`. If `hdfs dfs -copyToLocal` says "No such file
or directory", the folder does not exist in HDFS under that home; `hdfs dfs -ls` first shows what is really there.

## 4. Check what slave 7 has (installs nothing)

    python3 check_node.py

It lists Python, the 10 packages the app needs (OK / NO), memory, disk, GPU and internet, and ends with what to ask
the course mentor for when something is missing. Run it again with another Python to check that one, for example the
mentor's Anaconda: `/path/to/anaconda/envs/<env>/bin/python check_node.py`. When everything is OK, add `--run`: it runs
the real app once (model, an analysis, generation, the web server and the page) and ends with "THE APP RUNS HERE".

## 5. Set up once, then start

Either with the mentor's ready Python (check_node.py says OK for it), nothing to install:

    PYTHON=/path/to/anaconda/envs/<env>/bin/python bash run_node.sh

or, if slave 7 has internet, with a Python and packages of its own in this folder:

    bash setup_node.sh
    bash run_node.sh

`setup_node.sh` checks every file, gets Python 3.11 (slave 7 runs Ubuntu 20.04, whose own Python is 3.8, so it sets up a
portable Python 3.11 in `.python/`, no sudo needed), creates `.venv`, installs the packages (CPU build of PyTorch unless
the node has an NVIDIA GPU) and loads the models once. With internet on slave 7 it downloads Python (30 MB) and the
packages (about 250 MB); a zip built with the offline kit carries both in `offline/` and needs no internet. It uses
about 1.5 GB of disk in `~/whistle_slave7`.

The app keeps running only while that ssh session is open. To keep it running after logout:

    nohup bash run_node.sh > server.log 2>&1 &

## 6. Open the page

The app listens on port 8000 of slave 7, for slave 7 only. From the laptop, open a second terminal and keep this open:

    ssh -N -L 8000:127.0.0.1:8000 student@<slave 7 IP>

then browse to http://127.0.0.1:8000. The tunnel carries the browser's requests to the app on slave 7 and the results
back; all the computing happens on slave 7.

If port 8000 is already taken on slave 7, start with `PORT=8017 bash run_node.sh` and use `8000:127.0.0.1:8017` in the
tunnel.
