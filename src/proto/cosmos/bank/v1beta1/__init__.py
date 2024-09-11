# Generated by the protocol buffer compiler.  DO NOT EDIT!
# sources: cosmos/bank/v1beta1/authz.proto, cosmos/bank/v1beta1/bank.proto, cosmos/bank/v1beta1/genesis.proto, cosmos/bank/v1beta1/query.proto, cosmos/bank/v1beta1/tx.proto
# plugin: python-betterproto
# This file has been @generated
import warnings
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING,
    Dict,
    List,
    Optional,
)

import betterproto
import grpclib
from betterproto.grpc.grpclib_server import ServiceBase

from ...base import v1beta1 as __base_v1_beta1__
from ...base.query import v1beta1 as __base_query_v1_beta1__


if TYPE_CHECKING:
    import grpclib.server
    from betterproto.grpc.grpclib_client import MetadataLike
    from grpclib.metadata import Deadline


@dataclass(eq=False, repr=False)
class Params(betterproto.Message):
    """Params defines the parameters for the bank module."""

    send_enabled: List["SendEnabled"] = betterproto.message_field(1)
    """
    Deprecated: Use of SendEnabled in params is deprecated.
     For genesis, use the newly added send_enabled field in the genesis object.
     Storage, lookup, and manipulation of this information is now in the keeper.
    
     As of cosmos-sdk 0.47, this only exists for backwards compatibility of genesis files.
    """

    default_send_enabled: bool = betterproto.bool_field(2)

    def __post_init__(self) -> None:
        super().__post_init__()
        if self.is_set("send_enabled"):
            warnings.warn("Params.send_enabled is deprecated", DeprecationWarning)


@dataclass(eq=False, repr=False)
class SendEnabled(betterproto.Message):
    """
    SendEnabled maps coin denom to a send_enabled status (whether a denom is
     sendable).
    """

    denom: str = betterproto.string_field(1)
    enabled: bool = betterproto.bool_field(2)


@dataclass(eq=False, repr=False)
class Input(betterproto.Message):
    """Input models transaction input."""

    address: str = betterproto.string_field(1)
    coins: List["__base_v1_beta1__.Coin"] = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class Output(betterproto.Message):
    """Output models transaction outputs."""

    address: str = betterproto.string_field(1)
    coins: List["__base_v1_beta1__.Coin"] = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class Supply(betterproto.Message):
    """
    Supply represents a struct that passively keeps track of the total supply
     amounts in the network.
     This message is deprecated now that supply is indexed by denom.
    """

    total: List["__base_v1_beta1__.Coin"] = betterproto.message_field(1)

    def __post_init__(self) -> None:
        warnings.warn("Supply is deprecated", DeprecationWarning)
        super().__post_init__()


@dataclass(eq=False, repr=False)
class DenomUnit(betterproto.Message):
    """
    DenomUnit represents a struct that describes a given
     denomination unit of the basic token.
    """

    denom: str = betterproto.string_field(1)
    """
    denom represents the string name of the given denom unit (e.g uatom).
    """

    exponent: int = betterproto.uint32_field(2)
    """
    exponent represents power of 10 exponent that one must
     raise the base_denom to in order to equal the given DenomUnit's denom
     1 denom = 10^exponent base_denom
     (e.g. with a base_denom of uatom, one can create a DenomUnit of 'atom' with
     exponent = 6, thus: 1 atom = 10^6 uatom).
    """

    aliases: List[str] = betterproto.string_field(3)
    """aliases is a list of string aliases for the given denom"""


