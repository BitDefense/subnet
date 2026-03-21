# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# Copyright © 2026 Aleksei Gubin

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import typing
import bittensor as bt

from pydantic import BaseModel


class Invariant(BaseModel):
    contract: str
    type: str
    target: str
    storage: str
    slot_type: str


class Challenge(bt.Synapse):
    """
    The BitDefense Challenge protocol representation.
    """

    chain_id: str
    block_number: str
    tx: typing.Dict[str, typing.Any]
    invariants: typing.List[Invariant]

    output: typing.Optional[typing.List[int]] = None

    def deserialize(self) -> typing.List[int]:
        """
        Deserialize the challenge output.
        Returns an empty list if output is None.
        """
        if self.output is None:
            return []
        return self.output

    # @classmethod
    # def from_headers(cls, headers: dict) -> "Challenge":
    #     """
    #     Constructs a Synapse instance from a dictionary of headers.
    #     Injects a dummy 'tx' dictionary if it is empty to satisfy Pydantic validation
    #     during the header parsing phase before the JSON body is processed.
    #     """
    #     input_dict = cls.parse_headers_to_inputs(headers)

    #     # Manually handle lowercased keys from headers if they don't match snake_case
    #     if "chainid" in input_dict and "chain_id" not in input_dict:
    #         input_dict["chain_id"] = input_dict.pop("chainid")
    #     if "blocknumber" in input_dict and "block_number" not in input_dict:
    #         input_dict["block_number"] = input_dict.pop("blocknumber")

    #     # Inject dummy data for complex required fields to pass the dummy header phase.
    #     # Bittensor provides `{}` for nested models during header parsing.
    #     if isinstance(input_dict.get("tx"), dict) and not input_dict["tx"]:
    #         input_dict["tx"] = {
    #             "hash": "",
    #             "payload": {
    #                 "type": "",
    #                 "chainId": "",
    #                 "nonce": "",
    #                 "gasPrice": "",
    #                 "gas": "",
    #                 "to": "",
    #                 "value": "",
    #                 "input": "",
    #                 "r": "",
    #                 "s": "",
    #                 "v": "",
    #                 "hash": "",
    #                 "from": "",
    #             },
    #         }

    #     return cls(**input_dict)


class MempoolTransaction(bt.Synapse):
    """
    Synapse representing a raw Ethereum transaction sent from Platform to Validator.
    """

    chain_id: int
    block_number: int
    tx: typing.Dict[str, typing.Any]
    received: bool = False

    def deserialize(self) -> bool:
        return self.received
