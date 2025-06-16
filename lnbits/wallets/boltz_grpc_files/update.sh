
wget https://raw.githubusercontent.com/BoltzExchange/boltz-client/refs/heads/master/pkg/boltzrpc/boltzrpc.proto -O boltz_grpc_files/boltzrpc.proto
poetry run python -m grpc_tools.protoc -I . --python_out=. --grpc_python_out=. --pyi_out=. boltz_grpc_files/boltzrpc.proto
