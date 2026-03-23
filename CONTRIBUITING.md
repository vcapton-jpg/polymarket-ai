# Règles de contributions

### Structure

Le projet est structuré de la façon suivante :

prediction_markets/
│
├── app/
│   ├── config.py                    
│   ├── db/
│   │   ├── models.py                
│   │   ├── session.py               
│   │   ├── session_sync.py          
│   │   └── migrations/              
│   │
│   ├── schemas/                     
│   │   ├── market.py
│   │   ├── news.py
│   │   ├── signal.py
│   │   └── event.py
│   │
│   ├── services/
│   │   ├── ingestion/               
│   │   ├── processing/              
│   │   ├── event_engine/            
│   │   ├── retrieval/               
│   │   ├── llm/                     
│   │   └── scoring/                 
│   │
│   ├── workers/
│   │   ├── celery_app.py            
│   │   ├── tasks_ingestion.py
│   │   ├── tasks_pipeline.py
│   │   ├── tasks_scoring.py
│   │   └── tasks_outcomes.py
│   │
│   └── api/
│       └── main.py
│
├── ml/                              
│
├── tests/                           
│   ├── conftest.py                  
│   ├── unit/
│   │   └── services/                
│   └── integration/
│       ├── test_pipeline_end_to_end.py
│       └── test_hybrid_search.py
│
├── scripts/              
│   ├── backfill_embeddings.py
│   ├── recalibrate_weights.py
│   ├── export_ml_dataset.py
│   └── seed_sources_registry.py
│
├── Dockerfile                       
├── docker-compose.yml               
├── docker-compose.prod.yml          
├── pyproject.toml                   
├── poetry.lock                      
├── .env.example                     
└── .gitignore

### Règles sur les branches :

- `main` -> cette branche est **strictement** réservée aux versions stable du projet. **On ne peux que fusionner du code venant de la branche `dev` sur `main`**
- `dev` -> il s'agit de la branche principale du projet, la branche de développement. **On ne peux rien pousser directement sur cette branche**

**Format des noms de branche :**

- `feature/*` -> Ajout d'une fonctionnalité
- `hotfix/*` -> Correction urgente sur la production
- `bugfix/*` -> Correction de bug
- `refactor/*` -> Refactorisation du code
- `chore/*` -> Tâches techniques, CI/CD, modification de dépendances...
- `docs/*` -> Ajout de documentation
- `tests/*` -> Ajout ou modifications de tests
- `releases/*` -> Création d'une version de production

Toute branche n'étant pas dans ce format ne sera pas testé par le pipeline et ne pourra pas être fusionnée avec la branche de développement.

