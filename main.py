from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import users_router, google_calendar_router, goals_router, milestones_router, tasks_router, todos_router, events_router, tags_router, subtasks_router



app = FastAPI()

origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
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


@app.get('/')
async def root() -> dict[str, str]:
    return {'message': 'Hello world'}




