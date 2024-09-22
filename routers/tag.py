from fastapi import APIRouter, HTTPException, Depends
from models import Milestone, MilestoneBase, MilestoneUpdate, get_current_active_user
from sqlmodel import Session, select
from routers.users import User
from db import get_session
from typing import Annotated
import uuid

tags_router = APIRouter()