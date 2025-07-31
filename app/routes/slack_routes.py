from fastapi import APIRouter, Request, Form, BackgroundTasks
from fastapi.responses import PlainTextResponse

from services.pr_service import PRService

router = APIRouter()
pr_service = PRService()


# For PR link summarization. Validate, queue tasks, and send immediate response.
@router.post("/summarizepr")
async def handle_summarizepr(
    request: Request,
    text: str = Form(...),
    response_url: str = Form(...),  # Provided by Slack.
    background_tasks: BackgroundTasks = BackgroundTasks(),
):
    if "github.com" not in text or "/pull/" not in text:
        return PlainTextResponse(
            "Please provide a valid GitHub PR link.", status_code=200
        )

    print(response_url)

    background_tasks.add_task(pr_service.process_pr_summary, text, response_url)
    immediate_response = (
        "🔄 Analyzing PR... This may take a moment. I'll update you shortly!"
    )

    return PlainTextResponse(immediate_response, status_code=200)
