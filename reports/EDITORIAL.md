# Juniper Global Outlook

Geopolitical developments, community resilience, and potential downstream exposure.

Write for the reader in the direct voice of a geopolitical assessment. Start with the development, then carry its implications through the paragraph. No conversational explanation of the product, academic framing, or instructions to the reader. Use natural constructions such as “possibly prolonging procurement uncertainty” and “potentially constraining output” when the link is assessed rather than documented. Qualifiers must reflect evidence, not merely soften unsupported claims.

Mission-driven organizations and affected communities remain central. Trace specific exposure through livelihoods, workforce, production, logistics, commodity buyers, financing and reputation where evidence supports the connection. Name the NGO response when verified. Do not invent buyer, lender or project relationships. Equator Principles apply only within their financing scope.

## Edition structure

- Publication date and information cutoff, both with explicit timezones.
- Global assessment and three to five major developments.
- Americas, Europe, Middle East and North Africa, Sub-Saharan Africa, Asia-Pacific. Split geography this way to avoid overlapping EMEA and MENA coverage.
- Each regional development: dated evidence, relevant NGO activity, potential downstream effects, a time-bounded outlook, confidence and indicators that could overturn it.
- Sources with original URLs, publication dates and access dates.

## Selection and evidence

Select subjects by material change since the previous edition, mission relevance, impact, evidence quality and cross-regional spillover. Do not repeat a topic without a material update. Regions with insufficient verified material can be omitted and the coverage limitation stated. No forced regional filler.

Separate reported facts from analysis within each entry. Reverify all earlier conversational examples, including El Niño status, USMCA developments, mine operating status and aid statistics. Historical analogues require dates and comparable conditions; they do not establish current losses. Numerical probabilities require a defensible method. Use qualitative confidence with a reason otherwise.

Use a 30 to 90 day outlook where suitable, with explicit assumptions and disconfirming indicators. Charts require sourced data, units and dates. No invented aggregate costs or causal connections.

## Publishing

The live security feed supplies leads, not sufficient evidence for this product. Research and synthesis must precede review. Store editions as JSON using the example structure, then publish through `python pipeline/publish_outlook.py reports/edition.json`. Only a reviewed edition with `status: published` is accepted. The website opens the latest published edition and keeps an archive. Generating researched drafts automatically requires a research/model provider and a separate workflow; the current feed does not provide that capability.