@dataclass(eq=False, repr=False)
class Metadata(betterproto.Message):
    """
    Metadata represents a struct that describes
     a basic token.
    """

    description: str = betterproto.string_field(1)
    denom_units: List["DenomUnit"] = betterproto.message_field(2)
    """denom_units represents the list of DenomUnit's for a given coin"""

    base: str = betterproto.string_field(3)
    """
    base represents the base denom (should be the DenomUnit with exponent = 0).
    """

    display: str = betterproto.string_field(4)
    """
    display indicates the suggested denom that should be
     displayed in clients.
    """

    name: str = betterproto.string_field(5)
    """
    name defines the name of the token (eg: Cosmos Atom)
    
     Since: cosmos-sdk 0.43
    """

    symbol: str = betterproto.string_field(6)
    """
    symbol is the token symbol usually shown on exchanges (eg: ATOM). This can
     be the same as the display.
    
     Since: cosmos-sdk 0.43
    """

    uri: str = betterproto.string_field(7)
    """
    URI to a document (on or off-chain) that contains additional information. Optional.
    
     Since: cosmos-sdk 0.46
    """

    uri_hash: str = betterproto.string_field(8)
    """
    URIHash is a sha256 hash of a document pointed by URI. It's used to verify that
     the document didn't change. Optional.
    
     Since: cosmos-sdk 0.46
    """


@dataclass(eq=False, repr=False)
class MsgSend(betterproto.Message):
    """
    MsgSend represents a message to send coins from one account to another.
    """

    from_address: str = betterproto.string_field(1)
    to_address: str = betterproto.string_field(2)
    amount: List["__base_v1_beta1__.Coin"] = betterproto.message_field(3)


@dataclass(eq=False, repr=False)
class MsgSendResponse(betterproto.Message):
    """MsgSendResponse defines the Msg/Send response type."""

    pass


@dataclass(eq=False, repr=False)
class MsgMultiSend(betterproto.Message):
    """
    MsgMultiSend represents an arbitrary multi-in, multi-out send message.
    """

    inputs: List["Input"] = betterproto.message_field(1)
    """
    Inputs, despite being `repeated`, only allows one sender input. This is
     checked in MsgMultiSend's ValidateBasic.
    """

    outputs: List["Output"] = betterproto.message_field(2)


@dataclass(eq=False, repr=False)
class MsgMultiSendResponse(betterproto.Message):
    """MsgMultiSendResponse defines the Msg/MultiSend response type."""

    pass


@dataclass(eq=False, repr=False)
class MsgUpdateParams(betterproto.Message):
    """
    MsgUpdateParams is the Msg/UpdateParams request type.

     Since: cosmos-sdk 0.47
    """

    authority: str = betterproto.string_field(1)
    """
    authority is the address that controls the module (defaults to x/gov unless overwritten).
    """

    params: "Params" = betterproto.message_field(2)
    """
    params defines the x/bank parameters to update.
    
     NOTE: All parameters must be supplied.
    """


@dataclass(eq=False, repr=False)
class MsgUpdateParamsResponse(betterproto.Message):
    """
    MsgUpdateParamsResponse defines the response structure for executing a
     MsgUpdateParams message.

     Since: cosmos-sdk 0.47
    """

    pass


@dataclass(eq=False, repr=False)
class MsgSetSendEnabled(betterproto.Message):
    """
    MsgSetSendEnabled is the Msg/SetSendEnabled request type.

     Only entries to add/update/delete need to be included.
     Existing SendEnabled entries that are not included in this
     message are left unchanged.

     Since: cosmos-sdk 0.47
    """

    authority: str = betterproto.string_field(1)
    send_enabled: List["SendEnabled"] = betterproto.message_field(2)
    """send_enabled is the list of entries to add or update."""

    use_default_for: List[str] = betterproto.string_field(3)
    """
    use_default_for is a list of denoms that should use the params.default_send_enabled value.
     Denoms listed here will have their SendEnabled entries deleted.
     If a denom is included that doesn't have a SendEnabled entry,
     it will be ignored.
    """


@dataclass(eq=False, repr=False)
class MsgSetSendEnabledResponse(betterproto.Message):
    """
    MsgSetSendEnabledResponse defines the Msg/SetSendEnabled response type.

     Since: cosmos-sdk 0.47
    """

    pass


@dataclass(eq=False, repr=False)
class QueryBalanceRequest(betterproto.Message):
    """
    QueryBalanceRequest is the request type for the Query/Balance RPC method.
    """

    address: str = betterproto.string_field(1)
    """address is the address to query balances for."""

    denom: str = betterproto.string_field(2)
    """denom is the coin denom to query balances for."""


