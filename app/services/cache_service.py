from utils.redis_client import redis_client
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)
TTL = 3600  # 1 hour


async def set_pr_cache(pr_url: str, pr_dict: Dict[str, Any]) -> bool:
    try:
        pipe = redis_client.pipeline()
        pipe.hset(name=pr_url, mapping=pr_dict)
        pipe.expire(name=pr_url, time=TTL)
        await pipe.execute()

        print(f"Successfully cached PR data for: {pr_url}")
        # logger.info(f"Successfully cached PR data for: {pr_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to cache PR data for {pr_url}: {e}")
        return False


async def update_pr_state_cache(pr_url: str, new_state: str) -> Dict[str, Any]:
    try:
        exists = await redis_client.exists(pr_url)

        if not exists:
            print(f"No existing cache for: {pr_url}")
            return {
                "status": "ignored",
                "message": "No existing cache entry found",
                "data": {"pr_url": pr_url},
            }

        await redis_client.hset(name=pr_url, key="state", value=new_state)
        print(f"Successfully updated state to '{new_state}' for: {pr_url}")
        return {
            "status": "success",
            "message": f"Cache updated to state '{new_state}'",
            "data": {"pr_url": pr_url, "new_state": new_state},
        }
    except Exception as e:
        # logger.error(f"Failed to update state for {pr_url}: {e}")
        print(f"Failed to update state for {pr_url}: {e}")
        return {
            "status": "error",
            "message": f"Cache update failed: {str(e)}",
            "data": {"pr_url": pr_url},
        }


async def update_pr_cache_fields(pr_url: str, updates: Dict[str, Any]) -> bool:
    """Update multiple fields in the cached PR data"""
    try:
        await redis_client.hset(name=pr_url, mapping=updates)

        print(f"Successfully updated fields {list(updates.keys())} for: {pr_url}")
        return True
    except Exception as e:
        logger.error(f"Failed to update fields for {pr_url}: {e}")
        return False


async def get_pr_cache(pr_url: str) -> Optional[Dict[str, Any]]:
    try:
        pr_cache = await redis_client.hgetall(name=pr_url)

        if not pr_cache:
            print(f"Cache MISS for: {pr_url}")
            # logger.info(f"Cache MISS for: {pr_url}")
            return None

        print(f"Cache HIT for: {pr_url}")
        # logger.info(f"Cache HIT for: {pr_url}")
        return pr_cache

    except Exception as e:
        print(f"Failed to retrieve cache for {pr_url}: {e}")
        # logger.error(f"Failed to retrieve cache for {pr_url}: {e}")
        return None


async def del_pr_cache(pr_url: str) -> bool:
    try:
        deleted_count = await redis_client.delete(pr_url)

        if deleted_count > 0:
            print(f"Successfully deleted cache for: {pr_url}")
            # logger.info(f"Successfully deleted cache for: {pr_url}")
            return True
        else:
            print(f"No cache found to delete for: {pr_url}")
            # logger.warning(f"No cache found to delete for: {pr_url}")
            return False

    except Exception as e:
        print(f"Failed to delete cache for {pr_url}: {e}")
        # logger.error(f"Failed to delete cache for {pr_url}: {e}")
        return False
