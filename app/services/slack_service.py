import httpx


class SlackService:
    async def send_to_slack_response_url(self, response_url: str, response_text: str):
        # Send delayed response back to slack
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                payload = {
                    "text": response_text,
                    "response_type": "in_channel",  # or "ephemeral" for private
                }
                await client.post(response_url, json=payload)
        except Exception as e:
            print(f"Failed to send response to Slack: {e}")
