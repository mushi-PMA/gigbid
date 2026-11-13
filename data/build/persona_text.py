"""Phrase pools for rendering persona documents. Variation is on purpose: the same project must read differently
in a case study, a README and a proposal, and implied skills must show up only through what was done."""
from __future__ import annotations

# How an explicit skill is mentioned. Three registers: story (case study), technical (README), pitch (proposal).
EXPLICIT_STORY = [
    "I built the core in {s}.", "{s} did most of the heavy lifting.", "The team already knew {s}, so I used it.",
    "Most of the work was done with {s}.", "I picked {s} because it kept the code short and testable.",
    "{s} was the main tool here.", "I used {s} for the central part of the solution.",
]
EXPLICIT_TECH = [
    "Built with {s}.", "Uses {s}.", "{s} for the main logic.", "Stack: {s}.", "Implemented in {s}.",
    "Relies on {s}.",
]
EXPLICIT_PITCH = [
    "I used {s} for it.", "It was built with {s}.", "The stack was {s}.", "{s} was central to the work.",
]

# Implied skills: what was done, without naming the skill. Several phrasings per skill.
CLUES: dict[str, list[str]] = {
    "OCR": ["Scanned pages were first turned into lines of text with positions before any model saw them.",
            "A pre-step reads characters off photographed pages so the model works on plain text.",
            "Pages that arrive as pictures go through a text-recognition step first."],
    "Docker": ["The service ships as one image that runs the same on a laptop and in the cloud.",
               "Everything starts with a single compose command on any machine.",
               "Deployments use a pinned build recipe so library versions never drift."],
    "MLOps": ["Every model version is tracked, tested on a frozen set and promoted by a script.",
              "A monitoring job compares live inputs with the training data and alerts on drift.",
              "Retraining runs on a schedule and the old model stays live until the new one beats it."],
    "A/B Testing": ["New versions ran against the old one on a random half of traffic before full rollout.",
                    "Users were split at random and the difference was read with confidence intervals."],
    "Apache Airflow": ["A nightly DAG pulls yesterday's data and rebuilds the tables.",
                       "Scheduled tasks with retries and dependencies run every night at 02:00."],
    "Data Engineering": ["I built the pipelines that land raw feeds into clean tables.",
                         "The nightly loads and the tables other teams query were part of the job."],
    "Image Processing": ["Frames are cropped, normalised and de-noised before the network sees them.",
                         "Lighting correction and resizing steps sit in front of the model."],
    "Vector Databases": ["Passages are stored as embeddings and fetched by similarity.",
                         "A nearest-neighbour lookup over stored passage embeddings finds candidate text."],
    "Prompt Engineering": ["I wrote and versioned the instructions given to the language model and tested every wording change.",
                           "System messages were iterated against a fixed set of questions."],
    "FastAPI": ["Typed Python endpoints validate each request and publish interactive docs for free.",
                "The model sits behind async Python endpoints with request validation."],
    "Statistics": ["Effects were checked with confidence intervals and significance tests.",
                   "Proper sampling and hypothesis tests replaced eyeballing charts."],
    "Pandas": ["Tabular preparation was done in dataframes, with checks after every merge.",
               "Joins, group-bys and reshaping lived in short dataframe functions."],
    "Large Language Models": ["A hosted large model drafts the text from the raw input.",
                              "A general-purpose language model writes the first version and rules check it."],
    "Amazon Web Services": ["It runs on S3 buckets, queues and EC2 instances with least-privilege roles.",
                            "Storage is S3 and compute is EC2 behind a load balancer."],
    "Redis": ["Hot lookups are served from an in-memory key-value store with expiry.",
              "Recent results are cached in memory so repeat requests return in milliseconds."],
    "Data Visualization": ["Weekly charts show the trend by topic and location.",
                           "Managers see trend charts instead of tables."],
    "Data Scraping": ["A scheduled collector fetches pages politely, respecting rate limits and robots rules."],
    "Mobile App Development": ["The model was shrunk to run on a phone and works offline."],
    "DevOps": ["Every merge runs the tests and builds a release automatically.",
               "A pipeline checks and deploys each commit."],
    "AWS Lambda": ["Event-driven functions handle each call, so there is no server to look after."],
    "Stripe": ["Card payments go through a hosted payment provider, and webhooks confirm every charge.",
               "Checkout sessions and webhook handling cover payments, refunds and failed charges."],
    "PostgreSQL": ["A relational database with migrations and indexes handles the busy queries.",
                   "SQL tables with foreign keys, migrations and a few partial indexes sit underneath."],
    "TypeScript": ["All code is typed end to end, with shared types between browser and server.",
                   "Types shared between the browser and the server caught most integration bugs early."],
    "REST API": ["A JSON API that both web and mobile clients call, with documented endpoints.",
                 "Documented HTTP endpoints serve the front end."],
    "Responsive Design": ["Layouts adapt from phone to wide desktop; small screens came first.",
                          "It works comfortably on small screens."],
    "Dashboard": ["One screen of live tables and charts for the operations team.",
                  "A single page gives managers live numbers and filters."],
    "Automation": ["A scheduled script replaces the manual steps and runs unattended every morning.",
                   "The refresh runs by itself and emails the result."],
    "Front-End Development": ["I hand-tuned the browser side: bundle size, rendering and keyboard use."],
    "Business Intelligence": ["A governed reporting layer serves the whole business with agreed definitions."],
    "Data Modeling": ["Fact and dimension tables are arranged in a star layout with agreed definitions.",
                      "A shared model holds the definitions once, so every report agrees."],
    "Data Cleaning": ["Duplicates were removed, formats fixed and missing values handled before any analysis.",
                      "Inconsistent records were tidied first, with a log of every change."],
    "ETL": ["Extract, reshape and load steps feed the reporting tables each night."],
    "Marketing Analytics": ["Ad spend was joined with orders to see return per channel."],
    "Time Series Analysis": ["Seasonality, holidays and trend are handled by week and by day."],
    "Data Warehousing": ["A central analytics store sits apart from the live application database."],
    "Predictive Modeling": ["A model predicts next week's values from past patterns."],
    "Reporting": ["A scheduled pack goes to the board with the same layout every period."],
    "Python": ["The glue and tooling are scripts in the language data teams use every day."],
    "Tailwind CSS": ["Styling is utility classes written directly in the markup."],
}

