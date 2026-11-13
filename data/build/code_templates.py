"""Small, real-looking code files used in the persona repos.

Placeholders: @ENTITY@ (snake case), @Entity@ (Pascal case), @ENTITIES@ (plural), @F1@, @F2@, @F3@ (field names).
Each kind maps to (relative path, source text). No skill name is written in a comment unless real code would.
"""

TEMPLATES: dict[str, tuple[str, str]] = {
    "fastapi_service": ("src/@ENTITY@/api.py", '''from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from .model import load_model

app = FastAPI(title="@Entity@ service")
model = load_model()


class @Entity@Request(BaseModel):
    @F1@: str
    @F2@: float | None = None
    @F3@: str | None = None


class @Entity@Response(BaseModel):
    label: str
    score: float


@app.get("/health")
def health() -> dict:
    return {"ok": True}


@app.post("/score", response_model=@Entity@Response)
def score(request: @Entity@Request) -> @Entity@Response:
    if not request.@F1@.strip():
        raise HTTPException(status_code=422, detail="@F1@ is empty")
    label, probability = model.predict(request.model_dump())
    return @Entity@Response(label=label, score=round(probability, 4))
'''),

    "pytorch_train": ("src/@ENTITY@/train.py", '''import torch
from torch import nn
from torch.utils.data import DataLoader, Dataset


class @Entity@Dataset(Dataset):
    def __init__(self, features: torch.Tensor, labels: torch.Tensor):
        self.features, self.labels = features, labels

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, index: int):
        return self.features[index], self.labels[index]


def build_network(input_size: int, classes: int) -> nn.Module:
    return nn.Sequential(
        nn.Linear(input_size, 256), nn.ReLU(), nn.Dropout(0.2),
        nn.Linear(256, 64), nn.ReLU(),
        nn.Linear(64, classes),
    )


def train(dataset: Dataset, input_size: int, classes: int, epochs: int = 12, lr: float = 3e-4) -> nn.Module:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    network = build_network(input_size, classes).to(device)
    optimiser = torch.optim.AdamW(network.parameters(), lr=lr, weight_decay=1e-2)
    loss_fn = nn.CrossEntropyLoss()
    loader = DataLoader(dataset, batch_size=64, shuffle=True)
    for epoch in range(epochs):
        total = 0.0
        for batch_x, batch_y in loader:
            batch_x, batch_y = batch_x.to(device), batch_y.to(device)
            optimiser.zero_grad()
            loss = loss_fn(network(batch_x), batch_y)
            loss.backward()
            optimiser.step()
            total += loss.item() * len(batch_y)
        print(f"epoch {epoch + 1}: loss {total / len(dataset):.4f}")
    return network
'''),

    "sklearn_pipeline": ("src/@ENTITY@/pipeline.py", '''import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

TEXT_OR_CATEGORY = ["@F1@", "@F3@"]
NUMBERS = ["@F2@"]


def build_pipeline() -> Pipeline:
    prepare = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore"), TEXT_OR_CATEGORY),
        ("numbers", StandardScaler(), NUMBERS),
    ])
    return Pipeline([("prepare", prepare), ("model", GradientBoostingClassifier(random_state=7))])


def run(path: str, target: str = "label") -> Pipeline:
    data = pd.read_csv(path).dropna(subset=[target])
    x_train, x_test, y_train, y_test = train_test_split(
        data.drop(columns=[target]), data[target], test_size=0.2, stratify=data[target], random_state=7)
    pipeline = build_pipeline().fit(x_train, y_train)
    print(classification_report(y_test, pipeline.predict(x_test)))
    return pipeline
'''),

    "airflow_dag": ("dags/@ENTITY@_nightly.py", '''from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

from @ENTITY@.jobs import extract_source, rebuild_features, publish_table

default_args = {"owner": "data", "retries": 2, "retry_delay": timedelta(minutes=10)}

with DAG(
    dag_id="@ENTITY@_nightly",
    start_date=datetime(2025, 1, 1),
    schedule="0 2 * * *",
    catchup=False,
    default_args=default_args,
) as dag:
    extract = PythonOperator(task_id="extract_source", python_callable=extract_source)
    features = PythonOperator(task_id="rebuild_features", python_callable=rebuild_features)
    publish = PythonOperator(task_id="publish_table", python_callable=publish_table)
    extract >> features >> publish
'''),

    "pandas_etl": ("etl/clean_@ENTITIES@.py", '''import pandas as pd


def load(path: str) -> pd.DataFrame:
    frame = pd.read_csv(path, dtype=str)
    frame.columns = [c.strip().lower().replace(" ", "_") for c in frame.columns]
    return frame


def clean(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.drop_duplicates()
    frame["@F1@"] = frame["@F1@"].str.strip().str.title()
    frame["@F2@"] = pd.to_numeric(frame["@F2@"].str.replace(r"[^0-9.\\-]", "", regex=True), errors="coerce")
    frame["@F3@"] = pd.to_datetime(frame["@F3@"], errors="coerce")
    missing = frame[["@F1@", "@F2@"]].isna().any(axis=1)
    print(f"dropping {int(missing.sum())} rows with missing keys")
    return frame[~missing]


def monthly_summary(frame: pd.DataFrame) -> pd.DataFrame:
    return (frame.assign(month=frame["@F3@"].dt.to_period("M"))
                 .groupby("month")["@F2@"].agg(["count", "sum", "mean"]).reset_index())


if __name__ == "__main__":
    print(monthly_summary(clean(load("data/@ENTITIES@.csv"))).tail(12))
'''),

    "rag_index": ("src/@ENTITY@/search.py", '''import numpy as np
from openai import OpenAI

client = OpenAI()
EMBED_MODEL = "text-embedding-3-small"


def chunk(text: str, size: int = 900, overlap: int = 150) -> list[str]:
    pieces, start = [], 0
    while start < len(text):
        pieces.append(text[start:start + size])
        start += size - overlap
    return pieces


def embed(texts: list[str]) -> np.ndarray:
    response = client.embeddings.create(model=EMBED_MODEL, input=texts)
    vectors = np.array([item.embedding for item in response.data], dtype="float32")
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


class Index:
    def __init__(self, documents: list[str]):
        self.chunks = [piece for doc in documents for piece in chunk(doc)]
        self.vectors = embed(self.chunks)

    def search(self, question: str, k: int = 5) -> list[tuple[float, str]]:
        scores = self.vectors @ embed([question])[0]
        best = np.argsort(-scores)[:k]
        return [(float(scores[i]), self.chunks[i]) for i in best]


def answer(index: Index, question: str) -> str:
    context = "\\n---\\n".join(text for _, text in index.search(question))
    reply = client.chat.completions.create(
        model="gpt-4o-mini", temperature=0,
        messages=[{"role": "system", "content": "Answer only from the context. Quote the clause."},
                  {"role": "user", "content": f"Context:\\n{context}\\n\\nQuestion: {question}"}])
    return reply.choices[0].message.content
'''),

    "transformers_infer": ("src/@ENTITY@/infer.py", '''from transformers import pipeline

_classifier = None


def get_classifier(model_name: str = "distilbert-base-uncased-finetuned-sst-2-english"):
    global _classifier
    if _classifier is None:
        _classifier = pipeline("text-classification", model=model_name, truncation=True, max_length=256)
    return _classifier


def score_batch(texts: list[str], batch_size: int = 16) -> list[dict]:
    results = get_classifier()(texts, batch_size=batch_size)
    return [{"@F1@": text, "label": r["label"].lower(), "confidence": round(r["score"], 3)}
            for text, r in zip(texts, results)]
'''),

    "time_series_features": ("src/@ENTITY@/features.py", '''import pandas as pd
import xgboost as xgb


def add_lags(frame: pd.DataFrame, target: str, lags=(1, 7, 14, 28)) -> pd.DataFrame:
    frame = frame.sort_values(["@F1@", "date"]).copy()
    for lag in lags:
        frame[f"{target}_lag_{lag}"] = frame.groupby("@F1@")[target].shift(lag)
    frame[f"{target}_roll_7"] = frame.groupby("@F1@")[target].transform(lambda s: s.shift(1).rolling(7).mean())
    frame["dow"] = frame["date"].dt.dayofweek
    frame["month"] = frame["date"].dt.month
    return frame.dropna()


def fit_forecaster(frame: pd.DataFrame, target: str, cutoff: str):
    features = [c for c in frame.columns if c.startswith(target + "_") or c in ("dow", "month")]
    train, valid = frame[frame["date"] < cutoff], frame[frame["date"] >= cutoff]
    model = xgb.XGBRegressor(n_estimators=400, learning_rate=0.05, max_depth=6, subsample=0.8)
    model.fit(train[features], train[target], eval_set=[(valid[features], valid[target])], verbose=False)
    error = (model.predict(valid[features]) - valid[target]).abs().mean()
    print(f"validation MAE: {error:.2f}")
    return model
'''),

    "dockerfile": ("Dockerfile", '''FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY src ./src
EXPOSE 8000
HEALTHCHECK CMD python -c "import urllib.request as u; u.urlopen('http://localhost:8000/health')"
CMD ["uvicorn", "src.@ENTITY@.api:app", "--host", "0.0.0.0", "--port", "8000"]
'''),

    "dockerfile_node": ("Dockerfile", '''FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM node:20-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
EXPOSE 3000
CMD ["node", "dist/server.js"]
'''),

    "ab_test_stats": ("analysis/@ENTITY@_test.py", '''import numpy as np
from scipy import stats


def two_proportion_test(wins_a: int, n_a: int, wins_b: int, n_b: int) -> dict:
    p_a, p_b = wins_a / n_a, wins_b / n_b
    pooled = (wins_a + wins_b) / (n_a + n_b)
    standard_error = np.sqrt(pooled * (1 - pooled) * (1 / n_a + 1 / n_b))
    z = (p_b - p_a) / standard_error
    return {"lift": p_b / p_a - 1, "z": z, "p_value": 2 * (1 - stats.norm.cdf(abs(z)))}


def bootstrap_difference(a: np.ndarray, b: np.ndarray, rounds: int = 5000, seed: int = 11) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    diffs = [rng.choice(b, len(b)).mean() - rng.choice(a, len(a)).mean() for _ in range(rounds)]
    return float(np.percentile(diffs, 2.5)), float(np.percentile(diffs, 97.5))


def required_sample_size(base_rate: float, minimum_lift: float, alpha=0.05, power=0.8) -> int:
    effect = base_rate * minimum_lift
    z_alpha, z_power = stats.norm.ppf(1 - alpha / 2), stats.norm.ppf(power)
    return int(np.ceil(2 * base_rate * (1 - base_rate) * ((z_alpha + z_power) / effect) ** 2))
'''),

    "scraper": ("scraper/@ENTITY@_spider.py", '''import csv
import time

import requests
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "price-research-bot/1.0 (contact: research@example.org)"}


def fetch(url: str) -> BeautifulSoup:
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def parse_listing(page: BeautifulSoup) -> list[dict]:
    rows = []
    for card in page.select("div.product-card"):
        price = card.select_one("span.price")
        rows.append({"@F1@": card.select_one("h2").get_text(strip=True),
                     "@F2@": float(price.get_text(strip=True).replace("$", "").replace(",", "")) if price else None})
    return rows


def crawl(start_urls: list[str], out_path: str, delay: float = 1.5) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["@F1@", "@F2@"])
        writer.writeheader()
        for url in start_urls:
            writer.writerows(parse_listing(fetch(url)))
            time.sleep(delay)
'''),

    "kmeans_rfm": ("src/@ENTITY@/segments.py", '''import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def rfm_table(orders: pd.DataFrame, today: pd.Timestamp) -> pd.DataFrame:
    grouped = orders.groupby("customer_id").agg(
        recency=("order_date", lambda d: (today - d.max()).days),
        frequency=("order_id", "nunique"),
        monetary=("@F2@", "sum"),
    )
    return grouped


def segment(rfm: pd.DataFrame, clusters: int = 5) -> pd.DataFrame:
    scaled = StandardScaler().fit_transform(rfm.assign(monetary=rfm["monetary"].clip(upper=rfm["monetary"].quantile(0.99))))
    rfm = rfm.copy()
    rfm["segment"] = KMeans(n_clusters=clusters, n_init=10, random_state=3).fit_predict(scaled)
    return rfm.groupby("segment").agg(["mean", "count"]).round(1)
'''),

    "express_route": ("server/routes/@ENTITIES@.ts", '''import { Router } from "express";
import { z } from "zod";
import { pool } from "../db";
import { requireUser } from "../auth";

const router = Router();

const @Entity@Input = z.object({
  @F1@: z.string().min(1),
  @F2@: z.number().nonnegative(),
  @F3@: z.string().optional(),
});

router.get("/", requireUser, async (req, res) => {
  const { rows } = await pool.query(
    "SELECT * FROM @ENTITIES@ WHERE owner_id = $1 ORDER BY created_at DESC LIMIT 100",
    [req.user.id],
  );
  res.json(rows);
});

router.post("/", requireUser, async (req, res) => {
  const parsed = @Entity@Input.safeParse(req.body);
  if (!parsed.success) return res.status(422).json({ errors: parsed.error.flatten() });
  const { @F1@, @F2@, @F3@ } = parsed.data;
  const { rows } = await pool.query(
    "INSERT INTO @ENTITIES@ (owner_id, @F1@, @F2@, @F3@) VALUES ($1, $2, $3, $4) RETURNING *",
    [req.user.id, @F1@, @F2@, @F3@ ?? null],
  );
  res.status(201).json(rows[0]);
});

export default router;
'''),

    "react_component": ("src/components/@Entity@List.tsx", '''import { useEffect, useState } from "react";

type @Entity@ = { id: string; @F1@: string; @F2@: number };

export function @Entity@List({ ownerId }: { ownerId: string }) {
  const [items, setItems] = useState<@Entity@[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    fetch(`/api/@ENTITIES@?owner=${ownerId}`, { signal: controller.signal })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(`HTTP ${r.status}`))))
      .then(setItems)
      .catch((e) => e.name !== "AbortError" && setError(e.message));
    return () => controller.abort();
  }, [ownerId]);

  if (error) return <p role="alert">Could not load: {error}</p>;
  if (items.length === 0) return <p>Nothing here yet.</p>;
  return (
    <ul className="divide-y">
      {items.map((item) => (
        <li key={item.id} className="flex justify-between py-2">
          <span>{item.@F1@}</span>
          <span>{item.@F2@.toFixed(2)}</span>
        </li>
      ))}
    </ul>
  );
}
'''),

    "nextjs_api_stripe": ("app/api/checkout/route.ts", '''import { NextResponse } from "next/server";
import Stripe from "stripe";
import { prisma } from "@/lib/prisma";

const stripe = new Stripe(process.env.STRIPE_SECRET_KEY!);

export async function POST(request: Request) {
  const { @ENTITY@Id } = await request.json();
  const @ENTITY@ = await prisma.@ENTITY@.findUnique({ where: { id: @ENTITY@Id } });
  if (!@ENTITY@) return NextResponse.json({ error: "not found" }, { status: 404 });

  const session = await stripe.checkout.sessions.create({
    mode: "payment",
    line_items: [{
      quantity: 1,
      price_data: { currency: "usd", unit_amount: Math.round(@ENTITY@.@F2@ * 100),
                    product_data: { name: @ENTITY@.@F1@ } },
    }],
    metadata: { @ENTITY@Id },
    success_url: `${process.env.APP_URL}/thanks?session={CHECKOUT_SESSION_ID}`,
    cancel_url: `${process.env.APP_URL}/`,
  });
  return NextResponse.json({ url: session.url });
}
'''),

    "prisma_schema": ("prisma/schema.prisma", '''generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  createdAt DateTime @default(now())
  @ENTITIES@ @Entity@[]
}

model @Entity@ {
  id        String   @id @default(cuid())
  @F1@      String
  @F2@      Float
  @F3@      String?
  owner     User     @relation(fields: [ownerId], references: [id])
  ownerId   String
  createdAt DateTime @default(now())

  @@index([ownerId, createdAt])
}
'''),

    "graphql_schema": ("src/schema.ts", '''import { gql } from "graphql-tag";

export const typeDefs = gql`
  type @Entity@ {
    id: ID!
    @F1@: String!
    @F2@: Float!
    @F3@: String
  }

  type Query {
    @ENTITIES@(first: Int = 20, after: ID): [@Entity@!]!
    @ENTITY@(id: ID!): @Entity@
  }

  type Mutation {
    create@Entity@(@F1@: String!, @F2@: Float!): @Entity@!
  }
`;

export const resolvers = {
  Query: {
    @ENTITIES@: (_: unknown, args: { first: number }, ctx: any) => ctx.db.@ENTITIES@.list(args.first),
    @ENTITY@: (_: unknown, args: { id: string }, ctx: any) => ctx.loaders.@ENTITY@ById.load(args.id),
  },
  Mutation: {
    create@Entity@: (_: unknown, args: any, ctx: any) => ctx.db.@ENTITIES@.insert(args),
  },
};
'''),

    "django_api": ("backend/@ENTITIES@/views.py", '''from django.db.models import Q
from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticatedOrReadOnly

from .models import @Entity@


class @Entity@Serializer(serializers.ModelSerializer):
    class Meta:
        model = @Entity@
        fields = ["id", "@F1@", "@F2@", "@F3@", "created_at"]


class @Entity@ViewSet(viewsets.ModelViewSet):
    serializer_class = @Entity@Serializer
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get_queryset(self):
        queryset = @Entity@.objects.all().order_by("-created_at")
        term = self.request.query_params.get("q")
        if term:
            queryset = queryset.filter(Q(@F1@__icontains=term) | Q(@F3@__icontains=term))
        return queryset
'''),

    "docker_compose": ("docker-compose.yml", '''services:
  db:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_DB: app
    volumes:
      - db-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
  cache:
    image: redis:7-alpine
  api:
    build: .
    environment:
      DATABASE_URL: postgres://postgres:${DB_PASSWORD}@db:5432/app
      REDIS_URL: redis://cache:6379
    depends_on:
      db:
        condition: service_healthy
    ports:
      - "3000:3000"
volumes:
  db-data:
'''),

    "github_ci": (".github/workflows/ci.yml", '''name: ci
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
          cache: pip
      - run: pip install -r requirements.txt pytest
      - run: pytest -q
  image:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker build -t app:${{ github.sha }} .
'''),

    "k8s_deploy": ("deploy/model-serving.yaml", '''apiVersion: apps/v1
kind: Deployment
metadata:
  name: model-serving
spec:
  replicas: 2
  selector:
    matchLabels: {app: model-serving}
  template:
    metadata:
      labels: {app: model-serving}
    spec:
      containers:
        - name: api
          image: registry.example.org/model-serving:1.4.2
          ports: [{containerPort: 8000}]
          resources:
            requests: {cpu: "500m", memory: 1Gi}
            limits: {cpu: "2", memory: 3Gi}
          readinessProbe:
            httpGet: {path: /health, port: 8000}
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: model-serving
spec:
  scaleTargetRef: {apiVersion: apps/v1, kind: Deployment, name: model-serving}
  minReplicas: 2
  maxReplicas: 8
  metrics:
    - type: Resource
      resource: {name: cpu, target: {type: Utilization, averageUtilization: 65}}
'''),

    "llm_eval": ("src/@ENTITY@/run_eval.py", '''import json
import statistics
from pathlib import Path

from .client import ask


def load_cases(path: str) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def judge(question: str, answer: str, reference: str) -> int:
    verdict = ask(
        system="Grade the answer against the reference. Reply with 1 if correct and 0 if not.",
        user=f"Question: {question}\\nReference: {reference}\\nAnswer: {answer}",
        temperature=0,
    )
    return 1 if verdict.strip().startswith("1") else 0


def run(path: str, prompt_template: str) -> dict:
    scores = []
    for case in load_cases(path):
        answer = ask(system=prompt_template, user=case["question"], temperature=0)
        scores.append(judge(case["question"], answer, case["reference"]))
    return {"n": len(scores), "accuracy": statistics.mean(scores)}
'''),

    "sql_cohort": ("sql/@ENTITY@_retention.sql", '''WITH first_seen AS (
    SELECT @F1@ AS customer_id,
           DATE_TRUNC('month', MIN(created_at)) AS cohort_month
    FROM @ENTITIES@
    GROUP BY @F1@
),
activity AS (
    SELECT DISTINCT @F1@ AS customer_id,
           DATE_TRUNC('month', created_at) AS active_month
    FROM @ENTITIES@
)
SELECT f.cohort_month,
       (EXTRACT(YEAR FROM a.active_month) - EXTRACT(YEAR FROM f.cohort_month)) * 12
         + EXTRACT(MONTH FROM a.active_month) - EXTRACT(MONTH FROM f.cohort_month) AS months_since_start,
       COUNT(DISTINCT a.customer_id) AS active_customers,
       ROUND(100.0 * COUNT(DISTINCT a.customer_id)
             / FIRST_VALUE(COUNT(DISTINCT a.customer_id)) OVER (PARTITION BY f.cohort_month ORDER BY a.active_month), 1)
         AS retention_pct
FROM first_seen f
JOIN activity a USING (customer_id)
GROUP BY f.cohort_month, a.active_month
ORDER BY f.cohort_month, months_since_start;
'''),

    "sql_view_kpi": ("sql/v_@ENTITY@_kpis.sql", '''CREATE OR REPLACE VIEW v_@ENTITY@_kpis AS
SELECT DATE_TRUNC('week', created_at)               AS week,
       @F3@                                         AS segment,
       COUNT(*)                                     AS rows_count,
       SUM(@F2@)                                    AS total_value,
       AVG(@F2@)                                    AS average_value,
       SUM(@F2@) - LAG(SUM(@F2@)) OVER (PARTITION BY @F3@ ORDER BY DATE_TRUNC('week', created_at)) AS week_change
FROM @ENTITIES@
WHERE created_at >= CURRENT_DATE - INTERVAL '26 weeks'
  AND @F2@ IS NOT NULL
GROUP BY 1, 2;
'''),

    "dbt_model": ("models/marts/fct_@ENTITIES@.sql", '''{{ config(materialized='incremental', unique_key='@ENTITY@_id') }}

with source as (
    select * from {{ ref('stg_@ENTITIES@') }}
    {% if is_incremental() %}
    where updated_at > (select max(updated_at) from {{ this }})
    {% endif %}
),

customers as (
    select customer_id, region from {{ ref('dim_customers') }}
)

select
    source.@ENTITY@_id,
    source.@F1@,
    source.@F2@,
    customers.region,
    source.updated_at
from source
left join customers using (customer_id)
'''),

    "dax_measures": ("model/measures.dax", '''Total Value = SUM ( @ENTITIES@[@F2@] )

Value LY =
CALCULATE ( [Total Value], SAMEPERIODLASTYEAR ( 'Date'[Date] ) )

Value YoY % =
DIVIDE ( [Total Value] - [Value LY], [Value LY] )

Rolling 3M Value =
CALCULATE ( [Total Value], DATESINPERIOD ( 'Date'[Date], MAX ( 'Date'[Date] ), -3, MONTH ) )

Share of Total =
DIVIDE ( [Total Value], CALCULATE ( [Total Value], ALL ( @ENTITIES@[@F3@] ) ) )
'''),

    "r_analysis": ("analysis/@ENTITY@_summary.R", '''library(dplyr)
library(ggplot2)
library(readr)

data <- read_csv("data/@ENTITIES@.csv", show_col_types = FALSE) |>
  filter(!is.na(@F2@)) |>
  mutate(@F1@ = factor(@F1@))

summary_table <- data |>
  group_by(@F1@) |>
  summarise(n = n(), mean = mean(@F2@), sd = sd(@F2@), median = median(@F2@), .groups = "drop")

print(summary_table)
print(kruskal.test(@F2@ ~ @F1@, data = data))

ggplot(data, aes(x = @F1@, y = @F2@)) +
  geom_boxplot(outlier.alpha = 0.3) +
  labs(x = NULL, y = "@F2@", title = "Distribution by group") +
  theme_minimal()
ggsave("figures/@ENTITY@_boxplot.png", width = 7, height = 4, dpi = 150)
'''),
}
