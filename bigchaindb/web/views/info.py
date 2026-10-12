# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""API Index endpoint"""

import flask
from flask_restful import Resource

from bigchaindb.web.views.base import base_ws_uri
from bigchaindb import version
from bigchaindb.web.websocket_server import EVENTS_ENDPOINT


class RootIndex(Resource):
    def get(self):
        docs_url = [
            'https://docs.bigchaindb.com/projects/server/en/v',
            version.__version__ + '/'
        ]
        return flask.jsonify({
            'api': {
                'v1': get_api_v1_info('/api/v1/')
            },
            'docs': ''.join(docs_url),
            'software': 'BigchainDB',
            'version': version.__version__,
        })


class ApiV1Index(Resource):
    def get(self):
        return flask.jsonify(get_api_v1_info('/'))


class ShaclStatsApi(Resource):
    """Eval scrape of in-process SHACL+Δ / conflict counters (one gunicorn worker)."""

    def get(self):
        import json
        from flask import request
        from bigchaindb.common.shacl_validator import (
            ABCI_RESET_PATH,
            ABCI_STATS_PATH,
            get_shacl_validator,
        )

        validator = get_shacl_validator()
        reset = str(request.args.get("reset") or "").strip().lower() in ("1", "true", "yes")
        if reset:
            validator.reset_stats()
            with open(ABCI_RESET_PATH, "w") as handle:
                handle.write("1")
        abci = None
        try:
            with open(ABCI_STATS_PATH) as handle:
                abci = json.load(handle)
        except (OSError, ValueError):
            abci = None
        body = validator.stats_snapshot()
        body["reset"] = reset
        body["abci"] = abci
        return flask.jsonify(body)


def get_api_v1_info(api_prefix):
    """Return a dict with all the information specific for the v1 of the
    api.
    """
    websocket_root = base_ws_uri() + EVENTS_ENDPOINT
    docs_url = [
        'https://docs.bigchaindb.com/projects/server/en/v',
        version.__version__,
        '/http-client-server-api.html',
    ]

    return {
        'docs': ''.join(docs_url),
        'transactions': '{}transactions/'.format(api_prefix),
        'blocks': '{}blocks/'.format(api_prefix),
        'assets': '{}assets/'.format(api_prefix),
        'outputs': '{}outputs/'.format(api_prefix),
        'streams': websocket_root,
        'metadata': '{}metadata/'.format(api_prefix),
        'validators': '{}validators'.format(api_prefix),
    }
