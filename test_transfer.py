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


import logging
import os
import tempfile
import unittest
import uuid

from mock import Mock, patch

import git_lfs_swift_transfer


@patch('git_lfs_swift_transfer.write_msg', Mock())
@patch('sys.stdin')
@patch('git_lfs_swift_transfer.swift_loop')
class ParseArgsTestCase(unittest.TestCase):

    def tearDown(self):
        if hasattr(self, 'tmpfile'):
            try:
                os.unlink(self.tmpfile)
            except:
                pass
        root_logger = logging.getLogger()
        hdlrs = [hdlr for hdlr in root_logger.handlers]
        for hdlr in hdlrs:
            root_logger.removeHandler(hdlr)

    def testNoArgs(self, swift_loop, stdin):
        stdin.readline = Mock(
            return_value='{"event":"init", "operation": "upload"}\n')
        git_lfs_swift_transfer.main([])
        cargs = swift_loop.call_args
        self.assertEqual("upload", cargs[0][0])
        self.assertIsNone(cargs[0][1])
        self.assertEqual(cargs[0][2], 5*2**30)
        self.assertFalse(cargs[0][3])
        logger = git_lfs_swift_transfer.logger
        self.assertEqual(len(logger.handlers), 1)
        self.assertIsInstance(logger.handlers[0], logging.NullHandler)

    def testAllArgs(self, swift_loop, stdin):
        stdin.readline = Mock(
            return_value='{"event":"init", "operation": "upload"}\n')
        fd, self.tmpfile = tempfile.mkstemp('-test-swift-transfer')
        args = ['--logfile', self.tmpfile, '--loglevel', 'ERROR', '--use-slo',
                '--segment-size', '45', '--tempdir', self.tmpfile]
        git_lfs_swift_transfer.main(args)
        cargs = swift_loop.call_args
        self.assertEqual("upload", cargs[0][0])
        self.assertEqual(self.tmpfile, cargs[0][1])
        self.assertEqual(cargs[0][2], 45)
        self.assertTrue(cargs[0][3])
        logger = git_lfs_swift_transfer.logger
        self.assertEqual(len(logger.handlers), 0)
        root_logger = logging.getLogger()
        self.assertEqual(len(root_logger.handlers), 1)
        self.assertIsInstance(root_logger.handlers[0], logging.FileHandler)

    def testLogLevelINFO(self, swift_loop, stdin):
        stdin.readline = Mock(
            return_value='{"event":"init", "operation": "upload"}\n')
        fd, self.tmpfile = tempfile.mkstemp('-test-swift-transfer')
        args = ['--logfile', self.tmpfile, '--loglevel', 'INFO']
        git_lfs_swift_transfer.main(args)
        with open(self.tmpfile) as f:
                l = f.readlines()
                self.assertEqual(len(l), 1)

    def testLogLevelDEBUG(self, swift_loop, stdin):
        stdin.readline = Mock(
            return_value='{"event":"init", "operation": "upload"}\n')
        fd, self.tmpfile = tempfile.mkstemp('-test-swift-transfer')
        args = ['--logfile', self.tmpfile, '--loglevel', 'DEBUG']
        git_lfs_swift_transfer.main(args)
        with open(self.tmpfile) as f:
                l = f.readlines()
                self.assertEqual(len(l), 2)

    def testLogLevelWARN(self, swift_loop, stdin):
        stdin.readline = Mock(
            return_value='{"event":"init", "operation": "upload"}\n')
        fd, self.tmpfile = tempfile.mkstemp('-test-swift-transfer')
        for lvl in ('WARNING', 'ERROR', 'CRITICAL'):
            args = ['--logfile', self.tmpfile, '--loglevel', lvl]
            git_lfs_swift_transfer.main(args)
            self.assertEqual(os.stat(self.tmpfile).st_size, 0)

    def testTempDirWithDownload(self, swift_loop, stdin):
        stdin.readline = Mock(
            return_value='{"event":"init", "operation": "download"}\n')
        fd, self.tmpfile = tempfile.mkstemp('-test-swift-transfer')
        args = ['--tempdir', self.tmpfile]
        git_lfs_swift_transfer.main(args)
        cargs = swift_loop.call_args
        self.assertEqual("download", cargs[0][0])
        self.assertEqual(self.tmpfile, cargs[0][1])

        with patch('tempfile.mkdtemp', Mock(return_value='mytemp')):
            git_lfs_swift_transfer.main([])
            cargs = swift_loop.call_args
            self.assertEqual('mytemp', cargs[0][1])


class FakeSwiftService(object):

    iterables = []

    def __init__(self, options=None):
        self.options = options
        FakeSwiftService.current_instance = self
        self.objs = []

        def transfer(container, objs):
            self.container = container
            self.objs.append(objs[0])
            return next(self.iterables)

        self.download = self.upload = transfer

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False


