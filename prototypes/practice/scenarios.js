/* V2-009: public fictional examples. Authored coaching, not live model evaluations. */
const sampleRoles = {
  backend: {
    name: "Backend engineer",
    summary: "Build reliable services and explain technical decisions.",
    topics: "Ownership, reliable updates, and technical tradeoffs.",
    background: "API and database projects",
    focus: "Technical depth",
    question: "How did you make the inventory update safe to retry?",
    contextQuestion:
      "Your sample resume describes inventory services. How did you make an update safe to retry?",
    original:
      "I built the inventory update endpoint. I used a client supplied idempotency key and a unique database constraint. I stored the result in the same transaction as the update, so a retry returned the saved result. In a sample test with one hundred requests, including twenty duplicates, each unique update applied once. The tradeoff was storing request results and deciding when to expire them.",
    retry:
      "My goal was to prevent duplicate inventory updates when clients retried. I owned the endpoint and stored the idempotency key, update, and result in one transaction. In a sample test of 100 requests with 20 duplicates, each unique update applied once. The storage cost meant we also needed an expiry policy.",
    opening: "I built the inventory update endpoint.",
    revisedOpening:
      "My goal was to prevent duplicate inventory updates when clients retried.",
    result:
      "In a sample test with one hundred requests, including twenty duplicates, each unique update applied once.",
    observation:
      "The answer opens with the endpoint you built, then names the implementation.",
    suggestion:
      "Start by explaining that retries could apply the same update twice.",
    strength:
      "You cite 100 requests, 20 duplicates, and one update per unique request.",
    suggestedOpening:
      "I needed retries to be safe, so a duplicated request could not change inventory twice.",
    coverage:
      "This answer explains reliable updates. It does not yet show how you would handle other engineering challenges.",
    followup: "How would you decide when to expire the saved results?",
    mockFollowup:
      "What tradeoff would you explain to the team before shipping this?",
    clarityQuestion:
      "How would you explain the purpose of safe retries to a colleague outside engineering?",
    clarityFollowup:
      "How would you explain the storage cost without using database terminology?",
    next: "Practice explaining the expiry tradeoff.",
    audio: "/sample-answer.wav",
    times: { gap: [0, 3], strength: [12, 19] },
  },
  product: {
    name: "Product manager",
    summary: "Understand customer needs and make clear product decisions.",
    topics: "Prioritization, customer evidence, and product outcomes.",
    background: "Customer research and onboarding improvements",
    focus: "Prioritization",
    question: "How did you decide which onboarding improvement to prioritize?",
    contextQuestion:
      "Your sample resume describes onboarding research. How did you choose the first improvement?",
    original:
      "I added a guided checklist to onboarding. I spoke with eight new customers and saw that six could not find the first setup step. I compared a checklist with a full redesign and chose the smaller change. In a fictional pilot, 14 of 20 customers completed setup, compared with 9 of 20 before. The pilot was small, so I planned another round before expanding it.",
    retry:
      "My goal was to help new customers complete setup. I owned the research and prioritized a guided checklist after six of eight customers struggled to find the first step. I chose it over a full redesign because we could test it sooner. In a fictional pilot, 14 of 20 completed setup, compared with 9 of 20 before. I would check the result with a larger group before expanding it.",
    opening: "I added a guided checklist to onboarding.",
    revisedOpening: "My goal was to help new customers complete setup.",
    result:
      "In a fictional pilot, 14 of 20 customers completed setup, compared with 9 of 20 before.",
    observation:
      "The answer names the checklist before explaining the customer problem.",
    suggestion: "Open with the difficulty customers faced when starting setup.",
    strength:
      "You compare setup completion before and after the change and acknowledge the small pilot.",
    suggestedOpening:
      "I wanted to help customers find the first setup step and complete onboarding.",
    coverage:
      "This answer covers one prioritization decision. It does not establish a repeatable improvement across all customers.",
    followup: "What evidence would make you reconsider the checklist?",
    mockFollowup:
      "How would you handle a stakeholder asking for the full redesign instead?",
    clarityQuestion:
      "How would you explain your onboarding decision to a colleague unfamiliar with the project?",
    clarityFollowup:
      "How would you summarize the customer problem in one sentence?",
    next: "Practice explaining how you would validate the pilot result.",
  },
  success: {
    name: "Customer success manager",
    summary:
      "Support customers, set expectations, and build lasting relationships.",
    topics: "Customer needs, clear communication, and follow-through.",
    background: "Customer onboarding and account support",
    focus: "Customer communication",
    question: "How did you help a customer whose onboarding had stalled?",
    contextQuestion:
      "Your sample resume describes account support. How did you help a customer resume onboarding?",
    original:
      "I arranged weekly calls with the customer. Their team had missed two onboarding milestones because nobody owned the training plan. I agreed on one owner and a short schedule with the account lead. The customer completed both outstanding milestones within three weeks. I kept the first sessions small so the customer could fit them around daily work.",
    retry:
      "My goal was to get the customer back on track without adding pressure to their team. I found that the training plan had no owner, then agreed on one owner and a short schedule with the account lead. The customer completed both outstanding milestones within three weeks. I kept sessions small and checked that the schedule was manageable.",
    opening: "I arranged weekly calls with the customer.",
    revisedOpening:
      "My goal was to get the customer back on track without adding pressure to their team.",
    result:
      "The customer completed both outstanding milestones within three weeks.",
    observation:
      "The answer opens with meetings before explaining why onboarding stalled.",
    suggestion:
      "State the customer's difficulty first, then explain how you agreed on a practical next step.",
    strength:
      "You describe an agreed owner and a specific result within three weeks.",
    suggestedOpening:
      "The customer had missed two milestones because the training plan had no owner.",
    coverage:
      "This answer covers an onboarding recovery. It does not demonstrate renewal outcomes or long-term satisfaction.",
    followup:
      "How would you check that the customer could keep making progress independently?",
    mockFollowup:
      "How would you respond if the customer asked for a deadline you could not meet?",
    clarityQuestion:
      "How would you briefly explain the customer's difficulty and your response to an account lead?",
    clarityFollowup: "Which detail best explains why the weekly calls helped?",
    next: "Practice setting realistic expectations with a customer.",
  },
  finance: {
    name: "Finance analyst",
    summary:
      "Explain financial results and support practical business decisions.",
    topics: "Forecasting, variance analysis, and business communication.",
    background: "Monthly forecasts and budget reviews",
    focus: "Financial analysis",
    question: "How did you investigate an unexpected spending variance?",
    contextQuestion:
      "Your sample resume describes budget reviews. How did you investigate a spending variance?",
    original:
      "I built a monthly variance report. Marketing spending was 12 percent above budget, so I reconciled invoices with the campaign schedule. Most of the difference came from a campaign brought forward from the next month. I separated timing from additional spending and updated the forecast with the budget owner. The revised quarter forecast was 2 percent above budget rather than 12 percent.",
    retry:
      "My goal was to explain whether higher spending would affect the quarter. I reconciled campaign invoices after monthly marketing spending came in 12 percent above budget. Most of the difference was timing, so I separated it from additional spending and updated the forecast with the budget owner. The revised quarter forecast was 2 percent above budget. I would continue checking new commitments before treating that estimate as final.",
    opening: "I built a monthly variance report.",
    revisedOpening:
      "My goal was to explain whether higher spending would affect the quarter.",
    result:
      "The revised quarter forecast was 2 percent above budget rather than 12 percent.",
    observation:
      "The answer names the report before explaining the business question it answered.",
    suggestion:
      "Explain that you needed to distinguish a timing difference from additional spending.",
    strength:
      "You reconcile invoices, involve the budget owner, and distinguish the monthly variance from the quarter forecast.",
    suggestedOpening:
      "I needed to establish whether the spending increase would change our quarter forecast.",
    coverage:
      "This answer covers one spending variance. A revised forecast is an estimate, not a realized saving.",
    followup:
      "What would you check before relying on the revised quarter forecast?",
    mockFollowup:
      "How would you explain the remaining overspend to a budget owner?",
    clarityQuestion:
      "How would you explain a timing variance to a budget owner without finance experience?",
    clarityFollowup:
      "How would you distinguish a forecast change from a cost saving?",
    next: "Practice explaining the uncertainty in a forecast.",
  },
};

function sampleScenario(roleId, goal, includeResume = false) {
  const role = sampleRoles[roleId];
  const clarity = goal === "Clarity";
  return {
    ...role,
    question: clarity
      ? role.clarityQuestion
      : includeResume
        ? role.contextQuestion
        : role.question,
    followup: clarity ? role.clarityFollowup : role.followup,
    title: clarity
      ? "Make the purpose clear before the detail."
      : "Start with the problem you solved.",
    lede: clarity
      ? "Give your listener the context they need to follow your answer."
      : "Explain the goal first, then describe your approach.",
    observation: clarity
      ? `${role.observation} A listener unfamiliar with the work has to infer its purpose.`
      : role.observation,
    suggestion: clarity
      ? `Use everyday language to explain the purpose. ${role.suggestion}`
      : role.suggestion,
    next: clarity
      ? "Practice explaining the result in one clear sentence."
      : role.next,
  };
}
