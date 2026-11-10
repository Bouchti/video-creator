"""
PMP Exam Lab videos, rendered with HyperFrames (HTML + GSAP -> MP4).

Two shapes, five formats:

    shorts (9:16)  question  one exam-style scenario, a pause to pick, the reveal and the rule
                   trap      the tempting wrong answer: why it pulls you in and why PMI rejects it
                   term      two terms people confuse, side by side, with a one-line quiz
                   mindset   one rule the exam rewards, with a do / don't example
    long (16:9)    walkthrough  N bank questions walked through with the elimination logic
                   course       a full lesson: chapters, concept slides, examples, a check question per chapter

Questions come verbatim from the PMP Exam Lab question bank (pmp-simulator export), so the correct
answer is never invented. The LLM writes only the narration and the short on-screen wording.

    python -m pmp_video short question
    python -m pmp_video short trap --domain people
    python -m pmp_video short term --topic "Risk vs issue"
    python -m pmp_video long walkthrough --count 10 --approach agile
    python -m pmp_video long course --topic "Business Environment for the 2026 PMP" --minutes 12
    python -m pmp_video render output/pmp/<project>        # re-render a saved project
"""
