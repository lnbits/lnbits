
wget https://raw.githubusercontent.com/BoltzExchange/boltz-client/master/boltzrpc/boltzrpc.proto -O lnbits/wallets/boltz_grpc_files/boltzrpc.proto
poetry run python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. --pyi_out=. lnbits/wallets/boltz_grpc_files/boltzrpc.proto