@dataclass(eq=False, repr=False)
class QueryBalanceResponse(betterproto.Message):
    """
    QueryBalanceResponse is the response type for the Query/Balance RPC method.
    """

    balance: "__base_v1_beta1__.Coin" = betterproto.message_field(1)
    """balance is the balance of the coin."""


@dataclass(eq=False, repr=False)
class QueryAllBalancesRequest(betterproto.Message):
    """
    QueryBalanceRequest is the request type for the Query/AllBalances RPC method.
    """

    address: str = betterproto.string_field(1)
    """address is the address to query balances for."""

    pagination: "__base_query_v1_beta1__.PageRequest" = betterproto.message_field(2)
    """pagination defines an optional pagination for the request."""


@dataclass(eq=False, repr=False)
class QueryAllBalancesResponse(betterproto.Message):
    """
    QueryAllBalancesResponse is the response type for the Query/AllBalances RPC
     method.
    """

    balances: List["__base_v1_beta1__.Coin"] = betterproto.message_field(1)
    """balances is the balances of all the coins."""

    pagination: "__base_query_v1_beta1__.PageResponse" = betterproto.message_field(2)
    """pagination defines the pagination in the response."""


@dataclass(eq=False, repr=False)
class QuerySpendableBalancesRequest(betterproto.Message):
    """
    QuerySpendableBalancesRequest defines the gRPC request structure for querying
     an account's spendable balances.

     Since: cosmos-sdk 0.46
    """

    address: str = betterproto.string_field(1)
    """address is the address to query spendable balances for."""

    pagination: "__base_query_v1_beta1__.PageRequest" = betterproto.message_field(2)
    """pagination defines an optional pagination for the request."""


@dataclass(eq=False, repr=False)
class QuerySpendableBalancesResponse(betterproto.Message):
    """
    QuerySpendableBalancesResponse defines the gRPC response structure for querying
     an account's spendable balances.

     Since: cosmos-sdk 0.46
    """

    balances: List["__base_v1_beta1__.Coin"] = betterproto.message_field(1)
    """balances is the spendable balances of all the coins."""

    pagination: "__base_query_v1_beta1__.PageResponse" = betterproto.message_field(2)
    """pagination defines the pagination in the response."""


@dataclass(eq=False, repr=False)
class QuerySpendableBalanceByDenomRequest(betterproto.Message):
    """
    QuerySpendableBalanceByDenomRequest defines the gRPC request structure for
     querying an account's spendable balance for a specific denom.

     Since: cosmos-sdk 0.47
    """

    address: str = betterproto.string_field(1)
    """address is the address to query balances for."""

    denom: str = betterproto.string_field(2)
    """denom is the coin denom to query balances for."""


@dataclass(eq=False, repr=False)
class QuerySpendableBalanceByDenomResponse(betterproto.Message):
    """
    QuerySpendableBalanceByDenomResponse defines the gRPC response structure for
     querying an account's spendable balance for a specific denom.

     Since: cosmos-sdk 0.47
    """

    balance: "__base_v1_beta1__.Coin" = betterproto.message_field(1)
    """balance is the balance of the coin."""


@dataclass(eq=False, repr=False)
class QueryTotalSupplyRequest(betterproto.Message):
    """
    QueryTotalSupplyRequest is the request type for the Query/TotalSupply RPC
     method.
    """

    pagination: "__base_query_v1_beta1__.PageRequest" = betterproto.message_field(1)
    """
    pagination defines an optional pagination for the request.
    
     Since: cosmos-sdk 0.43
    """


@dataclass(eq=False, repr=False)
class QueryTotalSupplyResponse(betterproto.Message):
    """
    QueryTotalSupplyResponse is the response type for the Query/TotalSupply RPC
     method
    """

    supply: List["__base_v1_beta1__.Coin"] = betterproto.message_field(1)
    """supply is the supply of the coins"""

    pagination: "__base_query_v1_beta1__.PageResponse" = betterproto.message_field(2)
    """
    pagination defines the pagination in the response.
    
     Since: cosmos-sdk 0.43
    """


