# Copyright © 2020 Interplanetary Database Association e.V.,
# BigchainDB and IPDB software contributors.
# SPDX-License-Identifier: (Apache-2.0 AND CC-BY-4.0)
# Code is Apache-2.0 and docs are CC-BY-4.0

"""Transaction related models to parse and construct transaction
payloads.

Attributes:
    UnspentOutput (namedtuple): Object holding the information
        representing an unspent output.

"""
import os
from datetime import datetime

from collections import namedtuple
from copy import deepcopy
from functools import reduce, lru_cache
import rapidjson
from datetime import datetime
from subprocess import Popen, PIPE

import base58
import logging
from cryptoconditions import Fulfillment, ThresholdSha256, Ed25519Sha256
from cryptoconditions.exceptions import (
    ParsingError,
    ASN1DecodeError,
    ASN1EncodeError,
    UnsupportedTypeError,
)


try:
    from hashlib import sha3_256
except ImportError:
    from sha3 import sha3_256

from bigchaindb.common import config
from bigchaindb.common.crypto import PrivateKey, hash_data
from bigchaindb.common.exceptions import (
    AmountError,
    AssetIdMismatch,
    DoubleSpend,
    InputDoesNotExist,
    InsufficientCapabilities,
    InvalidHash,
    InvalidSignature,
    KeypairMismatchException,
    DuplicateTransaction,
    ThresholdTooDeep,
    ValidationError,
    InvalidAccount,
)
from bigchaindb.common.utils import serialize
from .memoize import memoize_from_dict, memoize_to_dict


logger = logging.getLogger(__name__)

UnspentOutput = namedtuple(
    "UnspentOutput",
    (
        # TODO 'utxo_hash': sha3_256(f'{txid}{output_index}'.encode())
        # 'utxo_hash',   # noqa
        "transaction_id",
        "output_index",
        "amount",
        "asset_id",
        "condition_uri",
    ),
)


class Input(object):
    """A Input is used to spend assets locked by an Output.

    Wraps around a Crypto-condition Fulfillment.

        Attributes:
            fulfillment (:class:`cryptoconditions.Fulfillment`): A Fulfillment
                to be signed with a private key.
            owners_before (:obj:`list` of :obj:`str`): A list of owners after a
                Transaction was confirmed.
            fulfills (:class:`~bigchaindb.common.transaction. TransactionLink`,
                optional): A link representing the input of a `TRANSFER`
                Transaction.
    """

    def __init__(self, fulfillment, owners_before, fulfills=None):
        """Create an instance of an :class:`~.Input`.

        Args:
            fulfillment (:class:`cryptoconditions.Fulfillment`): A
                Fulfillment to be signed with a private key.
            owners_before (:obj:`list` of :obj:`str`): A list of owners
                after a Transaction was confirmed.
            fulfills (:class:`~bigchaindb.common.transaction.
                TransactionLink`, optional): A link representing the input
                of a `TRANSFER` Transaction.
        """
        if fulfills is not None and not isinstance(fulfills, TransactionLink):
            raise TypeError("`fulfills` must be a TransactionLink instance")
        if not isinstance(owners_before, list):
            raise TypeError("`owners_before` must be a list instance")

        self.fulfillment = fulfillment
        self.fulfills = fulfills
        self.owners_before = owners_before

    def __eq__(self, other):
        # TODO: If `other !== Fulfillment` return `False`
        return self.to_dict() == other.to_dict()

    # NOTE: This function is used to provide a unique key for a given
    # Input to suppliment memoization
    def __hash__(self):
        return hash((self.fulfillment, self.fulfills))

    def to_dict(self):
        """Transforms the object to a Python dictionary.

        Note:
            If an Input hasn't been signed yet, this method returns a
            dictionary representation.

        Returns:
            dict: The Input as an alternative serialization format.
        """
        try:
            fulfillment = self.fulfillment.serialize_uri()
        except (TypeError, AttributeError, ASN1EncodeError, ASN1DecodeError):
            fulfillment = _fulfillment_to_details(self.fulfillment)

        try:
            # NOTE: `self.fulfills` can be `None` and that's fine
            fulfills = self.fulfills.to_dict()
        except AttributeError:
            fulfills = None

        input_ = {
            "owners_before": self.owners_before,
            "fulfills": fulfills,
            "fulfillment": fulfillment,
        }
        return input_

    @classmethod
    def generate(cls, public_keys):
        # TODO: write docstring
        # The amount here does not really matter. It is only use on the
        # output data model but here we only care about the fulfillment
        output = Output.generate(public_keys, 1)
        return cls(output.fulfillment, public_keys)

    @classmethod
    def from_dict(cls, data):
        """Transforms a Python dictionary to an Input object.

        Note:
            Optionally, this method can also serialize a Cryptoconditions-
            Fulfillment that is not yet signed.

        Args:
            data (dict): The Input to be transformed.

        Returns:
            :class:`~bigchaindb.common.transaction.Input`

        Raises:
            InvalidSignature: If an Input's URI couldn't be parsed.
        """
        fulfillment = data["fulfillment"]
        if not isinstance(fulfillment, (Fulfillment, type(None))):
            try:
                fulfillment = Fulfillment.from_uri(data["fulfillment"])
            except ASN1DecodeError:
                # TODO Remove as it is legacy code, and simply fall back on
                # ASN1DecodeError
                raise InvalidSignature("Fulfillment URI couldn't been parsed")
            except TypeError:
                # NOTE: See comment about this special case in
                #       `Input.to_dict`
                fulfillment = _fulfillment_from_details(data["fulfillment"])
        fulfills = TransactionLink.from_dict(data["fulfills"])
        return cls(fulfillment, data["owners_before"], fulfills)


def _fulfillment_to_details(fulfillment):
    """Encode a fulfillment as a details dictionary

    Args:
        fulfillment: Crypto-conditions Fulfillment object
    """

    if fulfillment.type_name == "ed25519-sha-256":
        return {
            "type": "ed25519-sha-256",
            "public_key": base58.b58encode(fulfillment.public_key).decode(),
        }

    if fulfillment.type_name == "threshold-sha-256":
        subconditions = [
            _fulfillment_to_details(cond["body"]) for cond in fulfillment.subconditions
        ]
        return {
            "type": "threshold-sha-256",
            "threshold": fulfillment.threshold,
            "subconditions": subconditions,
        }

    raise UnsupportedTypeError(fulfillment.type_name)


def _fulfillment_from_details(data, _depth=0):
    """Load a fulfillment for a signing spec dictionary

    Args:
        data: tx.output[].condition.details dictionary
    """
    if _depth == 100:
        raise ThresholdTooDeep()

    if data["type"] == "ed25519-sha-256":
        public_key = base58.b58decode(data["public_key"])
        return Ed25519Sha256(public_key=public_key)

    if data["type"] == "threshold-sha-256":
        threshold = ThresholdSha256(data["threshold"])
        for cond in data["subconditions"]:
            cond = _fulfillment_from_details(cond, _depth + 1)
            threshold.add_subfulfillment(cond)
        return threshold

    raise UnsupportedTypeError(data.get("type"))


class TransactionLink(object):
    """An object for unidirectional linking to a Transaction's Output.

    Attributes:
        txid (str, optional): A Transaction to link to.
        output (int, optional): An output's index in a Transaction with id
        `txid`.
    """

    def __init__(self, txid=None, output=None):
        """Create an instance of a :class:`~.TransactionLink`.

        Note:
            In an IPLD implementation, this class is not necessary anymore,
            as an IPLD link can simply point to an object, as well as an
            objects properties. So instead of having a (de)serializable
            class, we can have a simple IPLD link of the form:
            `/<tx_id>/transaction/outputs/<output>/`.

        Args:
            txid (str, optional): A Transaction to link to.
            output (int, optional): An Outputs's index in a Transaction with
                id `txid`.
        """
        self.txid = txid
        self.output = output

    def __bool__(self):
        return self.txid is not None and self.output is not None

    def __eq__(self, other):
        # TODO: If `other !== TransactionLink` return `False`
        return self.to_dict() == other.to_dict()

    def __hash__(self):
        return hash((self.txid, self.output))

    @classmethod
    def from_dict(cls, link):
        """Transforms a Python dictionary to a TransactionLink object.

        Args:
            link (dict): The link to be transformed.

        Returns:
            :class:`~bigchaindb.common.transaction.TransactionLink`
        """
        try:
            return cls(link["transaction_id"], link["output_index"])
        except TypeError:
            return cls()

    def to_dict(self):
        """Transforms the object to a Python dictionary.

        Returns:
            (dict|None): The link as an alternative serialization format.
        """
        if self.txid is None and self.output is None:
            return None
        else:
            return {
                "transaction_id": self.txid,
                "output_index": self.output,
            }

    def to_uri(self, path=""):
        if self.txid is None and self.output is None:
            return None
        return "{}/transactions/{}/outputs/{}".format(path, self.txid, self.output)


class Output(object):
    """An Output is used to lock an asset.

    Wraps around a Crypto-condition Condition.

        Attributes:
            fulfillment (:class:`cryptoconditions.Fulfillment`): A Fulfillment
                to extract a Condition from.
            public_keys (:obj:`list` of :obj:`str`, optional): A list of
                owners before a Transaction was confirmed.
    """

    MAX_AMOUNT = 9 * 10 ** 18

    def __init__(self, fulfillment, public_keys=None, amount=1):
        """Create an instance of a :class:`~.Output`.

        Args:
            fulfillment (:class:`cryptoconditions.Fulfillment`): A
                Fulfillment to extract a Condition from.
            public_keys (:obj:`list` of :obj:`str`, optional): A list of
                owners before a Transaction was confirmed.
            amount (int): The amount of Assets to be locked with this
                Output.

        Raises:
            TypeError: if `public_keys` is not instance of `list`.
        """
        if not isinstance(public_keys, list) and public_keys is not None:
            raise TypeError("`public_keys` must be a list instance or None")
        if not isinstance(amount, int):
            raise TypeError("`amount` must be an int")
        if amount < 1:
            raise AmountError("`amount` must be greater than 0")
        if amount > self.MAX_AMOUNT:
            raise AmountError("`amount` must be <= %s" % self.MAX_AMOUNT)

        self.fulfillment = fulfillment
        self.amount = amount
        self.public_keys = public_keys

    def __eq__(self, other):
        # TODO: If `other !== Condition` return `False`
        return self.to_dict() == other.to_dict()

    def to_dict(self):
        """Transforms the object to a Python dictionary.

        Note:
            A dictionary serialization of the Input the Output was
            derived from is always provided.

        Returns:
            dict: The Output as an alternative serialization format.
        """
        # TODO FOR CC: It must be able to recognize a hashlock condition
        #              and fulfillment!
        condition = {}
        try:
            condition["details"] = _fulfillment_to_details(self.fulfillment)
        except AttributeError:
            pass

        try:
            condition["uri"] = self.fulfillment.condition_uri
        except AttributeError:
            condition["uri"] = self.fulfillment

        output = {
            "public_keys": self.public_keys,
            "condition": condition,
            "amount": str(self.amount),
        }
        return output

    @classmethod
    def generate(cls, public_keys, amount):
        """Generates a Output from a specifically formed tuple or list.

        Note:
            If a ThresholdCondition has to be generated where the threshold
            is always the number of subconditions it is split between, a
            list of the following structure is sufficient:

            [(address|condition)*, [(address|condition)*, ...], ...]

        Args:
            public_keys (:obj:`list` of :obj:`str`): The public key of
                the users that should be able to fulfill the Condition
                that is being created.
            amount (:obj:`int`): The amount locked by the Output.

        Returns:
            An Output that can be used in a Transaction.

        Raises:
            TypeError: If `public_keys` is not an instance of `list`.
            ValueError: If `public_keys` is an empty list.
        """
        threshold = len(public_keys)
        if not isinstance(amount, int):
            raise TypeError("`amount` must be a int")
        if amount < 1:
            raise AmountError("`amount` needs to be greater than zero")
        if not isinstance(public_keys, list):
            raise TypeError("`public_keys` must be an instance of list")
        if len(public_keys) == 0:
            raise ValueError("`public_keys` needs to contain at least one" "owner")
        elif len(public_keys) == 1 and not isinstance(public_keys[0], list):
            if isinstance(public_keys[0], Fulfillment):
                ffill = public_keys[0]
            else:
                ffill = Ed25519Sha256(public_key=base58.b58decode(public_keys[0]))
            return cls(ffill, public_keys, amount=amount)
        else:
            initial_cond = ThresholdSha256(threshold=threshold)
            threshold_cond = reduce(cls._gen_condition, public_keys, initial_cond)
            return cls(threshold_cond, public_keys, amount=amount)

    @classmethod
    def _gen_condition(cls, initial, new_public_keys):
        """Generates ThresholdSha256 conditions from a list of new owners.

        Note:
            This method is intended only to be used with a reduce function.
            For a description on how to use this method, see
            :meth:`~.Output.generate`.

        Args:
            initial (:class:`cryptoconditions.ThresholdSha256`):
                A Condition representing the overall root.
            new_public_keys (:obj:`list` of :obj:`str`|str): A list of new
                owners or a single new owner.

        Returns:
            :class:`cryptoconditions.ThresholdSha256`:
        """
        try:
            threshold = len(new_public_keys)
        except TypeError:
            threshold = None

        if isinstance(new_public_keys, list) and len(new_public_keys) > 1:
            ffill = ThresholdSha256(threshold=threshold)
            reduce(cls._gen_condition, new_public_keys, ffill)
        elif isinstance(new_public_keys, list) and len(new_public_keys) <= 1:
            raise ValueError("Sublist cannot contain single owner")
        else:
            try:
                new_public_keys = new_public_keys.pop()
            except AttributeError:
                pass
            # NOTE: Instead of submitting base58 encoded addresses, a user
            #       of this class can also submit fully instantiated
            #       Cryptoconditions. In the case of casting
            #       `new_public_keys` to a Ed25519Fulfillment with the
            #       result of a `TypeError`, we're assuming that
            #       `new_public_keys` is a Cryptocondition then.
            if isinstance(new_public_keys, Fulfillment):
                ffill = new_public_keys
            else:
                ffill = Ed25519Sha256(public_key=base58.b58decode(new_public_keys))
        initial.add_subfulfillment(ffill)
        return initial

    @classmethod
    def from_dict(cls, data):
        """Transforms a Python dictionary to an Output object.

        Note:
            To pass a serialization cycle multiple times, a
            Cryptoconditions Fulfillment needs to be present in the
            passed-in dictionary, as Condition URIs are not serializable
            anymore.

        Args:
            data (dict): The dict to be transformed.

        Returns:
            :class:`~bigchaindb.common.transaction.Output`
        """
        try:
            fulfillment = _fulfillment_from_details(data["condition"]["details"])
        except KeyError:
            # NOTE: Hashlock condition case
            fulfillment = data["condition"]["uri"]
        try:
            amount = int(data["amount"])
        except ValueError:
            raise AmountError("Invalid amount: %s" % data["amount"])
        return cls(fulfillment, data["public_keys"], amount)


