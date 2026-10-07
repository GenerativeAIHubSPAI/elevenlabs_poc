"""Shared botocore settings for AWS clients.

Without explicit limits botocore waits up to 60 seconds to connect and another 60
per read, and retries on top of that, so a slow or unreachable endpoint could
stall a request -- or the static KB preload -- for several minutes.
"""

from botocore.config import Config


def aws_client_config(
    read_timeout: int = 30,
    max_pool_connections: int = 10,
) -> Config:
    return Config(
        connect_timeout=5,
        read_timeout=read_timeout,
        retries={"max_attempts": 3, "mode": "standard"},
        max_pool_connections=max_pool_connections,
    )
