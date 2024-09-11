# type: ignore
from proto.layer.oracle import MsgTip as MsgTip_pb
from terra_sdk.core.msg import Msg


__all__ = ["MsgTip"]

import attr

# @dataclass(eq=False, repr=False)
# class MsgTip(betterproto.Message):
#     tipper: str = betterproto.string_field(1)
#     query_data: bytes = betterproto.bytes_field(2)
#     amount: "__cosmos_base_v1_beta1__.Coin" = betterproto.message_field(3)


@attr.s
class MsgTip(Msg):
    """Tip oracle report revealing value from ``creator`` to ``query_data``.

    Args:
        tipper (str): msg_sender
        query_data (str): query_data
        amount (str): amount
    """

    type_amino = "layer/MsgTip"
    """"""
    type_url = "/layer.oracle.MsgTip"
    """"""
    action = "send"
    """"""
    prototype = MsgTip_pb
    """"""

    tipper: str = attr.ib()
    query_data: bytes = attr.ib()
    amount: str = attr.ib()

    def to_amino(self) -> dict:
        return {
            "type": self.type_amino,
            "value": {
                "tipper": self.tipper,
                "query_data": self.query_data,
                "amount": self.amount,
            },
        }

    @classmethod
    def from_data(cls, data: dict):
        return cls(
            tipper=data["tipper"],
            query_data=data["query_data"],
            amount=data["amount"],
        )

    def to_data(self) -> dict:
        return {
            "@type": self.type_url,
            "tipper": self.tipper,
            "query_data": self.query_data,
            "amount": self.amount,
        }

    @classmethod
    def from_proto(cls, proto: MsgTip_pb):
        return cls(
            tipper=proto.tipper,
            query_data=proto.query_data,
            amount=proto.amount,
        )

    def to_proto(self) -> MsgTip_pb:
        proto = MsgTip_pb()
        proto.tipper = self.tipper
        proto.query_data = self.query_data
        proto.amount = self.amount
        return proto