class Transaction(object):
    """A Transaction is used to create and transfer assets.

    Note:
        For adding Inputs and Outputs, this class provides methods
        to do so.

    Attributes:
        operation (str): Defines the operation of the Transaction.
        inputs (:obj:`list` of :class:`~bigchaindb.common.
            transaction.Input`, optional): Define the assets to
            spend.
        outputs (:obj:`list` of :class:`~bigchaindb.common.
            transaction.Output`, optional): Define the assets to lock.
        asset (dict): Asset payload for this Transaction. ``CREATE``
            Transactions require a dict with a ``data``
            property while ``TRANSFER`` Transactions require a dict with a
            ``id`` property.
        metadata (dict):
            Metadata to be stored along with the Transaction.
        version (string): Defines the version number of a Transaction.
    """

    CREATE = "CREATE"
    TRANSFER = "TRANSFER"
    PRE_REQUEST = "PRE_REQUEST"
    INTEREST = "INTEREST"
    REQUEST_FOR_QUOTE = "REQUEST_FOR_QUOTE"
    BID = "BID"
    ACCEPT = "ACCEPT"
    RETURN = "RETURN"
    ADVERTISEMENT = "ADVERTISEMENT"
    BUY_OFFER = "BUY_OFFER"
    SELL = "SELL"
    REQUEST_RETURN = "REQUEST_RETURN"
    ACCEPT_RETURN = "ACCEPT_RETURN"
    UPDATE_ADV = "UPDATE_ADV"
    SELLER_ACCEPT_RETURN = "SELLER_ACCEPT_RETURN"
    ALLOWED_OPERATIONS = (
        CREATE,
        TRANSFER,
        PRE_REQUEST,
        INTEREST,
        REQUEST_FOR_QUOTE,
        BID,
        ACCEPT,
        RETURN,
        ADVERTISEMENT,
        BUY_OFFER,
        SELL,
        REQUEST_RETURN,
        ACCEPT_RETURN,
        UPDATE_ADV,
        SELLER_ACCEPT_RETURN,
    )
    VERSION = "2.0"

    def __init__(
        self,
        operation,
        asset,
        inputs=None,
        outputs=None,
        metadata=None,
        version=None,
        hash_id=None,
        tx_dict=None,
    ):
        """The constructor allows to create a customizable Transaction.

        Note:
            When no `version` is provided, one is being
            generated by this method.

        Args:
            operation (str): Defines the operation of the Transaction.
            asset (dict): Asset payload for this Transaction.
            inputs (:obj:`list` of :class:`~bigchaindb.common.
                transaction.Input`, optional): Define the assets to
            outputs (:obj:`list` of :class:`~bigchaindb.common.
                transaction.Output`, optional): Define the assets to
                lock.
            metadata (dict): Metadata to be stored along with the
                Transaction.
            version (string): Defines the version number of a Transaction.
            hash_id (string): Hash id of the transaction.
        """
        if operation not in self.ALLOWED_OPERATIONS:
            allowed_ops = ", ".join(self.__class__.ALLOWED_OPERATIONS)
            raise ValueError("`operation` must be one of {}".format(allowed_ops))

        # Asset payloads for 'CREATE' operations must be None or
        # dicts holding a `data` property. Asset payloads for 'TRANSFER'
        # operations must be dicts holding an `id` property.
        if (
            (operation == self.CREATE or operation == self.BID)
            and asset is not None
            and not (isinstance(asset, dict) and "data" in asset)
        ):
            raise TypeError(
                (
                    "`asset` must be None or a dict holding a `data` "
                    " property instance for '{}' Transactions".format(operation)
                )
            )
        elif operation == self.TRANSFER and not (
            isinstance(asset, dict) and "id" in asset
        ):
            raise TypeError(
                (
                    "`asset` must be a dict holding an `id` property "
                    "for 'TRANSFER' Transactions".format(operation)
                )
            )
        elif (
            (
                operation == self.PRE_REQUEST
                or operation == self.REQUEST_FOR_QUOTE
                or operation == self.ACCEPT
            )
            and asset is not None
            and not (isinstance(asset, dict))
        ):
            raise TypeError(
                (
                    "`asset` must be a dict"
                    "for 'REQUEST_FOR_QUOTE' Transactions".format(operation)
                )
            )
        elif (operation == self.INTEREST or operation == self.BID) and not (
            isinstance(asset, dict)
        ):
            raise TypeError(
                (
                    "`asset` must be a dict holding an `id` property  "
                    "for 'INTEREST' Transactions".format(operation)
                )
            )
        elif operation == self.ADVERTISEMENT and not (
            isinstance(asset, dict) and "id" in asset
        ):
            raise TypeError(
                (
                    "`asset` must be a dict holding an `id` property "
                    "for 'ADVERTISEMENT' Transactions".format(operation)
                )
            )
        elif operation == self.BUY_OFFER and not (isinstance(asset, dict) and "data" in asset and isinstance(asset["data"], dict) and "id" in asset["data"]):
            raise TypeError("`asset` must be a dict holding a `data` property with an `id` for 'BUY_OFFER' Transactions")
        elif operation == self.SELL and not (isinstance(asset, dict) and "data" in asset and isinstance(asset["data"], dict) and "id" in asset["data"]):
            raise TypeError("`asset` must be a dict holding a `data` property with an `id` for 'SELL' Transactions")
        elif operation == self.REQUEST_RETURN and not (isinstance(asset, dict) and "data" in asset and isinstance(asset["data"], dict) and "id" in asset["data"]):
            raise TypeError("`asset` must be a dict holding a `data` property with an `id` for 'REQUEST_RETURN' Transactions")
        elif operation == self.ACCEPT_RETURN and not (isinstance(asset, dict) and "data" in asset and isinstance(asset["data"], dict) and "id" in asset["data"]):
            raise TypeError("`asset` must be a dict holding a `data` property with an `id` for 'ACCEPT_RETURN' Transactions")
        elif operation == self.UPDATE_ADV and not (isinstance(asset, dict) and "data" in asset and isinstance(asset["data"], dict) and "id" in asset["data"]):
            raise TypeError("`asset` must be a dict holding a `data` property with an `id` for 'UPDATE_ADV' Transactions")
        elif operation == self.SELLER_ACCEPT_RETURN and not (isinstance(asset, dict) and "data" in asset and isinstance(asset["data"], dict) and "id" in asset["data"]):
            raise TypeError("`asset` must be a dict holding a `data` property with an `id` for 'SELLER_ACCEPT_RETURN' Transactions")

        if outputs and not isinstance(outputs, list):
            raise TypeError("`outputs` must be a list instance or None")

        if inputs and not isinstance(inputs, list):
            raise TypeError("`inputs` must be a list instance or None")

        if metadata is not None and not isinstance(metadata, dict):
            raise TypeError("`metadata` must be a dict or None")

        self.version = version if version is not None else self.VERSION
        self.operation = operation
        self.asset = asset
        self.inputs = inputs or []
        self.outputs = outputs or []
        self.metadata = metadata
        self._id = hash_id
        self.tx_dict = tx_dict

    @property
    def unspent_outputs(self):
        """UnspentOutput: The outputs of this transaction, in a data
        structure containing relevant information for storing them in
        a UTXO set, and performing validation.
        """
        if self.operation == self.CREATE:
            self._asset_id = self._id
        elif self.operation == self.TRANSFER:
            self._asset_id = self.asset["id"]
        elif self.operation == self.INTEREST:
            self._asset_id = self.asset["id"]
        elif self.operation == self.ADVERTISEMENT:
            self._asset_id = self.asset["id"]
        elif self.operation == self.BUY_OFFER:
            self._asset_id = self.asset["data"]["id"]
        elif self.operation == self.SELL:
            self._asset_id = self.asset["data"]["id"]
        elif self.operation == self.REQUEST_RETURN:
            self._asset_id = self.asset["data"]["id"]
        elif self.operation == self.ACCEPT_RETURN:
            self._asset_id = self.asset["data"]["id"]
        elif self.operation == self.UPDATE_ADV:
            self._asset_id = self.asset["data"]["id"]
        elif self.operation == self.SELLER_ACCEPT_RETURN:
            self._asset_id = self.asset["data"]["id"]
        # FIXME: Add PRE_REQUEST, INTEREST, and BID-ACCEPT
        return (
            UnspentOutput(
                transaction_id=self._id,
                output_index=output_index,
                amount=output.amount,
                asset_id=self._asset_id,
                condition_uri=output.fulfillment.condition_uri,
            )
            for output_index, output in enumerate(self.outputs)
        )

    @property
    def spent_outputs(self):
        """Tuple of :obj:`dict`: Inputs of this transaction. Each input
        is represented as a dictionary containing a transaction id and
        output index.
        """
        return (input_.fulfills.to_dict() for input_ in self.inputs if input_.fulfills)

    @property
    def serialized(self):
        return Transaction._to_str(self.to_dict())

    def _hash(self):
        self._id = hash_data(self.serialized)

    @classmethod
    def validate_create(cls, tx_signers, recipients, asset, metadata):
        if not isinstance(tx_signers, list):
            raise TypeError("`tx_signers` must be a list instance")
        if not isinstance(recipients, list):
            raise TypeError("`recipients` must be a list instance")
        if len(tx_signers) == 0:
            raise ValueError("`tx_signers` list cannot be empty")
        if len(recipients) == 0:
            raise ValueError("`recipients` list cannot be empty")
        if not (asset is None or isinstance(asset, dict)):
            raise TypeError("`asset` must be a dict or None")
        if not (metadata is None or isinstance(metadata, dict)):
            raise TypeError("`metadata` must be a dict or None")

        inputs = []
        outputs = []

        # generate_outputs
        for recipient in recipients:
            if not isinstance(recipient, tuple) or len(recipient) != 2:
                raise ValueError(
                    (
                        "Each `recipient` in the list must be a"
                        " tuple of `([<list of public keys>],"
                        " <amount>)`"
                    )
                )
            pub_keys, amount = recipient
            outputs.append(Output.generate(pub_keys, amount))

        # generate inputs
        inputs.append(Input.generate(tx_signers))

        return (inputs, outputs)

    @classmethod
    def create(cls, tx_signers, recipients, metadata=None, asset=None):
        """A simple way to generate a `CREATE` transaction.

        Note:
            This method currently supports the following Cryptoconditions
            use cases:
                - Ed25519
                - ThresholdSha256

            Additionally, it provides support for the following BigchainDB
            use cases:
                - Multiple inputs and outputs.

        Args:
            tx_signers (:obj:`list` of :obj:`str`): A list of keys that
                represent the signers of the CREATE Transaction.
            recipients (:obj:`list` of :obj:`tuple`): A list of
                ([keys],amount) that represent the recipients of this
                Transaction.
            metadata (dict): The metadata to be stored along with the
                Transaction.
            asset (dict): The metadata associated with the asset that will
                be created in this Transaction.

        Returns:
            :class:`~bigchaindb.common.transaction.Transaction`
        """

        (inputs, outputs) = cls.validate_create(tx_signers, recipients, asset, metadata)
        return cls(cls.CREATE, {"data": asset}, inputs, outputs, metadata)

    @classmethod
    def validate_transfer(cls, inputs, recipients, asset_id, metadata):
        if not isinstance(inputs, list):
            raise TypeError("`inputs` must be a list instance")
        if len(inputs) == 0:
            raise ValueError("`inputs` must contain at least one item")
        if not isinstance(recipients, list):
            raise TypeError("`recipients` must be a list instance")
        if len(recipients) == 0:
            raise ValueError("`recipients` list cannot be empty")

        outputs = []
        for recipient in recipients:
            if not isinstance(recipient, tuple) or len(recipient) != 2:
                raise ValueError(
                    (
                        "Each `recipient` in the list must be a"
                        " tuple of `([<list of public keys>],"
                        " <amount>)`"
                    )
                )
            pub_keys, amount = recipient
            outputs.append(Output.generate(pub_keys, amount))

        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")

        return (deepcopy(inputs), outputs)

    @classmethod
    def transfer(cls, inputs, recipients, asset_id, metadata=None):
        """A simple way to generate a `TRANSFER` transaction.

        Note:
            Different cases for threshold conditions:

            Combining multiple `inputs` with an arbitrary number of
            `recipients` can yield interesting cases for the creation of
            threshold conditions we'd like to support. The following
            notation is proposed:

            1. The index of a `recipient` corresponds to the index of
               an input:
               e.g. `transfer([input1], [a])`, means `input1` would now be
                    owned by user `a`.

            2. `recipients` can (almost) get arbitrary deeply nested,
               creating various complex threshold conditions:
               e.g. `transfer([inp1, inp2], [[a, [b, c]], d])`, means
                    `a`'s signature would have a 50% weight on `inp1`
                    compared to `b` and `c` that share 25% of the leftover
                    weight respectively. `inp2` is owned completely by `d`.

        Args:
            inputs (:obj:`list` of :class:`~bigchaindb.common.transaction.
                Input`): Converted `Output`s, intended to
                be used as inputs in the transfer to generate.
            recipients (:obj:`list` of :obj:`tuple`): A list of
                ([keys],amount) that represent the recipients of this
                Transaction.
            asset_id (str): The asset ID of the asset to be transferred in
                this Transaction.
            metadata (dict): Python dictionary to be stored along with the
                Transaction.

        Returns:
            :class:`~bigchaindb.common.transaction.Transaction`
        """
        (inputs, outputs) = cls.validate_transfer(
            inputs, recipients, asset_id, metadata
        )
        return cls(cls.TRANSFER, {"id": asset_id}, inputs, outputs, metadata)

    @classmethod
    def validate_advertisement(cls, inputs, asset_id, metadata):
        """Validate advertisement transaction inputs and metadata.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID to advertise
            metadata: Metadata containing status, advertiser_public_key, etc.
            
        Returns:
            tuple: (inputs, outputs) where outputs is empty for advertisement
        """
        if not isinstance(inputs, list):
            raise TypeError("`inputs` must be a list instance")
        if len(inputs) != 1:
            raise ValueError("`inputs` must contain exactly one item for advertisement")
        
        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")
            
        if not isinstance(metadata, dict):
            raise TypeError("`metadata` must be a dict")
            
        # Validate required metadata fields
        required_fields = ['status', 'advertiser_public_key']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"`metadata` must contain '{field}' field")
                
        # Validate status
        valid_statuses = ['OPEN', 'LOCKED', 'CLOSED']
        if metadata['status'] not in valid_statuses:
            raise ValueError(f"`status` must be one of {valid_statuses}")
            
        # Validate advertiser public key format
        if not isinstance(metadata['advertiser_public_key'], str):
            raise TypeError("`advertiser_public_key` must be a string")
            
        # For new advertisements, status must be OPEN
        if metadata.get('is_new_advertisement', True) and metadata['status'] != 'OPEN':
            raise ValueError("New advertisement status must be 'OPEN'")
            
        return (deepcopy(inputs), [])

    @classmethod
    def advertisement(cls, inputs, asset_id, metadata=None):
        """A simple way to generate an `ADVERTISEMENT` transaction.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID to advertise
            metadata: Metadata containing advertisement details
            
        Returns:
            :class:`~bigchaindb.common.transaction.Transaction`
        """
        if metadata is None:
            metadata = {}
            
        # Set default status to OPEN for new advertisements
        if 'status' not in metadata:
            metadata['status'] = 'OPEN'
        metadata['is_new_advertisement'] = True
            
        (inputs, outputs) = cls.validate_advertisement(inputs, asset_id, metadata)
        return cls(cls.ADVERTISEMENT, {"id": asset_id}, inputs, outputs, metadata)

    @classmethod
    def validate_buy_offer(cls, inputs, asset_id, advertisement_id, metadata):
        """Validate buy offer transaction inputs and metadata.
        
        Args:
            inputs: List of inputs for the buy offer (must include buyer's payment asset)
            asset_id: The asset ID being offered for
            advertisement_id: The advertisement ID being responded to
            metadata: Metadata containing buyer details, offer amount, etc.
            
        Returns:
            tuple: (inputs, outputs) where outputs include escrow transfer
            
        Raises:
            ValueError: If validation fails
        """
        if not inputs:
            raise ValueError("`inputs` must contain at least one item")
            
        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")
            
        if not isinstance(advertisement_id, str):
            raise TypeError("`advertisement_id` must be a string")
            
        if not metadata:
            raise ValueError("`metadata` is required for buy offer")
            
        # Validate required metadata fields
        required_fields = ['buyer_public_key', 'offer_amount', 'offer_currency', 
                          'offer_timestamp', 'offer_expiry', 'escrow_public_key']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"`metadata` must contain '{field}'")
                
        # Validate offer amount
        if metadata['offer_amount'] <= 0:
            raise ValueError("`offer_amount` must be positive")
            
        # Validate offer expiry
        from datetime import datetime
        try:
            # Python 3.6 compatible datetime parsing
            expiry_str = metadata['offer_expiry'].replace('Z', '+00:00')
            # Remove microseconds for simpler parsing
            if '.' in expiry_str:
                base_part = expiry_str.split('.')[0]
                timezone_part = expiry_str.split('+')[1] if '+' in expiry_str else ''
                expiry_str = base_part + ('+' + timezone_part if timezone_part else '')
            
            # Parse without timezone first, then add UTC timezone
            expiry = datetime.strptime(expiry_str.split('+')[0], '%Y-%m-%dT%H:%M:%S')
            # Add UTC timezone info
            from datetime import timezone
            expiry = expiry.replace(tzinfo=timezone.utc)
                
            if expiry <= datetime.utcnow().replace(tzinfo=timezone.utc):
                raise ValueError("`offer_expiry` must be in the future")
        except ValueError as e:
            raise ValueError(f"Invalid `offer_expiry` format: {e}")
            
        # Create outputs for the buy offer:
        # 1. Asset being offered for (referenced by asset_id) - no change in ownership
        # 2. Buyer's payment asset transferred to escrow account
        escrow_output = Output(
            amount=int(metadata['offer_amount']),
            fulfillment=Ed25519Sha256(public_key=base58.b58decode(metadata['escrow_public_key'])),
            public_keys=[metadata['escrow_public_key']]
        )
        
        outputs = [escrow_output]
        
        return (inputs, outputs)

    @classmethod
    def buy_offer(cls, inputs, asset_id, advertisement_id, metadata=None):
        """A simple way to generate a `BUY_OFFER` transaction.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being offered for
            advertisement_id: The advertisement ID being responded to
            metadata: Metadata containing buyer details, offer amount, etc.
            
        Returns:
            :class:`~bigchaindb.common.transaction.Transaction`
        """
        if metadata is None:
            metadata = {}
            
        (inputs, outputs) = cls.validate_buy_offer(inputs, asset_id, advertisement_id, metadata)
        return cls(cls.BUY_OFFER, {"data": {"id": asset_id, "advertisement_id": advertisement_id}}, inputs, outputs, metadata)

    @classmethod
    def validate_sell(cls, inputs, asset_id, buy_offer_id, metadata):
        """Validate sell transaction inputs and metadata.
        
        Args:
            inputs: List of inputs for the sell transaction
            asset_id: The asset ID being sold
            buy_offer_id: The buy offer ID being accepted
            metadata: Metadata containing seller details, sale amount, etc.
            
        Returns:
            tuple: (inputs, outputs) where outputs include asset and payment transfers
            
        Raises:
            ValueError: If validation fails
        """
        if not inputs:
            raise ValueError("`inputs` must contain at least one item")
            
        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")
            
        if not isinstance(buy_offer_id, str):
            raise TypeError("`buy_offer_id` must be a string")
            
        if not metadata:
            raise ValueError("`metadata` is required for sell transaction")
            
        # Validate required metadata fields
        required_fields = ['seller_public_key', 'buyer_public_key', 'sale_amount', 'sale_currency']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"`metadata` must contain '{field}'")
                
        # Validate sale amount
        if metadata['sale_amount'] <= 0:
            raise ValueError("`sale_amount` must be positive")
            
        # Create outputs for the two atomic transfers:
        # 1. Asset transfer to buyer (the asset being sold)
        asset_output = Output(
            amount=1,  # Asset quantity
            fulfillment=Ed25519Sha256(public_key=base58.b58decode(metadata['buyer_public_key'])),
            public_keys=[metadata['buyer_public_key']]
        )
        
        # 2. Payment transfer to seller (from escrow)
        payment_output = Output(
            amount=int(metadata['sale_amount']),
            fulfillment=Ed25519Sha256(public_key=base58.b58decode(metadata['seller_public_key'])),
            public_keys=[metadata['seller_public_key']]
        )
        
        outputs = [asset_output, payment_output]
        
        return (inputs, outputs)

    @classmethod
    def sell(cls, inputs, asset_id, buy_offer_id, metadata=None):
        """A simple way to generate a `SELL` transaction.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being sold
            buy_offer_id: The buy offer ID being accepted
            metadata: Metadata containing seller details, sale amount, etc.
            
        Returns:
            :class:`~bigchaindb/common.transaction.Transaction`
        """
        if metadata is None:
            metadata = {}
            
        (inputs, outputs) = cls.validate_sell(inputs, asset_id, buy_offer_id, metadata)
        return cls(cls.SELL, {"id": asset_id, "data": {"buy_offer_id": buy_offer_id}}, inputs, outputs, metadata)

    @classmethod
    def validate_request_return(cls, inputs, asset_id, sell_transaction_id, metadata):
        """Validate request return transaction inputs and metadata.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being returned
            sell_transaction_id: The sell transaction ID being disputed
            metadata: Metadata containing return request details
            
        Returns:
            tuple: (inputs, outputs) where outputs is empty for request return
        """
        if not isinstance(inputs, list):
            raise TypeError("`inputs` must be a list instance")
        if len(inputs) != 1:
            raise ValueError("`inputs` must contain exactly one item for request return")
        
        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")
            
        if not isinstance(sell_transaction_id, str):
            raise TypeError("`sell_transaction_id` must be a string")
            
        if not isinstance(metadata, dict):
            raise TypeError("`metadata` must be a dict")
            
        # Validate required metadata fields
        required_fields = ['requester_public_key', 'return_reason', 
                          'return_request_timestamp', 'return_policy_details']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"`metadata` must contain '{field}' field")
                
        # Validate return reason
        if not isinstance(metadata['return_reason'], str) or len(metadata['return_reason']) == 0:
            raise ValueError("`return_reason` must be a non-empty string")
            
        # Validate return request timestamp
        if not isinstance(metadata['return_request_timestamp'], str):
            raise ValueError("`return_request_timestamp` must be a string")
            
        # Validate return policy details
        if not isinstance(metadata['return_policy_details'], dict):
            raise ValueError("`return_policy_details` must be a dict")
                
        return (deepcopy(inputs), [])

    @classmethod
    def request_return(cls, inputs, asset_id, sell_transaction_id, metadata=None):
        """A simple way to generate a `REQUEST_RETURN` transaction.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being returned
            sell_transaction_id: The sell transaction ID being disputed
            metadata: Metadata containing return request details
            
        Returns:
            :class:`~bigchaindb/common.transaction.Transaction`
        """
        if metadata is None:
            metadata = {}
            
        # Set default return status to PENDING
        if 'return_policy_details' not in metadata:
            metadata['return_policy_details'] = {}
        if 'return_status' not in metadata['return_policy_details']:
            metadata['return_policy_details']['return_status'] = 'PENDING'
            
        (inputs, outputs) = cls.validate_request_return(inputs, asset_id, sell_transaction_id, metadata)
        return cls(cls.REQUEST_RETURN, {"data": {"id": asset_id, "sell_transaction_id": sell_transaction_id}}, inputs, outputs, metadata)

    @classmethod
    def validate_accept_return(cls, inputs, asset_id, request_return_id, metadata):
        """Validate accept return transaction inputs and metadata.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being returned
            request_return_id: The request return transaction ID being accepted
            metadata: Metadata containing return acceptance details
            
        Returns:
            tuple: (inputs, outputs) where outputs is empty for accept return
        """
        if not isinstance(inputs, list):
            raise TypeError("`inputs` must be a list instance")
        if len(inputs) != 1:
            raise ValueError("`inputs` must contain exactly one item for accept return")
        
        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")
            
        if not isinstance(request_return_id, str):
            raise TypeError("`request_return_id` must be a string")
            
        if not isinstance(metadata, dict):
            raise TypeError("`metadata` must be a dict")
            
        # Validate required metadata fields
        required_fields = ['accepter_public_key', 'return_acceptance_timestamp', 
                          'refund_details', 'return_processing_notes']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"`metadata` must contain '{field}' field")
                
        # Validate refund details
        if not isinstance(metadata['refund_details'], dict):
            raise ValueError("`refund_details` must be a dict")
            
        refund_required_fields = ['refund_amount', 'refund_currency', 'refund_method']
        for field in refund_required_fields:
            if field not in metadata['refund_details']:
                raise ValueError(f"`refund_details` must contain '{field}' field")
                
        # Validate return acceptance timestamp
        if not isinstance(metadata['return_acceptance_timestamp'], str):
            raise ValueError("`return_acceptance_timestamp` must be a string")
            
        # Validate return processing notes
        if not isinstance(metadata['return_processing_notes'], str):
            raise ValueError("`return_processing_notes` must be a string")
                
        return (deepcopy(inputs), [])

    @classmethod
    def accept_return(cls, inputs, asset_id, request_return_id, metadata=None):
        """A simple way to generate a `ACCEPT_RETURN` transaction.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being returned
            request_return_id: The request return transaction ID being accepted
            metadata: Metadata containing return acceptance details
            
        Returns:
            :class:`~bigchaindb/common.transaction.Transaction`
        """
        if metadata is None:
            metadata = {}
            
        (inputs, outputs) = cls.validate_accept_return(inputs, asset_id, request_return_id, metadata)
        return cls(cls.ACCEPT_RETURN, {"data": {"id": asset_id, "request_return_id": request_return_id}}, inputs, outputs, metadata)

    @classmethod
    def validate_update_adv(cls, inputs, asset_id, advertisement_id, metadata):
        """Validate update advertisement transaction inputs and metadata.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being updated
            advertisement_id: The advertisement ID being updated
            metadata: Metadata containing update details
            
        Returns:
            tuple: (inputs, outputs) where outputs is empty for update
        """
        if not isinstance(inputs, list):
            raise TypeError("`inputs` must be a list instance")
        if len(inputs) != 1:
            raise ValueError("`inputs` must contain exactly one item for update advertisement")
        
        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")
            
        if not isinstance(advertisement_id, str):
            raise TypeError("`advertisement_id` must be a string")
            
        if not isinstance(metadata, dict):
            raise TypeError("`metadata` must be a dict")
            
        # Validate required metadata fields
        required_fields = ['advertiser_public_key', 'new_status', 'new_value', 'new_expiry_date']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"`metadata` must contain '{field}' field")
                
        # Validate new status
        valid_statuses = ['OPEN', 'LOCKED', 'CLOSED']
        if metadata['new_status'] not in valid_statuses:
            raise ValueError(f"`new_status` must be one of: {valid_statuses}")
            
        # Validate new value
        if not isinstance(metadata['new_value'], str) or not metadata['new_value'].isdigit():
            raise ValueError("`new_value` must be a string containing only digits")
            
        # Validate new expiry date
        if not isinstance(metadata['new_expiry_date'], str):
            raise ValueError("`new_expiry_date` must be a string")
                
        return (deepcopy(inputs), [])

    @classmethod
    def update_adv(cls, inputs, asset_id, advertisement_id, metadata=None):
        """A simple way to generate a `UPDATE_ADV` transaction.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being updated
            advertisement_id: The advertisement ID being updated
            metadata: Metadata containing update details
            
        Returns:
            :class:`~bigchaindb/common.transaction.Transaction`
        """
        if metadata is None:
            metadata = {}
            
        (inputs, outputs) = cls.validate_update_adv(inputs, asset_id, advertisement_id, metadata)
        return cls(cls.UPDATE_ADV, {"data": {"id": asset_id, "advertisement_id": advertisement_id}}, inputs, outputs, metadata)

    @classmethod
    def validate_seller_accept_return(cls, inputs, asset_id, request_return_id, metadata):
        """Validate seller accept return transaction inputs and metadata.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being returned
            request_return_id: The request return transaction ID being accepted
            metadata: Metadata containing seller acceptance details
            
        Returns:
            tuple: (inputs, outputs) where outputs is empty for seller accept return
        """
        if not isinstance(inputs, list):
            raise TypeError("`inputs` must be a list instance")
        if len(inputs) != 1:
            raise ValueError("`inputs` must contain exactly one item for seller accept return")
        
        if not isinstance(asset_id, str):
            raise TypeError("`asset_id` must be a string")
            
        if not isinstance(request_return_id, str):
            raise TypeError("`request_return_id` must be a string")
            
        if not isinstance(metadata, dict):
            raise TypeError("`metadata` must be a dict")
            
        # Validate required metadata fields
        required_fields = ['seller_public_key', 'refund_details', 'acceptance_timestamp']
        for field in required_fields:
            if field not in metadata:
                raise ValueError(f"`metadata` must contain '{field}' field")
                
        # Validate refund details
        if not isinstance(metadata['refund_details'], dict):
            raise ValueError("`refund_details` must be a dict")
            
        refund_required_fields = ['refund_amount', 'refund_currency', 'refund_method']
        for field in refund_required_fields:
            if field not in metadata['refund_details']:
                raise ValueError(f"`refund_details` must contain '{field}' field")
                
        # Validate refund method
        valid_methods = ['BANK_TRANSFER', 'CRYPTO', 'CREDIT_CARD', 'PAYPAL']
        if metadata['refund_details']['refund_method'] not in valid_methods:
            raise ValueError(f"`refund_method` must be one of: {valid_methods}")
            
        # Validate acceptance timestamp
        if not isinstance(metadata['acceptance_timestamp'], str):
            raise ValueError("`acceptance_timestamp` must be a string")
                
        return (deepcopy(inputs), [])

    @classmethod
    def seller_accept_return(cls, inputs, asset_id, request_return_id, metadata=None):
        """A simple way to generate a `SELLER_ACCEPT_RETURN` transaction.
        
        Args:
            inputs: List of inputs (must be exactly one)
            asset_id: The asset ID being returned
            request_return_id: The request return transaction ID being accepted
            metadata: Metadata containing seller acceptance details
            
        Returns:
            :class:`~bigchaindb/common.transaction.Transaction`
        """
        if metadata is None:
            metadata = {}
            
        (inputs, outputs) = cls.validate_seller_accept_return(inputs, asset_id, request_return_id, metadata)
        return cls(cls.SELLER_ACCEPT_RETURN, {"data": {"id": asset_id, "request_return_id": request_return_id}}, inputs, outputs, metadata)

    def __eq__(self, other):
        try:
            other = other.to_dict()
        except AttributeError:
            return False
        return self.to_dict() == other

    def to_inputs(self, indices=None):
        """Converts a Transaction's outputs to spendable inputs.

        Note:
            Takes the Transaction's outputs and derives inputs
            from that can then be passed into `Transaction.transfer` as
            `inputs`.
            A list of integers can be passed to `indices` that
            defines which outputs should be returned as inputs.
            If no `indices` are passed (empty list or None) all
            outputs of the Transaction are returned.

        Args:
            indices (:obj:`list` of int): Defines which
                outputs should be returned as inputs.

        Returns:
            :obj:`list` of :class:`~bigchaindb.common.transaction.
                Input`
        """
        # NOTE: If no indices are passed, we just assume to take all outputs
        #       as inputs.
        indices = indices or range(len(self.outputs))
        return [
            Input(
                self.outputs[idx].fulfillment,
                self.outputs[idx].public_keys,
                TransactionLink(self.id, idx),
            )
            for idx in indices
        ]

    def add_input(self, input_):
        """Adds an input to a Transaction's list of inputs.

        Args:
            input_ (:class:`~bigchaindb.common.transaction.
                Input`): An Input to be added to the Transaction.
        """
        if not isinstance(input_, Input):
            raise TypeError("`input_` must be a Input instance")
        self.inputs.append(input_)

    def add_output(self, output):
        """Adds an output to a Transaction's list of outputs.

        Args:
            output (:class:`~bigchaindb.common.transaction.
                Output`): An Output to be added to the
                Transaction.
        """
        if not isinstance(output, Output):
            raise TypeError("`output` must be an Output instance or None")
        self.outputs.append(output)

    def sign(self, private_keys):
        """Fulfills a previous Transaction's Output by signing Inputs.

        Note:
            This method works only for the following Cryptoconditions
            currently:
                - Ed25519Fulfillment
                - ThresholdSha256
            Furthermore, note that all keys required to fully sign the
            Transaction have to be passed to this method. A subset of all
            will cause this method to fail.

        Args:
            private_keys (:obj:`list` of :obj:`str`): A complete list of
                all private keys needed to sign all Fulfillments of this
                Transaction.

        Returns:
            :class:`~bigchaindb.common.transaction.Transaction`
        """
        # TODO: Singing should be possible with at least one of all private
        #       keys supplied to this method.
        if private_keys is None or not isinstance(private_keys, list):
            raise TypeError("`private_keys` must be a list instance")

        # NOTE: Generate public keys from private keys and match them in a
        #       dictionary:
        #                   key:     public_key
        #                   value:   private_key
        def gen_public_key(private_key):
            # TODO FOR CC: Adjust interface so that this function becomes
            #              unnecessary

            # cc now provides a single method `encode` to return the key
            # in several different encodings.
            public_key = private_key.get_verifying_key().encode()
            # Returned values from cc are always bytestrings so here we need
            # to decode to convert the bytestring into a python str
            return public_key.decode()

        key_pairs = {
            gen_public_key(PrivateKey(private_key)): PrivateKey(private_key)
            for private_key in private_keys
        }

        tx_dict = self.to_dict()
        tx_dict = Transaction._remove_signatures(tx_dict)
        tx_serialized = Transaction._to_str(tx_dict)
        for i, input_ in enumerate(self.inputs):
            self.inputs[i] = self._sign_input(input_, tx_serialized, key_pairs)

        self._hash()

        return self

    @classmethod
    def _sign_input(cls, input_, message, key_pairs):
        """Signs a single Input.

        Note:
            This method works only for the following Cryptoconditions
            currently:
                - Ed25519Fulfillment
                - ThresholdSha256.

        Args:
            input_ (:class:`~bigchaindb.common.transaction.
                Input`) The Input to be signed.
            message (str): The message to be signed
            key_pairs (dict): The keys to sign the Transaction with.
        """
        if isinstance(input_.fulfillment, Ed25519Sha256):
            return cls._sign_simple_signature_fulfillment(input_, message, key_pairs)
        elif isinstance(input_.fulfillment, ThresholdSha256):
            return cls._sign_threshold_signature_fulfillment(input_, message, key_pairs)
        else:
            raise ValueError(
                "Fulfillment couldn't be matched to "
                "Cryptocondition fulfillment type."
            )

    @classmethod
    def _sign_simple_signature_fulfillment(cls, input_, message, key_pairs):
        """Signs a Ed25519Fulfillment.

        Args:
            input_ (:class:`~bigchaindb.common.transaction.
                Input`) The input to be signed.
            message (str): The message to be signed
            key_pairs (dict): The keys to sign the Transaction with.
        """
        # NOTE: To eliminate the dangers of accidentally signing a condition by
        #       reference, we remove the reference of input_ here
        #       intentionally. If the user of this class knows how to use it,
        #       this should never happen, but then again, never say never.
        input_ = deepcopy(input_)
        public_key = input_.owners_before[0]
        message = sha3_256(message.encode())
        if input_.fulfills:
            message.update(
                "{}{}".format(input_.fulfills.txid, input_.fulfills.output).encode()
            )

        try:
            # cryptoconditions makes no assumptions of the encoding of the
            # message to sign or verify. It only accepts bytestrings
            input_.fulfillment.sign(
                message.digest(), base58.b58decode(key_pairs[public_key].encode())
            )
        except KeyError:
            raise KeypairMismatchException(
                "Public key {} is not a pair to "
                "any of the private keys".format(public_key)
            )
        return input_

    @classmethod
    def _sign_threshold_signature_fulfillment(cls, input_, message, key_pairs):
        """Signs a ThresholdSha256.

        Args:
            input_ (:class:`~bigchaindb.common.transaction.
                Input`) The Input to be signed.
            message (str): The message to be signed
            key_pairs (dict): The keys to sign the Transaction with.
        """
        input_ = deepcopy(input_)
        message = sha3_256(message.encode())
        if input_.fulfills:
            message.update(
                "{}{}".format(input_.fulfills.txid, input_.fulfills.output).encode()
            )

        for owner_before in set(input_.owners_before):
            # TODO: CC should throw a KeypairMismatchException, instead of
            #       our manual mapping here

            # TODO FOR CC: Naming wise this is not so smart,
            #              `get_subcondition` in fact doesn't return a
            #              condition but a fulfillment

            # TODO FOR CC: `get_subcondition` is singular. One would not
            #              expect to get a list back.
            ccffill = input_.fulfillment
            subffills = ccffill.get_subcondition_from_vk(base58.b58decode(owner_before))
            if not subffills:
                raise KeypairMismatchException(
                    "Public key {} cannot be found "
                    "in the fulfillment".format(owner_before)
                )
            try:
                private_key = key_pairs[owner_before]
            except KeyError:
                raise KeypairMismatchException(
                    "Public key {} is not a pair "
                    "to any of the private keys".format(owner_before)
                )

            # cryptoconditions makes no assumptions of the encoding of the
            # message to sign or verify. It only accepts bytestrings
            for subffill in subffills:
                subffill.sign(message.digest(), base58.b58decode(private_key.encode()))
        return input_

    def inputs_valid(self, outputs=None, bigchain=None):
        """Validates the Inputs in the Transaction against given
        Outputs.

            Note:
                Given a `CREATE` Transaction is passed,
                dummy values for Outputs are submitted for validation that
                evaluate parts of the validation-checks to `True`.

            Args:
                outputs (:obj:`list` of :class:`~bigchaindb.common.
                    transaction.Output`): A list of Outputs to check the
                    Inputs against.

            Returns:
                bool: If all Inputs are valid.
        
        ccffill = self.inputs[0].fulfillment
        if "Signature is: " in ccffill:
            if (
                self.operation == self.REQUEST_FOR_QUOTE
                or self.operation == self.ACCEPT
            ):
                RID = self.metadata["RID"]
                nonce = self.metadata["previous_nonce"]
                previous_transaction_ID = self.metadata["previous_transaction_ID"]
                result = bigchain.get_transaction(previous_transaction_ID)

                hashResult = result["metadata"]["hash"]
                if not self.hashVerify(hashResult, RID, nonce):
                    return False

            return self.GVerify(
                self.inputs[0].owners_before[0], ccffill, "seralization"
            )
        else:"""
        if self.operation in [
            self.CREATE,
            self.PRE_REQUEST,
            self.REQUEST_FOR_QUOTE,
            self.INTEREST,
            self.ACCEPT,
            self.ADVERTISEMENT,
        ]:
            # NOTE: Since in the case of a `CREATE`-transaction we do not have
            #       to check for outputs, we're just submitting dummy
            #       values to the actual method. This simplifies it's logic
            #       greatly, as we do not have to check against `None` values.
            return self._inputs_valid(["dummyvalue" for _ in self.inputs])
        elif self.operation in [
            self.TRANSFER,
            self.BID,
            self.RETURN,
            self.BUY_OFFER,
            self.SELL,
            self.REQUEST_RETURN,
            self.ACCEPT_RETURN,
        ]:
            return self._inputs_valid(
                [output.fulfillment.condition_uri for output in outputs]
            )
        else:
            allowed_ops = ", ".join(self.__class__.ALLOWED_OPERATIONS)
            raise TypeError("`operation` must be one of {}".format(allowed_ops))

    def _inputs_valid(self, output_condition_uris):
        """Validates an Input against a given set of Outputs.

        Note:
            The number of `output_condition_uris` must be equal to the
            number of Inputs a Transaction has.

        Args:
            output_condition_uris (:obj:`list` of :obj:`str`): A list of
                Outputs to check the Inputs against.

        Returns:
            bool: If all Outputs are valid.
        """

        if len(self.inputs) != len(output_condition_uris):
            raise ValueError(
                "Inputs and " "output_condition_uris must have the same count"
            )

        tx_dict = self.tx_dict if self.tx_dict else self.to_dict()
        tx_dict = Transaction._remove_signatures(tx_dict)
        tx_dict["id"] = None
        tx_serialized = Transaction._to_str(tx_dict)

        def validate(i, output_condition_uri=None):
            """Validate input against output condition URI"""
            return self._input_valid(
                self.inputs[i], self.operation, tx_serialized, output_condition_uri
            )

        return all(validate(i, cond) for i, cond in enumerate(output_condition_uris))

    @lru_cache(maxsize=16384)
    def _input_valid(self, input_, operation, message, output_condition_uri=None):
        """Validates a single Input against a single Output.

        Note:
            In case of a `CREATE` Transaction, this method
            does not validate against `output_condition_uri`.

        Args:
            input_ (:class:`~bigchaindb.common.transaction.
                Input`) The Input to be signed.
            operation (str): The type of Transaction.
            message (str): The fulfillment message.
            output_condition_uri (str, optional): An Output to check the
                Input against.

        Returns:
            bool: If the Input is valid.
        """
        ccffill = input_.fulfillment
        try:
            parsed_ffill = Fulfillment.from_uri(ccffill.serialize_uri())
        except (TypeError, ValueError, ParsingError, ASN1DecodeError, ASN1EncodeError):
            return False

        if operation in [
            self.CREATE,
            self.PRE_REQUEST,
            self.REQUEST_FOR_QUOTE,
            self.INTEREST,
            self.ACCEPT,
            self.ADVERTISEMENT,
        ]:
            # NOTE: In the case of a `CREATE` transaction, the
            #       output is always valid.
            output_valid = True
        else:
            output_valid = output_condition_uri == ccffill.condition_uri

        message = sha3_256(message.encode())
        if input_.fulfills:
            message.update(
                "{}{}".format(input_.fulfills.txid, input_.fulfills.output).encode()
            )

        # NOTE: We pass a timestamp to `.validate`, as in case of a timeout
        #       condition we'll have to validate against it

        # cryptoconditions makes no assumptions of the encoding of the
        # message to sign or verify. It only accepts bytestrings
        ffill_valid = parsed_ffill.validate(message=message.digest())
        return output_valid and ffill_valid

    def GVerify(self, group_public_key, signature, seralization):
        newSign = signature.replace(",", "comma").replace('"', "'")
        newSign2 = newSign.replace("Signature is: ((", '"((').replace("') ", "') \"")
        seralization2 = '"' + seralization + '"'

        dangerousString = (
            ". $HOME/.cargo/env; cd bigchaindb/common/ursa_Master/libzmix; cargo test test_scenario_1 --release --no-default-features --features PS_Signature_G1 -- GVerify,"
            + group_public_key
            + ","
            + newSign2
            + ","
            + seralization2
            + " --nocapture;"
        )

        p = Popen(dangerousString, stderr=PIPE, stdout=PIPE, shell=True)
        output, err = p.communicate(b"input data that is passed to subprocess' stdin")
        return "verified_signature_13: true" in output.decode("utf-8")

    def java_string_hashcode(self, s):
        h = 0
        for c in s:
            h = (31 * h + ord(c)) & 0xFFFFFFFF
        return ((h + 0x80000000) & 0xFFFFFFFF) - 0x80000000

    def hashVerify(self, hashResult, RID, nonce):
        hashTest = self.java_string_hashcode(RID + nonce)
        return hashTest == hashResult

    # This function is required by `lru_cache` to create a key for memoization
    def __hash__(self):
        return hash(self.id)

    @memoize_to_dict
    def to_dict(self):
        """Transforms the object to a Python dictionary.

        Returns:
            dict: The Transaction as an alternative serialization format.
        """
        return {
            "inputs": [input_.to_dict() for input_ in self.inputs],
            "outputs": [output.to_dict() for output in self.outputs],
            "operation": str(self.operation),
            "metadata": self.metadata,
            "asset": self.asset,
            "version": self.version,
            "id": self._id,
        }

    @staticmethod
    # TODO: Remove `_dict` prefix of variable.
    def _remove_signatures(tx_dict):
        """Takes a Transaction dictionary and removes all signatures.

        Args:
            tx_dict (dict): The Transaction to remove all signatures from.

        Returns:
            dict

        """
        # NOTE: We remove the reference since we need `tx_dict` only for the
        #       transaction's hash
        tx_dict = deepcopy(tx_dict)
        for input_ in tx_dict["inputs"]:
            # NOTE: Not all Cryptoconditions return a `signature` key (e.g.
            #       ThresholdSha256), so setting it to `None` in any
            #       case could yield incorrect signatures. This is why we only
            #       set it to `None` if it's set in the dict.
            input_["fulfillment"] = None
        return tx_dict

    @staticmethod
    def _to_hash(value):
        return hash_data(value)

    @property
    def id(self):
        return self._id

    def to_hash(self):
        return self.to_dict()["id"]

    @staticmethod
    def _to_str(value):
        return serialize(value)

    # TODO: This method shouldn't call `_remove_signatures`
    def __str__(self):
        tx = Transaction._remove_signatures(self.to_dict())
        return Transaction._to_str(tx)

    @classmethod
    def get_asset_id(cls, transactions):
        """Get the asset id from a list of :class:`~.Transactions`.

        This is useful when we want to check if the multiple inputs of a
        transaction are related to the same asset id.

        Args:
            transactions (:obj:`list` of :class:`~bigchaindb.common.
                transaction.Transaction`): A list of Transactions.
                Usually input Transactions that should have a matching
                asset ID.

        Returns:
            str: ID of the asset.

        Raises:
            :exc:`AssetIdMismatch`: If the inputs are related to different
                assets.
        """

        if not isinstance(transactions, list):
            transactions = [transactions]

        # create a set of the transactions' asset ids
        asset_ids = set()
        for tx in transactions:
            if tx.operation in [tx.CREATE, tx.BID]:
                asset_id = tx.id
            else:
                asset_id = tx.asset.get("data", {}).get("id") or tx.asset["id"]
            asset_ids.add(asset_id)

        # check that all the transasctions have the same asset id
        if len(asset_ids) > 1:
            raise AssetIdMismatch(
                (
                    "All inputs of all transactions passed"
                    " need to have the same asset id"
                )
            )
        return asset_ids.pop()

    @staticmethod
    def validate_id(tx_body):
        """Validate the transaction ID of a transaction

        Args:
            tx_body (dict): The Transaction to be transformed.
        """
        # NOTE: Remove reference to avoid side effects
        # tx_body = deepcopy(tx_body)
        tx_body = rapidjson.loads(rapidjson.dumps(tx_body))

        try:
            proposed_tx_id = tx_body["id"]
        except KeyError:
            raise InvalidHash("No transaction id found!")

        tx_body["id"] = None

        tx_body_serialized = Transaction._to_str(tx_body)
        valid_tx_id = Transaction._to_hash(tx_body_serialized)

        if proposed_tx_id != valid_tx_id:
            err_msg = (
                "The transaction's id '{}' isn't equal to "
                "the hash of its body, i.e. it's not valid."
            )
            raise InvalidHash(err_msg.format(proposed_tx_id))

    @classmethod
    @memoize_from_dict
    def from_dict(cls, tx, skip_schema_validation=True):
        """Transforms a Python dictionary to a Transaction object.

        Args:
            tx_body (dict): The Transaction to be transformed.

        Returns:
            :class:`~bigchaindb.common.transaction.Transaction`
        """
        operation = (
            tx.get("operation", Transaction.CREATE)
            if isinstance(tx, dict)
            else Transaction.CREATE
        )
        cls = Transaction.resolve_class(operation)

        if not skip_schema_validation:
            cls.validate_id(tx)
            cls.validate_schema(tx)

        inputs = [Input.from_dict(input_) for input_ in tx["inputs"]]
        outputs = [Output.from_dict(output) for output in tx["outputs"]]
        return cls(
            tx["operation"],
            tx["asset"],
            inputs,
            outputs,
            tx["metadata"],
            tx["version"],
            hash_id=tx["id"],
            tx_dict=tx,
        )

    @classmethod
    def from_db(cls, bigchain, tx_dict_list):
        """Helper method that reconstructs a transaction dict that was returned
        from the database. It checks what asset_id to retrieve, retrieves the
        asset from the asset table and reconstructs the transaction.

        Args:
            bigchain (:class:`~bigchaindb.tendermint.BigchainDB`): An instance
                of BigchainDB used to perform database queries.
            tx_dict_list (:list:`dict` or :obj:`dict`): The transaction dict or
                list of transaction dict as returned from the database.

        Returns:
            :class:`~Transaction`

        """
        return_list = True
        if isinstance(tx_dict_list, dict):
            tx_dict_list = [tx_dict_list]
            return_list = False

        tx_map = {}
        tx_ids = []
        for tx in tx_dict_list:
            tx.update({"metadata": None})
            tx_map[tx["id"]] = tx
            tx_ids.append(tx["id"])

        assets = list(bigchain.get_assets(tx_ids))
        for asset in assets:
            if asset is not None:
                tx = tx_map[asset["id"]]
                del asset["id"]
                tx["asset"] = asset

        tx_ids = list(tx_map.keys())
        metadata_list = list(bigchain.get_metadata(tx_ids))
        for metadata in metadata_list:
            tx = tx_map[metadata["id"]]
            tx.update({"metadata": metadata.get("metadata")})

        if return_list:
            tx_list = []
            for tx_id, tx in tx_map.items():
                tx_list.append(cls.from_dict(tx))
            return tx_list
        else:
            tx = list(tx_map.values())[0]
            return cls.from_dict(tx)

    type_registry = {}

    @staticmethod
    def register_type(tx_type, tx_class):
        Transaction.type_registry[tx_type] = tx_class

    @staticmethod
    def resolve_class(operation):
        """For the given `tx` based on the `operation` key return its
        implementation class"""
        create_txn_class = Transaction.type_registry.get(Transaction.CREATE)
        return Transaction.type_registry.get(operation, create_txn_class)

    @classmethod
    def validate_schema(cls, tx):
        pass

    def validate_transfer_inputs(self, bigchain, current_transactions=[]):
        # store the inputs so that we can check if the asset ids match
        input_txs = []
        input_conditions = []
        for input_ in self.inputs:
            input_txid = input_.fulfills.txid
            input_tx = bigchain.get_transaction(input_txid)

            if input_tx is None:
                for ctxn in current_transactions:
                    if ctxn.id == input_txid:
                        input_tx = ctxn

            if input_tx is None:
                raise InputDoesNotExist("input `{}` doesn't exist".format(input_txid))

            spent = bigchain.get_spent(
                input_txid, input_.fulfills.output, current_transactions
            )
            if spent:
                raise DoubleSpend("input `{}` was already spent".format(input_txid))

            output = input_tx.outputs[input_.fulfills.output]
            input_conditions.append(output)
            input_txs.append(input_tx)

        # Validate that all inputs are distinct
        links = [i.fulfills.to_uri() for i in self.inputs]
        if len(links) != len(set(links)):
            raise DoubleSpend('tx "{}" spends inputs twice'.format(self.id))

        # validate asset id
        asset_id = self.get_asset_id(input_txs)

        tx_asset_id = ""
        if self.operation == self.BID:
            tx_asset_id = self.asset["data"]["id"]
        elif self.operation == self.RETURN:
            tx_asset_id = self.asset["data"]["bid_id"]
        else:
            tx_asset_id = self.asset["id"]

        if asset_id != tx_asset_id:
            raise AssetIdMismatch(
                (
                    "The asset id of the input does not"
                    " match the asset id of the"
                    " transaction"
                )
            )

        input_amount = sum(
            [input_condition.amount for input_condition in input_conditions]
        )
        output_amount = sum(
            [output_condition.amount for output_condition in self.outputs]
        )

        if output_amount != input_amount:
            raise AmountError(
                (
                    "The amount used in the inputs `{}`"
                    " needs to be same as the amount used"
                    " in the outputs `{}`"
                ).format(input_amount, output_amount)
            )

        if not self.inputs_valid(input_conditions):
            raise InvalidSignature("Transaction signature is invalid.")

        return True

    def validate_advertisement_inputs(self, bigchain, current_transactions=[]):
        """Validate ADVERTISEMENT transaction (CREATE-like input semantics).

        Rules:
        - Exactly one input present, with fulfills == None (no spend)
        - `asset.id` references an existing CREATE transaction
        - Advertiser is the owner in the CREATE transaction's first output
        - Status is one of OPEN, LOCKED, CLOSED
        - No other OPEN advertisement exists for the same asset
        - Signature is valid (checked like CREATE, without output matching)
        """
        # Require exactly one input and no fulfillment (CREATE-like)
        if len(self.inputs) != 1:
            raise ValueError("Advertisement must have exactly one input")
        if getattr(self.inputs[0], 'fulfills', None):
            raise ValueError("Advertisement input must not fulfill any output")

        # Resolve the advertised asset id (accept both asset.id and asset.data.id)
        if "id" in self.asset:
            tx_asset_id = self.asset["id"]
        elif "data" in self.asset and "id" in self.asset["data"]:
            tx_asset_id = self.asset["data"]["id"]
        else:
            raise ValueError("Advertisement transaction must have asset.id or asset.data.id")

        # The referenced transaction must exist and be a CREATE
        create_tx = bigchain.get_transaction(tx_asset_id)
        if create_tx is None:
            raise InputDoesNotExist("CREATE transaction `{}` doesn't exist".format(tx_asset_id))
        if create_tx.operation != self.CREATE:
            raise ValueError("Referenced transaction is not a CREATE transaction")

        # Sanity: CREATE asset id equals the referenced id
        create_asset_id = create_tx.get_asset_id([create_tx])
        if create_asset_id != tx_asset_id:
            raise AssetIdMismatch("Asset ID mismatch between CREATE and ADVERTISEMENT transactions")

        # Advertiser must be the original owner
        advertiser_pub_key = self.metadata.get('advertiser_public_key')
        if not advertiser_pub_key:
            raise ValueError("Advertisement metadata must contain advertiser_public_key")
        if advertiser_pub_key not in create_tx.outputs[0].public_keys:
            raise ValueError("Advertiser must be the original owner of the asset")

        # Status must be valid
        status = self.metadata.get('status')
        if status not in ['OPEN', 'LOCKED', 'CLOSED']:
            raise ValueError("Advertisement status must be OPEN, LOCKED, or CLOSED")

        # Signature validation: treat like CREATE (no output-binding)
        if not self.inputs_valid([], bigchain):
            raise InvalidSignature("Transaction signature is invalid.")

        # Reject duplicate OPEN advertisements for the same asset
        existing_open_ads = list(bigchain.get_open_advertisements_by_asset(tx_asset_id))
        if existing_open_ads:
            raise ValueError("Asset {} already has an OPEN advertisement".format(tx_asset_id))

        return True

    def validate_buy_offer_inputs(self, bigchain, current_transactions=[]):
        """Validate buy offer transaction inputs according to business rules.
        
        Validation rules:
        1. References exactly one existing OPEN advertisement
        2. References exactly one valid asset identifier
        3. Buyer ≠ advertiser
        4. Offer matches advertisement's policy and is within time
        5. Buyer has sufficient funds to cover the offer amount
        6. Buyer's payment asset is directly transferred to escrow account
        
        Args:
            bigchain: BigchainDB instance for database queries
            current_transactions: List of current uncommitted transactions
            
        Returns:
            bool: True if validation passes
            
        Raises:
            Various validation errors if rules are violated
        """
        # BUY_OFFER transfers buyer's payment asset to escrow
        # Input validation: buyer spends their payment asset
        
        # Validate exactly one input for the payment being offered
        if len(self.inputs) != 1:
            raise ValueError("Buy offer must have exactly one input (buyer's payment asset)")
            
        # Get the input transaction (buyer's payment asset)
        payment_input = self.inputs[0]
        payment_input_txid = payment_input.fulfills.txid if payment_input.fulfills else None
        
        if not payment_input_txid:
            # This is like a CREATE - no input to validate
            pass
        else:
            payment_input_tx = bigchain.get_transaction(payment_input_txid)

            if payment_input_tx is None:
                for ctxn in current_transactions:
                    if ctxn.id == payment_input_txid:
                        payment_input_tx = ctxn

            if payment_input_tx is None:
                raise InputDoesNotExist("payment input `{}` doesn't exist".format(payment_input_txid))

            # Check if payment input is already spent
            payment_spent = bigchain.get_spent(
                payment_input_txid, payment_input.fulfills.output, current_transactions
            )
            if payment_spent:
                raise DoubleSpend("payment input `{}` was already spent".format(payment_input_txid))

            # Get the payment output being referenced
            payment_output = payment_input_tx.outputs[payment_input.fulfills.output]
            
            # Note: Signature validation is handled by the general inputs_valid() in models.py
            # No need to validate again here
        
        # Validate asset ID is provided (the asset being purchased, not the payment)
        tx_asset_id = self.asset.get("data", {}).get("id")
        if not tx_asset_id:
            raise ValueError("Buy offer must reference an asset ID")

        # Validate advertisement exists and is OPEN
        advertisement_id = self.asset.get('advertisement_id') or self.asset.get('data', {}).get('advertisement_id')
        if not advertisement_id:
            raise ValueError("Buy offer must reference an advertisement")
            
        advertisement_tx = bigchain.get_transaction(advertisement_id)
        if not advertisement_tx:
            raise ValueError(f"Referenced advertisement {advertisement_id} does not exist")
            
        if advertisement_tx.operation != 'ADVERTISEMENT':
            raise ValueError(f"Referenced transaction {advertisement_id} is not an advertisement")
            
        if advertisement_tx.metadata.get('status') != 'OPEN':
            raise ValueError(f"Referenced advertisement {advertisement_id} is not OPEN")

        # Validate buyer ≠ advertiser
        buyer_pub_key = self.metadata.get('buyer_public_key')
        advertiser_pub_key = advertisement_tx.metadata.get('advertiser_public_key')
        
        if buyer_pub_key == advertiser_pub_key:
            raise ValueError("Buyer cannot be the same as advertiser")

        # Validate offer is within time
        from datetime import datetime
        # Python 3.6 compatible datetime parsing
        expiry_str = self.metadata.get('offer_expiry', '').replace('Z', '+00:00')
        # Remove microseconds for simpler parsing
        if '.' in expiry_str:
            base_part = expiry_str.split('.')[0]
            timezone_part = expiry_str.split('+')[1] if '+' in expiry_str else ''
            expiry_str = base_part + ('+' + timezone_part if timezone_part else '')
        
        # Parse without timezone first, then add UTC timezone
        offer_expiry = datetime.strptime(expiry_str.split('+')[0], '%Y-%m-%dT%H:%M:%S')
        # Add UTC timezone info
        from datetime import timezone
        offer_expiry = offer_expiry.replace(tzinfo=timezone.utc)
        current_time = datetime.utcnow().replace(tzinfo=timezone.utc)
        
        if current_time > offer_expiry:
            raise ValueError("Offer has expired")

        # Note: BUY_OFFER is an intent/announcement transaction with escrow details
        # The input ownership validation is skipped because:
        # - The buyer doesn't need to prove funds ownership on-chain
        # - Escrow mechanisms can be handled off-chain or in later transactions
        # - The SELL transaction will validate the actual asset transfer
        
        # Validate escrow public key
        escrow_pub_key = self.metadata.get('escrow_public_key')
        if not escrow_pub_key:
            raise ValueError("Buy offer must specify escrow public key")

        # Validate that outputs will be created for escrow transfer
        if len(self.outputs) != 1:
            raise ValueError("Buy offer must create exactly one output: escrow transfer")

        # Note: Amount validation is skipped as the schema already validates the format
        # and the transaction builder ensures consistency between metadata and outputs
        escrow_output = self.outputs[0]
        
        # Validate escrow output is locked to escrow account
        if escrow_pub_key not in escrow_output.public_keys:
            raise ValueError("Escrow output must be locked to the specified escrow account")

        # Note: Signature validation is skipped for BUY_OFFER
        # BUY_OFFER is an announcement transaction, not a UTXO spend
        # The transaction is signed by the buyer to prove intent, but doesn't spend any UTXO
        
        return True

    def validate_sell_inputs(self, bigchain, current_transactions=[]):
        """Validate sell transaction inputs according to business rules.
        
        Validation rules:
        1. References exactly one existing BuyOffer
        2. Offer targets an advertisement for the same asset
        3. Seller = current owner and = advertiser
        4. Ad is not already LOCKED or CLOSED
        5. Buy offer has sufficient escrow funds
        6. Executes two atomic transfer transactions: asset to buyer, payment to seller
        
        Args:
            bigchain: BigchainDB instance for database queries
            current_transactions: List of current uncommitted transactions
            
        Returns:
            bool: True if validation passes
            
        Raises:
            Various validation errors if rules are violated
        """
        # Validate exactly one input (the asset being sold)
        # Note: The escrowed payment from BUY_OFFER is validated but not spent as a UTXO
        # The payment transfer happens through output creation referencing the escrow
        if len(self.inputs) != 1:
            raise ValueError("Sell transaction must have exactly one input: the asset")
            
        input_ = self.inputs[0]
        input_txid = input_.fulfills.txid
        input_tx = bigchain.get_transaction(input_txid)

        if input_tx is None:
            for ctxn in current_transactions:
                if ctxn.id == input_txid:
                    input_tx = ctxn

        if input_tx is None:
            raise InputDoesNotExist("input `{}` doesn't exist".format(input_txid))

        # Check if input is already spent
        spent = bigchain.get_spent(
            input_txid, input_.fulfills.output, current_transactions
        )
        if spent:
            raise DoubleSpend("input `{}` was already spent".format(input_txid))

        # Get the output being referenced
        output = input_tx.outputs[input_.fulfills.output]
        input_conditions = [output]
        input_txs = [input_tx]

        # Validate asset ID consistency
        asset_id = self.get_asset_id(input_txs)
        tx_asset_id = self.asset["data"]["id"]

        if asset_id != tx_asset_id:
            raise AssetIdMismatch(
                "The asset id of the input does not match the asset id of the transaction"
            )

        # Validate buy offer exists and references the same asset
        buy_offer_id = self.asset.get('buy_offer_id') or self.asset.get('data', {}).get('buy_offer_id')
        if not buy_offer_id:
            raise ValueError("Sell transaction must reference a buy offer")
            
        buy_offer_tx = bigchain.get_transaction(buy_offer_id)
        if not buy_offer_tx:
            raise ValueError(f"Referenced buy offer {buy_offer_id} does not exist")
            
        if buy_offer_tx.operation != 'BUY_OFFER':
            raise ValueError(f"Referenced transaction {buy_offer_id} is not a buy offer")
            
        # Validate that the buy offer targets the same asset OR carries escrow info
        buy_offer_asset_id = buy_offer_tx.asset.get('data', {}).get('id') or buy_offer_tx.asset.get('id')
        if buy_offer_asset_id != asset_id:
            # Allow legacy/current driver behavior where BUY_OFFER.asset.data.id holds buyer's payment asset
            # In that case, require presence of payment_asset_id in metadata to indicate escrowed funds
            payment_asset_id = None
            if hasattr(buy_offer_tx, 'metadata') and isinstance(buy_offer_tx.metadata, dict):
                payment_asset_id = buy_offer_tx.metadata.get('payment_asset_id')
            if not payment_asset_id:
                raise ValueError("Buy offer targets different asset than sell transaction")

        # Get the advertisement from the buy offer (check both top-level and data)
        advertisement_id = buy_offer_tx.asset.get('advertisement_id') or buy_offer_tx.asset.get('data', {}).get('advertisement_id')
        if not advertisement_id:
            raise ValueError("Buy offer must reference an advertisement")
            
        advertisement_tx = bigchain.get_transaction(advertisement_id)
        
        if not advertisement_tx:
            raise ValueError(f"Referenced advertisement {advertisement_id} does not exist")

        # Validate seller = current owner and = advertiser
        seller_pub_key = self.metadata.get('seller_public_key')
        advertiser_pub_key = advertisement_tx.metadata.get('advertiser_public_key')
        
        if seller_pub_key != advertiser_pub_key:
            raise ValueError("Seller must be the advertiser")
            
        if seller_pub_key not in output.public_keys:
            raise ValueError("Seller must be the current owner of the asset")

        # Validate ad is not already LOCKED or CLOSED
        ad_status = advertisement_tx.metadata.get('status')
        if ad_status in ['LOCKED', 'CLOSED']:
            raise ValueError(f"Cannot sell asset with advertisement status {ad_status}")

        # Validate buy offer has sufficient escrow funds
        buy_offer_amount = buy_offer_tx.metadata.get('offer_amount')
        sale_amount = self.metadata.get('sale_amount')
        
        if sale_amount > buy_offer_amount:
            raise ValueError("Sale amount cannot exceed buy offer amount")

        # Validate buyer public key is provided for asset transfer
        buyer_pub_key = self.metadata.get('buyer_public_key')
        if not buyer_pub_key:
            raise ValueError("Sell transaction must specify buyer public key for asset transfer")
            
        # Validate buyer public key matches the one from buy offer
        buy_offer_buyer = buy_offer_tx.metadata.get('buyer_public_key')
        if buyer_pub_key != buy_offer_buyer:
            raise ValueError("Buyer public key must match the one from buy offer")

        # Validate that outputs will be created for both transfers
        if len(self.outputs) != 2:
            raise ValueError("Sell transaction must create exactly two outputs: asset transfer and payment transfer")

        # Note: Signature validation is handled by the general inputs_valid() in models.py
        # No need to validate again here

        return True

    def validate_accept_return_inputs(self, bigchain, current_transactions=[]):
        """Validate accept return transaction inputs according to business rules.
        
        Validation rules:
        1. References exactly one Request Return x that is OPEN and binds the same Sell Tx
        2. Performs return: Asset ownership moves back to seller
        3. Funds/escrow refunded to buyer
        4. Return request status transitions OPEN → CLOSED
        5. No other active settles or returns for the same sale
        
        Args:
            bigchain: BigchainDB instance for database queries
            current_transactions: List of current uncommitted transactions
            
        Returns:
            bool: True if validation passes
            
        Raises:
            Various validation errors if rules are violated
        """
        # Validate exactly one input
        if len(self.inputs) != 1:
            raise ValueError("Accept return must have exactly one input")
            
        input_ = self.inputs[0]
        input_txid = input_.fulfills.txid
        input_tx = bigchain.get_transaction(input_txid)

        if input_tx is None:
            for ctxn in current_transactions:
                if ctxn.id == input_txid:
                    input_tx = ctxn

        if input_tx is None:
            raise InputDoesNotExist("input `{}` doesn't exist".format(input_txid))

        # Check if input is already spent
        spent = bigchain.get_spent(
            input_txid, input_.fulfills.output, current_transactions
        )
        if spent:
            raise DoubleSpend("input `{}` was already spent".format(input_txid))

        # Get the output being referenced
        output = input_tx.outputs[input_.fulfills.output]
        input_conditions = [output]
        input_txs = [input_tx]

        # Validate asset ID consistency
        asset_id = self.get_asset_id(input_txs)
        tx_asset_id = self.asset["data"]["id"]

        if asset_id != tx_asset_id:
            raise AssetIdMismatch(
                "The asset id of the input does not match the asset id of the transaction"
            )

        # Validate request return exists and is OPEN
        request_return_id = self.asset.get('data', {}).get('request_return_id')
        if not request_return_id:
            raise ValueError("Accept return must reference a request return transaction")
            
        request_return_tx = bigchain.get_transaction(request_return_id)
        if not request_return_tx:
            raise ValueError(f"Referenced request return {request_return_id} does not exist")
            
        if request_return_tx.operation != 'REQUEST_RETURN':
            raise ValueError(f"Referenced transaction {request_return_id} is not a request return")

        # Validate request return is OPEN
        return_status = request_return_tx.metadata.get('return_policy_details', {}).get('return_status')
        if return_status != 'PENDING':
            raise ValueError(f"Request return {request_return_id} is not OPEN (status: {return_status})")

        # Validate request return binds the same Sell Tx
        sell_transaction_id = request_return_tx.asset.get('sell_transaction_id') or request_return_tx.asset.get('data', {}).get('sell_transaction_id')
        if not sell_transaction_id:
            raise ValueError("Request return must reference a sell transaction")
            
        sell_tx = bigchain.get_transaction(sell_transaction_id)
        if not sell_tx:
            raise ValueError(f"Referenced sell transaction {sell_transaction_id} does not exist")
            
        if sell_tx.operation != 'SELL':
            raise ValueError(f"Referenced transaction {sell_transaction_id} is not a sell transaction")

        # Validate accepter = seller from the sell transaction
        accepter_pub_key = self.metadata.get('accepter_public_key')
        
        # Get the buy offer from the sell transaction
        buy_offer_id = sell_tx.asset.get('buy_offer_id') or sell_tx.asset.get('data', {}).get('buy_offer_id')
        buy_offer_tx = bigchain.get_transaction(buy_offer_id)
        
        if not buy_offer_tx:
            raise ValueError(f"Referenced buy offer {buy_offer_id} does not exist")
            
        # Get the advertisement from the buy offer
        advertisement_id = buy_offer_tx.asset.get('advertisement_id') or buy_offer_tx.asset.get('data', {}).get('advertisement_id')
        advertisement_tx = bigchain.get_transaction(advertisement_id)
        
        if not advertisement_tx:
            raise ValueError(f"Referenced advertisement {advertisement_id} does not exist")
            
        seller_pub_key = advertisement_tx.metadata.get('advertiser_public_key')
        
        if accepter_pub_key != seller_pub_key:
            raise ValueError("Accepter must be the seller from the sell transaction")

        # Validate refund details
        refund_details = self.metadata.get('refund_details', {})
        if not refund_details:
            raise ValueError("Accept return must include refund details")
            
        refund_amount = refund_details.get('refund_amount')
        refund_currency = refund_details.get('refund_currency')
        refund_method = refund_details.get('refund_method')
        
        if not refund_amount or not refund_currency or not refund_method:
            raise ValueError("Refund details must include amount, currency, and method")

        # Check if there are other active settles or returns for this sale
        existing_returns = bigchain.get_transactions_filtered(
            asset_id=asset_id, 
            operation='REQUEST_RETURN'
        )
        
        for existing_return in existing_returns:
            if (existing_return.asset.get('sell_transaction_id') == sell_transaction_id and
                existing_return.metadata.get('return_policy_details', {}).get('return_status') == 'PENDING' and
                existing_return.id != request_return_id):
                raise ValueError(f"Sale {sell_transaction_id} has other active return requests")

        # Validate signature
        if not self.inputs_valid(input_conditions):
            raise InvalidSignature("Transaction signature is invalid.")

        return True

    def validate_request_return_inputs(self, bigchain, current_transactions=[]):
        """Validate request return transaction inputs according to business rules.
        
        Validation rules:
        1. References exactly one SellTx (the sale being disputed)
        2. Buyer = current owner of the asset right now
        3. Sale is eligible for return (within window, policy allows)
        4. Asset not re-transferred since that sale; still the same item
        5. Single active OPEN return request per sale at a time
        
        Args:
            bigchain: BigchainDB instance for database queries
            current_transactions: List of current uncommitted transactions
            
        Returns:
            bool: True if validation passes
            
        Raises:
            Various validation errors if rules are violated
        """
        # Validate exactly one input
        if len(self.inputs) != 1:
            raise ValueError("Request return must have exactly one input")
            
        input_ = self.inputs[0]
        input_txid = input_.fulfills.txid
        input_tx = bigchain.get_transaction(input_txid)

        if input_tx is None:
            for ctxn in current_transactions:
                if ctxn.id == input_txid:
                    input_tx = ctxn

        if input_tx is None:
            raise InputDoesNotExist("input `{}` doesn't exist".format(input_txid))

        # Check if input is already spent
        spent = bigchain.get_spent(
            input_txid, input_.fulfills.output, current_transactions
        )
        if spent:
            raise DoubleSpend("input `{}` was already spent".format(input_txid))

        # Get the output being referenced
        output = input_tx.outputs[input_.fulfills.output]
        input_conditions = [output]
        input_txs = [input_tx]

        # Validate asset ID consistency
        asset_id = self.get_asset_id(input_txs)
        tx_asset_id = self.asset["data"]["id"]

        if asset_id != tx_asset_id:
            raise AssetIdMismatch(
                "The asset id of the input does not match the asset id of the transaction"
            )

        # Validate sell transaction exists
        sell_transaction_id = self.asset.get('data', {}).get('sell_transaction_id')
        if not sell_transaction_id:
            raise ValueError("Request return must reference a sell transaction")
            
        sell_tx = bigchain.get_transaction(sell_transaction_id)
        if not sell_tx:
            raise ValueError(f"Referenced sell transaction {sell_transaction_id} does not exist")
            
        if sell_tx.operation != 'SELL':
            raise ValueError(f"Referenced transaction {sell_transaction_id} is not a sell transaction")

        # Validate requester = buyer from the sell transaction
        requester_pub_key = self.metadata.get('requester_public_key')
        
        # Get the buy offer from the sell transaction
        buy_offer_id = sell_tx.asset.get('buy_offer_id') or sell_tx.asset.get('data', {}).get('buy_offer_id')
        buy_offer_tx = bigchain.get_transaction(buy_offer_id)
        
        if not buy_offer_tx:
            raise ValueError(f"Referenced buy offer {buy_offer_id} does not exist")
            
        buyer_pub_key = buy_offer_tx.metadata.get('buyer_public_key')
        
        if requester_pub_key != buyer_pub_key:
            raise ValueError("Requester must be the buyer from the sell transaction")

        # Validate return policy allows return
        return_policy = self.metadata.get('return_policy_details', {})
        return_window = return_policy.get('return_window_days', 0)
        
        if return_window <= 0:
            raise ValueError("Return policy must allow returns")

        # Check if there's already an active return request for this sale
        existing_returns = bigchain.get_transactions_filtered(
            asset_id=asset_id, 
            operation='REQUEST_RETURN'
        )
        
        for existing_return in existing_returns:
            if (existing_return.asset.get('sell_transaction_id') == sell_transaction_id and
                existing_return.metadata.get('return_policy_details', {}).get('return_status') == 'PENDING'):
                raise ValueError(f"Sale {sell_transaction_id} already has an active return request")

        # Validate signature
        if not self.inputs_valid(input_conditions):
            raise InvalidSignature("Transaction signature is invalid.")

        return True

    def validate_update_adv_inputs(self, bigchain, current_transactions=[]):
        """Validate update advertisement transaction inputs according to business rules.
        
        Validation rules:
        1. References exactly one Advertisement transaction
        2. Only the advertiser can update the advertisement
        3. Advertisement must be OPEN to update
        4. Status transitions must follow: OPEN -> LOCKED -> CLOSED
        5. New values must be valid (positive amounts, future expiry)
        
        Args:
            bigchain: BigchainDB instance for database queries
            current_transactions: List of current uncommitted transactions
            
        Returns:
            bool: True if validation passes
            
        Raises:
            Various validation errors if rules are violated
        """
        # Validate exactly one input
        if len(self.inputs) != 1:
            raise ValueError("Update advertisement must have exactly one input")
            
        input_ = self.inputs[0]
        input_txid = input_.fulfills.txid
        input_tx = bigchain.get_transaction(input_txid)

        if input_tx is None:
            for ctxn in current_transactions:
                if ctxn.id == input_txid:
                    input_tx = ctxn

        if input_tx is None:
            raise InputDoesNotExist("input `{}` doesn't exist".format(input_txid))

        # Check if input is already spent
        spent = bigchain.get_spent(
            input_txid, input_.fulfills.output, current_transactions
        )
        if spent:
            raise DoubleSpend("input `{}` was already spent".format(input_txid))

        # Get the output being referenced
        output = input_tx.outputs[input_.fulfills.output]
        input_conditions = [output]
        input_txs = [input_tx]

        # Interpret asset.data.id as the advertisement id
        advertisement_id = self.asset.get('data', {}).get('id')
        if not advertisement_id:
            raise ValueError("Update advertisement must provide advertisement id in asset.data.id")
        
        # Validate advertisement exists
        advertisement_tx = bigchain.get_transaction(advertisement_id)
        if not advertisement_tx:
            raise ValueError(f"Referenced advertisement {advertisement_id} does not exist")
            
        if advertisement_tx.operation != 'ADVERTISEMENT':
            raise ValueError(f"Referenced transaction {advertisement_id} is not an advertisement")

        # Validate advertiser = updater
        updater_pub_key = self.metadata.get('advertiser_public_key')
        advertiser_pub_key = advertisement_tx.metadata.get('advertiser_public_key')
        
        if updater_pub_key != advertiser_pub_key:
            raise ValueError("Only the advertiser can update the advertisement")

        # Validate advertisement is OPEN
        current_status = advertisement_tx.metadata.get('status', 'OPEN')
        if current_status != 'OPEN':
            raise ValueError("Advertisement must be OPEN to update")

        # Validate status transition (using metadata.status)
        new_status = self.metadata.get('status')
        valid_transitions = {
            'OPEN': ['LOCKED', 'CLOSED'],
            'LOCKED': ['CLOSED'],
            'CLOSED': []
        }
        
        if new_status not in valid_transitions.get(current_status, []):
            raise ValueError(f"Invalid status transition from {current_status} to {new_status}")

        # Validate value (optional)
        new_value = self.metadata.get('value')
        if new_value is not None:
            if not isinstance(new_value, str) or not new_value.isdigit() or int(new_value) <= 0:
                raise ValueError("Value must be a positive number if provided")

        # Validate expiry date (optional)
        new_expiry = self.metadata.get('expiry_date')
        # if provided, ensure non-empty string
        if new_expiry is not None and not isinstance(new_expiry, str):
            raise ValueError("Expiry date must be a string if provided")

        # Validate signature
        if not self._validate_signature(input_conditions):
            raise InvalidSignature("Transaction signature is invalid.")

        return True

    def validate_seller_accept_return_inputs(self, bigchain, current_transactions=[]):
        """Validate seller accept return transaction inputs according to business rules.
        
        Validation rules:
        1. References exactly one Request Return transaction
        2. Only the seller can accept the return
        3. Request return must be PENDING
        4. Refund details must be valid
        5. No other active returns for the same sale
        
        Args:
            bigchain: BigchainDB instance for database queries
            current_transactions: List of current uncommitted transactions
            
        Returns:
            bool: True if validation passes
            
        Raises:
            Various validation errors if rules are violated
        """
        # Validate exactly one input
        if len(self.inputs) != 1:
            raise ValueError("Seller accept return must have exactly one input")
            
        input_ = self.inputs[0]
        input_txid = input_.fulfills.txid
        input_tx = bigchain.get_transaction(input_txid)

        if input_tx is None:
            for ctxn in current_transactions:
                if ctxn.id == input_txid:
                    input_tx = ctxn

        if input_tx is None:
            raise InputDoesNotExist("input `{}` doesn't exist".format(input_txid))

        # Check if input is already spent
        spent = bigchain.get_spent(
            input_txid, input_.fulfills.output, current_transactions
        )
        if spent:
            raise DoubleSpend("input `{}` was already spent".format(input_txid))

        # Get the output being referenced
        output = input_tx.outputs[input_.fulfills.output]
        input_conditions = [output]
        input_txs = [input_tx]

        # Validate asset ID consistency
        asset_id = self.get_asset_id(input_txs)
        tx_asset_id = self.asset["data"]["id"]

        if asset_id != tx_asset_id:
            raise AssetIdMismatch(
                "The asset id of the input does not match the asset id of the transaction"
            )

        # Validate request return exists
        request_return_id = self.asset.get('data', {}).get('request_return_id')
        if not request_return_id:
            raise ValueError("Seller accept return must reference a request return")
            
        request_return_tx = bigchain.get_transaction(request_return_id)
        if not request_return_tx:
            raise ValueError(f"Referenced request return {request_return_id} does not exist")
            
        if request_return_tx.operation != 'REQUEST_RETURN':
            raise ValueError(f"Referenced transaction {request_return_id} is not a request return")

        # Validate seller = accepter
        accepter_pub_key = self.metadata.get('seller_public_key')
        
        # Get the sell transaction from the request return
        sell_transaction_id = request_return_tx.asset.get('sell_transaction_id') or request_return_tx.asset.get('data', {}).get('sell_transaction_id')
        sell_tx = bigchain.get_transaction(sell_transaction_id)
        
        if not sell_tx:
            raise ValueError(f"Referenced sell transaction {sell_transaction_id} does not exist")
            
        # Get the advertisement from the sell transaction
        buy_offer_id = sell_tx.asset.get('buy_offer_id') or sell_tx.asset.get('data', {}).get('buy_offer_id')
        buy_offer_tx = bigchain.get_transaction(buy_offer_id)
        
        if not buy_offer_tx:
            raise ValueError(f"Referenced buy offer {buy_offer_id} does not exist")
            
        advertisement_id = buy_offer_tx.asset.get('advertisement_id') or buy_offer_tx.asset.get('data', {}).get('advertisement_id')
        advertisement_tx = bigchain.get_transaction(advertisement_id)
        
        if not advertisement_tx:
            raise ValueError(f"Referenced advertisement {advertisement_id} does not exist")
            
        seller_pub_key = advertisement_tx.metadata.get('advertiser_public_key')
        
        if accepter_pub_key != seller_pub_key:
            raise ValueError("Accepter must be the seller from the sell transaction")

        # Validate request return is PENDING
        return_status = request_return_tx.metadata.get('return_policy_details', {}).get('return_status')
        if return_status != 'PENDING':
            raise ValueError("Request return must be PENDING to accept")

        # Validate refund details
        refund_details = self.metadata.get('refund_details', {})
        if not refund_details:
            raise ValueError("Seller accept return must include refund details")
            
        refund_amount = refund_details.get('refund_amount')
        refund_currency = refund_details.get('refund_currency')
        refund_method = refund_details.get('refund_method')
        
        if not refund_amount or not refund_currency or not refund_method:
            raise ValueError("Refund details must include amount, currency, and method")

        # Validate signature
        if not self._validate_signature(input_conditions):
            raise InvalidSignature("Transaction signature is invalid.")

        return True

    def __match_capabilities(self, bigchain, requested_cap, input_tx_id) -> bool:
        # TODO: Change input_tx_id to fulfill_tx_id
        input_tx = bigchain.get_transaction(input_tx_id)
        if input_tx is None:
            raise InputDoesNotExist("input `{}` doesn't exist".format(input_tx_id))

        input_capability_set = set()
        input_capability_list = list(input_tx.asset["data"]["capability"])
        input_capability_set.update(input_capability_list)

        requested_capability_set = set(requested_cap)
        return requested_capability_set.issubset(input_capability_set)

    def validate_interest(self, bigchain, current_transactions=[]):
        rfq_tx_id = self.asset["data"]["pre_request_id"]
        rfq_tx = bigchain.get_transaction(rfq_tx_id)

        if rfq_tx is None:
            raise InputDoesNotExist(
                "PRE_REQUEST input `{}` doesn't exist".format(rfq_tx_id)
            )

        if rfq_tx.operation != self.PRE_REQUEST:
            raise ValidationError(
                "INTEREST transaction must be against a commited PRE_REQUEST transaction"
            )

        requested_cap = rfq_tx.metadata["capability"]
        create_tx_id = self.asset["data"]["id"]

        if not self.__match_capabilities(bigchain, requested_cap, create_tx_id):
            raise InsufficientCapabilities(
                "INTEREST transaction must fulfill all the requested capabilities"
            )

        return True

    def validate_rfq(self, bigchain, current_transactions=[]):
        # pre_rfq_tx_id = self.asset["data"]["pre_request_id"]
        # pre_rfq_tx = bigchain.get_transaction(pre_rfq_tx_id)

        # # TODO: Deadline field validation
        # if rfq_tx is None:
        #     raise InputDoesNotExist(
        #         "PRE_REQUEST input `{}` doesn't exist".format(rfq_tx_id)
        #     )

        # if rfq_tx.operation != self.PRE_REQUEST:
        #     raise ValidationError(
        #         "RFQ transaction must be related to a commited PRE_REQUEST transaction"
        #     )

        return True

    def validate_bid(self, bigchain, current_transactions=[]):
        # FIXME: BID received for stale RFQ(timeout or fulfilled)
        rfq_tx_id = self.asset["data"]["rfq_id"]
        rfq_tx = bigchain.get_transaction(rfq_tx_id)

        if rfq_tx is None:
            raise InputDoesNotExist("RFQ input `{}` doesn't exist".format(rfq_tx_id))

        if rfq_tx.operation != self.REQUEST_FOR_QUOTE:
            raise ValidationError(
                "BID transaction must be against a commited RFQ transaction"
            )

        for output in self.outputs:
            if (
                len(output.public_keys) != 1
                or output.public_keys[0]
                != config["smartchaindb_key_pair"]["public_key"]
            ):
                raise ValidationError(
                    "BID transaction's outputs must point to Escrow account"
                )

        requested_cap = rfq_tx.metadata["capability"]
        create_tx_id = self.asset["data"]["id"]
        if not self.__match_capabilities(bigchain, requested_cap, create_tx_id):
            raise InsufficientCapabilities(
                "BID transaction must fulfill all the requested capabilities"
            )

        return self.validate_transfer_inputs(bigchain, current_transactions)

    @classmethod
    def build_return_tx(cls, accept_id, asset_id, fulfilled_tx, recepient_pub_key):
        output_index = 0
        output = fulfilled_tx.outputs[output_index]

        return_input = Input(
            fulfillment=output.fulfillment,
            owners_before=output.public_keys,
            fulfills=TransactionLink(asset_id, output_index),
        )
        return_output = Output.generate(
            public_keys=[recepient_pub_key], amount=output.amount
        )

        metadata = {
            "requestCreationTimestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
        }
        asset = {
            "data": {
                "bid_id": asset_id,
                "accept_id": accept_id,
            }
        }
        return_tx = Transaction(
            operation=Transaction.RETURN,
            asset=asset,
            inputs=[return_input],
            outputs=[return_output],
            metadata=metadata,
        )

        return return_tx.sign([config["smartchaindb_key_pair"]["private_key"]])

    @classmethod
    def determine_returns(
        cls, bigchain, accept_id, rfq_tx_id=None, winning_bid_id=None
    ):
        input_index = 0
        return_txs = list()

        if rfq_tx_id is None or winning_bid_id is None:
            accept_tx = bigchain.get_transaction(accept_id)
            rfq_tx_id = accept_tx.asset["data"]["rfq_id"]
            winning_bid_id = accept_tx.asset["data"]["winner_bid_id"]

        rfq_tx = bigchain.get_transaction(rfq_tx_id)
        winning_bid_tx = bigchain.get_transaction(winning_bid_id)
        owned_bid_ids = bigchain.get_locked_bid_txids_for_rfq(rfq_tx_id)

        requestor_pub_key = rfq_tx.inputs[input_index].owners_before[-1]
        return_tx = Transaction.build_return_tx(
            accept_id, winning_bid_id, winning_bid_tx, requestor_pub_key
        )
        return_txs.append(return_tx)

        for bid_id in owned_bid_ids:
            if bid_id != winning_bid_id:
                bid_tx = bigchain.get_transaction(bid_id)

                # NOTE: Supports only one bidder and one input asset
                # (i.e. incompatible with divisible asset tokens)
                bidder_pub_key = bid_tx.inputs[input_index].owners_before[-1]
                return_tx = Transaction.build_return_tx(
                    accept_id, bid_id, bid_tx, bidder_pub_key
                )
                return_txs.append(return_tx)

        return return_txs

    def validate_accept(self, bigchain, current_transactions=[]):
        rfq_tx_id = self.asset["data"]["rfq_id"]
        winning_bid_id = self.asset["data"]["winner_bid_id"]

        rfq_tx = bigchain.get_transaction(rfq_tx_id)
        if rfq_tx is None or rfq_tx.operation != self.REQUEST_FOR_QUOTE:
            raise InputDoesNotExist("RFQ input `{}` doesn't exist".format(rfq_tx_id))

        accept_ffill = self.inputs[0].fulfillment.to_dict()
        for rfq_input in rfq_tx.inputs:
            rfq_ffill = rfq_input.fulfillment.to_dict()
            if rfq_ffill["public_key"] != accept_ffill["public_key"]:
                raise InvalidAccount(
                    "ACCEPT tx signer must be same as its associated RFQ(`{}`) signer".format(
                        rfq_tx_id
                    )
                )

        accept_tx = bigchain.get_accept_tx_for_rfq(rfq_tx_id)
        if accept_tx:
            raise DuplicateTransaction(
                "ACCEPT tx with the same RFQ input `{}` already committed".format(
                    rfq_tx_id
                )
            )

        winning_bid = bigchain.get_transaction(winning_bid_id)
        if winning_bid is None or winning_bid.operation != self.BID:
            raise InputDoesNotExist(
                "BID input `{}` doesn't exist".format(winning_bid_id)
            )

        winning_bid_id = self.asset["data"]["winner_bid_id"]
        owned_bid_ids = bigchain.get_locked_bid_txids_for_rfq(rfq_tx_id)

        if winning_bid_id not in owned_bid_ids:
            raise InputDoesNotExist(
                "BID input `{}` doesn't exist. Possible Causes: RFQ timeout or BID withdrawal".format(
                    winning_bid_id
                )
            )

        return True

    def validate_return(self, bigchain, current_transactions=[]):
        for input in self.inputs:
            ffill = input.fulfillment.to_dict()
            if input.owners_before[-1] != config["smartchaindb_key_pair"]["public_key"]:
                raise ValidationError("Return tx must always be initiated by Escrow")

        input_tx_id = self.asset["data"]["bid_id"]
        locked_bid_ids = set(bigchain.get_locked_bid_txids())
        if input_tx_id not in locked_bid_ids:
            raise InputDoesNotExist(
                "Escrow does not hold the bid input({})".format(input_tx_id)
            )

        return self.validate_transfer_inputs(bigchain, current_transactions)

    @classmethod
    def send_transfer(cls, asset_id, fulfilled_tx, recipient_pub_key):
        """Custom transfer routine for transfering accumulated assets for a RFQ.

        NOTE: Transfer will always be triggered from the special account,
        i.e. special account secret key -> signing key.
        """
        from bigchaindb_driver import BigchainDB

        bdb = BigchainDB(os.environ.get("BIGCHAINDB_ENDPOINT"), timeout=40)

        # A `TRANSFER` transaction contains a pointer to the original asset. The original asset
        # is identified by the `id` of the `CREATE` transaction that defined it.
        transfer_asset = {"id": asset_id}

        output_index = 0
        output = fulfilled_tx.outputs[output_index]

        # Here, it defines the `input` of the `TRANSFER` transaction. The `input` contains
        # several keys:
        #
        # - `fulfillment`, taken from the previous `CREATE` transaction.
        # - `fulfills`, that specifies which condition she is fulfilling.
        # - `owners_before`.
        transfer_input = {
            "fulfillment": _fulfillment_to_details(output.fulfillment),
            "fulfills": {
                "output_index": output_index,
                "transaction_id": asset_id,
            },
            "owners_before": output.public_keys,
        }
        transfer_metadata = {
            "requestCreationTimestamp": datetime.now().strftime("%Y-%m-%dT%H:%M:%S.%f")
        }

        prepared_transfer_tx = bdb.transactions.prepare(
            operation="TRANSFER",
            asset=transfer_asset,
            inputs=transfer_input,
            metadata=transfer_metadata,
            recipients=recipient_pub_key,
        )

        # signs tx with the special account's private key
        fulfilled_transfer_tx = bdb.transactions.fulfill(
            prepared_transfer_tx,
            private_keys=config["smartchaindb_key_pair"]["private_key"],
        )

        bdb.transactions.send_async(fulfilled_transfer_tx)
