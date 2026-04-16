import json
import logging
import os
import re
from urllib.parse import urlsplit

import requests
import time
from django.conf import settings
from django.db.models import Avg, Count, Max, Min, Q
from django.urls import NoReverseMatch, Resolver404, resolve, reverse

from jobs.models import Bid, Category, Job, Reviews, Skill

from .models import AssistantChat, CustomUser, DirectHire, Message, Notification

logger = logging.getLogger(__name__)


def _safe_reverse(name, **kwargs):
    try:
        return reverse(name, kwargs=kwargs or None)
    except NoReverseMatch:
        return f"{settings.SITE_URL.rstrip('/')}/home/"


def _normalize_prompt(prompt):
    return " ".join(str(prompt or "").strip().lower().split())


def _clean_path(path):
    raw = str(path or "").strip() or "/home/"
    parsed = urlsplit(raw)
    candidate = parsed.path or raw
    return candidate if candidate.startswith("/") else f"/{candidate}"


def _history_for_model(user):
    if not user or not getattr(user, "is_authenticated", False):
        return []
    return list(
        AssistantChat.objects.filter(user=user)
        .order_by("-created_at")
        .values("role", "content", "meta")[:16]
    )[::-1]


def _recent_history_summary(history):
    recent = history[-5:] if history else []
    return " | ".join(
        f"{item.get('role')}: {item.get('content')}"
        for item in recent
        if item.get("content")
    )


def _recent_user_prompts(history, limit=4):
    items = [item.get("content", "") for item in history if item.get("role") == "user" and item.get("content")]
    return items[-limit:]


def _last_user_prompt(history):
    prompts = _recent_user_prompts(history, limit=1)
    return prompts[-1] if prompts else ""


def _topic_from_text(text):
    lowered = _normalize_prompt(text)
    if any(term in lowered for term in ("profile", "credibility", "bio", "specialization", "portfolio")):
        return "profile"
    if any(term in lowered for term in ("budget", "quote price", "client's budget", "clients budget")) and any(
        term in lowered for term in ("bid", "client", "quote", "budget")
    ):
        return "bidding"
    if any(term in lowered for term in ("how many", "platform", "artisans", "fundis", "clients", "jobs")):
        return "platform_counts"
    if any(term in lowered for term in ("bid", "proposal", "quote")):
        return "bidding"
    if any(term in lowered for term in ("job post", "post job", "job brief", "hire")):
        return "job_posting"
    if any(term in lowered for term in ("message", "chat", "conversation", "inbox")):
        return "messages"
    if any(term in lowered for term in ("review", "rating", "score", "credibility")):
        return "reviews"
    if any(term in lowered for term in ("privacy", "private", "data")):
        return "privacy"
    return ""


def _resolve_follow_up_prompt(prompt, history):
    lowered = _normalize_prompt(prompt)
    softened = lowered.replace("?", "").replace(".", "").strip()
    last_prompt = _last_user_prompt(history)
    last_topic = _topic_from_text(last_prompt)

    if not last_prompt:
        return prompt

    if softened in {"what about clients", "and clients", "clients"} and last_topic == "platform_counts":
        return "how many clients are on the platform?"
    if softened in {"what about jobs", "and jobs", "jobs"} and last_topic == "platform_counts":
        return "how many jobs are on the platform?"
    if softened in {"what about reviews", "reviews", "and reviews"} and last_topic == "profile":
        return "how can I improve my reviews and credibility on my profile?"
    if softened in {"how", "how do i fix that", "how do i improve that", "what should i change"} and last_topic == "profile":
        return "help me improve my profile with specific next steps"
    if softened in {"what about budget", "what about the budget", "and budget", "budget"} and last_topic == "bidding":
        return "how should i set my bid amount against the client's budget?"
    if softened in {"and then", "what next", "what should i do next", "where do i start"} and last_topic:
        return f"{last_prompt} what should i do next?"
    if softened.startswith("what about ") and last_topic == "platform_counts":
        return f"how many {softened.replace('what about ', '').strip()} are on the platform?"
    return prompt


def _page_snapshot(path):
    current = _clean_path(path)
    route_name = ""
    page_label = "current page"
    try:
        match = resolve(current)
        route_name = match.view_name or ""
    except Resolver404:
        route_name = ""

    labels = {
        "home": "home overview",
        "job_list": "job board",
        "post_job": "job posting page",
        "job_detail": "job workspace",
        "artisan_bids": "artisan bids",
        "category_list": "category explorer",
        "users:dashboard": "dashboard",
        "users:notifications": "messages and notifications",
        "users:profile": "profile",
        "users:settings": "settings and security",
        "users:verify_email": "email verification",
        "users:verify_phone": "phone verification",
        "users:two_factor_setup": "two-factor setup",
        "users:two_factor_manage": "two-factor management",
    }
    if route_name in labels:
        page_label = labels[route_name]
    elif current in {"/home/", "/"}:
        page_label = "home overview"
    elif current.startswith("/job/"):
        page_label = "job workspace"
    elif current.startswith("/accounts/messages/"):
        page_label = "conversation workspace"
    elif current.startswith("/accounts/artisan/") or current.startswith("/accounts/artisans/"):
        page_label = "artisan discovery"
    elif current.startswith("/accounts/"):
        page_label = "account workspace"
    elif current.startswith("/jobs/"):
        page_label = "job board"

    return {
        "path": current,
        "route_name": route_name,
        "label": page_label,
    }


def _recent_platform_items(user, role):
    items = []
    if role == "client":
        recent_jobs = (
            Job.objects.filter(client=user)
            .select_related("category")
            .order_by("-updated_at")[:4]
        )
        for job in recent_jobs:
            items.append(
                {
                    "type": "job",
                    "title": job.title,
                    "subtitle": f"{job.get_status_display()} in {job.location}",
                    "url": _safe_reverse("job_detail", job_id=job.id),
                    "icon": "briefcase",
                }
            )
    elif role == "artisan" and hasattr(user, "artisan_profile"):
        recent_bids = (
            Bid.objects.filter(artisan=user.artisan_profile)
            .select_related("job", "job__category")
            .order_by("-updated_at")[:4]
        )
        for bid in recent_bids:
            items.append(
                {
                    "type": "bid",
                    "title": bid.job.title,
                    "subtitle": f"Bid {bid.get_status_display().lower()} at KES {bid.amount}",
                    "url": _safe_reverse("artisan_bid_detail", bid_id=bid.id),
                    "icon": "send-check",
                }
            )
    return items


