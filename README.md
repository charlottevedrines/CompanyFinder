# Repo under construction

## Project overview

We are building an AI agent that automates the search for small French IT services companies (ESNs, with 10 to 50 employees) that are likely to be put up for sale. This is one of the most active M&A segments in France, because private equity funds and large IT groups buy small ESNs and merge them into bigger competitors.

These companies often share a profile: a founder-CEO in their late career, often alone at the helm for 15 to 20 years, whose business depends on a personal client network. When that person nears retirement with no successor, a sale becomes almost inevitable. Our signals target that profile: the CEO’s age and tenure, the absence of a co-manager, the creation of a holding company, and stagnating revenue.

## Target users
PE funds, specialized IT brokers and corporate development teams. They currently find these companies by cold-calling and word of mouth, and the agent automates that prospecting.

## Repo architecture 
project/\
├── main.py                 # Starts the workflow\
├── orchestrator.py         # Decides what to do next\
├── runner.py               # Executes tools and updates state\
├── models.py               # Shared input/output structures\
├── storage.py              # Loads input and saves results\
├── tools/\
│   ├── __init__.py\
│   ├── registry.py         # Available tools and their descriptions\
│   ├── company_enrichment.py\
│   └── website_search.py\
└── tests/\
    └── ...\

### Scope of the project: 
- Company type: ESN
- Country: France
