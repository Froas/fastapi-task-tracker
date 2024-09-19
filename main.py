from fastapi import FastAPI

from routers.users import users_router
from routers.goals import goals_router
from routers.milestones import milestones_router
from routers.tasks import tasks_router
from routers.todos import todos_router
from routers.events import events_router

app = FastAPI()

app.include_router(users_router, prefix='/users', tags=['users'])
app.include_router(goals_router, tags=['goals'])
app.include_router(milestones_router, tags=['milestones'])
app.include_router(tasks_router, tags=['tasks'])
app.include_router(todos_router, tags=['todos'])
app.include_router(events_router, tags=['events'])

@app.get('/')
async def root() -> dict[str, str]:
    return {'message': 'Hello world'}




