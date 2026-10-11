"""Draft developer replies to negative reviews (a human edits and posts them).

Claude drafts when ANTHROPIC_API_KEY is set; otherwise a category template is used.
"""
import os

from pipeline.taxonomy import label

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-opus-5-5")
SUPPORT_EMAIL = os.getenv("SUPPORT_EMAIL", "app@moveinsync.com")

TEMPLATES = {
    "login_access": "Sorry you're having trouble signing in. Please email {email} with your registered phone/email "
                    "and company name so we can check OTP delivery for your account right away.",
    "app_crash_performance": "Sorry the app isn't opening reliably for you. Please share your phone model and Android "
                             "version at {email} - we're actively fixing device-specific issues in the next update.",
    "tracking_eta": "Thanks for flagging the tracking/ETA issue - accurate live tracking matters most right before "
                    "pickup. Please share your trip date and route at {email} so we can investigate.",
    "forced_prompts": "Thanks for the honest feedback on the prompts. We're making trip feedback skippable and "
                      "reducing pop-ups. Please share anything else that slows you down at {email}.",
}
DEFAULT = ("Sorry about this experience. Please email {email} with your company name, trip date and details "
           "so we can look into it with your transport team and get back to you.")

PROMPT = """You write short public replies from the MoveInSync app team to Google Play reviews.
Rules: 2-3 sentences, under 350 characters (Play Store limit), warm and specific to what the user said,
no generic 'we value your feedback', never blame the user, never promise dates, never ask for OTPs/passwords.
If the issue is with a cab/driver/route, say we'll take it up with their company's transport team.
End by inviting them to email {email} with trip/company details. Reply in the review's language
(English if mixed Hinglish is unclear). Output only the reply text."""


def draft(text: str, stars: int, category: str) -> tuple[str, str]:
    """Returns (reply, engine)."""
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            client = anthropic.Anthropic()
            resp = client.messages.create(
                model=CLAUDE_MODEL,
                max_tokens=2000,
                system=PROMPT.format(email=SUPPORT_EMAIL),
                output_config={"effort": "low"},
                messages=[{"role": "user", "content": f"Stars: {stars}\nIssue category: {label(category)}\n"
                                                      f"Review: {text}"}],
            )
            if resp.stop_reason != "refusal":
                reply = next((b.text for b in resp.content if b.type == "text"), "").strip()
                if reply:
                    return reply[:350], "claude"
        except anthropic.APIError as e:
            print(f"[replies] Claude draft failed, using template: {e}")
    return TEMPLATES.get(category, DEFAULT).format(email=SUPPORT_EMAIL), "template"
