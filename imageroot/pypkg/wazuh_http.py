#
# Copyright (C) 2026 Nethesis S.r.l.
# SPDX-License-Identifier: GPL-3.0-or-later
#

# Requests to the push and chat servers. A redirect is never followed: urllib would repeat the POST
# as a GET without its body, the server would answer 200 and the summary would count as delivered,
# and an Authorization header would go along to whatever host the redirect names.

import urllib.request


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # None makes urllib raise HTTPError with the 3xx status, like any other refusal
        return None


_opener = urllib.request.build_opener(_NoRedirect)


def send(request, timeout):
    """Send a request and drop the answer. Raises urllib.error.HTTPError on any status from 300 up."""
    with _opener.open(request, timeout=timeout):
        pass
