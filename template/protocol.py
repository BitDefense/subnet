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

from pydantic import BaseModel, Field, ConfigDict

class TransactionPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    
    type: str
    chainId: str
    nonce: str
    gasPrice: str
    gas: str
    to: str
    value: str
    input: str
    r: str
    s: str
    v: str
    hash: str
    blockHash: str
    blockNumber: str
    transactionIndex: str
    from_address: str = Field(alias="from")

class Transaction(BaseModel):
    hash: str
    payload: TransactionPayload

class Invariant(BaseModel):
    contract: str
    type: str
    target: str
    storage: str
    storage_slot_type: str

class Challenge(bt.Synapse):
    """
    The BitDefense Challenge protocol representation.
    """
    chain_id: str
    block_number: str
    tx: Transaction
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
