  Free tier available, deploys directly from Git:

  1. Push your code to GitHub
  2. Go to https://railway.app
  3. Connect your repo
  4. Add a Procfile:
  web: uvicorn app.main:app --host 0.0.0.0 --port $PORT
  5. Deploy
