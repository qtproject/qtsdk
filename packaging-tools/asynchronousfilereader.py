"""
AsynchronousFileReader
======================

Simple thread based asynchronous file reader for Python.

see https://github.com/soxofaan/asynchronousfilereader

The MIT License (MIT)

Copyright (c) 2014 Stefaan Lippens

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""

__version__ = '0.2.1'

import threading
try:
    # Python 2
    from Queue import Queue
except ImportError:
    # Python 3
    from queue import Queue


class AsynchronousFileReader(threading.Thread):
    """
    Helper class to implement asynchronous reading of a file
    in a separate thread. Pushes read lines on a queue to
    be consumed in another thread.
    """

    def __init__(self, fd, queue=None, autostart=True):
        self._fd = fd
        if queue is None:
            queue = Queue()
        self.queue = queue

        threading.Thread.__init__(self)

        if autostart:
            self.start()

    def run(self):
        """
        The body of the tread: read lines and put them on the queue.
        """
        while True:
            line = self._fd.readline()
            if not line:
                break
            self.queue.put(line)

    def eof(self):
        """
        Check whether there is no more content to expect.
        """
        return not self.is_alive() and self.queue.empty()

    def readlines(self):
        """
        Get currently available lines.
        """
        while not self.queue.empty():
            yield self.queue.get()

