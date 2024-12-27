# Generated by the gRPC Python protocol compiler plugin. DO NOT EDIT!
"""Client and server classes corresponding to protobuf-defined services."""
import grpc
import warnings

import lnbits.wallets.lnd_grpc_files.invoices_pb2 as invoices__pb2
import lnbits.wallets.lnd_grpc_files.lightning_pb2 as lightning__pb2

GRPC_GENERATED_VERSION = '1.68.1'
GRPC_VERSION = grpc.__version__
_version_not_supported = False

try:
    from grpc._utilities import first_version_is_lower
    _version_not_supported = first_version_is_lower(GRPC_VERSION, GRPC_GENERATED_VERSION)
except ImportError:
    _version_not_supported = True

if _version_not_supported:
    raise RuntimeError(
        f'The grpc package installed is at version {GRPC_VERSION},'
        + f' but the generated code in invoices_pb2_grpc.py depends on'
        + f' grpcio>={GRPC_GENERATED_VERSION}.'
        + f' Please upgrade your grpc module to grpcio>={GRPC_GENERATED_VERSION}'
        + f' or downgrade your generated code using grpcio-tools<={GRPC_VERSION}.'
    )


class InvoicesStub(object):
    """
    Comments in this file will be directly parsed into the API
    Documentation as descriptions of the associated method, message, or field.
    These descriptions should go right above the definition of the object, and
    can be in either block or // comment format.

    An RPC method can be matched to an lncli command by placing a line in the
    beginning of the description in exactly the following format:
    lncli: `methodname`

    Failure to specify the exact name of the command will cause documentation
    generation to fail.

    More information on how exactly the gRPC documentation is generated from
    this proto file can be found here:
    https://github.com/lightninglabs/lightning-api

    Invoices is a service that can be used to create, accept, settle and cancel
    invoices.
    """

    def __init__(self, channel):
        """Constructor.

        Args:
            channel: A grpc.Channel.
        """
        self.SubscribeSingleInvoice = channel.unary_stream(
                '/invoicesrpc.Invoices/SubscribeSingleInvoice',
                request_serializer=invoices__pb2.SubscribeSingleInvoiceRequest.SerializeToString,
                response_deserializer=lightning__pb2.Invoice.FromString,
                _registered_method=True)
        self.CancelInvoice = channel.unary_unary(
                '/invoicesrpc.Invoices/CancelInvoice',
                request_serializer=invoices__pb2.CancelInvoiceMsg.SerializeToString,
                response_deserializer=invoices__pb2.CancelInvoiceResp.FromString,
                _registered_method=True)
        self.AddHoldInvoice = channel.unary_unary(
                '/invoicesrpc.Invoices/AddHoldInvoice',
                request_serializer=invoices__pb2.AddHoldInvoiceRequest.SerializeToString,
                response_deserializer=invoices__pb2.AddHoldInvoiceResp.FromString,
                _registered_method=True)
        self.SettleInvoice = channel.unary_unary(
                '/invoicesrpc.Invoices/SettleInvoice',
                request_serializer=invoices__pb2.SettleInvoiceMsg.SerializeToString,
                response_deserializer=invoices__pb2.SettleInvoiceResp.FromString,
                _registered_method=True)
        self.LookupInvoiceV2 = channel.unary_unary(
                '/invoicesrpc.Invoices/LookupInvoiceV2',
                request_serializer=invoices__pb2.LookupInvoiceMsg.SerializeToString,
                response_deserializer=lightning__pb2.Invoice.FromString,
                _registered_method=True)
        self.HtlcModifier = channel.stream_stream(
                '/invoicesrpc.Invoices/HtlcModifier',
                request_serializer=invoices__pb2.HtlcModifyResponse.SerializeToString,
                response_deserializer=invoices__pb2.HtlcModifyRequest.FromString,
                _registered_method=True)


