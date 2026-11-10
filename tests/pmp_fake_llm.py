"""A stand-in for agents.llm.ask: fixed, realistic answers per schema so the pipeline runs without an LLM."""
from __future__ import annotations

import re

QUESTION = {
    "012dd47f": {
        "explanation_supports_answer": True,
        "title": "8 Sprints, No Value Check: Who Do You Call First?",
        "hook": "Eight sprints shipped. Nobody checked the value.",
        "scenario_screen": "After eight sprints, nobody has checked whether the features create business value. "
                           "There are no adoption metrics. Who do you engage first?",
        "scenario_say": "Your agile team has shipped features for eight sprints. The business has never checked "
                        "whether those features deliver the value they promised, and there are no adoption "
                        "metrics. Who do you engage first?",
        "options_screen": ["Product owner and sponsor: start a benefits review",
                           "Add a benefits check to every sprint review",
                           "Have the business analyst build adoption metrics",
                           "Run a workshop with the team and business unit"],
        "reasons": ["the sponsor and product owner own benefits, so they can launch a real review.",
                    "a good habit later, but it skips the people who own the benefits.",
                    "metrics help, but without the owners nobody acts on them.",
                    "a workshop without governance gives opinions, not a decision.",
                    ],
        "rule": "Benefits have owners. Start with them.",
        "rule_say": "When value is in question, go to the people accountable for benefits: the sponsor and the "
                    "product owner.",
    },
}
QUESTION["012dd47f"]["reasons"][0] = ("A wins: the sponsor and product owner own benefits realization, "
                                     "so they can start a formal review.")

TRAP = {
    "explanation_supports_answer": True,
    "title": "The Sprint Review Trap That Costs You Points",
    "hook": "This answer feels responsible. It costs points.",
    "scenario_screen": "The shared test environment is corrupted. Three teams depend on it. "
                       "The sprint review is coming. What do you do?",
    "scenario_say": "Your shared test environment is corrupted and three teams depend on it. Completed stories "
                    "cannot be validated before the sprint review. What should you do?",
    "options_screen": ["Escalate to senior management for resources",
                       "Hold the review, be clear about what is untested",
                       "Postpone the review and extend the sprint",
                       "Test with temporary workarounds"],
    "trap_index": 2,
    "tempting": "Postponing sounds careful. You only show work that is fully tested, so nobody sees a surprise.",
    "wrong": "But agile protects the cadence. Extending the sprint breaks the rhythm and delays the feedback "
             "the review exists for.",
    "right_say": "The answer is B. Hold the review and be transparent about what still needs testing.",
    "rule": "Protect the cadence. Be transparent.",
}

TERM = {
    "title": "Risk vs Issue: The PMP Difference in 45 Seconds",
    "hook": "Risk or issue? One word changes your answer.",
    "left": {"term": "Risk", "definition": "An uncertain event that has not happened yet.",
             "example": "The vendor might deliver two weeks late.",
             "say": "A risk is uncertain and in the future. It might happen. You log it in the risk register and "
                    "plan a response."},
    "right": {"term": "Issue", "definition": "Something that is happening now and needs action.",
              "example": "The vendor just told you delivery is late.",
              "say": "An issue is already here. It is certain and current. You log it in the issue log and act on "
                     "it now."},
    "tip": "Ask: has it happened yet? No is a risk. Yes is an issue.",
    "tip_say": "On the exam, ask one question: has it happened yet? If not, it is a risk. If it has, it is an issue.",
    "quiz_question": "A key developer resigns today. Risk or issue?",
    "quiz_answer": "Issue. It already happened.",
}

MINDSET = {
    "title": "PMI Mindset: Assess Before You Act",
    "hook": "On the PMP, the first move is rarely action.",
    "rule": "Assess before you act.",
    "explain_say": "Most situational questions reward the project manager who first understands the problem: "
                   "the facts, the impact and the people involved.",
    "scenario": "A stakeholder emails you, angry that a feature is missing.",
    "do": "Meet them, understand the gap, check the plan.",
    "dont": "Promise the feature right away.",
    "do_say": "Do this: meet them, understand what they expected, and check it against the plan.",
    "dont_say": "Don't promise the feature on the spot. You do not know the impact yet.",
}

COURSE = {
    "title": "Business Environment for the 2026 PMP",
    "subtitle": "Benefits, governance and value delivery explained",
    "intro_say": "Business Environment is a bigger part of the new exam. In this lesson you learn how projects "
                 "connect to strategy, who owns benefits, and how to think through value questions.",
    "chapters": [
        {"title": "Benefits and value", "keywords": "benefits realization value sponsor",
         "sections": [{"heading": "Who owns benefits", "bullets": ["Sponsor owns the business case",
                                                                  "Product owner maximizes value",
                                                                  "PM delivers the capability"],
                       "say": "The sponsor owns the business case and the benefits. The product owner maximizes "
                              "the value of what the team builds. The project manager delivers the capability "
                              "that makes benefits possible."}],
         "example": {"heading": "Value nobody measured", "scenario": "Eight sprints shipped, no adoption data.",
                     "say": "When value is unclear, go to the people who own it, the sponsor and the product owner, "
                            "and start a benefits review."}},
        {"title": "External change", "keywords": "funding political uncertainty value",
         "sections": [{"heading": "When the environment shifts", "bullets": ["Assess the impact first",
                                                                           "Protect delivered value",
                                                                           "Update the plan, then communicate"],
                       "say": "Elections, regulations and markets change. First assess the impact on your project. "
                              "Then protect the value you can still deliver. Update the plan and communicate."}],
         "example": {"heading": "Funding at risk", "scenario": "An election may end future funding.",
                     "say": "Restructure the plan to deliver the most value inside the funding you are sure of."}},
    ],
    "recap": ["Benefits have owners: sponsor and product owner",
              "Assess external change before acting",
              "Deliver value inside known constraints"],
    "outro_say": "That is Business Environment for the 2026 PMP.",
}


def _generic_question(prompt: str) -> dict:
    opts = re.findall(r"^[ABCD]\. (.+)$", prompt, flags=re.M)[:4]
    short = [" ".join(o.split()[:10]) for o in opts]
    return {"explanation_supports_answer": "remove contingency reserves" not in prompt,
            "title": "A Situational PMP Question, Explained",
            "hook": "What would a PMP do first?",
            "scenario_screen": "A situation from the exam. Pick the best first step.",
            "scenario_say": "Here is a situation from the exam. Think about the best first step.",
            "options_screen": short,
            "reasons": ["it is the best first step here." for _ in short],
            "rule": "Assess, then act.",
            "rule_say": "Understand the situation before you act."}


def ask(system, prompt, schema=None, **kw):
    props = (schema or {}).get("properties", {})
    if "trap_index" in props:
        return dict(TRAP)
    if "quiz_question" in props:
        return dict(TERM)
    if "do_say" in props:
        return dict(MINDSET)
    if "chapters" in props:
        return dict(COURSE)
    for key, value in QUESTION.items():
        if key in prompt or value["scenario_screen"][:20] in prompt:
            return dict(value)
    if "eight sprints" in prompt:
        return dict(QUESTION["012dd47f"])
    return _generic_question(prompt)
