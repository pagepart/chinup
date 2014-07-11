from __future__ import absolute_import, unicode_literals

from .lowlevel import batches
from .queue import delete_queues
from . import settings


class ChinupTestMixin(object):
    """
    Clear batches record in setUp, and provide assertBatches.
    """
    def setUp(self):
        super(ChinupTestMixin, self).setUp()
        settings.TESTING = True
        delete_queues()
        batches[:] = []

    def assertBatches(self, nb, nr):
        lb, lr = len(batches), sum(len(b) for b in batches)
        if (lb, lr) != (nb, nr):
            from pprint import pformat
            pretty_batches = pformat(
                [['{} {}'.format(r['method'], re.sub(r'\?.*', '', r['relative_url']))
                  for r in b] for b in batches])
            raise AssertionError("Batches/requests actual {}/{} != expected {}/{}:\n{}".format(
                lb, lr, nb, nr, pretty_batches))

        # Reset for the next call
        batches[:] = []