class InvoicesServicer(object):
    """
    Comments in this file will be directly parsed into the API
    Documentation as descriptions of the associated method, message, or field.
    These descriptions should go right above the definition of the object, and
    can be in either block or // comment format.

    An RPC method can be matched to an lncli command by placing a line in the
    beginning of the description in exactly the following format:
    lncli: `methodname`

    Failure to specify the exact name of the command will cause documentation
    generation to fail.

    More information on how exactly the gRPC documentation is generated from
    this proto file can be found here:
    https://github.com/lightninglabs/lightning-api

    Invoices is a service that can be used to create, accept, settle and cancel
    invoices.
    """

    def SubscribeSingleInvoice(self, request, context):
        """
        SubscribeSingleInvoice returns a uni-directional stream (server -> client)
        to notify the client of state transitions of the specified invoice.
        Initially the current invoice state is always sent out.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def CancelInvoice(self, request, context):
        """lncli: `cancelinvoice`
        CancelInvoice cancels a currently open invoice. If the invoice is already
        canceled, this call will succeed. If the invoice is already settled, it will
        fail.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def AddHoldInvoice(self, request, context):
        """lncli: `addholdinvoice`
        AddHoldInvoice creates a hold invoice. It ties the invoice to the hash
        supplied in the request.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def SettleInvoice(self, request, context):
        """lncli: `settleinvoice`
        SettleInvoice settles an accepted invoice. If the invoice is already
        settled, this call will succeed.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def LookupInvoiceV2(self, request, context):
        """
        LookupInvoiceV2 attempts to look up at invoice. An invoice can be referenced
        using either its payment hash, payment address, or set ID.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')

    def HtlcModifier(self, request_iterator, context):
        """
        HtlcModifier is a bidirectional streaming RPC that allows a client to
        intercept and modify the HTLCs that attempt to settle the given invoice. The
        server will send HTLCs of invoices to the client and the client can modify
        some aspects of the HTLC in order to pass the invoice acceptance tests.
        """
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details('Method not implemented!')
        raise NotImplementedError('Method not implemented!')


def add_InvoicesServicer_to_server(servicer, server):
    rpc_method_handlers = {
            'SubscribeSingleInvoice': grpc.unary_stream_rpc_method_handler(
                    servicer.SubscribeSingleInvoice,
                    request_deserializer=invoices__pb2.SubscribeSingleInvoiceRequest.FromString,
                    response_serializer=lightning__pb2.Invoice.SerializeToString,
            ),
            'CancelInvoice': grpc.unary_unary_rpc_method_handler(
                    servicer.CancelInvoice,
                    request_deserializer=invoices__pb2.CancelInvoiceMsg.FromString,
                    response_serializer=invoices__pb2.CancelInvoiceResp.SerializeToString,
            ),
            'AddHoldInvoice': grpc.unary_unary_rpc_method_handler(
                    servicer.AddHoldInvoice,
                    request_deserializer=invoices__pb2.AddHoldInvoiceRequest.FromString,
                    response_serializer=invoices__pb2.AddHoldInvoiceResp.SerializeToString,
            ),
            'SettleInvoice': grpc.unary_unary_rpc_method_handler(
                    servicer.SettleInvoice,
                    request_deserializer=invoices__pb2.SettleInvoiceMsg.FromString,
                    response_serializer=invoices__pb2.SettleInvoiceResp.SerializeToString,
            ),
            'LookupInvoiceV2': grpc.unary_unary_rpc_method_handler(
                    servicer.LookupInvoiceV2,
                    request_deserializer=invoices__pb2.LookupInvoiceMsg.FromString,
                    response_serializer=lightning__pb2.Invoice.SerializeToString,
            ),
            'HtlcModifier': grpc.stream_stream_rpc_method_handler(
                    servicer.HtlcModifier,
                    request_deserializer=invoices__pb2.HtlcModifyResponse.FromString,
                    response_serializer=invoices__pb2.HtlcModifyRequest.SerializeToString,
            ),
    }
    generic_handler = grpc.method_handlers_generic_handler(
            'invoicesrpc.Invoices', rpc_method_handlers)
    server.add_generic_rpc_handlers((generic_handler,))
    server.add_registered_method_handlers('invoicesrpc.Invoices', rpc_method_handlers)


 # This class is part of an EXPERIMENTAL API.
class Invoices(object):
    """
    Comments in this file will be directly parsed into the API
    Documentation as descriptions of the associated method, message, or field.
    These descriptions should go right above the definition of the object, and
    can be in either block or // comment format.

    An RPC method can be matched to an lncli command by placing a line in the
    beginning of the description in exactly the following format:
    lncli: `methodname`

    Failure to specify the exact name of the command will cause documentation
    generation to fail.

    More information on how exactly the gRPC documentation is generated from
    this proto file can be found here:
    https://github.com/lightninglabs/lightning-api

    Invoices is a service that can be used to create, accept, settle and cancel
    invoices.
    """

    @staticmethod
    def SubscribeSingleInvoice(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_stream(
            request,
            target,
            '/invoicesrpc.Invoices/SubscribeSingleInvoice',
            invoices__pb2.SubscribeSingleInvoiceRequest.SerializeToString,
            lightning__pb2.Invoice.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def CancelInvoice(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/invoicesrpc.Invoices/CancelInvoice',
            invoices__pb2.CancelInvoiceMsg.SerializeToString,
            invoices__pb2.CancelInvoiceResp.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def AddHoldInvoice(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/invoicesrpc.Invoices/AddHoldInvoice',
            invoices__pb2.AddHoldInvoiceRequest.SerializeToString,
            invoices__pb2.AddHoldInvoiceResp.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def SettleInvoice(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/invoicesrpc.Invoices/SettleInvoice',
            invoices__pb2.SettleInvoiceMsg.SerializeToString,
            invoices__pb2.SettleInvoiceResp.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def LookupInvoiceV2(request,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.unary_unary(
            request,
            target,
            '/invoicesrpc.Invoices/LookupInvoiceV2',
            invoices__pb2.LookupInvoiceMsg.SerializeToString,
            lightning__pb2.Invoice.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)

    @staticmethod
    def HtlcModifier(request_iterator,
            target,
            options=(),
            channel_credentials=None,
            call_credentials=None,
            insecure=False,
            compression=None,
            wait_for_ready=None,
            timeout=None,
            metadata=None):
        return grpc.experimental.stream_stream(
            request_iterator,
            target,
            '/invoicesrpc.Invoices/HtlcModifier',
            invoices__pb2.HtlcModifyResponse.SerializeToString,
            invoices__pb2.HtlcModifyRequest.FromString,
            options,
            channel_credentials,
            insecure,
            call_credentials,
            compression,
            wait_for_ready,
            timeout,
            metadata,
            _registered_method=True)