CONTEXT_STORY = [
    "In {year} a {client_type} in {industry} asked me to {problem}.",
    "The client, a {client_type} working in {industry}, wanted to {problem}.",
    "Brief ({year}, {industry}): {problem}.",
    "A {client_type} in the {industry} sector came to me in {year}. They needed to {problem}.",
]
RESULT_STORY = ["Result: {metric}.", "Outcome: {metric}.", "What changed: {metric}.", "After launch: {metric}."]
LESSONS = [
    "I would agree the definition of success with the client earlier next time.",
    "A small first release with real users taught us more than the planning did.",
    "Most of the delay came from waiting for access, so I now ask for it in week one.",
    "Handover notes and a recorded walkthrough made the last week calm.",
    "I kept a short decision log, which saved a long meeting when priorities changed.",
    "Weekly demos kept the client close to the work and removed surprises.",
]
README_NOTES = [
    "See the case study for the business background.", "Tests live next to the code they cover.",
    "Config is read from environment variables.", "Sample data is synthetic.",
    "Pull requests need a passing test run.",
]
SETUP = {
    "Python": "python -m venv .venv\nsource .venv/bin/activate\npip install -r requirements.txt\npytest -q",
    "TypeScript": "npm ci\nnpm run dev\nnpm test",
    "R": "Rscript -e 'renv::restore()'\nRscript analysis/run_all.R",
}

