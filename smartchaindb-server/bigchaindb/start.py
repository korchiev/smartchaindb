# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

import logging
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from bigchaindb import utils

import setproctitle

from abci import TmVersion, ABCI

import bigchaindb
from bigchaindb.lib import BigchainDB
from bigchaindb.core import App
from bigchaindb.parallel_validation import ParallelValidationApp
from bigchaindb.web import server, websocket_server
from bigchaindb.events import Exchange, EventTypes
from bigchaindb.utils import Process, recover
from bigchaindb.return_executor import ReturnExecutor


logger = logging.getLogger(__name__)

BANNER = """
****************************************************************************
*                                                                          *
*   ┏┓ ╻┏━╸┏━╸╻ ╻┏━┓╻┏┓╻╺┳┓┏┓    ┏━┓ ┏━┓ ╺┳┓┏━╸╻ ╻                         *
*   ┣┻┓┃┃╺┓┃  ┣━┫┣━┫┃┃┗┫ ┃┃┣┻┓   ┏━┛ ┃┃┃  ┃┃┣╸ ┃┏┛                         *
*   ┗━┛╹┗━┛┗━╸╹ ╹╹ ╹╹╹ ╹╺┻┛┗━┛   ┗━╸╹┗━┛╹╺┻┛┗━╸┗┛                          *
*   codename "fluffy cat"                                                  *
*   Initialization complete. BigchainDB Server is ready and waiting.       *
*                                                                          *
*   You can send HTTP requests via the HTTP API documented in the          *
*   BigchainDB Server docs at:                                             *
*    https://bigchaindb.com/http-api                                       *
*                                                                          *
*   Listening to client connections on: {:<15}                    *
*                                                                          *
****************************************************************************
"""


def start(args):
    # Exchange object for event stream api
    logger.info("Starting BigchainDB")
    exchange = Exchange()
    # start the web api
    app_server = server.create_server(
        settings=bigchaindb.config["server"],
        log_config=bigchaindb.config["log"],
        bigchaindb_factory=BigchainDB,
    )
    p_webapi = Process(name="bigchaindb_webapi", target=app_server.run, daemon=True)
    p_webapi.start()

    logger.info(BANNER.format(bigchaindb.config["server"]["bind"]))

    # start websocket server
    p_websocket_server = Process(
        name="bigchaindb_ws",
        target=websocket_server.start,
        daemon=True,
        args=(exchange.get_subscriber_queue(EventTypes.BLOCK_VALID),),
    )
    p_websocket_server.start()

    p_exchange = Process(name="bigchaindb_exchange", target=exchange.run, daemon=True)
    p_exchange.start()

    return_queue = multiprocessing.Queue()
    pool = ThreadPoolExecutor(max_workers=10)
    return_executor = multiprocessing.Process(
        target=ReturnExecutor.worker,
        args=(
            pool,
            return_queue,
        ),
    )
    return_executor.start()

    recovery_daemon = multiprocessing.Process(
        target=utils.recover,
        args=(
            BigchainDB(),
            return_queue,
        ),
    )
    recovery_daemon.start()

    # We need to import this after spawning the web server
    # because import ABCIServer will monkeypatch all sockets
    # for gevent.
    from abci.server import ABCIServer

    setproctitle.setproctitle("bigchaindb")

    # Start the ABCIServer
    abci = ABCI(TmVersion(bigchaindb.config["tendermint"]["version"]))
    if args.experimental_parallel_validation:
        app = ABCIServer(
            app=ParallelValidationApp(
                abci=abci.types,
                events_queue=exchange.get_publisher_queue(),
                return_queue=return_queue,
            )
        )
    else:
        app = ABCIServer(
            app=App(
                abci=abci.types,
                events_queue=exchange.get_publisher_queue(),
                return_queue=return_queue,
            )
        )
    app.run()


if __name__ == "__main__":
    start()
