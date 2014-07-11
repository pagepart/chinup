from __future__ import absolute_import, unicode_literals

import logging

from .lowlevel import batches
from . import queue, settings


logger = logging.getLogger(__name__)


class ChinupMiddleware(object):
    def process_request(self, request):
        queue.delete_queues()

    def process_response(self, request, response):
        if settings.DEBUG and batches:
            logger.info("%d requests in %d batches",
                        sum(len(b) for b in batches),
                        len(batches))
            batches[:] = []

        return response