@dataclass(eq=False, repr=False)
class QuerySupplyOfRequest(betterproto.Message):
    """
    QuerySupplyOfRequest is the request type for the Query/SupplyOf RPC method.
    """

    denom: str = betterproto.string_field(1)
    """denom is the coin denom to query balances for."""


@dataclass(eq=False, repr=False)
class QuerySupplyOfResponse(betterproto.Message):
    """
    QuerySupplyOfResponse is the response type for the Query/SupplyOf RPC method.
    """

    amount: "__base_v1_beta1__.Coin" = betterproto.message_field(1)
    """amount is the supply of the coin."""


@dataclass(eq=False, repr=False)
class QueryParamsRequest(betterproto.Message):
    """
    QueryParamsRequest defines the request type for querying x/bank parameters.
    """

    pass


@dataclass(eq=False, repr=False)
class QueryParamsResponse(betterproto.Message):
    """
    QueryParamsResponse defines the response type for querying x/bank parameters.
    """

    params: "Params" = betterproto.message_field(1)


@dataclass(eq=False, repr=False)
class QueryDenomsMetadataRequest(betterproto.Message):
    """
    QueryDenomsMetadataRequest is the request type for the Query/DenomsMetadata RPC method.
    """

    pagination: "__base_query_v1_beta1__.PageRequest" = betterproto.message_field(1)
    """pagination defines an optional pagination for the request."""


@dataclass(eq=False, repr=False)
class QueryDenomsMetadataResponse(betterproto.Message):
    """
    QueryDenomsMetadataResponse is the response type for the Query/DenomsMetadata RPC
     method.
    """

    metadatas: List["Metadata"] = betterproto.message_field(1)
    """
    metadata provides the client information for all the registered tokens.
    """

    pagination: "__base_query_v1_beta1__.PageResponse" = betterproto.message_field(2)
    """pagination defines the pagination in the response."""


@dataclass(eq=False, repr=False)
class QueryDenomMetadataRequest(betterproto.Message):
    """
    QueryDenomMetadataRequest is the request type for the Query/DenomMetadata RPC method.
    """

    denom: str = betterproto.string_field(1)
    """denom is the coin denom to query the metadata for."""


@dataclass(eq=False, repr=False)
class QueryDenomMetadataResponse(betterproto.Message):
    """
    QueryDenomMetadataResponse is the response type for the Query/DenomMetadata RPC
     method.
    """

    metadata: "Metadata" = betterproto.message_field(1)
    """
    metadata describes and provides all the client information for the requested token.
    """


@dataclass(eq=False, repr=False)
class QueryDenomOwnersRequest(betterproto.Message):
    """
    QueryDenomOwnersRequest defines the request type for the DenomOwners RPC query,
     which queries for a paginated set of all account holders of a particular
     denomination.
    """

    denom: str = betterproto.string_field(1)
    """
    denom defines the coin denomination to query all account holders for.
    """

    pagination: "__base_query_v1_beta1__.PageRequest" = betterproto.message_field(2)
    """pagination defines an optional pagination for the request."""


@dataclass(eq=False, repr=False)
class DenomOwner(betterproto.Message):
    """
    DenomOwner defines structure representing an account that owns or holds a
     particular denominated token. It contains the account address and account
     balance of the denominated token.

     Since: cosmos-sdk 0.46
    """

    address: str = betterproto.string_field(1)
    """address defines the address that owns a particular denomination."""

    balance: "__base_v1_beta1__.Coin" = betterproto.message_field(2)
    """balance is the balance of the denominated coin for an account."""


@dataclass(eq=False, repr=False)
class QueryDenomOwnersResponse(betterproto.Message):
    """
    QueryDenomOwnersResponse defines the RPC response of a DenomOwners RPC query.

     Since: cosmos-sdk 0.46
    """

    denom_owners: List["DenomOwner"] = betterproto.message_field(1)
    pagination: "__base_query_v1_beta1__.PageResponse" = betterproto.message_field(2)
    """pagination defines the pagination in the response."""


