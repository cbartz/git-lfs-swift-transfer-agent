# coding=utf-8
# Copyright 2017 Christopher Bartz <bartz@dkrz.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from setuptools import setup
setup(
    name="git-lfs-swift-transfer-agent",
    version="0.1",
    scripts=['git_lfs_swift_transfer.py'],
    install_requires=['python-swiftclient'],
    tests_require='mock',
    author="Christopher Bartz",
    author_email="bartz@dkrz.de",
    description="git lfs transfer agent implementation for OpenStack Swift",
    license="Apache 2.0",
    url="https://github.com/cbartz/git-lfs-swift-transfer-agent",
    keywords="git lfs swift transfer agent",
    test_suite='test_transfer'
)
