
from rasa_sdk.endpoint import create_app as ra_create_app

from sanic import Sanic

def create_app() -> Sanic:
  '''Application factory to load the Rasa actions server and actions'''
  ACTIONS_MODULE = "actions"
  app = ra_create_app('.'.join([__package__, ACTIONS_MODULE]))

  #TODO: Add config and middleware here

  return app
