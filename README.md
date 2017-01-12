# git-lfs-swift-transfer-agent

## Description
git-lfs-swift-transfer-agent is an implementation of the [custom transfer type](https://github.com/git-lfs/git-lfs/blob/master/docs/custom-transfers.md) _swift_ for
[Git LFS](https://github.com/git-lfs/git-lfs). Please see 
[git-lfs-swift-server](https://github.com/cbartz/git-lfs-swift-server) for the
server-side implementation.
 
[OpenStack Swift](https://github.com/openstack/swift) clusters have a maximum object
size (5 GiB per default). Objects larger in size have to be split into smaller segments. The basic transfer agent shipped by git-lfs has no knowledge about this.
The _git-lfs-swift_ transfer agent is able to handle large objects. 
 

## Installation

In principle, only the script `git_lfs_swift_transfer.py` (with executable permission) and the [python-swiftclient](https://github.com/openstack/python-swiftclient) is required.
You can also use setuptools to install the python-swiftclient requirement and to install the transfer script
to the default location: 

    git clone https://github.com/cbartz/git-lfs-swift-transfer-agent
    cd git-lfs-swift-transfer-agent
    python setup.py install


## Configuration

Please see [https://github.com/git-lfs/git-lfs/blob/master/docs/custom-transfers.md](https://github.com/git-lfs/git-lfs/blob/master/docs/custom-transfers.md).
In principle, the configuration:

    lfs.customtransfer.swift.path /path/to/git_lfs_swift_transfer.py

is sufficient for your particular git repository. But there are optional configuration parameters, which can be 
set with the git configuration variable `lfs.custromtransfer.swift.args` :

* `--logfile /path/to/file` write logs to specified file
* `--loglevel LVL` choose one of: DEBUG, INFO, WARNING, ERROR, CRITICAL
* `--use-slo` per default, [DLOs](http://docs.openstack.org/developer/swift/overview_large_objects.html#module-swift.common.middleware.dlo)
    are used to store large objects. If not supported or wanted, [SLOs](http://docs.openstack.org/developer/swift/overview_large_objects.html#module-swift.common.middleware.slo)
    can be used with this option.
* `--segment-size n` The size of the segments for large objects. Files larger than this size, gets split up. If not specified, 5 GiB are used.
* `--tempdir /path/to/dir` git-lfs downloads the files first to a specified directory, before moving to the final destination. With this option, the download directory can be specified.
 If not specified, it is tried to create a temporary directory inside python.

So, for example, if logs with a loglevel DEBUG are desired to the file /tmp/logfile, do the configuration as follows:

    lfs.customtransfer.swift.args --logfile /tmp/logfile --loglevel DEBUG

Please be aware, that if logging and concurrency is used (with `lfs.customtransfer.swift.concurrent`), depending on your running
platform, the logfiles could end up mangled.