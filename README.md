Version 2.0 \

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
