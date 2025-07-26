from utils.redis_client import redis_client

TTL = 3600  # 1 hour


async def set_pr_cache(pr_url: str, pr_dict):
    await redis_client.hset(name=pr_url, mapping=pr_dict)
    await redis_client.expire(name=pr_url, time=TTL)


async def get_pr_cache(pr_url: str):
    pr_cache = await redis_client.hgetall(name=pr_url)
    return pr_cache