def _extract_money_amount(prompt):
    match = re.search(r"(?:kes|ksh|kshs|shs)?\s*([0-9][0-9,]{2,})", str(prompt or ""), re.I)
    if not match:
        return None
    try:
        return int(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _build_user_snapshot(user):
    if not user or not getattr(user, "is_authenticated", False):
        return {
            "is_authenticated": False,
            "role": "guest",
            "headline": "Guest visitor exploring FundiConnect.",
            "categories": list(Category.objects.order_by("name").values_list("name", flat=True)[:10]),
        }

    snapshot = {
        "is_authenticated": True,
        "display_name": user.display_name,
        "username": user.username,
        "role": "artisan" if user.is_artisan else "client",
        "email_verified": bool(getattr(user, "email_verified", False)),
        "phone_verified": bool(getattr(user, "phone_verified", False)),
        "profile_completed": bool(getattr(user, "profile_completed", False)),
        "two_factor_enabled": bool(getattr(user, "two_factor_enabled", False)),
        "unread_messages": Message.objects.filter(conversation__participants=user, is_read=False)
        .exclude(sender=user)
        .count(),
        "notifications": Notification.objects.filter(user=user, is_read=False).count(),
    }

    if user.is_client:
        jobs = Job.objects.filter(client=user)
        snapshot.update(
            {
                "open_jobs": jobs.filter(status="open").count(),
                "draft_jobs": jobs.filter(status="draft").count(),
                "active_jobs": jobs.filter(status="in_progress").count(),
                "completed_jobs": jobs.filter(status="completed").count(),
                "closed_jobs": jobs.filter(status="closed").count(),
                "pending_bids": Bid.objects.filter(job__client=user, status="pending").count(),
                "accepted_bids": Bid.objects.filter(job__client=user, status="accepted").count(),
                "pending_direct_hires": DirectHire.objects.filter(client=user, status="pending").count(),
                "recent_jobs": list(jobs.order_by("-updated_at").values_list("title", flat=True)[:5]),
            }
        )
        if hasattr(user, "client_profile"):
            snapshot["location"] = user.client_profile.city or user.client_profile.address

    elif user.is_artisan and hasattr(user, "artisan_profile"):
        artisan_profile = user.artisan_profile
        bids = Bid.objects.filter(artisan=artisan_profile)
        assigned_jobs = Job.objects.filter(artisan=user)
        matching_jobs = Job.objects.filter(status="open", category__slug=artisan_profile.category)
        budget_stats = matching_jobs.aggregate(avg=Avg("budget"), low=Min("budget"), high=Max("budget"))
        snapshot.update(
            {
                "category": artisan_profile.get_category_display(),
                "specialization": artisan_profile.specialization,
                "location": artisan_profile.location,
                "availability": artisan_profile.get_availability_display(),
                "credibility_score": artisan_profile.credibility_score,
                "average_rating": round(float(artisan_profile.average_rating() or 0), 1),
                "review_count": artisan_profile.total_reviews(),
                "pending_bids": bids.filter(status="pending").count(),
                "accepted_bids": bids.filter(status="accepted").count(),
                "rejected_bids": bids.filter(status="rejected").count(),
                "active_jobs": assigned_jobs.filter(status="in_progress").count(),
                "completed_jobs": assigned_jobs.filter(status="completed").count(),
                "pending_direct_hires": DirectHire.objects.filter(artisan=user, status="pending").count(),
                "matching_open_jobs": matching_jobs.count(),
                "market_budget_avg": round(float(budget_stats["avg"] or 0), 2),
                "market_budget_low": round(float(budget_stats["low"] or 0), 2),
                "market_budget_high": round(float(budget_stats["high"] or 0), 2),
            }
        )

    snapshot["recent_items"] = _recent_platform_items(user, snapshot["role"])
    return snapshot


def _build_platform_snapshot():
    category_counts = list(
        Category.objects.annotate(job_count=Count("job"))
        .order_by("-job_count", "name")
        .values("name", "slug", "icon", "job_count")[:8]
    )
    return {
        "open_jobs": Job.objects.filter(status="open").count(),
        "in_progress_jobs": Job.objects.filter(status="in_progress").count(),
        "completed_jobs": Job.objects.filter(status="completed").count(),
        "active_artisans": CustomUser.objects.filter(user_type="artisan").count(),
        "active_clients": CustomUser.objects.filter(user_type="client").count(),
        "categories": category_counts,
        "top_skills": list(Skill.objects.order_by("name").values_list("name", flat=True)[:14]),
        "average_rating": round(float(Reviews.objects.aggregate(avg=Avg("rating"))["avg"] or 0), 1),
    }


def _build_facts(snapshot, platform_snapshot, page_snapshot):
    return {
        "role": snapshot.get("role"),
        "email_verified": snapshot.get("email_verified"),
        "phone_verified": snapshot.get("phone_verified"),
        "profile_completed": snapshot.get("profile_completed"),
        "two_factor_enabled": snapshot.get("two_factor_enabled"),
        "unread_messages": snapshot.get("unread_messages"),
        "notifications": snapshot.get("notifications"),
        "open_jobs": platform_snapshot.get("open_jobs"),
        "in_progress_jobs": platform_snapshot.get("in_progress_jobs"),
        "completed_jobs": platform_snapshot.get("completed_jobs"),
        "active_artisans": platform_snapshot.get("active_artisans"),
        "active_clients": platform_snapshot.get("active_clients"),
        "page": page_snapshot.get("label"),
    }


def _suggest(label, url_name=None, url=None, icon="arrow-right-circle", reason=""):
    target = url or (_safe_reverse(url_name) if url_name else None)
    return {
        "label": label,
        "url": target,
        "icon": icon,
        "reason": reason,
    }


def _intent_flags(prompt):
    lowered = _normalize_prompt(prompt)
    return {
        "greeting": lowered in {"hi", "hello", "hey", "good morning", "good afternoon", "good evening"},
        "follow_up": lowered in {"yes", "yeah", "yep", "continue", "ok", "okay", "go on", "show me"},
        "stuck": any(phrase in lowered for phrase in ("i am stuck", "im stuck", "stuck", "help me", "what should i do", "where do i start")),
        "platform_counts": any(
            phrase in lowered
            for phrase in ("how many artisans", "how many fundis", "how many clients", "how many jobs", "platform stats", "on the platform")
        ),
        "job_posting": any(phrase in lowered for phrase in ("post job", "create job", "write job", "job brief", "hire fundi", "hire artisan")),
        "bidding": any(phrase in lowered for phrase in ("bid", "proposal", "quote", "apply for job", "write my bid")),
        "messages": any(phrase in lowered for phrase in ("message", "chat", "conversation", "inbox", "reply")),
        "dashboard": any(phrase in lowered for phrase in ("dashboard", "summary", "status", "overview", "what next")),
        "reviews": any(phrase in lowered for phrase in ("review", "rating", "credibility", "trust", "score")),
        "profile": any(phrase in lowered for phrase in ("profile", "settings", "verification", "2fa", "password", "security")),
        "categories": any(phrase in lowered for phrase in ("category", "categories", "skill", "skills", "service")),
        "budget": any(phrase in lowered for phrase in ("budget", "pricing", "price", "cost")),
        "direct_hire": any(phrase in lowered for phrase in ("direct hire", "invite artisan", "hire directly")),
        "rewrite": any(phrase in lowered for phrase in ("rewrite", "improve", "polish", "draft", "compose")),
    }


def _platform_count_response(prompt, platform_snapshot):
    lowered = _normalize_prompt(prompt)
    # Enhanced: if the user asks about completed jobs/artisans who completed jobs, return richer info
    if "completed" in lowered and ("artisan" in lowered or "fundi" in lowered or "who" in lowered or "which" in lowered):
        # Find completed jobs and artisans who completed them
        try:
            completed_jobs = Job.objects.filter(status="completed").select_related("artisan")[:8]
            artisans = []
            platform_items = []
            for job in completed_jobs:
                art = getattr(job, "artisan", None)
                if art and art.display_name:
                    name = art.display_name
                elif art and getattr(art, "username", None):
                    name = art.username
                else:
                    name = "Unknown artisan"
                if name not in artisans:
                    artisans.append(name)
                platform_items.append(
                    {
                        "type": "job",
                        "title": job.title,
                        "subtitle": f"Completed by {name}",
                        "url": _safe_reverse("job_detail", job_id=job.id),
                        "icon": "briefcase-check",
                    }
                )
            count_text = f"There are currently {len(artisans)} artisans who have completed jobs on FundiConnect."
            if artisans:
                names = ", ".join(artisans[:6])
                text = f"{count_text} Recent artisans who completed jobs include: {names}."
            else:
                text = f"{count_text} No recent completed-job artisans could be identified."
            return {
                "text": text,
                "suggestions": [
                    _suggest("Browse completed jobs", "job_list", icon="briefcase-check", reason="See finished work."),
                    _suggest("Browse artisans", "users:artisans", icon="people", reason="Explore artisans who complete work."),
                ],
                "highlights": [
                    f"{len(completed_jobs)} recently completed jobs",
                    f"{len(artisans)} artisans with completed jobs",
                ],
                "platform_items": platform_items,
            }
        except Exception:
            # Fall back to the simple completed jobs summary if DB query fails
            logger.exception("Error while building completed-jobs summary")
            text = f"There are currently {platform_snapshot['active_artisans']} artisans on FundiConnect."
            return {
                "text": text,
                "suggestions": [
                    _suggest("Browse jobs", "job_list", icon="briefcase", reason="See live opportunities."),
                    _suggest("Browse artisans", "users:artisans", icon="people", reason="Explore current specialists."),
                ],
                "highlights": [
                    f"{platform_snapshot['open_jobs']} open jobs",
                    f"{platform_snapshot['active_artisans']} artisans",
                    f"{platform_snapshot['active_clients']} clients",
                ],
                "platform_items": [],
            }
    if "artisan" in lowered or "fundi" in lowered:
        text = f"There are currently {platform_snapshot['active_artisans']} artisans on FundiConnect."
    elif "client" in lowered:
        text = f"There are currently {platform_snapshot['active_clients']} clients on FundiConnect."
    elif "in progress" in lowered:
        text = f"There are currently {platform_snapshot['in_progress_jobs']} jobs in progress on FundiConnect."
    elif "completed" in lowered:
        text = f"There are currently {platform_snapshot['completed_jobs']} completed jobs recorded on FundiConnect."
    else:
        text = (
            f"Right now FundiConnect has {platform_snapshot['open_jobs']} open jobs, "
            f"{platform_snapshot['active_artisans']} artisans, and {platform_snapshot['active_clients']} clients."
        )
    return {
        "text": text,
        "suggestions": [
            _suggest("Browse jobs", "job_list", icon="briefcase", reason="See live opportunities."),
            _suggest("Browse artisans", "users:artisans", icon="people", reason="Explore current specialists."),
        ],
        "highlights": [
            f"{platform_snapshot['open_jobs']} open jobs",
            f"{platform_snapshot['active_artisans']} artisans",
            f"{platform_snapshot['active_clients']} clients",
        ],
    }


def _artisan_profile_response(snapshot):
    gaps = []
    if not snapshot.get("phone_verified"):
        gaps.append("verify your phone number so your account looks more trustworthy")
    if not snapshot.get("two_factor_enabled"):
        gaps.append("turn on two-factor authentication to strengthen account security")
    if not snapshot.get("review_count"):
        gaps.append("complete a few jobs and request your first reviews to start building social proof")
    if snapshot.get("credibility_score", 0) < 40:
        gaps.append("add sharper portfolio work and keep your specialization very specific")

    specialization = snapshot.get("specialization") or "your trade focus"
    category = snapshot.get("category") or "your category"
    location = snapshot.get("location") or "your service area"
    text = (
        f"To improve your profile quickly, tighten {specialization.lower()} under {category.lower()}, keep your location set to {location}, "
        "and make sure clients can immediately see what you do best. "
    )
    if gaps:
        text += "Your next best fixes are to " + ", ".join(gaps[:3]) + "."
    else:
        text += "Your core setup looks solid, so the next lift comes from stronger reviews, faster replies, and more precise bid wording."
    return {
        "text": text,
        "suggestions": [
            _suggest("Edit profile", "users:profile", icon="person-badge", reason="Improve public-facing details."),
            _suggest("Verify phone", "users:verify_phone", icon="phone", reason="Complete trust signals."),
            _suggest("Set up 2FA", "users:two_factor_setup", icon="shield-lock", reason="Strengthen security."),
        ],
        "highlights": [
            f"Credibility score {snapshot.get('credibility_score', 0)}",
            f"{snapshot.get('review_count', 0)} reviews so far",
            f"Phone verified: {snapshot.get('phone_verified', False)}",
        ],
    }


def _client_profile_response(snapshot):
    text = (
        "To improve your client profile, make sure your contact details are current, verify any pending security steps, "
        "and keep your job briefs clear enough that artisans can price them confidently."
    )
    return {
        "text": text,
        "suggestions": [
            _suggest("Open profile", "users:profile", icon="person-circle", reason="Review your profile details."),
            _suggest("Open settings", "users:settings", icon="gear", reason="Complete security and verification."),
            _suggest("Post a job", "post_job", icon="briefcase-fill", reason="Create a clearer brief."),
        ],
        "highlights": [
            f"Email verified: {snapshot.get('email_verified', False)}",
            f"Phone verified: {snapshot.get('phone_verified', False)}",
            f"{snapshot.get('active_jobs', 0)} active jobs",
        ],
    }


def _stuck_response(snapshot):
    if snapshot.get("role") == "artisan":
        steps = []
        if snapshot.get("pending_bids", 0) == 0:
            steps.append("browse fresh jobs and submit 3 to 5 targeted bids")
        if snapshot.get("review_count", 0) == 0:
            steps.append("finish one small job and ask for your first review")
        if not snapshot.get("phone_verified"):
            steps.append("verify your phone so your account looks more complete")
        if not steps:
            steps = ["open your dashboard", "reply to active clients", "follow up on accepted work"]
        text = "You are not blocked, you just need the next concrete move. Right now I’d focus on " + ", then ".join(steps[:3]) + "."
        suggestions = [
            _suggest("Browse jobs", "job_list", icon="search-heart", reason="Find matches to bid on."),
            _suggest("Open my bids", "artisan_bids", icon="send-check", reason="Review proposal progress."),
            _suggest("Edit profile", "users:profile", icon="person-badge", reason="Improve trust and conversions."),
        ]
    elif snapshot.get("role") == "client":
        steps = []
        if snapshot.get("open_jobs", 0) == 0 and snapshot.get("active_jobs", 0) == 0:
            steps.append("post a clear job with location, budget, and timing")
        if snapshot.get("pending_bids", 0) > 0:
            steps.append("compare your pending bids and shortlist the clearest one")
        if snapshot.get("unread_messages", 0) > 0:
            steps.append("reply to unread artisan messages to keep hiring moving")
        if not steps:
            steps = ["open your dashboard", "review live jobs", "message the best-fit artisan"]
        text = "You are close to progress. The best next move is to " + ", then ".join(steps[:3]) + "."
        suggestions = [
            _suggest("Post a job", "post_job", icon="briefcase-fill", reason="Create the next opportunity."),
            _suggest("Open dashboard", "users:dashboard", icon="speedometer2", reason="Review current work."),
            _suggest("Open inbox", "users:notifications", icon="chat-dots", reason="Continue live conversations."),
        ]
    else:
        text = "A good first step is to browse current jobs or categories, then create an account once you know whether you’ll hire or offer services."
        suggestions = [
            _suggest("Browse jobs", "job_list", icon="briefcase", reason="See what is live now."),
            _suggest("Browse categories", "category_list", icon="grid", reason="Explore the marketplace."),
            _suggest("Create account", "users:register", icon="person-plus", reason="Unlock role-specific help."),
        ]
    return {"text": text, "suggestions": suggestions, "highlights": []}


def _guest_response(platform_snapshot, page_snapshot):
    category_names = ", ".join(category["name"] for category in platform_snapshot["categories"][:5])
    text = (
        f"FundiConnect is active right now with {platform_snapshot['open_jobs']} open jobs and "
        f"{platform_snapshot['active_artisans']} artisans. You can explore categories like {category_names}, "
        "create an account, then either post jobs as a client or start bidding as an artisan."
    )
    return {
        "text": text,
        "suggestions": [
            _suggest("Explore home", "home", icon="house-door", reason="See live platform highlights."),
            _suggest("Browse jobs", "job_list", icon="briefcase", reason="Review current opportunities."),
            _suggest("Create account", "users:register", icon="person-plus", reason="Unlock role-based help."),
        ],
        "highlights": [
            f"{platform_snapshot['open_jobs']} jobs open now",
            f"{platform_snapshot['active_artisans']} artisans available",
            f"Current page: {page_snapshot['label']}",
        ],
    }


def _client_response(prompt, snapshot):
    lowered = _normalize_prompt(prompt)
    suggestions = [
        _suggest("Post a job", "post_job", icon="briefcase-fill", reason="Create a clearer brief."),
        _suggest("Open dashboard", "users:dashboard", icon="speedometer2", reason="Review active work."),
        _suggest("Browse artisans", "users:artisans", icon="people", reason="Compare specialists."),
        _suggest("Open inbox", "users:notifications", icon="chat-dots", reason="Follow up faster."),
    ]

    if "compare" in lowered and "bid" in lowered:
        text = (
            f"You currently have {snapshot.get('pending_bids', 0)} pending bids. Compare them on six things: "
            "scope clarity, timeline realism, what is included, relevant proof of work, communication quality, and total value."
        )
    elif "rewrite" in lowered or "draft" in lowered or "job" in lowered:
        text = (
            "A high-converting FundiConnect job post should include the exact problem, the location, budget range, urgency, "
            "expected finish window, and any access or material constraints. If you paste your brief next, I can rewrite it."
        )
    elif "budget" in lowered or "price" in lowered or "cost" in lowered:
        text = (
            "For client-side pricing, anchor your budget around task complexity, urgency, travel needs, and whether materials are included. "
            "Giving a range usually attracts better bids than leaving the budget vague."
        )
    elif "direct" in lowered or "hire" in lowered:
        text = (
            f"You have {snapshot.get('pending_direct_hires', 0)} pending direct hires and {snapshot.get('active_jobs', 0)} active jobs. "
            "Direct hire works best when you already trust the artisan's reviews, specialization, and responsiveness."
        )
    else:
        text = (
            f"You are signed in as a client with {snapshot.get('open_jobs', 0)} open jobs, "
            f"{snapshot.get('active_jobs', 0)} active jobs, and {snapshot.get('pending_bids', 0)} pending bids. "
            "I can help you write stronger job posts, compare bids, hire the right fundi, and keep delivery moving."
        )

    highlights = [
        f"{snapshot.get('pending_bids', 0)} pending bids",
        f"{snapshot.get('active_jobs', 0)} active jobs",
        f"{snapshot.get('unread_messages', 0)} unread messages",
    ]
    return {"text": text, "suggestions": suggestions, "highlights": highlights}


def _artisan_response(prompt, snapshot):
    lowered = _normalize_prompt(prompt)
    suggestions = [
        _suggest("Browse jobs", "job_list", icon="search-heart", reason="See matching work."),
        _suggest("Open my bids", "artisan_bids", icon="send-check", reason="Track proposal outcomes."),
        _suggest("Edit profile", "users:profile", icon="person-badge", reason="Improve credibility."),
        _suggest("Open inbox", "users:notifications", icon="chat-left-text", reason="Reply to clients."),
    ]

    if "bid" in lowered or "proposal" in lowered or "rewrite" in lowered:
        text = (
            "A strong artisan bid should confirm the task in one sentence, mention directly relevant experience, "
            "state a realistic completion window, explain what your price includes, and end with a confident next step."
        )
    elif "profile" in lowered or "credibility" in lowered or "review" in lowered:
        text = (
            f"Your credibility score is {snapshot.get('credibility_score', 0)} with an average rating of "
            f"{snapshot.get('average_rating', 0)} from {snapshot.get('review_count', 0)} reviews. "
            "The fastest way to improve trust is a precise specialization, complete location details, strong portfolio proof, and fresh reviews."
        )
    elif "job" in lowered or "what next" in lowered:
        text = (
            f"You have {snapshot.get('pending_bids', 0)} pending bids, {snapshot.get('accepted_bids', 0)} accepted bids, "
            f"and {snapshot.get('active_jobs', 0)} active jobs. Prioritize jobs that closely match your specialization and where your timeline is believable."
        )
    else:
        text = (
            f"You are signed in as an artisan with {snapshot.get('pending_bids', 0)} pending bids, "
            f"{snapshot.get('accepted_bids', 0)} accepted bids, and {snapshot.get('active_jobs', 0)} active jobs. "
            "I can help you sharpen bids, raise credibility, and choose which opportunities to pursue."
        )

    highlights = [
        f"{snapshot.get('pending_bids', 0)} bids pending",
        f"Credibility score {snapshot.get('credibility_score', 0)}",
        f"{snapshot.get('unread_messages', 0)} unread messages",
    ]
    return {"text": text, "suggestions": suggestions, "highlights": highlights}


def _artisan_bid_response(prompt, snapshot):
    lowered = _normalize_prompt(prompt)
    amount = _extract_money_amount(prompt)
    average_market_budget = snapshot.get("market_budget_avg", 0)
    low_market_budget = snapshot.get("market_budget_low", 0)
    high_market_budget = snapshot.get("market_budget_high", 0)

    if amount:
        lower_band = max(round(amount * 0.85), 0)
        upper_band = round(amount * 1.0)
        market_line = ""
        if average_market_budget:
            market_line = (
                f" In your category, current open-job budgets on FundiConnect average about KES {average_market_budget:,.0f}"
                f"{f', usually between KES {low_market_budget:,.0f} and KES {high_market_budget:,.0f}' if low_market_budget and high_market_budget else ''}."
            )
        text = (
            f"If the client budget is KES {amount:,.0f}, a sensible bid usually lands between about KES {lower_band:,.0f} and KES {upper_band:,.0f} "
            "if the scope is straightforward and the budget already looks realistic." + market_line + " "
            "Bid near the top of the range if materials, travel, urgency, or complexity are high. Bid lower only if you can still deliver confidently without underpricing yourself. "
            "In your message, explain exactly what your amount includes so the client can compare value, not just price."
        )
    elif "budget" in lowered or "price" in lowered or "amount" in lowered:
        market_line = ""
        if average_market_budget:
            market_line = (
                f" In your current category, open jobs average about KES {average_market_budget:,.0f}"
                f"{f', usually between KES {low_market_budget:,.0f} and KES {high_market_budget:,.0f}' if low_market_budget and high_market_budget else ''}."
            )
        text = (
            "When you set your bid amount, start from labour time, materials, transport, urgency, and your margin instead of blindly matching the client budget."
            + market_line
            + " If the client's number is too low, you can still bid higher, but explain clearly what your amount includes and why."
        )
    else:
        text = (
            "To make a bid on FundiConnect, open a job from the job board, review the scope, location, and budget, then use the bid form on the job detail page. "
            "Enter your amount, write a short message that proves you understand the job, choose a realistic completion time, and submit. "
            "If the bid is still pending later, you can usually revise or withdraw it instead of sending a vague follow-up."
        )

    return {
        "text": text,
        "suggestions": [
            _suggest("Browse jobs", "job_list", icon="search-heart", reason="Find the next job to bid on."),
            _suggest("Open my bids", "artisan_bids", icon="send-check", reason="Track and refine your bids."),
            _suggest("Edit profile", "users:profile", icon="person-badge", reason="Boost trust before bidding."),
        ],
        "highlights": [
            f"{snapshot.get('matching_open_jobs', 0)} matching open jobs",
            f"Market average budget KES {snapshot.get('market_budget_avg', 0):,.0f}" if snapshot.get("market_budget_avg") else "Use scope and included costs to set your price",
            f"{snapshot.get('pending_bids', 0)} current pending bids",
        ],
    }


def _client_budget_response(prompt, snapshot):
    amount = _extract_money_amount(prompt)
    if amount:
        text = (
            f"If you are setting a client budget around KES {amount:,.0f}, make sure that number reflects labour, materials, travel, urgency, and any risk of rework. "
            "If you are unsure, posting a range like KES "
            f"{round(amount * 0.9):,.0f} to {round(amount * 1.15):,.0f} often gets more realistic bids than a single hard number."
        )
    else:
        text = (
            "When setting a client budget on FundiConnect, work from the job scope, urgency, materials, travel, and expected finish time. "
            "A range usually attracts better bids than a vague or unrealistically low figure."
        )
    return {
        "text": text,
        "suggestions": [
            _suggest("Post a job", "post_job", icon="briefcase-fill", reason="Set a clearer brief and budget."),
            _suggest("Browse artisans", "users:artisans", icon="people", reason="Compare specialists before hiring."),
        ],
        "highlights": [
            f"{snapshot.get('pending_bids', 0)} pending bids" if snapshot.get("pending_bids") is not None else "Budget clarity improves bid quality",
            f"{snapshot.get('active_jobs', 0)} active jobs" if snapshot.get("active_jobs") is not None else "Ranges often work better than fixed guesses",
        ],
    }


def _privacy_response(snapshot):
    text = (
        "I only use the signed-in user's workspace context, visible marketplace information, and platform state needed to answer the current question. "
        "I should not expose another user's private messages, contact details, or account-specific data."
    )
    suggestions = [
        _suggest("Open settings", "users:settings", icon="shield-lock", reason="Review security controls."),
        _suggest("Open profile", "users:profile", icon="person-circle", reason="Review your public-facing details."),
    ]
    highlights = [
        f"Signed-in role: {snapshot.get('role', 'guest')}",
        "Private chats stay scoped to participants",
        "Account-level details stay user-specific",
    ]
    return {"text": text, "suggestions": suggestions, "highlights": highlights}


def _direct_answer(prompt, snapshot, platform_snapshot, page_snapshot):
    lowered = _normalize_prompt(prompt)

    if snapshot.get("role") == "artisan" and (
        "how do i make a bid" in lowered
        or "how can i make a bid" in lowered
        or "make a bid" in lowered
        or ("budget" in lowered and ("client" in lowered or "bid" in lowered or _extract_money_amount(prompt)))
    ):
        return _artisan_bid_response(prompt, snapshot)
    if snapshot.get("role") == "client" and ("set a budget" in lowered or ("budget" in lowered and "client" in lowered)):
        return _client_budget_response(prompt, snapshot)
    if "how many artisans" in lowered or "how many fundis" in lowered:
        return _platform_count_response(prompt, platform_snapshot)
    if "how many clients" in lowered or "how many jobs" in lowered or "platform stats" in lowered:
        return _platform_count_response(prompt, platform_snapshot)
    if lowered in {"who are you", "what can you do", "what do you do"}:
        return {
            "text": (
                "I am FundiConnect's in-platform assistant. I can help with jobs, bids, profile setup, reviews, messaging, verification, "
                "security steps, and role-specific next actions without exposing private data from other users."
            ),
            "suggestions": [
                _suggest("Open dashboard", "users:dashboard", icon="speedometer2", reason="See your current workspace."),
                _suggest("Browse jobs", "job_list", icon="briefcase", reason="Review live opportunities."),
            ],
            "highlights": ["Role-aware help", "Privacy-respecting answers", "Platform-specific guidance"],
        }
    if "privacy" in lowered or "private" in lowered or "data" in lowered:
        return _privacy_response(snapshot)
    if ("improve my profile" in lowered or "improve profile" in lowered or "fix my profile" in lowered) and snapshot.get("role") == "artisan":
        return _artisan_profile_response(snapshot)
    if ("improve my profile" in lowered or "improve profile" in lowered or "fix my profile" in lowered) and snapshot.get("role") == "client":
        return _client_profile_response(snapshot)
    if lowered in {"help me", "help me i am stuck", "i am stuck", "im stuck", "what should i do"}:
        return _stuck_response(snapshot)
    if page_snapshot.get("route_name") == "users:profile" and snapshot.get("role") == "artisan" and ("help" in lowered or "profile" in lowered):
        return _artisan_profile_response(snapshot)
    return None


def _messages_response(snapshot):
    return {
        "text": (
            f"Your inbox is part of the live workspace and you currently have {snapshot.get('unread_messages', 0)} unread messages. "
            "Keep job details, scope changes, and next steps in chat so the platform stays organized."
        ),
        "suggestions": [
            _suggest("Open inbox", "users:notifications", icon="chat-square-text", reason="Continue active conversations."),
            _suggest("Go to dashboard", "users:dashboard", icon="speedometer2", reason="Review work and messages together."),
        ],
        "highlights": [
            f"{snapshot.get('unread_messages', 0)} unread messages",
            f"{snapshot.get('notifications', 0)} unread notifications",
        ],
    }


def _profile_response(snapshot):
    return {
        "text": (
            f"Your account status is email verified: {snapshot.get('email_verified', False)}, "
            f"phone verified: {snapshot.get('phone_verified', False)}, profile completed: {snapshot.get('profile_completed', False)}, "
            f"two-factor enabled: {snapshot.get('two_factor_enabled', False)}. "
            "I can guide you to the exact security or profile step you still need."
        ),
        "suggestions": [
            _suggest("Open settings", "users:settings", icon="gear", reason="Manage security and verification."),
            _suggest("Open profile", "users:profile", icon="person-circle", reason="Complete public-facing details."),
            _suggest("Set up 2FA", "users:two_factor_setup", icon="shield-lock", reason="Strengthen account protection."),
        ],
        "highlights": [
            f"Email verified: {snapshot.get('email_verified', False)}",
            f"Phone verified: {snapshot.get('phone_verified', False)}",
            f"2FA enabled: {snapshot.get('two_factor_enabled', False)}",
        ],
    }


def _category_response(platform_snapshot):
    category_names = ", ".join(category["name"] for category in platform_snapshot["categories"][:6])
    top_skills = ", ".join(platform_snapshot["top_skills"][:6])
    return {
        "text": (
            f"FundiConnect categories currently include {category_names}. Popular seeded skills include {top_skills}. "
            "I can help match a job to the right category or help an artisan choose the strongest skills to display."
        ),
        "suggestions": [
            _suggest("Browse categories", "category_list", icon="grid", reason="Explore the service structure."),
            _suggest("Browse artisans", "users:artisans", icon="people-fill", reason="Find category specialists."),
        ],
        "highlights": [
            f"{len(platform_snapshot['categories'])} top categories highlighted",
            f"{len(platform_snapshot['top_skills'])} popular skills surfaced",
        ],
    }


def _reviews_response(snapshot):
    if snapshot.get("role") == "artisan":
        text = (
            f"Your current rating is {snapshot.get('average_rating', 0)} from {snapshot.get('review_count', 0)} reviews, "
            f"with a credibility score of {snapshot.get('credibility_score', 0)}. "
            "Consistent communication and asking for reviews after completed jobs usually improves conversion fastest."
        )
    else:
        text = (
            "Reviews help future clients and artisans trust each other faster. "
            "The most useful reviews mention communication, timeliness, quality, and whether the agreed scope was delivered."
        )
    return {
        "text": text,
        "suggestions": [
            _suggest("View reviews", "review_list", icon="star", reason="See current marketplace feedback."),
            _suggest("Open dashboard", "users:dashboard", icon="speedometer2", reason="Review work that can be rated."),
        ],
        "highlights": [f"Marketplace average rating {snapshot.get('average_rating', 0) or 'available in profiles'}"],
    }


def _page_response(page_snapshot, snapshot):
    text = f"You are currently on the {page_snapshot['label']}. I can help you decide the best next step on this page."
    suggestions = []
    if page_snapshot["route_name"] == "post_job":
        suggestions.append(_suggest("Draft this job clearly", "post_job", icon="pencil-square", reason="Write a stronger client brief."))
    elif page_snapshot["route_name"] == "job_list":
        suggestions.append(_suggest("Browse jobs", "job_list", icon="briefcase", reason="Review live opportunities."))
    elif page_snapshot["route_name"] == "users:settings":
        suggestions.append(_suggest("Open security settings", "users:settings", icon="shield-check", reason="Manage verification and passwords."))
    elif snapshot.get("is_authenticated"):
        suggestions.append(_suggest("Open dashboard", "users:dashboard", icon="speedometer2", reason="Return to your main workspace."))
    else:
        suggestions.append(_suggest("Explore home", "home", icon="house-door", reason="Return to the marketplace overview."))
    return {
        "text": text,
        "suggestions": suggestions,
        "highlights": [f"Current page: {page_snapshot['label']}"],
    }


def _retrieval_answer(prompt, snapshot, platform_snapshot, history, page_snapshot):
    effective_prompt = _resolve_follow_up_prompt(prompt, history)
    flags = _intent_flags(effective_prompt)
    direct = _direct_answer(effective_prompt, snapshot, platform_snapshot, page_snapshot)
    if direct:
        retrieval = direct
    elif not snapshot.get("is_authenticated"):
        retrieval = _guest_response(platform_snapshot, page_snapshot)
    elif flags["messages"]:
        retrieval = _messages_response(snapshot)
    elif flags["profile"]:
        retrieval = _profile_response(snapshot)
    elif flags["categories"]:
        retrieval = _category_response(platform_snapshot)
    elif flags["reviews"]:
        retrieval = _reviews_response(snapshot)
    elif flags["greeting"]:
        retrieval = (
            _client_response(effective_prompt, snapshot)
            if snapshot.get("role") == "client"
            else _artisan_response(effective_prompt, snapshot)
        )
    elif flags["follow_up"] and history:
        topic = _topic_from_text(_last_user_prompt(history))
        if topic == "profile" and snapshot.get("role") == "artisan":
            retrieval = _artisan_profile_response(snapshot)
        elif topic == "profile" and snapshot.get("role") == "client":
            retrieval = _client_profile_response(snapshot)
        elif topic == "platform_counts":
            retrieval = _platform_count_response(effective_prompt, platform_snapshot)
        elif topic == "bidding":
            retrieval = _artisan_response("help me improve my next bid", snapshot)
        elif topic == "job_posting":
            retrieval = _client_response("help me improve my next job post", snapshot)
        else:
            retrieval = _page_response(page_snapshot, snapshot)
            retrieval["text"] = (
                f"{retrieval['text']} If you paste the exact job brief, bid, or message you want improved, I can rewrite it directly."
            )
    elif snapshot.get("role") == "client":
        retrieval = _client_response(effective_prompt, snapshot)
    elif snapshot.get("role") == "artisan":
        retrieval = _artisan_response(effective_prompt, snapshot)
    else:
        retrieval = _page_response(page_snapshot, snapshot)

    retrieval["platform_items"] = snapshot.get("recent_items", [])
    retrieval["resolved_prompt"] = effective_prompt
    if not retrieval.get("highlights"):
        retrieval["highlights"] = [
            f"{platform_snapshot['open_jobs']} open jobs live",
            f"{platform_snapshot['active_artisans']} artisans on platform",
            f"Current page: {page_snapshot['label']}",
        ]
    return retrieval


def _build_finalization_context(prompt, retrieval, snapshot, platform_snapshot, history, page_snapshot, ui_context=None):
    return {
        "system": _assistant_system_instruction(),
        "user_prompt": prompt,
        "resolved_prompt": retrieval.get("resolved_prompt", prompt),
        "facts": _build_facts(snapshot, platform_snapshot, page_snapshot),
        "retrieval_text": retrieval.get("text", ""),
        "retrieval_suggestions": retrieval.get("suggestions", []),
        "retrieval_highlights": retrieval.get("highlights", []),
        "retrieval_platform_items": retrieval.get("platform_items", []),
        "user_snapshot": snapshot,
        "platform_snapshot": platform_snapshot,
        "page_snapshot": page_snapshot,
        "history_summary": _recent_history_summary(history),
        "ui_context": ui_context or {},
        "functions": getattr(settings, 'FUNDICONNECT_ASSISTANT_FUNCTIONS', []),
    }


def _assistant_system_instruction():
    return (
        os.environ.get('FUNDICONNECT_ASSISTANT_SYSTEM_INSTRUCTION')
        or getattr(
            settings,
            'FUNDICONNECT_ASSISTANT_SYSTEM_INSTRUCTION',
            (
                "You are FundiConnect AI, the platform's privacy-first assistant for clients and artisans. "
                "Answer only with FundiConnect-relevant guidance. Use platform facts and user-specific data only when it belongs to the signed-in user or is safe aggregate platform data. "
                "Never reveal another user's private information, messages, phone numbers, emails, or hidden job details. "
                "Be specific, practical, and action-oriented. Avoid repeating generic role summaries. "
                "When exact counts, current page recommendations, or job search results are needed, use the provided tools. "
                "Return strict JSON with the keys text, suggestions, highlights, and platform_items."
            ),
        )
    )


def _gemini_models():
    raw = (
        os.environ.get("FUNDICONNECT_ASSISTANT_GEMINI_CANDIDATES")
        or getattr(settings, "FUNDICONNECT_ASSISTANT_GEMINI_CANDIDATES", "")
        or os.environ.get("FUNDICONNECT_ASSISTANT_GEMINI_MODEL")
        or getattr(settings, "FUNDICONNECT_ASSISTANT_GEMINI_MODEL", "")
        or os.environ.get("GEMINI_MODEL")
        or getattr(settings, "GEMINI_MODEL", "")
        or "gemini-2.5-flash,gemini-3-flash-preview,gemini-2.5-pro"
    )
    return [item.strip() for item in str(raw).split(",") if item.strip()]


def _thinking_budget_value():
    raw = (
        os.environ.get("FUNDICONNECT_ASSISTANT_THINKING_BUDGET")
        or getattr(settings, "FUNDICONNECT_ASSISTANT_THINKING_BUDGET", "")
        or os.environ.get("FUNDICONNECT_ASSISTANT_THINKING_LEVEL")
        or getattr(settings, "FUNDICONNECT_ASSISTANT_THINKING_LEVEL", "")
        or "medium"
    )
    try:
        return int(raw)
    except (TypeError, ValueError):
        pass
    mapped = {
        "off": 0,
        "none": 0,
        "low": 1024,
        "medium": 4096,
        "high": 8192,
        "max": 12288,
        "dynamic": -1,
        "auto": -1,
    }
    return mapped.get(str(raw).strip().lower(), 4096)


def _thinking_config_for_model(types, model):
    budget = _thinking_budget_value()
    lowered = str(model or "").lower()
    if "2.5-pro" in lowered and budget == 0:
        budget = 1024
    try:
        if "2.5" in lowered:
            return types.ThinkingConfig(thinking_budget=budget)
        return types.ThinkingConfig(include_thoughts=False)
    except Exception:
        return None


def _render_gemini_prompt(payload):
    return (
        "Use the following FundiConnect context to answer the latest user request.\n"
        "Rules:\n"
        "1. Answer the resolved prompt directly and specifically.\n"
        "2. Use exact platform facts when available.\n"
        "3. Use tools when current counts, job search results, or page-aware recommendations are needed.\n"
        "4. Avoid repetitive role summaries and generic filler.\n"
        "5. Return strict JSON only using this shape:\n"
        '{"text":"string","suggestions":[{"label":"string","url":"string or null","icon":"string","reason":"string"}],"highlights":["string"],"platform_items":[{"type":"string","title":"string","subtitle":"string","url":"string or null","icon":"string"}]}\n\n'
        f"Resolved prompt:\n{payload.get('resolved_prompt') or payload.get('user_prompt')}\n\n"
        f"Retrieval draft:\n{payload.get('retrieval_text')}\n\n"
        f"Context payload:\n{json.dumps(payload, ensure_ascii=True)}"
    )


def _build_gemini_tools(payload):
    snapshot = payload.get("user_snapshot") or {}
    platform_snapshot = payload.get("platform_snapshot") or {}
    page_snapshot = payload.get("page_snapshot") or {}

    def get_user_snapshot() -> dict:
        """Return the signed-in user's own FundiConnect snapshot for personalized guidance."""
        return snapshot

    def get_platform_snapshot() -> dict:
        """Return safe aggregate marketplace counts and category summaries for FundiConnect."""
        return platform_snapshot

    def get_page_recommendations(page: str = "", role: str = "") -> dict:
        """Return page-aware next-step recommendations based on the current FundiConnect screen and user role."""
        resolved_page = page or page_snapshot.get("route_name") or page_snapshot.get("label") or "current page"
        resolved_role = role or snapshot.get("role") or "guest"
        route_name = page_snapshot.get("route_name") or ""
        if route_name == "post_job" or resolved_page == "post_job":
            recommendations = [
                _suggest("Clarify the task title", icon="type", reason="State the exact work needed in one line."),
                _suggest("Set a realistic budget", icon="cash-stack", reason="A realistic range improves bid quality."),
                _suggest("Add access details", icon="geo-alt", reason="Location and access notes improve matching."),
            ]
        elif route_name == "place_bid" or resolved_page == "place_bid":
            recommendations = [
                _suggest("Mirror the brief", icon="clipboard-check", reason="Open by confirming the exact scope."),
                _suggest("Explain your price", icon="currency-exchange", reason="Tell the client what the amount covers."),
                _suggest("Show proof of work", icon="patch-check", reason="Mention similar jobs or certifications."),
            ]
        elif resolved_role == "client":
            recommendations = [
                _suggest("Post a job", "post_job", icon="briefcase-fill", reason="Create a clearer brief."),
                _suggest("Browse artisans", "users:artisans", icon="people", reason="Compare rated artisans."),
            ]
        else:
            recommendations = [
                _suggest("Browse jobs", "job_list", icon="search-heart", reason="Open matching opportunities."),
                _suggest("Open my bids", "artisan_bids", icon="send-check", reason="Track live proposals."),
            ]
        return {"page": resolved_page, "role": resolved_role, "recommendations": recommendations}

    def search_open_jobs(query: str = "", category: str = "", location: str = "", limit: int = 5) -> dict:
        """Search open FundiConnect jobs by keyword, category, and location and return public results."""
        jobs = Job.objects.filter(status="open").select_related("category", "client").order_by("-created_at")
        if query:
            jobs = jobs.filter(Q(title__icontains=query) | Q(description__icontains=query))
        if category:
            jobs = jobs.filter(Q(category__slug__icontains=category) | Q(category__name__icontains=category))
        if location:
            jobs = jobs.filter(location__icontains=location)
        items = []
        capped_limit = max(1, min(int(limit or 5), 8))
        for job in jobs[:capped_limit]:
            items.append(
                {
                    "id": job.id,
                    "title": job.title,
                    "budget": float(job.budget or 0),
                    "location": job.location,
                    "category": getattr(job.category, "name", ""),
                    "urgency": job.get_urgency_display(),
                    "url": _safe_reverse("job_detail", job_id=job.id),
                }
            )
        return {"count": len(items), "jobs": items}

    def get_bid_budget_guidance(client_budget: float = 0, scope_hint: str = "", urgency: str = "") -> dict:
        """Return pragmatic bid-pricing guidance for FundiConnect artisans relative to a client's stated budget."""
        try:
            budget_value = float(client_budget or 0)
        except (TypeError, ValueError):
            budget_value = 0
        cautious_floor = round(budget_value * 0.85, 2) if budget_value else 0
        value_target = round(budget_value * 0.95, 2) if budget_value else 0
        premium_ceiling = round(budget_value * 1.1, 2) if budget_value else 0
        return {
            "client_budget": budget_value,
            "recommended_ranges": {
                "competitive": cautious_floor,
                "value_target": value_target,
                "premium_ceiling": premium_ceiling,
            },
            "scope_hint": scope_hint,
            "urgency": urgency,
            "notes": [
                "Stay near the client's budget unless you can justify better materials, warranty, specialist expertise, or faster turnaround.",
                "Break down labour, materials, transport, and timing so the client can compare value, not only price.",
                "If scope is uncertain, quote a clear base scope and mention what would change the final amount.",
            ],
        }

    return [get_user_snapshot, get_platform_snapshot, get_page_recommendations, search_open_jobs, get_bid_budget_guidance]


def _canon_title_for_item(it):
    title = str(it.get('title') or it.get('name') or it.get('store_name') or '').strip().lower()
    title = re.sub(r'[^a-z0-9\s]', ' ', title)
    title = re.sub(r'\s+', ' ', title).strip()
    title = re.sub(r'\b(please|now|today|here|for you|for your account)\b', '', title).strip()
    return title


def _dedupe_platform_items(items):
    out = []
    seen = set()
    for it in (items or []):
        if not isinstance(it, dict):
            continue
        key = (it.get('type'), it.get('id'), it.get('url'), (it.get('title') or it.get('name') or it.get('store_name')))
        if key in seen:
            continue
        seen.add(key)
        out.append(it)
    return out


def _filter_platform_items_for_prompt(prompt, text, items):
    """Lightweight port of the Baysoko filtering logic: dedupe, match by title/terms and return top 5."""
    items = _dedupe_platform_items(items)
    if not items:
        return []

    context = f"{prompt or ''} {text or ''}".lower()
    terms = {t for t in re.sub(r'[^a-z0-9\s]', ' ', context).split() if len(t) > 2}

    matched = []
    action_items = [it for it in items if it.get('type') == 'action_suggestion']

    for it in items:
        if not isinstance(it, dict):
            continue
        nm = _canon_title_for_item(it)
        if nm and nm in context:
            matched.append(it)
            continue
        nm_terms = {t for t in nm.split() if len(t) > 2}
        if nm_terms and terms and (nm_terms & terms):
            matched.append(it)

    if matched:
        ordered = _dedupe_platform_items(matched + action_items)
        return ordered[:5]

    # Fallback heuristics for common contexts
    if re.search(r"\b(order|orders|track|delivery)\b", context):
        return _dedupe_platform_items([it for it in items if (it.get('type') or '') in {'order'}] + action_items)[:5]
    if re.search(r"\b(cart|checkout)\b", context):
        return _dedupe_platform_items([it for it in items if (it.get('type') or '') in {'cart_item'}] + action_items)[:5]
    if re.search(r"\b(store|stores|seller|shop)\b", context):
        return _dedupe_platform_items([it for it in items if (it.get('type') or '') in {'store'}] + action_items)[:5]
    if re.search(r"\b(arrival|arrivals|listing|listings|item|items|featured|product|products|favorites|recent)\b", context):
        return _dedupe_platform_items([it for it in items if (it.get('type') or '') in {'listing', 'favorite'}] + action_items)[:5]

    return _dedupe_platform_items(action_items)[:5]


# Small query registry for FundiConnect: map patterns to DB-backed retrievals
QUERY_REGISTRY = [
    {
        'patterns': [r"how many artisans", r"how many fundis", r"how many artisans are"],
        'function': lambda prompt, user=None: {'text': f"There are {CustomUser.objects.filter(user_type='artisan').count()} artisans on FundiConnect.", 'data': []},
    },
    {
        'patterns': [r"completed jobs", r"who completed"],
        'function': lambda prompt, user=None: _get_completed_artisans(prompt),
    },
]


def try_database_query(prompt, user=None):
    try:
        low = str(prompt or '').lower()
        for entry in QUERY_REGISTRY:
            for pat in entry.get('patterns', []) or []:
                if re.search(pat, low):
                    try:
                        return entry['function'](prompt, user)
                    except Exception:
                        logger.exception('Query registry function failed for pattern %s', pat)
        return None
    except Exception:
        return None


def _get_completed_artisans(prompt=None):
    try:
        completed = Job.objects.filter(status='completed').select_related('artisan')[:12]
        artisans = []
        items = []
        for j in completed:
            art = getattr(j, 'artisan', None)
            name = None
            if art:
                name = getattr(art, 'display_name', None) or getattr(art, 'username', None)
            if name and name not in artisans:
                artisans.append(name)
            items.append({'type': 'job', 'id': j.id, 'title': j.title, 'subtitle': f"Completed by {name}", 'url': _safe_reverse('job_detail', job_id=j.id)})
        text = f"{len(artisans)} artisans have completed recent jobs on FundiConnect." if artisans else "No completed-job artisans found."
        if artisans:
            text += ' Recent artisans include: ' + ', '.join(artisans[:6]) + '.'
        return {'text': text, 'data': items, 'context': '\n'.join([f"- {i['title']}: {i['subtitle']}" for i in items[:6]])}
    except Exception:
        logger.exception('_get_completed_artisans failed')
        return None


def _extract_json(text):
    raw = str(text or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(raw[start : end + 1])
            except Exception:
                return None
    return None


def _generate_gemini_final(payload):
    api_key = os.environ.get("GEMINI_API_KEY") or getattr(settings, "GEMINI_API_KEY", "")
    if not api_key:
        return None

    try:
        from google import genai
        from google.genai import types

        # Apply key for SDK client and init
        os.environ["GEMINI_API_KEY"] = api_key
        client = genai.Client()

        try:
            temperature = float(
                os.environ.get("FUNDICONNECT_ASSISTANT_TEMPERATURE")
                or getattr(settings, "FUNDICONNECT_ASSISTANT_TEMPERATURE", 0.35)
            )
        except Exception:
            temperature = 0.35

        system_instruction = _assistant_system_instruction()
        prompt_body = _render_gemini_prompt(payload)
        gemini_tools = _build_gemini_tools(payload)

        # Try models with retries and backoff; log raw SDK responses for debugging
        for model in _gemini_models():
            attempt = 0
            while attempt < 2:
                attempt += 1
                try:
                    cfg_kwargs = {
                        "system_instruction": system_instruction,
                        "temperature": temperature,
                        "response_mime_type": "application/json",
                        "tools": gemini_tools,
                    }
                    thinking_config = _thinking_config_for_model(types, model)
                    if thinking_config is not None:
                        cfg_kwargs["thinking_config"] = thinking_config
                    cfg = types.GenerateContentConfig(**cfg_kwargs)

                    response = client.models.generate_content(
                        model=model,
                        contents=prompt_body,
                        config=cfg,
                    )

                    raw = getattr(response, 'text', None) or getattr(response, 'response', None) or str(response)
                    logger.info('GENAI_SDK_RAW_RESPONSE model=%s attempt=%s raw=%s', model, attempt, str(raw)[:1000])
                    parsed = _extract_json(raw)
                    if parsed and parsed.get('text'):
                        logger.info('GENAI_SDK_PARSED_SUCCESS model=%s', model)
                        return parsed
                    else:
                        logger.debug('GENAI_SDK_PARSE_FAILED model=%s parsed=%s', model, repr(parsed))
                except Exception:
                    logger.exception('GenAI client finalization failed for model %s attempt=%s', model, attempt)
                time.sleep(0.8 * attempt)
    except Exception:
        logger.debug("google-genai client unavailable, falling back to REST", exc_info=True)

    # REST fallback with retries and detailed logging
    for model in _gemini_models():
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        attempt = 0
        while attempt < 2:
            attempt += 1
            try:
                generation_config = {
                    "temperature": float(os.environ.get("FUNDICONNECT_ASSISTANT_TEMPERATURE") or getattr(settings, "FUNDICONNECT_ASSISTANT_TEMPERATURE", 0.35)),
                    "responseMimeType": "application/json",
                }
                if "2.5" in str(model):
                    generation_config["thinkingConfig"] = {"thinkingBudget": _thinking_budget_value()}

                payload_contents = {
                    "systemInstruction": {"parts": [{"text": _assistant_system_instruction()}]},
                    "contents": [
                        {
                            "parts": [
                                {"text": _render_gemini_prompt(payload)}
                            ]
                        }
                    ],
                    "generationConfig": generation_config,
                }

                timeout_val = int(os.environ.get("FUNDICONNECT_ASSISTANT_GEMINI_TIMEOUT", getattr(settings, "FUNDICONNECT_ASSISTANT_GEMINI_TIMEOUT", 60)))
                response = requests.post(
                    url,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=payload_contents,
                    timeout=timeout_val,
                )
                logger.info('GENAI_REST_RAW_RESPONSE model=%s attempt=%s status=%s body=%s', model, attempt, response.status_code, response.text[:1000])
                response.raise_for_status()
                data = response.json()
                candidate = (((data.get("candidates") or [{}])[0].get("content") or {}).get("parts") or [{}])[0]
                parsed = _extract_json(candidate.get("text"))
                if parsed and parsed.get("text"):
                    logger.info('GENAI_REST_PARSED_SUCCESS model=%s', model)
                    return parsed
            except Exception:
                logger.exception('Gemini REST finalization failed for model %s attempt=%s', model, attempt)
            time.sleep(0.9 * attempt)
    return None


def _fallback_finalize(prompt, retrieval, history, snapshot):
    text = retrieval.get("text", "").strip()
    lowered = _normalize_prompt(prompt)
    if lowered in {"yes", "yeah", "continue", "ok", "okay"} and history:
        recent = _recent_history_summary(history)
        if recent:
            text = f"{text} We were last discussing: {recent[:220]}."
    if any(token in lowered for token in ("rewrite", "draft", "compose")):
        if snapshot.get("role") == "client":
            text = (
                f"{text}\n\nTry this structure:\n"
                "1. What needs to be done.\n"
                "2. Where the job is located.\n"
                "3. Budget range.\n"
                "4. When you need it done.\n"
                "5. Any material or access notes."
            )
        elif snapshot.get("role") == "artisan":
            text = (
                f"{text}\n\nTry this bid structure:\n"
                "1. Confirm the exact task.\n"
                "2. Mention one similar job you have handled.\n"
                "3. State your delivery timeline.\n"
                "4. Explain what your price includes.\n"
                "5. End with a clear next step."
            )
    return {
        "text": text,
        "suggestions": retrieval.get("suggestions", []),
        "highlights": retrieval.get("highlights", []),
        "platform_items": retrieval.get("platform_items", []),
    }


def _trim_repetition(response, history):
    if not history:
        return response
    previous_assistant = [item.get("content", "").strip() for item in history if item.get("role") == "assistant" and item.get("content")]
    last_reply = previous_assistant[-1] if previous_assistant else ""
    current = response.get("text", "").strip()
    if last_reply and current and current == last_reply:
        response["text"] = f"{current} If you want, I can go one level deeper and make this specific to your next action."
    return response


def _finalize_response(response, retrieval, snapshot):
    if not response:
        response = {}
    response["text"] = str(response.get("text") or retrieval.get("text") or "I am here to help you move work forward on FundiConnect.").strip()

    suggestions = response.get("suggestions") or retrieval.get("suggestions") or []
    normalized_suggestions = []
    for item in suggestions[:5]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        if not label:
            continue
        normalized_suggestions.append(
            {
                "label": label,
                "url": item.get("url"),
                "icon": item.get("icon") or "arrow-right-circle",
                "reason": item.get("reason") or "",
            }
        )
    # Ensure we have at least a reasonable default suggestion
    if not normalized_suggestions:
        normalized_suggestions = [
            _suggest(
                "Open dashboard" if snapshot.get("is_authenticated") else "Explore home",
                "users:dashboard" if snapshot.get("is_authenticated") else "home",
                icon="speedometer2" if snapshot.get("is_authenticated") else "house-door",
                reason="Continue on the platform.",
            )
        ]

    # If the assistant reply ends with a next-step question, convert the intent into actionable suggestions.
    try:
        last_sentence = str(response.get("text", "")).strip().splitlines()[-1].strip()
    except Exception:
        last_sentence = ""

    if last_sentence.endswith("?") or re.search(r"\b(would you like|do you want|shall i|would you like me|want me to)\b", last_sentence, re.I):
        source_suggestions = retrieval.get("suggestions") or normalized_suggestions
        action_suggestions = []
        for item in (source_suggestions or [])[:3]:
            if not isinstance(item, dict):
                continue
            label = str(item.get("label") or "").strip()
            if not label:
                continue
            action_suggestions.append(
                {
                    "label": label,
                    "url": item.get("url"),
                    "icon": item.get("icon") or "arrow-right-circle",
                    "reason": item.get("reason") or "Recommended next step.",
                }
            )
        if action_suggestions:
            normalized_suggestions = action_suggestions

    # Normalize reasons and apply suggestion max from settings
    max_sugs = getattr(settings, 'FUNDICONNECT_ASSISTANT_SUGGESTION_MAX', 5) or 5
    for s in normalized_suggestions:
        if not s.get("reason"):
            s["reason"] = "Recommended next step."
    normalized_suggestions = normalized_suggestions[: int(max_sugs) ]
    response["suggestions"] = normalized_suggestions

    highlights = response.get("highlights") or retrieval.get("highlights") or []
    response["highlights"] = [str(item).strip() for item in highlights if str(item).strip()][:4]
    response["platform_items"] = response.get("platform_items") or retrieval.get("platform_items", [])
    # Sanitize text: remove repeated role-overview lines and collapse duplicated sentences
    response["text"] = _sanitize_response_text(response["text"]) 
    return response


def _sanitize_response_text(text):
    if not text:
        return text
    raw = str(text or "").strip()
    # Remove common repeated role summaries like "You are signed in as a ..."
    raw = re.sub(r"You are signed in as a [^\.\n]+[\.\n]", "", raw, flags=re.IGNORECASE)
    # Split into paragraphs, keep at most first 2 meaningful paragraphs
    parts = [p.strip() for p in re.split(r"\n\s*\n", raw) if p.strip()]
    if not parts:
        return raw
    parts = parts[:2]
    joined = "\n\n".join(parts)
    # Deduplicate repeated lines/sentences while preserving order
    seen = set()
    out_lines = []
    for line in re.split(r"[\n\.]+\s*", joined):
        s = line.strip()
        if not s:
            continue
        if s.lower() in seen:
            continue
        seen.add(s.lower())
        out_lines.append(s)
        if len(out_lines) >= 6:
            break
    # Reconstruct as readable sentences.
    if not out_lines:
        return joined
    # If original paragraphs existed, keep paragraph break after first sentence when possible
    return ". ".join(out_lines).strip() + ('.' if not out_lines[-1].endswith('.') else '')


def persist_assistant_exchange(user, prompt, response):
    if not user or not getattr(user, "is_authenticated", False):
        return
    AssistantChat.objects.create(user=user, role="user", content=prompt)
    AssistantChat.objects.create(
        user=user,
        role="assistant",
        content=response.get("text", ""),
        meta={
            "suggestions": response.get("suggestions", []),
            "highlights": response.get("highlights", []),
            "platform_items": response.get("platform_items", []),
        },
    )


def assistant_reply(prompt, user=None, context=None, path=""):
    snapshot = _build_user_snapshot(user)
    platform_snapshot = _build_platform_snapshot()
    ui_context = {}
    if isinstance(context, list):
        history = context
    elif isinstance(context, dict):
        maybe_history = context.get("history")
        history = maybe_history if isinstance(maybe_history, list) else _history_for_model(user)
        ui_context = {key: value for key, value in context.items() if key != "history"}
    else:
        history = _history_for_model(user)
    page_snapshot = _page_snapshot(path)

    retrieval = _retrieval_answer(prompt, snapshot, platform_snapshot, history, page_snapshot)
    final_payload = _build_finalization_context(prompt, retrieval, snapshot, platform_snapshot, history, page_snapshot, ui_context=ui_context)

    response = _generate_gemini_final(final_payload) or _fallback_finalize(prompt, retrieval, history, snapshot)

    response = _finalize_response(response, retrieval, snapshot)
    return _trim_repetition(response, history)


def _execute_assistant_function(name, args, user, snapshot, platform_snapshot):
    """Execute a limited, safe set of assistant functions.

    Returns a JSON-serializable result.
    """
    name = str(name or '').strip()
    if name == 'get_user_snapshot':
        return _build_user_snapshot(user)
    if name == 'get_platform_snapshot':
        return _build_platform_snapshot()
    if name == 'get_completed_artisans':
        # Return list of recent artisans who completed jobs and sample jobs
        try:
            completed = Job.objects.filter(status='completed').select_related('artisan')[:12]
            artisans = []
            jobs = []
            for j in completed:
                art = getattr(j, 'artisan', None)
                name = art.display_name if art and getattr(art, 'display_name', None) else (getattr(art, 'username', None) if art else None)
                if name and name not in artisans:
                    artisans.append(name)
                jobs.append({'id': j.id, 'title': j.title, 'completed_by': name})
            return {'ok': True, 'artisans': artisans, 'jobs': jobs}
        except Exception:
            logger.exception('get_completed_artisans failed')
            return {'ok': False, 'error': 'Failed to fetch completed artisans'}
    if name == 'search_jobs':
        # Simple job search by text in title/description
        q = (args.get('q') or args.get('query') or '') if isinstance(args, dict) else ''
        try:
            qs = Job.objects.filter(title__icontains=q)[:8] if q else Job.objects.order_by('-updated_at')[:8]
            out = [{'id': j.id, 'title': j.title, 'status': j.status, 'url': _safe_reverse('job_detail', job_id=j.id)} for j in qs]
            return {'ok': True, 'results': out}
        except Exception:
            logger.exception('search_jobs failed')
            return {'ok': False, 'error': 'Search failed'}
    if name == 'create_support_ticket':
        # Safe, lightweight ticket: persist as AssistantChat for audit and return an id
        title = args.get('title') if isinstance(args, dict) else None
        body = args.get('body') if isinstance(args, dict) else None
        try:
            meta = {'function': 'create_support_ticket'}
            ticket_text = f"Support ticket: {title or 'No title'} - {body or ''}"
            AssistantChat.objects.create(user=user or None, role='system', content=ticket_text, meta=meta)
            return {'ok': True, 'message': 'Ticket created', 'ticket': {'title': title, 'body': body}}
        except Exception:
            logger.exception('Failed to create support ticket')
            return {'ok': False, 'error': 'Failed to create ticket'}

    # Unknown function: return helpful error for the model
    return {'ok': False, 'error': f'Unknown function {name}'}