@dataclass(eq=False, repr=False)
class QuerySendEnabledRequest(betterproto.Message):
    """
    QuerySendEnabledRequest defines the RPC request for looking up SendEnabled entries.

     Since: cosmos-sdk 0.47
    """

    denoms: List[str] = betterproto.string_field(1)
    """
    denoms is the specific denoms you want look up. Leave empty to get all entries.
    """

    pagination: "__base_query_v1_beta1__.PageRequest" = betterproto.message_field(99)
    """
    pagination defines an optional pagination for the request. This field is
     only read if the denoms field is empty.
    """


@dataclass(eq=False, repr=False)
class QuerySendEnabledResponse(betterproto.Message):
    """
    QuerySendEnabledResponse defines the RPC response of a SendEnable query.

     Since: cosmos-sdk 0.47
    """

    send_enabled: List["SendEnabled"] = betterproto.message_field(1)
    pagination: "__base_query_v1_beta1__.PageResponse" = betterproto.message_field(99)
    """
    pagination defines the pagination in the response. This field is only
     populated if the denoms field in the request is empty.
    """


@dataclass(eq=False, repr=False)
class SendAuthorization(betterproto.Message):
    """
    SendAuthorization allows the grantee to spend up to spend_limit coins from
     the granter's account.

     Since: cosmos-sdk 0.43
    """

    spend_limit: List["__base_v1_beta1__.Coin"] = betterproto.message_field(1)
    allow_list: List[str] = betterproto.string_field(2)
    """
    allow_list specifies an optional list of addresses to whom the grantee can send tokens on behalf of the
     granter. If omitted, any recipient is allowed.
    
     Since: cosmos-sdk 0.47
    """


@dataclass(eq=False, repr=False)
class GenesisState(betterproto.Message):
    """GenesisState defines the bank module's genesis state."""

    params: "Params" = betterproto.message_field(1)
    """params defines all the parameters of the module."""

    balances: List["Balance"] = betterproto.message_field(2)
    """balances is an array containing the balances of all the accounts."""

    supply: List["__base_v1_beta1__.Coin"] = betterproto.message_field(3)
    """
    supply represents the total supply. If it is left empty, then supply will be calculated based on the provided
     balances. Otherwise, it will be used to validate that the sum of the balances equals this amount.
    """

    denom_metadata: List["Metadata"] = betterproto.message_field(4)
    """denom_metadata defines the metadata of the different coins."""

    send_enabled: List["SendEnabled"] = betterproto.message_field(5)
    """
    send_enabled defines the denoms where send is enabled or disabled.
    
     Since: cosmos-sdk 0.47
    """


@dataclass(eq=False, repr=False)
class Balance(betterproto.Message):
    """
    Balance defines an account address and balance pair used in the bank module's
     genesis state.
    """

    address: str = betterproto.string_field(1)
    """address is the address of the balance holder."""

    coins: List["__base_v1_beta1__.Coin"] = betterproto.message_field(2)
    """coins defines the different coins this balance holds."""


