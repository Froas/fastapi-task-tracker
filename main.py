from fastapi import FastAPI

from routers import users_router, goals_router, milestones_router, tasks_router, todos_router, events_router, tags_router, subtasks_router



app = FastAPI()

app.include_router(users_router, prefix='/users', tags=['users'])
app.include_router(goals_router, tags=['goals'])
app.include_router(milestones_router, tags=['milestones'])
app.include_router(tasks_router, tags=['tasks'])
app.include_router(todos_router, tags=['todos'])
app.include_router(events_router, tags=['events'])
app.include_router(tags_router, tags=['tags'])
app.include_router(subtasks_router, tags=['subtasks'])


@app.get('/')
async def root() -> dict[str, str]:
    return {'message': 'Hello world'}