@patch('git_lfs_swift_transfer.SwiftService', FakeSwiftService)
@patch('git_lfs_swift_transfer.write_msg')
@patch('git_lfs_swift_transfer.read_msg')
class SwiftLoopTestCase(unittest.TestCase):

    options = {
        'segment_container': 'container', 'use_slo': False,
        'os_storage_url': 'url', 'os_auth_token': 'token',
        'out_directory': 'tmpdir', 'segment_size': 5,
        'container_threads': 1, 'object_dd_threads': 1,
        'object_uu_threads': 1
        }

    @classmethod
    def _msg_iterable(cls, mode, objs):
        for o, s in objs:
            d = {'event': mode, 'oid': o,
                 'size': s,
                 'action': {'href': 'url/container',
                            'header': {'x-auth-token': 'token'}}}
            if mode == 'upload':
                d['path'] = '/path/to/file'
            yield d

        yield None

    def testUpload(self, read_msg, write_msg):
        objs = zip([uuid.uuid4().hex for x in range(3)], [3, 10, 5])

        read_msg.side_effect = self._msg_iterable('upload', objs)
        FakeSwiftService.iterables = iter(
            [[{'success': True, 'object': objs[0][0],
               'action': 'upload_object'}],
             [{'success': True, 'for_object': objs[1][0],
               'action': 'upload_segment', 'segment_size': 5},
              {'success': True, 'for_object': objs[1][0],
               'action': 'upload_segment', 'segment_size': 5},
              {'success': True, 'object': objs[1][0],
               'action': 'upload_object'}],
             [{'success': False, 'object': objs[2][0],
               'action': 'upload_object', 'error': 'failure'}]])
        git_lfs_swift_transfer.swift_loop('upload', 'tmpdir', 5, False)
        swift = FakeSwiftService.current_instance
        self.assertEqual(self.options, swift.options)
        self.assertEqual(swift.container, 'container')
        self.assertEqual([o.object_name for o in swift.objs],
                         map(lambda x: x[0], objs))
        self.assertEqual(write_msg.call_count, 6)
        cargs_list = write_msg.call_args_list

        msg = cargs_list[0][0][0]
        self.assertEqual(msg.get('bytesSoFar'), 3)
        self.assertEqual(msg.get('oid'), objs[0][0])
        self.assertEqual(msg.get('event'), 'progress')
        self.assertEqual(msg.get('bytesSinceLast'), 3)
        msg = cargs_list[1][0][0]
        self.assertEqual(msg.get('oid'), objs[0][0])
        self.assertEqual(msg.get('event'), 'complete')

        msg = cargs_list[2][0][0]
        self.assertEqual(msg.get('bytesSoFar'), 5)
        self.assertEqual(msg.get('oid'), objs[1][0])
        self.assertEqual(msg.get('event'), 'progress')
        self.assertEqual(msg.get('bytesSinceLast'), 5)
        msg = cargs_list[3][0][0]
        self.assertEqual(msg.get('bytesSoFar'), 10)
        self.assertEqual(msg.get('oid'), objs[1][0])
        self.assertEqual(msg.get('event'), 'progress')
        self.assertEqual(msg.get('bytesSinceLast'), 5)
        msg = cargs_list[4][0][0]
        self.assertEqual(msg.get('oid'), objs[1][0])
        self.assertEqual(msg.get('event'), 'complete')

        msg = cargs_list[5][0][0]
        self.assertEqual(msg.get('oid'), objs[2][0])
        self.assertEqual(msg.get('event'), 'complete')
        self.assertEqual(msg.get('error'), {'message': 'failure', 'code': 2})

    def testDownload(self, read_msg, write_msg):
        objs = zip([uuid.uuid4().hex for x in range(2)], [3, 10])

        read_msg.side_effect = self._msg_iterable('download', objs)
        FakeSwiftService.iterables = iter(
            [[{'success': True, 'object': objs[0][0],
               'action': 'download_object'}],
             [{'success': False, 'object': objs[1][0],
               'action': 'download_object', 'error': 'failure'}]])
        git_lfs_swift_transfer.swift_loop('download', 'tmpdir', 5, False)
        swift = FakeSwiftService.current_instance
        self.assertEqual(self.options, swift.options)
        self.assertEqual(swift.container, 'container')
        self.assertEqual(swift.objs, map(lambda x: x[0], objs))
        self.assertEqual(write_msg.call_count, 3)
        cargs_list = write_msg.call_args_list

        msg = cargs_list[0][0][0]
        self.assertEqual(msg.get('bytesSoFar'), 3)
        self.assertEqual(msg.get('oid'), objs[0][0])
        self.assertEqual(msg.get('event'), 'progress')
        self.assertEqual(msg.get('bytesSinceLast'), 3)
        msg = cargs_list[1][0][0]
        self.assertEqual(msg.get('oid'), objs[0][0])
        self.assertEqual(msg.get('event'), 'complete')
        self.assertEqual(msg.get('path'), 'tmpdir/' + objs[0][0])

        msg = cargs_list[2][0][0]
        self.assertEqual(msg.get('oid'), objs[1][0])
        self.assertEqual(msg.get('event'), 'complete')
        self.assertEqual(msg.get('error'), {'message': 'failure', 'code': 2})