class MsgStub(betterproto.ServiceStub):
    async def send(
        self,
        msg_send: "MsgSend",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "MsgSendResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Msg/Send",
            msg_send,
            MsgSendResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def multi_send(
        self,
        msg_multi_send: "MsgMultiSend",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "MsgMultiSendResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Msg/MultiSend",
            msg_multi_send,
            MsgMultiSendResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def update_params(
        self,
        msg_update_params: "MsgUpdateParams",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "MsgUpdateParamsResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Msg/UpdateParams",
            msg_update_params,
            MsgUpdateParamsResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def set_send_enabled(
        self,
        msg_set_send_enabled: "MsgSetSendEnabled",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "MsgSetSendEnabledResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Msg/SetSendEnabled",
            msg_set_send_enabled,
            MsgSetSendEnabledResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )


class QueryStub(betterproto.ServiceStub):
    async def balance(
        self,
        query_balance_request: "QueryBalanceRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QueryBalanceResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/Balance",
            query_balance_request,
            QueryBalanceResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def all_balances(
        self,
        query_all_balances_request: "QueryAllBalancesRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QueryAllBalancesResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/AllBalances",
            query_all_balances_request,
            QueryAllBalancesResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def spendable_balances(
        self,
        query_spendable_balances_request: "QuerySpendableBalancesRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QuerySpendableBalancesResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/SpendableBalances",
            query_spendable_balances_request,
            QuerySpendableBalancesResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def spendable_balance_by_denom(
        self,
        query_spendable_balance_by_denom_request: "QuerySpendableBalanceByDenomRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QuerySpendableBalanceByDenomResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/SpendableBalanceByDenom",
            query_spendable_balance_by_denom_request,
            QuerySpendableBalanceByDenomResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def total_supply(
        self,
        query_total_supply_request: "QueryTotalSupplyRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QueryTotalSupplyResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/TotalSupply",
            query_total_supply_request,
            QueryTotalSupplyResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def supply_of(
        self,
        query_supply_of_request: "QuerySupplyOfRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QuerySupplyOfResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/SupplyOf",
            query_supply_of_request,
            QuerySupplyOfResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def params(
        self,
        query_params_request: "QueryParamsRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QueryParamsResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/Params",
            query_params_request,
            QueryParamsResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def denom_metadata(
        self,
        query_denom_metadata_request: "QueryDenomMetadataRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QueryDenomMetadataResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/DenomMetadata",
            query_denom_metadata_request,
            QueryDenomMetadataResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def denoms_metadata(
        self,
        query_denoms_metadata_request: "QueryDenomsMetadataRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QueryDenomsMetadataResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/DenomsMetadata",
            query_denoms_metadata_request,
            QueryDenomsMetadataResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def denom_owners(
        self,
        query_denom_owners_request: "QueryDenomOwnersRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QueryDenomOwnersResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/DenomOwners",
            query_denom_owners_request,
            QueryDenomOwnersResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )

    async def send_enabled(
        self,
        query_send_enabled_request: "QuerySendEnabledRequest",
        *,
        timeout: Optional[float] = None,
        deadline: Optional["Deadline"] = None,
        metadata: Optional["MetadataLike"] = None
    ) -> "QuerySendEnabledResponse":
        return await self._unary_unary(
            "/cosmos.bank.v1beta1.Query/SendEnabled",
            query_send_enabled_request,
            QuerySendEnabledResponse,
            timeout=timeout,
            deadline=deadline,
            metadata=metadata,
        )


class MsgBase(ServiceBase):

    async def send(self, msg_send: "MsgSend") -> "MsgSendResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def multi_send(
        self, msg_multi_send: "MsgMultiSend"
    ) -> "MsgMultiSendResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def update_params(
        self, msg_update_params: "MsgUpdateParams"
    ) -> "MsgUpdateParamsResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def set_send_enabled(
        self, msg_set_send_enabled: "MsgSetSendEnabled"
    ) -> "MsgSetSendEnabledResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def __rpc_send(
        self, stream: "grpclib.server.Stream[MsgSend, MsgSendResponse]"
    ) -> None:
        request = await stream.recv_message()
        response = await self.send(request)
        await stream.send_message(response)

    async def __rpc_multi_send(
        self, stream: "grpclib.server.Stream[MsgMultiSend, MsgMultiSendResponse]"
    ) -> None:
        request = await stream.recv_message()
        response = await self.multi_send(request)
        await stream.send_message(response)

    async def __rpc_update_params(
        self, stream: "grpclib.server.Stream[MsgUpdateParams, MsgUpdateParamsResponse]"
    ) -> None:
        request = await stream.recv_message()
        response = await self.update_params(request)
        await stream.send_message(response)

    async def __rpc_set_send_enabled(
        self,
        stream: "grpclib.server.Stream[MsgSetSendEnabled, MsgSetSendEnabledResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.set_send_enabled(request)
        await stream.send_message(response)

    def __mapping__(self) -> Dict[str, grpclib.const.Handler]:
        return {
            "/cosmos.bank.v1beta1.Msg/Send": grpclib.const.Handler(
                self.__rpc_send,
                grpclib.const.Cardinality.UNARY_UNARY,
                MsgSend,
                MsgSendResponse,
            ),
            "/cosmos.bank.v1beta1.Msg/MultiSend": grpclib.const.Handler(
                self.__rpc_multi_send,
                grpclib.const.Cardinality.UNARY_UNARY,
                MsgMultiSend,
                MsgMultiSendResponse,
            ),
            "/cosmos.bank.v1beta1.Msg/UpdateParams": grpclib.const.Handler(
                self.__rpc_update_params,
                grpclib.const.Cardinality.UNARY_UNARY,
                MsgUpdateParams,
                MsgUpdateParamsResponse,
            ),
            "/cosmos.bank.v1beta1.Msg/SetSendEnabled": grpclib.const.Handler(
                self.__rpc_set_send_enabled,
                grpclib.const.Cardinality.UNARY_UNARY,
                MsgSetSendEnabled,
                MsgSetSendEnabledResponse,
            ),
        }


class QueryBase(ServiceBase):

    async def balance(
        self, query_balance_request: "QueryBalanceRequest"
    ) -> "QueryBalanceResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def all_balances(
        self, query_all_balances_request: "QueryAllBalancesRequest"
    ) -> "QueryAllBalancesResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def spendable_balances(
        self, query_spendable_balances_request: "QuerySpendableBalancesRequest"
    ) -> "QuerySpendableBalancesResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def spendable_balance_by_denom(
        self,
        query_spendable_balance_by_denom_request: "QuerySpendableBalanceByDenomRequest",
    ) -> "QuerySpendableBalanceByDenomResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def total_supply(
        self, query_total_supply_request: "QueryTotalSupplyRequest"
    ) -> "QueryTotalSupplyResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def supply_of(
        self, query_supply_of_request: "QuerySupplyOfRequest"
    ) -> "QuerySupplyOfResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def params(
        self, query_params_request: "QueryParamsRequest"
    ) -> "QueryParamsResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def denom_metadata(
        self, query_denom_metadata_request: "QueryDenomMetadataRequest"
    ) -> "QueryDenomMetadataResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def denoms_metadata(
        self, query_denoms_metadata_request: "QueryDenomsMetadataRequest"
    ) -> "QueryDenomsMetadataResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def denom_owners(
        self, query_denom_owners_request: "QueryDenomOwnersRequest"
    ) -> "QueryDenomOwnersResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def send_enabled(
        self, query_send_enabled_request: "QuerySendEnabledRequest"
    ) -> "QuerySendEnabledResponse":
        raise grpclib.GRPCError(grpclib.const.Status.UNIMPLEMENTED)

    async def __rpc_balance(
        self, stream: "grpclib.server.Stream[QueryBalanceRequest, QueryBalanceResponse]"
    ) -> None:
        request = await stream.recv_message()
        response = await self.balance(request)
        await stream.send_message(response)

    async def __rpc_all_balances(
        self,
        stream: "grpclib.server.Stream[QueryAllBalancesRequest, QueryAllBalancesResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.all_balances(request)
        await stream.send_message(response)

    async def __rpc_spendable_balances(
        self,
        stream: "grpclib.server.Stream[QuerySpendableBalancesRequest, QuerySpendableBalancesResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.spendable_balances(request)
        await stream.send_message(response)

    async def __rpc_spendable_balance_by_denom(
        self,
        stream: "grpclib.server.Stream[QuerySpendableBalanceByDenomRequest, QuerySpendableBalanceByDenomResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.spendable_balance_by_denom(request)
        await stream.send_message(response)

    async def __rpc_total_supply(
        self,
        stream: "grpclib.server.Stream[QueryTotalSupplyRequest, QueryTotalSupplyResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.total_supply(request)
        await stream.send_message(response)

    async def __rpc_supply_of(
        self,
        stream: "grpclib.server.Stream[QuerySupplyOfRequest, QuerySupplyOfResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.supply_of(request)
        await stream.send_message(response)

    async def __rpc_params(
        self, stream: "grpclib.server.Stream[QueryParamsRequest, QueryParamsResponse]"
    ) -> None:
        request = await stream.recv_message()
        response = await self.params(request)
        await stream.send_message(response)

    async def __rpc_denom_metadata(
        self,
        stream: "grpclib.server.Stream[QueryDenomMetadataRequest, QueryDenomMetadataResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.denom_metadata(request)
        await stream.send_message(response)

    async def __rpc_denoms_metadata(
        self,
        stream: "grpclib.server.Stream[QueryDenomsMetadataRequest, QueryDenomsMetadataResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.denoms_metadata(request)
        await stream.send_message(response)

    async def __rpc_denom_owners(
        self,
        stream: "grpclib.server.Stream[QueryDenomOwnersRequest, QueryDenomOwnersResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.denom_owners(request)
        await stream.send_message(response)

    async def __rpc_send_enabled(
        self,
        stream: "grpclib.server.Stream[QuerySendEnabledRequest, QuerySendEnabledResponse]",
    ) -> None:
        request = await stream.recv_message()
        response = await self.send_enabled(request)
        await stream.send_message(response)

    def __mapping__(self) -> Dict[str, grpclib.const.Handler]:
        return {
            "/cosmos.bank.v1beta1.Query/Balance": grpclib.const.Handler(
                self.__rpc_balance,
                grpclib.const.Cardinality.UNARY_UNARY,
                QueryBalanceRequest,
                QueryBalanceResponse,
            ),
            "/cosmos.bank.v1beta1.Query/AllBalances": grpclib.const.Handler(
                self.__rpc_all_balances,
                grpclib.const.Cardinality.UNARY_UNARY,
                QueryAllBalancesRequest,
                QueryAllBalancesResponse,
            ),
            "/cosmos.bank.v1beta1.Query/SpendableBalances": grpclib.const.Handler(
                self.__rpc_spendable_balances,
                grpclib.const.Cardinality.UNARY_UNARY,
                QuerySpendableBalancesRequest,
                QuerySpendableBalancesResponse,
            ),
            "/cosmos.bank.v1beta1.Query/SpendableBalanceByDenom": grpclib.const.Handler(
                self.__rpc_spendable_balance_by_denom,
                grpclib.const.Cardinality.UNARY_UNARY,
                QuerySpendableBalanceByDenomRequest,
                QuerySpendableBalanceByDenomResponse,
            ),
            "/cosmos.bank.v1beta1.Query/TotalSupply": grpclib.const.Handler(
                self.__rpc_total_supply,
                grpclib.const.Cardinality.UNARY_UNARY,
                QueryTotalSupplyRequest,
                QueryTotalSupplyResponse,
            ),
            "/cosmos.bank.v1beta1.Query/SupplyOf": grpclib.const.Handler(
                self.__rpc_supply_of,
                grpclib.const.Cardinality.UNARY_UNARY,
                QuerySupplyOfRequest,
                QuerySupplyOfResponse,
            ),
            "/cosmos.bank.v1beta1.Query/Params": grpclib.const.Handler(
                self.__rpc_params,
                grpclib.const.Cardinality.UNARY_UNARY,
                QueryParamsRequest,
                QueryParamsResponse,
            ),
            "/cosmos.bank.v1beta1.Query/DenomMetadata": grpclib.const.Handler(
                self.__rpc_denom_metadata,
                grpclib.const.Cardinality.UNARY_UNARY,
                QueryDenomMetadataRequest,
                QueryDenomMetadataResponse,
            ),
            "/cosmos.bank.v1beta1.Query/DenomsMetadata": grpclib.const.Handler(
                self.__rpc_denoms_metadata,
                grpclib.const.Cardinality.UNARY_UNARY,
                QueryDenomsMetadataRequest,
                QueryDenomsMetadataResponse,
            ),
            "/cosmos.bank.v1beta1.Query/DenomOwners": grpclib.const.Handler(
                self.__rpc_denom_owners,
                grpclib.const.Cardinality.UNARY_UNARY,
                QueryDenomOwnersRequest,
                QueryDenomOwnersResponse,
            ),
            "/cosmos.bank.v1beta1.Query/SendEnabled": grpclib.const.Handler(
                self.__rpc_send_enabled,
                grpclib.const.Cardinality.UNARY_UNARY,
                QuerySendEnabledRequest,
                QuerySendEnabledResponse,
            ),
        }
