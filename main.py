from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import (
    users_router,
    google_calendar_router,
    goals_router,
    milestones_router,
    tasks_router,
    todos_router,
    events_router,
    tags_router,
    subtasks_router,
    notes_router,
    templates_router,
    trash_router,
    backup_router,
    daily_draft_todos_router,
    daily_logs_router,
    todo_occurrences_router,
    metrics_router,
    ai_goal_plans_router,
)



app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    # Allow fallback dev ports when 3000 is occupied (e.g. by Docker).
    "http://localhost:3001",
    "http://127.0.0.1:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3002",
    "http://localhost:3003",
    "http://127.0.0.1:3003",
    "http://localhost:3004",
    "http://127.0.0.1:3004",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users_router, prefix='/users', tags=['users'])
app.include_router(goals_router, tags=['goals'])
app.include_router(milestones_router, tags=['milestones'])
app.include_router(tasks_router, tags=['tasks'])
app.include_router(todos_router, tags=['todos'])
app.include_router(events_router, tags=['events'])
app.include_router(tags_router, tags=['tags'])
app.include_router(google_calendar_router,prefix="/calendars", tags=['calendar integrations'])
app.include_router(subtasks_router, tags=['subtasks'])
app.include_router(notes_router, tags=['notes'])
app.include_router(templates_router, tags=['templates'])
app.include_router(trash_router, tags=['trash'])
app.include_router(backup_router, tags=['backup'])
app.include_router(daily_draft_todos_router, tags=['daily draft todos'])
app.include_router(daily_logs_router, tags=['daily logs'])
app.include_router(todo_occurrences_router, tags=['todo occurrences'])
app.include_router(metrics_router, tags=['metrics'])
app.include_router(ai_goal_plans_router, tags=['ai goal planning'])


@app.get('/')
async def root() -> dict[str, str]:
    return {'message': 'Hello world'}
