#!/usr/bin/env python
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
"""
Implementation of a transfer agent for the transfer type "swift" for git-lfs.

The implementation has been performed according to:
https://github.com/git-lfs/git-lfs/blob/master/docs/custom-transfers.md
(January 2017)
"""
import argparse
import json
import logging
import os.path
import sys
import tempfile

from swiftclient.service import SwiftUploadObject, SwiftService

logger = None  # Will be set after parsing args.


def write_msg(msg):
    """Write out the message in Line delimited JSON."""
    msg = json.dumps(msg) + '\n'
    logger.debug('write msg: %s', msg)
    sys.stdout.write(msg)
    sys.stdout.flush()


def read_msg():
    """Read Line delimited JSON from stdin. """
    l = sys.stdin.readline()
    logger.debug('received msg: %s', l)
    msg = json.loads(l.strip())

    if 'terminate' in (msg.get('type'), msg.get('event')):
        logger.info('terminate message received.')
        return None

    if msg.get('event') not in ('download', 'upload'):
        logger.critical('Received unexpected message: %s', l)
        sys.exit(-1)

    return msg


def swift_loop(mode, tmpdir, segment_size, use_slo):
    """Logic for doing the data transfer with swift."""

    msg = read_msg()
    if msg is None:
        return

    c_url = msg['action']['href']
    s_url, container = c_url.rstrip('/').rsplit('/', 1)

    token = msg['action']['header']['x-auth-token']
    options = {'os_storage_url': s_url, 'os_auth_token': token,
               'segment_size': segment_size, 'segment_container': container,
               'out_directory': tmpdir, 'use_slo': use_slo,
               'container_threads': 1, 'object_dd_threads': 1,
               'object_uu_threads': 1}
    logger.debug('options: %s', options)

    oid = msg['oid']
    size = msg['size']

    if mode == 'upload':
        obj = SwiftUploadObject(msg['path'], oid)
    else:
        obj = oid

    with SwiftService(options=options) as swift:
        while True:
            bytesSoFar = 0
            for r in getattr(swift, mode)(container, [obj]):
                if r['success']:
                    if r['action'] == 'upload_object':
                        oid = r['object']
                        if bytesSoFar < size:
                            write_msg({"event": "progress", "oid": oid,
                                       'bytesSoFar': size,
                                       "bytesSinceLast": size})
                        write_msg({'event': 'complete', 'oid': oid})
                    elif r['action'] == 'upload_segment':
                        oid = r['for_object']
                        bytesSinceLast = r['segment_size']
                        bytesSoFar += bytesSinceLast

                        write_msg({"event": "progress", "oid": oid,
                                   'bytesSoFar': bytesSoFar,
                                   "bytesSinceLast": bytesSinceLast})
                    elif r['action'] == 'download_object':
                        oid = r['object']
                        write_msg({"event": "progress", "oid": oid,
                                   'bytesSoFar': size,
                                   "bytesSinceLast": size})
                        write_msg({'event': 'complete', 'oid': oid,
                                   'path': os.path.join(tmpdir, oid)})
                else:
                    if r['action'] in ('download_object', 'upload_object'):
                        write_msg(
                            {'event': 'complete', 'oid': r['object'],
                             'error': {
                                 'code': 2, 'message': str(r['error'])}},)

            msg = read_msg()
            if msg is None:
                break

            oid = msg['oid']
            size = msg['size']

            if mode == 'upload':
                obj = SwiftUploadObject(msg['path'], oid)
            else:
                obj = oid


def main(args):
    try:
        parser = argparse.ArgumentParser(
            description="Transfer agent for type 'swift' for git-lfs.")
        parser.add_argument(
            "--logfile",
            help="logs are written out to specified file.")
        parser.add_argument(
            "--loglevel",
            choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
            default='WARNING')
        parser.add_argument(
            '--use-slo',
            help='use SLOs instead of DLOs for large objects.',
            action='store_true')
        parser.add_argument(
            "--segment-size",
            help="size of segments for large objects.",
            type=int, default=5*2**30)
        parser.add_argument(
            "--tempdir",
            help="specify temporary directory where files are downloaded "
                 "before moved away to the final destination by git-lfs.")
        parsed_args = parser.parse_args(args)

        global logger
        if parsed_args.logfile:
            root_logger = logging.getLogger()
            hdlr = logging.FileHandler(parsed_args.logfile)
            hdlr.setFormatter(
                logging.Formatter(
                    '%(asctime)s [%(name)s] %(levelname)s %(message)s'))
            root_logger.addHandler(hdlr)
            root_logger.setLevel(parsed_args.loglevel)

            logger = logging.getLogger(__name__)
            logger.setLevel(parsed_args.loglevel)
            logger.debug('Program called with args: %s', args)
        else:
            logger = logging.getLogger()
            logger.addHandler(logging.NullHandler())
    except Exception:
        logging.exception('Exception when parsing args.')
        sys.exit(-1)

    try:
        init_msg = json.loads(sys.stdin.readline().strip())
        if init_msg.get('event') == 'init':
            logger.info('init message received.')
            op = init_msg.get('operation')
            write_msg({})
            if op == 'download' and not parsed_args.tempdir:
                parsed_args.tempdir = tempfile.mkdtemp()

            swift_loop(
                op, parsed_args.tempdir, parsed_args.segment_size,
                parsed_args.use_slo)
    except Exception:
        logger.addHandler(logging.StreamHandler())
        logger.exception('Exception in main thread catched.')
        sys.exit(-1)

if __name__ == "__main__":
    # Git-LFS passes all args in one string.
    main([] if len(sys.argv) == 1 else sys.argv[1].split(' '))
