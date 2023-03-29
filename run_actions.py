import uvicorn

if __name__ == '__main__':
  # Start with reloading enabled (must be string to work)
  uvicorn.run("abot_actions:create_app", host='localhost', port=5055, factory=True, reload=True)
