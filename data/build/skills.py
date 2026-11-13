"""Canonical skill names, synonyms and implications.

Used for gold labels and by the RAG code:
    canonical_skill("power bi")      -> "Microsoft Power BI"
    expand_skills(["scikit-learn"])  -> {"scikit-learn", "Machine Learning", "Python", "Artificial Intelligence", ...}
"""
from __future__ import annotations

import re

# canonical name -> synonyms (matching ignores case, spaces, dots and dashes)
SYNONYMS: dict[str, list[str]] = {
    "Python": ["python script", "python3", "python programming", "py"],
    "JavaScript": ["js", "javascript es6", "ecmascript", "vanilla js"],
    "TypeScript": ["ts"],
    "SQL": ["structured query language", "sql queries", "t-sql", "sql programming"],
    "MySQL": ["mysql programming"],
    "PostgreSQL": ["postgres", "psql"],
    "Microsoft SQL Server": ["mssql", "sql server"],
    "MongoDB": ["mongo"],
    "HTML": ["html5"],
    "CSS": ["css3", "css 3"],
    "React": ["reactjs", "react.js", "react js"],
    "Next.js": ["nextjs", "next js"],
    "Node.js": ["nodejs", "node js", "node"],
    "Express.js": ["express", "expressjs"],
    "Vue.js": ["vue", "vuejs"],
    "Angular": ["angularjs", "angular js"],
    "Django": [],
    "Flask": [],
    "FastAPI": ["fast api"],
    "GraphQL": [],
    "REST API": ["restful api", "rest", "api development", "api integration", "api", "web api"],
    "Docker": ["containers", "containerization"],
    "Kubernetes": ["k8s"],
    "Git": ["github", "version control"],
    "Linux": [],
    "DevOps": ["ci/cd", "cicd", "continuous integration"],
    "Amazon Web Services": ["aws", "amazon aws"],
    "AWS Lambda": ["lambda"],
    "Google Cloud Platform": ["gcp", "google cloud"],
    "Microsoft Azure": ["azure"],
    "Tailwind CSS": ["tailwind"],
    "Redux": [],
    "Stripe": ["stripe payments", "stripe api"],
    "Firebase": [],
    "Redis": [],
    "Web Development": ["web app development", "website development", "web application", "full stack development",
                        "full-stack development", "fullstack"],
    "Front-End Development": ["frontend", "front end", "frontend development"],
    "Back-End Development": ["backend", "back end", "backend development"],
    "Responsive Design": ["responsive web design"],
    "WordPress": ["wordpress development"],
    "Shopify": [],
    "Mobile App Development": ["mobile app", "mobile development", "app development"],
    "Machine Learning": ["ml", "machine learning model", "ml model", "supervised learning"],
    "Deep Learning": ["dl", "neural networks", "neural network", "artificial neural network"],
    "Artificial Intelligence": ["ai", "ai development"],
    "Natural Language Processing": ["nlp", "text mining", "text analytics"],
    "Computer Vision": ["cv", "image recognition", "image classification", "object detection"],
    "Image Processing": ["image analysis"],
    "OCR": ["optical character recognition", "text extraction from images"],
    "Speech Recognition": ["asr", "speech to text", "voice recognition"],
    "TensorFlow": ["tf", "keras"],
    "PyTorch": ["torch", "pytorch lightning"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "XGBoost": ["lightgbm", "gradient boosting"],
    "Hugging Face": ["huggingface", "transformers library"],
    "Large Language Models": ["llm", "llms", "gpt", "language models"],
    "OpenAI API": ["openai", "gpt-4 api", "gpt api"],
    "ChatGPT": ["chat gpt"],
    "LangChain": ["lang chain", "langgraph"],
    "Retrieval-Augmented Generation": ["rag", "retrieval augmented generation"],
    "Vector Databases": ["vector database", "pgvector", "pinecone", "faiss", "embeddings"],
    "Prompt Engineering": ["prompt design"],
    "Generative AI": ["genai", "generative ai development"],
    "Chatbot Development": ["chatbot", "bot development", "ai chatbot", "conversational ai"],
    "Recommendation Systems": ["recommender system", "recommendation engine"],
    "Predictive Modeling": ["predictive analytics", "forecasting model"],
    "Time Series Analysis": ["time series", "time series forecasting"],
    "MLOps": ["model deployment", "ml deployment", "model serving"],
    "Data Science": ["data scientist"],
    "Data Mining": [],
    "Data Scraping": ["web scraping", "scrapy", "web crawling", "data extraction", "scraper"],
    "Pandas": ["pandas dataframe"],
    "NumPy": [],
    "Statistics": ["statistical analysis", "statistical modeling", "statistical modelling"],
    "A/B Testing": ["ab testing", "split testing", "experimentation"],
    "Data Analysis": ["data analytics", "data analyst", "analytics", "data analyzing"],
    "Data Visualization": ["visualization", "dataviz", "charts", "data viz"],
    "Dashboard": ["dashboards", "dashboard development", "dashboard design"],
    "Business Intelligence": ["bi", "bi reporting"],
    "Microsoft Power BI": ["power bi", "powerbi", "microsoft powerbi"],
    "Tableau": ["tableau desktop", "tableau public"],
    "Looker Studio": ["google data studio", "data studio", "google looker studio"],
    "Microsoft Excel": ["excel", "ms excel", "advanced excel", "excel vba", "vba", "pivot tables"],
    "Google Sheets": ["google spreadsheet", "gsheets"],
    "R": ["r programming", "r language", "rstudio"],
    "ETL": ["etl pipeline", "data pipeline", "data integration"],
    "Data Engineering": ["data engineer", "data pipelines"],
    "Apache Airflow": ["airflow"],
    "dbt": ["data build tool"],
    "Data Warehousing": ["data warehouse", "bigquery", "snowflake", "redshift"],
    "Data Modeling": ["data modelling", "database modeling"],
    "Database Design": ["database architecture", "database development", "database"],
    "Data Cleaning": ["data cleansing", "data wrangling", "data preparation"],
    "Data Entry": ["data entry work", "copy paste"],
    "Reporting": ["report automation", "campaign reporting", "kpi reporting"],
    "Google Analytics": ["ga4", "google analytics 4", "universal analytics"],
    "Marketing Analytics": ["marketing analysis"],
    "Market Research": ["online research", "market analysis"],
    "Automation": ["workflow automation", "process automation", "zapier", "scripting"],
    "Selenium": ["browser automation"],
    "Apache Spark": ["spark", "pyspark"],
    "Jupyter": ["jupyter notebook", "notebooks"],
    "Social Media Marketing": ["smm"],
    "Search Engine Optimization": ["seo"],
    "Graphic Design": ["graphics design"],
    "3D Modeling": ["3d modelling", "3d design"],
}

# canonical name -> skills a person who knows it also has (applied transitively)
IMPLIES: dict[str, list[str]] = {
    "scikit-learn": ["Machine Learning", "Python"],
    "XGBoost": ["Machine Learning", "Python"],
    "PyTorch": ["Deep Learning", "Python"],
    "TensorFlow": ["Deep Learning", "Python"],
    "Deep Learning": ["Machine Learning"],
    "Machine Learning": ["Artificial Intelligence", "Data Science"],
    "Natural Language Processing": ["Machine Learning"],
    "Computer Vision": ["Deep Learning", "Image Processing"],
    "OCR": ["Computer Vision"],
    "Speech Recognition": ["Deep Learning"],
    "Hugging Face": ["Natural Language Processing", "Deep Learning", "Python"],
    "Large Language Models": ["Natural Language Processing", "Generative AI"],
    "OpenAI API": ["Large Language Models", "Generative AI"],
    "ChatGPT": ["Large Language Models", "Generative AI"],
    "LangChain": ["Large Language Models", "Python"],
    "Retrieval-Augmented Generation": ["Large Language Models", "Vector Databases"],
    "Prompt Engineering": ["Large Language Models"],
    "Chatbot Development": ["Natural Language Processing"],
    "Recommendation Systems": ["Machine Learning"],
    "Predictive Modeling": ["Machine Learning", "Statistics"],
    "Time Series Analysis": ["Statistics", "Predictive Modeling"],
    "MLOps": ["Docker", "DevOps", "Machine Learning"],
    "Pandas": ["Python", "Data Analysis"],
    "NumPy": ["Python"],
    "FastAPI": ["Python", "REST API", "Back-End Development"],
    "Flask": ["Python", "REST API", "Back-End Development"],
    "Django": ["Python", "Back-End Development", "Web Development"],
    "Jupyter": ["Python"],
    "Apache Spark": ["Data Engineering"],
    "Apache Airflow": ["Data Engineering", "ETL", "Python"],
    "dbt": ["Data Engineering", "SQL", "Data Modeling"],
    "ETL": ["Data Engineering"],
    "Data Warehousing": ["SQL", "Data Engineering"],
    "Data Cleaning": ["Data Analysis"],
    "Data Mining": ["Data Analysis"],
    "Data Scraping": ["Python"],
    "Microsoft Power BI": ["Business Intelligence", "Data Visualization", "Dashboard"],
    "Tableau": ["Business Intelligence", "Data Visualization", "Dashboard"],
    "Looker Studio": ["Business Intelligence", "Data Visualization", "Dashboard"],
    "Dashboard": ["Data Visualization"],
    "Business Intelligence": ["Data Analysis", "Reporting"],
    "Data Visualization": ["Data Analysis"],
    "Statistics": ["Data Analysis"],
    "A/B Testing": ["Statistics"],
    "Marketing Analytics": ["Data Analysis", "Google Analytics"],
    "Microsoft SQL Server": ["SQL"],
    "MySQL": ["SQL", "Database Design"],
    "PostgreSQL": ["SQL", "Database Design"],
    "SQL": ["Database Design"],
    "MongoDB": ["Database Design"],
    "Next.js": ["React", "JavaScript", "Web Development"],
    "React": ["JavaScript", "Front-End Development", "Web Development"],
    "Redux": ["React", "JavaScript"],
    "Vue.js": ["JavaScript", "Front-End Development", "Web Development"],
    "Angular": ["TypeScript", "Front-End Development", "Web Development"],
    "TypeScript": ["JavaScript"],
    "Express.js": ["Node.js", "JavaScript", "Back-End Development", "REST API"],
    "Node.js": ["JavaScript", "Back-End Development"],
    "GraphQL": ["REST API", "Back-End Development"],
    "Tailwind CSS": ["CSS", "Front-End Development"],
    "Front-End Development": ["HTML", "CSS", "JavaScript", "Web Development"],
    "Back-End Development": ["Web Development"],
    "Responsive Design": ["CSS", "Front-End Development"],
    "Stripe": ["REST API"],
    "Firebase": ["Back-End Development"],
    "Redis": ["Back-End Development"],
    "Kubernetes": ["Docker", "DevOps"],
    "Docker": ["DevOps"],
    "AWS Lambda": ["Amazon Web Services"],
    "Amazon Web Services": ["DevOps"],
    "Google Cloud Platform": ["DevOps"],
    "Microsoft Azure": ["DevOps"],
    "Selenium": ["Automation", "Python"],
    "Microsoft Excel": ["Data Analysis"],
    "Google Sheets": ["Data Analysis"],
}


def _key(text: str) -> str:
    return re.sub(r"[\s._\-/]+", "", text.lower())


_LOOKUP: dict[str, str] = {}
for _name, _syns in SYNONYMS.items():
    _LOOKUP[_key(_name)] = _name
    for _s in _syns:
        _LOOKUP.setdefault(_key(_s), _name)
for _name in IMPLIES:
    _LOOKUP.setdefault(_key(_name), _name)


def canonical_skill(name: str) -> str:
    """Return the canonical name of a skill; unknown skills come back stripped but unchanged."""
    name = name.strip()
    return _LOOKUP.get(_key(name), name)


def expand_skills(skills: list[str] | set[str]) -> set[str]:
    """Canonical skills plus everything they imply (transitively)."""
    result: set[str] = set()
    todo = [canonical_skill(s) for s in skills if s and s.strip()]
    while todo:
        skill = todo.pop()
        if skill in result:
            continue
        result.add(skill)
        todo.extend(IMPLIES.get(skill, []))
    return result
