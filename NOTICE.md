# Third-party sources and components

## Data sources

The pipeline reads publicly available feeds. Content belongs to each publisher. For news sources this repository stores only the headline, a link to the original and Juniper Resilience's own tags and scores, not article text. Check each provider's terms before any commercial redistribution.

| Source | Use | Terms to check |
|---|---|---|
| U.S. State Department travel advisories | Advisory changes | U.S. government work, generally public domain |
| UK FCDO travel advice | Advisory changes | Open Government Licence v3.0 |
| CDC travel health notices | Health alerts | U.S. government work, generally public domain |
| USGS earthquake feed | Earthquakes | U.S. government work, public domain |
| GDACS | Disaster alerts | GDACS terms of use |
| ReliefWeb | Humanitarian updates | ReliefWeb terms; content owned by each contributing organisation |
| UN News | News headlines | UN terms of use |
| BBC, Al Jazeera, France 24, DW, The Guardian, NPR, Africanews, Kyiv Independent, Times of Israel | News headlines and links | Each publisher's RSS terms (typically personal, non-commercial use of headlines with a link back) |
| GDELT Project | News discovery | Free and open; cite "The GDELT Project" |
| Telegram public channels, Bluesky (off by default) | Unverified tips | Platform terms of service |

Country and city reference data derive from the Juniper Resilience Global Risk Matrix 2026, which itself draws on the sources listed in its Methodology tab.

## Software components

| Component | Licence | How it is used |
|---|---|---|
| D3.js | ISC | Loaded from cdnjs in the dashboard |
| TopoJSON client | ISC | Loaded from cdnjs in the dashboard |
| world-atlas (Natural Earth boundaries) | ISC; Natural Earth data is public domain | Loaded from jsDelivr for the map |
| feedparser | BSD 2-Clause | Python dependency |
| requests | Apache 2.0 | Python dependency |
| Manrope font | SIL Open Font Licence 1.1 | Loaded from Google Fonts |
