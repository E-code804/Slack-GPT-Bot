# Handles OpenAI API calls
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()

from typing import Dict, List, Optional


class OpenAIService:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    def summarize_pr(self, title: str, description: str, diff_content: str) -> Dict:
        """
        Summarize a PR using OpenAI, providing both file-level and overall summaries
        """
        try:
            # Create the prompt for OpenAI
            prompt = self._create_summarization_prompt(title, description, diff_content)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # or gpt-4o for better quality
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior software engineer reviewing pull requests. Analyze the code changes and provide clear, concise summaries.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1500,
                temperature=0.3,
            )

            # Return the response - do not worry about using parsing for now
            return response.choices[0].message.content
            # return self._parse_openai_response(response.choices[0].message.content)

        except Exception as e:
            return {
                "error": f"Failed to summarize PR: {str(e)}",
                "overall_summary": "Unable to generate summary",
                "file_summaries": [],
            }

    def _create_summarization_prompt(
        self, title: str, description: str, diff_content: str
    ) -> str:
        """Create a structured prompt for OpenAI"""
        return f"""
            Please analyze this pull request and provide a structured summary.

            **PR Title:** {title}

            **PR Description:** {description}

            **Code Changes (Git Diff):**
            ```diff
            {diff_content}
            ```

            Please provide your analysis in the following format:

            **OVERALL SUMMARY:**
            [A 1-2 sentence summary of what this PR accomplishes]

            **FILE CHANGES:**
            For each file that was modified, provide:
            - **filename**: Brief description of what changed in this file
            - **filename**: Brief description of what changed in this file

            **TECHNICAL DETAILS:**
            [Any important technical notes, potential impacts, or concerns]

            Focus on:
            1. What functionality was added, modified, or removed
            2. Bug fixes or improvements
            3. Refactoring or code organization changes
            4. New dependencies or configuration changes
            5. Potential impact on other parts of the system

            Keep descriptions clear and concise. Focus on the business logic and functional changes rather than minor formatting.
        """

    def _parse_openai_response(self, response_text: str) -> Dict:
        """Parse OpenAI response into structured format"""
        try:
            sections = response_text.split("**")

            overall_summary = ""
            file_summaries = []
            technical_details = ""

            current_section = None

            for section in sections:
                section = section.strip()
                if section.upper().startswith("OVERALL SUMMARY"):
                    current_section = "overall"
                elif section.upper().startswith("FILE CHANGES"):
                    current_section = "files"
                elif section.upper().startswith("TECHNICAL DETAILS"):
                    current_section = "technical"
                elif section and current_section:
                    if current_section == "overall":
                        overall_summary = section.strip()
                    elif current_section == "files":
                        file_summaries.extend(self._parse_file_changes(section))
                    elif current_section == "technical":
                        technical_details = section.strip()

            return {
                "overall_summary": overall_summary,
                "file_summaries": file_summaries,
                "technical_details": technical_details,
                "raw_response": response_text,
            }

        except Exception as e:
            # Fallback if parsing fails
            return {
                "overall_summary": response_text[:200] + "...",
                "file_summaries": [],
                "technical_details": "",
                "raw_response": response_text,
                "parse_error": str(e),
            }

    def _parse_file_changes(self, file_section: str) -> List[Dict]:
        """Parse file changes from the response"""
        file_summaries = []
        lines = file_section.split("\n")

        for line in lines:
            line = line.strip()
            if line.startswith("- ") and ":" in line:
                # Format: - filename: description
                parts = line[2:].split(":", 1)
                if len(parts) == 2:
                    filename = parts[0].strip()
                    description = parts[1].strip()
                    file_summaries.append(
                        {"filename": filename, "description": description}
                    )

        return file_summaries

    def format_summary_for_slack(self, summary: Dict) -> str:
        """Format the summary for Slack display"""
        if "error" in summary:
            return f"❌ {summary['error']}"

        slack_message = f"🔍 **PR Summary**\n\n"
        slack_message += f"📋 **Overview:** {summary['overall_summary']}\n\n"

        if summary["file_summaries"]:
            slack_message += "📁 **File Changes:**\n"
            for file_change in summary["file_summaries"]:
                slack_message += (
                    f"• `{file_change['filename']}`: {file_change['description']}\n"
                )
            slack_message += "\n"

        if summary["technical_details"]:
            slack_message += f"⚙️ **Technical Notes:** {summary['technical_details']}\n"

        return slack_message
