wget -q https://raw.githubusercontent.com/lightningnetwork/lnd/refs/heads/master/lnrpc/lightning.proto
wget -q https://raw.githubusercontent.com/lightningnetwork/lnd/refs/heads/master/lnrpc/routerrpc/router.proto
wget -q https://raw.githubusercontent.com/lightningnetwork/lnd/refs/heads/master/lnrpc/invoicesrpc/invoices.proto

uv run python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. --pyi_out=. lightning.proto
echo "generated lightning.proto"
uv run python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. --pyi_out=. router.proto
echo "generated router.proto"
uv run python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. --pyi_out=. invoices.proto
echo "generated invoices.proto"

rm lightning.proto router.proto invoices.proto
