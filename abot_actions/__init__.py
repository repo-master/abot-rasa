
from rasa_sdk.endpoint import create_app as ra_create_app

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from contextvars import ContextVar

from sanic import Sanic, Request, HTTPResponse


def create_app() -> Sanic:
  '''Application factory to load the Rasa actions server and actions'''
  
  # Which (sub)package to look for any class that inherits "Action" class. The app looks
  # for these classes recursively in all modules and subpackages also automatically.
  # This path will be relative to current package 'abot_actions'. Rasa didn't make use
  # of the `package` argument when it calls the 'import_module' function, so this hack is
  # needed for relative import in some way. Separate each level by a dot (.)
  ACTIONS_MODULE = "actions"

  app = ra_create_app('.'.join([__package__, ACTIONS_MODULE]))

  # Add config and middleware here

  ### Database middleware ###

  bind = create_async_engine("sqlite+aiosqlite:///:memory:", echo=True)
  _sessionmaker = sessionmaker(bind, AsyncSession, expire_on_commit=False)
  _base_model_session_ctx = ContextVar("session")

  @app.middleware("request")
  async def inject_session(request: Request):
    request.ctx.session = _sessionmaker()
    request.ctx.session_ctx_token = _base_model_session_ctx.set(
        request.ctx.session
    )

  @app.middleware("response")
  async def close_session(request: Request, response: HTTPResponse):
    if hasattr(request.ctx, "session_ctx_token"):
      _base_model_session_ctx.reset(request.ctx.session_ctx_token)
      await request.ctx.session.close()

  return app