# --- proposals --------------------------------------------------------------------------------------------
GENERIC_OPENINGS = [
    "Dear Sir/Madam, I am the perfect fit for your project.",
    "Hello, I have read your job post and I am very interested. I have more than 10 years of experience and can start immediately.",
    "Greetings! I can do this job. Please check my profile and give me a chance.",
    "Dear Hiring Manager, I am an expert in everything you need and I will deliver 100% quality.",
    "Hi, I am very excited about your project. I am hardworking and honest and I will finish on time.",
]
SEMI_OPENINGS = [
    "Hi, I read your post titled \"{title}\".", "Hello, thanks for posting \"{title}\".",
    "Hi there, I am replying to your job \"{title}\".",
]
PERSONAL_OPENINGS = [
    "You wrote \"{snippet}\", and the part about {skill} is what I work on most days.",
    "Your post says \"{snippet}\". That matches a project I delivered recently, so I know where the tricky parts are.",
    "The detail \"{snippet}\" tells me you need someone comfortable with {skill} and {skill2}, which is my daily work.",
    "I noticed \"{snippet}\" in your brief. With {skill} that is a few days of focused work, and I can show you a similar one.",
]
EVIDENCE_PARAS = [
    "Recently I built {short} for a {client_type} in {industry}. {clue} The result: {metric}.",
    "A close match is {short} I delivered in {year}. {explicit} The result: {metric}.",
    "In {year} I made {short} for a {client_type} ({industry}). {clue} Outcome: {metric}.",
    "For a similar need I created {short}. {explicit} It worked out well: {metric}.",
]
PLAN_PARAS = [
    "My plan: confirm the inputs and success measure with you on day one, deliver a first working version in about a week, and then improve it with your feedback. I would use {skills}.",
    "I would start with a short call to agree the scope, then build in small steps with a demo every few days. The work needs {skills}.",
    "Approach: look at your real data or pages first, build the smallest useful version with {skills}, test it, then hand over with notes.",
]
QUESTIONS = [
    "One question: what does a good result look like for you in the first month?",
    "Quick question: do you already have sample data or access I can start with?",
    "Could you tell me who will review the first version on your side?",
    "Which part is most urgent for you, speed or polish?",
]
CLOSINGS = ["Happy to start this week.", "I can share more detail on request.", "Thanks for reading.",
            "Let me know if a short call works.", "Best regards,"]
FILLER_LONG = [
    "I care a lot about communication, so you will get a short written update at the end of every working day.",
    "I document decisions as I go so that anyone on your team can pick the work up later.",
    "I test my work before showing it and I keep changes small so they are easy to review.",
    "If something in the scope turns out to be unclear, I raise it early instead of guessing.",
    "I have worked with clients across several time zones and I keep overlap hours for calls.",
]

# --- reviews ---------------------------------------------------------------------------------------------
REVIEWS = [
    ("She rebuilt how our {industry} team handles this part of the business. {outcome_phrase}. Clear updates all the way.", 5),
    ("We hired for the {industry} piece last year and it paid for itself quickly. {outcome_phrase}.", 5),
    ("Reliable, asks the right questions and delivers early. The {industry} work is still running without trouble.", 5),
    ("Good technical judgement. {outcome_phrase}. Communication could be quicker on Fridays, but the quality is high.", 4),
    ("Took a messy brief from our {industry} operation and made it simple. {outcome_phrase}.", 5),
    ("Solid work. The first version needed two rounds of changes, and the final result was what we wanted.", 4),
    ("Honest about what is possible. We saved money because the plan was scoped properly. {outcome_phrase}.", 5),
    ("The project for our {industry} unit finished a week late but the result was worth it. {outcome_phrase}.", 4),
    ("Very easy to work with and good documentation at handover. Our own team could take over without a call.", 5),
    ("Exactly what we needed for the {industry} work. {outcome_phrase}. Would hire again.", 5),
    ("Professional and calm under pressure when our requirements changed mid-way.", 5),
    ("Delivered what was agreed, nothing more. Fair price and no surprises.", 4),
]
CLIENT_NAMES = ["Northwind Studio", "Brightline Foods", "Harbor Logistics", "Kestrel Health", "Oakmont Retail",
                "Lumen Learning", "Bluepeak Travel", "Redwood Insurance", "Sable Media", "Greenfield Energy",
                "Pinecrest Legal", "Atlas Payments", "Copperline Hotels", "Meridian Staffing", "Fernhill Charity",
                "Quartz Software", "Summit Wellness", "Tidewater Marine", "Ironbridge Parts", "Cedar & Co"]
