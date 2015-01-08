Limitations
===========

Nearly every Graph API operation is supported through the batch interface.
Here's what we know doesn't work.

* Uploading the ``thumbnail`` for a Page Post ``call_to_action`` doesn't
  work. According to `the doc <https://developers.facebook.com/docs/reference/ads-api/unpublished-page-posts/v2.2#custom-image>`_,
  "The thumbnail parameter is not supported in batch requests."  The
  work around is to host the image on a server and use the ``picture``
  parameter with an URL.
