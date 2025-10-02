#!/usr/bin/env python3
"""
Test: Read wallet shares via API
This test retrieves and displays wallet shares using the REST API
"""

import asyncio
import os
import httpx
from loguru import logger

# Load config from .env.local
def load_config():
    config = {}
    env_path = os.path.join(os.path.dirname(__file__), '../../.env.local')

    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    config[key.strip()] = value.strip()

    return {
        'base_url': config.get('TEST_LNBITS_URL', os.getenv('TEST_LNBITS_URL')),
        'admin_key': config.get('TEST_ADMIN_API_KEY', os.getenv('TEST_ADMIN_API_KEY')),
        'wallet_id': config.get('TEST_WALLET_ID', os.getenv('TEST_WALLET_ID'))
    }

async def test_read_shares():
    """Test reading wallet shares"""
    config = load_config()

    if not config['admin_key']:
        logger.error("❌ TEST_ADMIN_API_KEY must be set in .env.local")
        return False

    if not config['wallet_id']:
        logger.error("❌ TEST_WALLET_ID must be set in .env.local")
        return False

    logger.info("🚀 Starting read wallet shares API test...")
    logger.info(f"📍 Base URL: {config['base_url']}")
    logger.info(f"📍 Wallet ID: {config['wallet_id']}")

    async with httpx.AsyncClient() as client:
        # Get wallet shares
        logger.info("📝 Fetching wallet shares...")
        response = await client.get(
            f"{config['base_url']}/api/v1/wallet_shares/{config['wallet_id']}",
            headers={'X-Api-Key': config['admin_key']}
        )

        if response.status_code != 200:
            logger.error(f"❌ Failed to get shares: {response.status_code}")
            logger.error(f"   Response: {response.text}")
            return False

        shares = response.json()

        if not isinstance(shares, list):
            logger.error(f"❌ Unexpected response format: {type(shares)}")
            return False

        logger.info(f"📊 Found {len(shares)} share(s)")

        if len(shares) > 0:
            logger.info("\n📄 Share Details:")
            for i, share in enumerate(shares, 1):
                logger.info(f"\n  Share {i}:")
                logger.info(f"    ID: {share['id']}")
                logger.info(f"    User: {share.get('username', share['user_id'])}")
                logger.info(f"    Permissions: {share['permissions']}")
                logger.info(f"    Shared by: {share['shared_by']}")
                logger.info(f"    Shared at: {share['shared_at']}")
                logger.info(f"    Accepted: {share['accepted']}")

                # Decode permissions
                perms = []
                if share['permissions'] & 1: perms.append('VIEW')
                if share['permissions'] & 2: perms.append('CREATE_INVOICE')
                if share['permissions'] & 4: perms.append('PAY_INVOICE')
                if share['permissions'] & 8: perms.append('MANAGE_SHARES')
                logger.info(f"    Permission flags: {', '.join(perms)}")
        else:
            logger.info("ℹ️  No shares found for this wallet")

        logger.info("\n🎉 SUCCESS! Shares read successfully!")
        return True

if __name__ == '__main__':
    success = asyncio.run(test_read_shares())
    exit(0 if success else 1)
